"""Settle a dispatch season from an encoded work-order corpus.

This program is written against the documents the corpus ships with:
packet_encoding.md for the wire format and its transforms, calibration_slice.md
for the published control figures, identity_policy.md, revision_policy.md,
capacity_policy.md, dispatch_policy.md and cost_policy.md for the settlement
rules, global_invariants.md for the reconciliation verdicts, and
report_schema.md for the field names of every report it writes.

Nothing recovered from any particular corpus appears here as a literal.  The
only fixed values below are ones the encoding document prints outright: the
magic word, the header and record widths and field offsets, the HMAC key, the
granularity ladder, the day ring, the flag table, and the declared domain of
each withheld constant.  Everything else is read from the directory handed in
on the command line, so the same program settles any corpus laid out this way.

Usage: derive_report.py <input-directory> <output-directory>
"""

import csv
import hashlib
import hmac
import json
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Constants the encoding document publishes outright.
# --------------------------------------------------------------------------

AUTHORITY_KEY = b"lane-dispatch-authority"
MAGIC_WORD = 0x4C44
HEADER_WIDTH = 24
SHORT_RECORD = 13
LONG_RECORD = 15
GRANULARITY_LADDER = (5, 10, 25, 50)
DAY_RING = 251
WORD_RING = 1 << 16
UINT64 = (1 << 64) - 1
AUX_OFFSETS = (8, 10, 12, 14)
BACKREF_SENTINEL = 0xF0

# packet_encoding.md, "Transform flag word".
FLAG_LOAD_MASK = 0x001
FLAG_SLACK_FOLD = 0x002
FLAG_WEIGHT_DIFF = 0x004
FLAG_DAY_DRIFT = 0x008
FLAG_PERMUTATION = 0x010
FLAG_BACK_REF = 0x020
FLAG_ENDIAN_ISLAND = 0x040
FLAG_LENGTH_SHADOW = 0x080
FLAG_ALIAS_ROTOR = 0x100
FLAG_PAYLOAD_ROTATION = 0x200
FLAG_COUNT_BIAS = 0x400

# packet_encoding.md prints the stream label alphabet in this order, and
# capacity_policy.md lists the four quantisation modes in this order.
LABEL_ALPHABET = ("arc", "beam", "cinder", "drift", "ember")
QUANT_LADDER = ("floor", "ceil", "nearest", "band")

# calibration_slice.md publishes its control figures in resolution order.  Each
# row below pairs one published control with the constant its comment describes
# and with the domain the encoding document declares for that constant.  The
# first value of each domain is the placeholder used for constants not yet
# settled, which is simply the lowest value the document allows.
RESOLUTION_PLAN = (
    ("payload_origin_total", "rotate_step", tuple(range(1, 8))),
    ("record_span_total", "shadow_bias", tuple(range(0, 16))),
    ("calibration_order_total", "count_bias", tuple(range(0, 8))),
    ("island_field_total", "island_offset", (8, 10, 12, 14)),
    ("ordinal_position_checksum", "permute_rounds", (1, 2, 3, 4)),
    ("masked_load_total", "stream_label", LABEL_ALPHABET),
    ("folded_slack_total", "chain_seed", tuple(range(0, 256))),
    ("delta_weight_total", "delta_span", tuple(range(2, 10))),
    ("drift_day_total", "drift_modulus", (97, 101, 103, 107, 109)),
    ("canonical_client_total", "alias_rotor", tuple(range(1, 8))),
    ("backref_program_total", "window_span", tuple(range(2, 9))),
    ("billable_slot_total", "quant_mode", QUANT_LADDER),
)

CALIBRATION = "calibration"
FIELD = "field"


class SettlementError(Exception):
    """Raised when a packet cannot be decoded under the constants in force."""


# --------------------------------------------------------------------------
# Small numeric helpers.
# --------------------------------------------------------------------------


def big_word(buf, at):
    return struct.unpack_from(">H", buf, at)[0]


def little_word(buf, at):
    return struct.unpack_from("<H", buf, at)[0]


def big_long(buf, at):
    return struct.unpack_from(">I", buf, at)[0]


def crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def scramble(state):
    """The xorshift64 the encoding document specifies: left 13, right 7, left 17."""
    state &= UINT64
    state ^= (state << 13) & UINT64
    state ^= state >> 7
    state ^= (state << 17) & UINT64
    return state & UINT64


def turn_left(blob, places):
    if not blob:
        return blob
    places %= len(blob)
    return blob[places:] + blob[:places] if places else blob


def turn_right(blob, places):
    if not blob:
        return blob
    places %= len(blob)
    return blob[-places:] + blob[:-places] if places else blob


def bring_to_multiple(amount, step, mode):
    """capacity_policy.md: bring load units to a whole multiple of granularity."""
    below, over = divmod(amount, step)
    if not over:
        return amount
    if mode == "floor":
        return below * step
    if mode == "ceil":
        return (below + 1) * step
    if mode == "nearest":
        return (below + 1) * step if 2 * over >= step else below * step
    if mode == "band":
        return (below + 1) * step if 4 * over >= 3 * step else below * step
    raise SettlementError("quantisation mode %r is not one the policy names" % mode)


def seed_of_block(head):
    """The keyed block seed the permutation transform draws from."""
    message = b"block|" + struct.pack(
        ">HHHHH", head.block_id, head.lane_hint, head.horizon_slot,
        head.span_hint, head.seed_hint)
    digest = hmac.new(AUTHORITY_KEY, message, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big") or 1


def travel_order(width, rounds, seed):
    """Fisher-Yates applied `rounds` times; entry p is the ordinal travelling at p."""
    slots = list(range(width))
    state = (seed & UINT64) or 1
    for _ in range(rounds):
        for cursor in range(width - 1, 0, -1):
            state = scramble(state)
            partner = state % (cursor + 1)
            slots[cursor], slots[partner] = slots[partner], slots[cursor]
    return slots


def load_mask(label, block_id, ordinal):
    message = label.encode("utf-8") + b"|" + struct.pack(">HH", block_id, ordinal)
    return hmac.new(AUTHORITY_KEY, message, hashlib.sha256).digest()[:4]


# --------------------------------------------------------------------------
# Reading the corpus.
# --------------------------------------------------------------------------


def read_rows(path):
    """Rows keyed by trimmed header names, cells trimmed, byte order mark dropped."""
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def read_body(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def bullet_value(body, label):
    """Pull `- label: value` out of a policy document."""
    needle = "- %s:" % label
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(needle):
            return stripped[len(needle):].strip()
    raise SettlementError("the policy document states no %r setting" % label)


def numbered_map(text):
    out = {}
    for chunk in text.split(","):
        chunk = chunk.strip()
        if "=" in chunk:
            name, _, value = chunk.partition("=")
            out[name.strip()] = int(value.strip())
    return out


def number_list(text):
    return [int(chunk.strip()) for chunk in text.split(",") if chunk.strip()]


def family_pairs(text):
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if "|" in chunk:
            left, _, right = chunk.partition("|")
            out.append((left.strip(), right.strip()))
    return out


def published_controls(body):
    """calibration_slice.md control figures, in the order the file lists them."""
    figures = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ") or "=" not in stripped:
            continue
        name, _, value = stripped[2:].partition("=")
        try:
            figures.append((name.strip(), int(value.strip())))
        except ValueError:
            continue
    return dict(figures)


@dataclass
class BlockHead:
    block_id: int
    flags: int
    stored_count: int
    genuine_count: int
    lane_hint: int
    horizon_slot: int
    span_hint: int
    seed_hint: int
    payload_crc: int


@dataclass
class Order:
    order_id: str
    block_id: int
    ordinal: int
    alias_key: str
    program_id: str
    load_units: int
    due_offset: int
    due_slot: int
    weight: int
    granularity: int
    submitted_day: int
    dispatch_mode: int
    long_form: bool


@dataclass
class Admissible:
    order: Order
    client_id: str
    site: str
    service_class: str
    budget_cap: int
    revision: int
    family: str
    slack: int
    billable_slots: int = 0


@dataclass
class Placed:
    order_id: str
    client_id: str
    site: str
    region: str
    service_class: str
    lane_id: str
    program_id: str
    revision: int
    billable_slots: int
    slack: int
    charge: int
    rebate: int
    capped: int
    net: int


@dataclass
class Lane:
    lane_id: str
    site: str
    class_lock: str
    exclusive_client: str
    slot_capacity: int
    rate: int


@dataclass
class Corpus:
    clients: list
    programs: list
    lanes: list
    sites: list
    heads: dict
    wires: dict
    block_ids: dict
    controls: dict
    tier_bounds: list
    base_ceiling: dict
    tier_factor: dict
    rebate_band: dict
    conflicts: set
    alias_order: list = field(default_factory=list)
    program_order: list = field(default_factory=list)

    @property
    def alias_count(self):
        return len(self.alias_order)

    @property
    def program_count(self):
        return len(self.program_order)


def gather(source_dir):
    """Read every file the settlement needs out of the directory handed in."""

    def at(name):
        return os.path.join(source_dir, name)

    clients = read_rows(at("client_directory.csv"))
    programs = read_rows(at("program_registry.csv"))
    sites = read_rows(at("site_directory.csv"))
    lanes = [
        Lane(row["lane_id"], row["site"], row["class_lock"], row["exclusive_client"],
             int(row["slot_capacity"]), int(row["rate_micros"]))
        for row in read_rows(at("lane_roster.csv"))
    ]

    heads = {}
    block_ids = {CALIBRATION: [], FIELD: []}
    for row in read_rows(at("block_manifest.csv")):
        population = row["population"]
        if population not in block_ids:
            continue
        block_id = int(row["block_id"])
        heads[(population, block_id)] = bytes.fromhex(row["header_hex"])
        block_ids[population].append(block_id)

    wires = {}
    for population, source in ((CALIBRATION, "calibration_orders.csv"),
                               (FIELD, "field_orders.csv")):
        for row in read_rows(at(source)):
            wires[(population, int(row["block_id"]))] = bytes.fromhex(row["payload_hex"])

    capacity_doc = read_body(at("capacity_policy.md"))
    cost_doc = read_body(at("cost_policy.md"))
    dispatch_doc = read_body(at("dispatch_policy.md"))

    clash = set()
    for left, right in family_pairs(bullet_value(dispatch_doc, "incompatible_families")):
        clash.add((left, right))
        clash.add((right, left))

    return Corpus(
        clients=clients,
        programs=programs,
        lanes=lanes,
        sites=sites,
        heads=heads,
        wires=wires,
        block_ids=block_ids,
        controls=published_controls(read_body(at("calibration_slice.md"))),
        tier_bounds=number_list(bullet_value(capacity_doc, "congestion_bounds")),
        base_ceiling=numbered_map(bullet_value(capacity_doc, "base_ceiling")),
        tier_factor=numbered_map(bullet_value(capacity_doc, "tier_factor")),
        rebate_band=numbered_map(bullet_value(cost_doc, "rebate_band")),
        conflicts=clash,
        alias_order=[row["alias_key"] for row in clients],
        program_order=sorted({row["program_id"] for row in programs}),
    )


# --------------------------------------------------------------------------
# Undoing the wire transforms.
# --------------------------------------------------------------------------


def read_head(corpus, population, block_id, constants):
    raw = corpus.heads[(population, block_id)]
    if len(raw) != HEADER_WIDTH:
        raise SettlementError("block header is not %d bytes" % HEADER_WIDTH)
    if crc(raw[:20]) != big_long(raw, 20):
        raise SettlementError("block header checksum disagrees")
    if big_word(raw, 0) != MAGIC_WORD:
        raise SettlementError("block magic word disagrees")

    flags = big_word(raw, 6)
    island = constants["island_offset"] if flags & FLAG_ENDIAN_ISLAND else None
    aux = {}
    for offset in AUX_OFFSETS:
        aux[offset] = little_word(raw, offset) if offset == island else big_word(raw, offset)

    stored = big_word(raw, 4)
    surplus = constants["count_bias"] if flags & FLAG_COUNT_BIAS else 0
    genuine = stored - surplus
    if genuine < 1 or genuine > stored:
        raise SettlementError("block genuine record count is out of range")

    return BlockHead(block_id=block_id, flags=flags, stored_count=stored,
                     genuine_count=genuine, lane_hint=aux[8], horizon_slot=aux[10],
                     span_hint=aux[12], seed_hint=aux[14],
                     payload_crc=big_long(raw, 16))


def origin_shift(head, wire, constants):
    """How far left the payload was turned before its checksum was taken."""
    if not (head.flags & FLAG_PAYLOAD_ROTATION) or not wire:
        return 0
    return (head.block_id * constants["rotate_step"]) % len(wire)


def settled_payload(corpus, population, head, constants):
    wire = corpus.wires[(population, head.block_id)]
    if crc(wire) != head.payload_crc:
        raise SettlementError("payload checksum disagrees")
    return turn_right(wire, origin_shift(head, wire, constants))


def carve(payload, head, constants):
    """Split a payload into physical records, unmasking each length code."""
    shadow = constants["shadow_bias"] if head.flags & FLAG_LENGTH_SHADOW else 0
    out = []
    cursor = 0
    for _ in range(head.stored_count):
        if cursor >= len(payload):
            raise SettlementError("record cursor ran past the payload")
        code = ((payload[cursor] >> 4) & 0x0F) ^ shadow
        if code == 0:
            width = SHORT_RECORD
        elif code == 1:
            width = LONG_RECORD
        else:
            raise SettlementError("record length code is out of range")
        if cursor + width > len(payload):
            raise SettlementError("record extends past the payload")
        out.append(payload[cursor:cursor + width])
        cursor += width
    if cursor != len(payload):
        raise SettlementError("payload holds trailing bytes")
    return out


def to_logical(physical, head, constants):
    """Put records back in logical ordinal order."""
    if not (head.flags & FLAG_PERMUTATION):
        return list(physical)
    slots = travel_order(len(physical), constants["permute_rounds"], seed_of_block(head))
    logical = [None] * len(physical)
    for position, ordinal in enumerate(slots):
        logical[ordinal] = physical[position]
    return logical


def decode_block(corpus, population, block_id, constants, running):
    """Decode one block, returning its header and every record it stores."""
    head = read_head(corpus, population, block_id, constants)
    payload = settled_payload(corpus, population, head, constants)
    ordered = to_logical(carve(payload, head, constants), head, constants)

    flags = head.flags
    carried_offset = constants["chain_seed"] if flags & FLAG_SLACK_FOLD else 0
    weights = []
    out = []

    for ordinal, blob in enumerate(ordered):
        mode = blob[0] & 0x0F
        if mode > 3:
            raise SettlementError("dispatch mode is out of range")

        load = big_long(blob, 3)
        if flags & FLAG_LOAD_MASK:
            load ^= int.from_bytes(
                load_mask(constants["stream_label"], block_id, ordinal), "big")

        offset = big_word(blob, 7)
        if flags & FLAG_SLACK_FOLD:
            offset = (offset - carried_offset) % WORD_RING
            carried_offset = offset

        stored_weight = big_word(blob, 9)
        if flags & FLAG_WEIGHT_DIFF:
            seat = ordinal % constants["delta_span"]
            if seat == 0:
                weight = stored_weight
            elif seat == 1:
                weight = (weights[-1] + stored_weight) % WORD_RING
            else:
                weight = (2 * weights[-1] - weights[-2] + stored_weight) % WORD_RING
        else:
            weight = stored_weight
        weights.append(weight)

        step_code = blob[11]
        if step_code >= len(GRANULARITY_LADDER):
            raise SettlementError("granularity code is out of range")

        day = blob[12]
        if flags & FLAG_DAY_DRIFT:
            drift = 1 + (running["loads"] % (constants["drift_modulus"] - 1))
            try:
                day = (day * pow(drift, -1, DAY_RING)) % DAY_RING
            except ValueError:
                raise SettlementError("the day drift factor has no inverse")

        stretch = big_word(blob, 13) if len(blob) == LONG_RECORD else 0

        seat = blob[1]
        if flags & FLAG_ALIAS_ROTOR:
            seat -= constants["alias_rotor"]
        alias_key = corpus.alias_order[seat % corpus.alias_count]

        marker = blob[2]
        if marker >= BACKREF_SENTINEL and flags & FLAG_BACK_REF:
            reach = ((marker - BACKREF_SENTINEL) % constants["window_span"]) + 1
            if reach > ordinal:
                raise SettlementError("back reference points before its block")
            program_id = out[ordinal - reach].program_id
        else:
            program_id = corpus.program_order[marker % corpus.program_count]

        out.append(Order(
            order_id="W%04d%02d" % (block_id, ordinal),
            block_id=block_id,
            ordinal=ordinal,
            alias_key=alias_key,
            program_id=program_id,
            load_units=load,
            due_offset=offset,
            due_slot=head.horizon_slot + offset + stretch,
            weight=weight,
            granularity=GRANULARITY_LADDER[step_code],
            submitted_day=day,
            dispatch_mode=mode,
            long_form=len(blob) == LONG_RECORD,
        ))

        # The drifting day factor counts genuine records only, and carries
        # across block boundaries within one population.
        if ordinal < head.genuine_count:
            running["loads"] += load

    return head, out


def decode_population(corpus, population, constants):
    """Decode every block of a population in manifest order."""
    running = {"loads": 0}
    heads = {}
    everything = []
    genuine = []
    for block_id in corpus.block_ids[population]:
        head, records = decode_block(corpus, population, block_id, constants, running)
        heads[block_id] = head
        everything.extend(records)
        genuine.extend(records[:head.genuine_count])
    return heads, genuine, everything


# --------------------------------------------------------------------------
# Identity, revisions and admission.
# --------------------------------------------------------------------------


def governing_client(corpus, alias_key):
    """identity_policy.md: follow the merge chain, closed chains to their least id."""
    by_alias = {row["alias_key"]: row for row in corpus.clients}
    by_id = {row["client_id"]: row for row in corpus.clients}
    row = by_alias.get(alias_key)
    if row is None:
        raise SettlementError("alias key %r is absent from the directory" % alias_key)
    walked = [row["client_id"]]
    while row.get("merged_into"):
        nxt = by_id.get(row["merged_into"])
        if nxt is None:
            break
        if nxt["client_id"] in walked:
            return by_id[min(walked)]
        walked.append(nxt["client_id"])
        row = nxt
    return row


def governing_revision(corpus, program_id, day):
    """revision_policy.md: half-open interval, higher revision wins an overlap."""
    winner = None
    for row in corpus.programs:
        if row["program_id"] != program_id:
            continue
        if int(row["effective_from"]) <= day < int(row["effective_to"]):
            if winner is None or int(row["revision"]) > int(winner["revision"]):
                winner = row
    return winner


def sort_dispositions(corpus, records):
    """Split decoded records into admissible, rejected and deferred."""
    admissible, rejected, deferred = [], [], []
    for order in records:
        client = governing_client(corpus, order.alias_key)
        day = order.submitted_day
        retires = client.get("retired_on") or ""
        if retires and day >= int(retires):
            rejected.append(order)
            continue
        revision = governing_revision(corpus, order.program_id, day)
        if revision is None:
            rejected.append(order)
            continue
        if day < int(client.get("effective_from") or 0):
            deferred.append(order)
            continue
        admissible.append(Admissible(
            order=order,
            client_id=client["client_id"],
            site=client["site"],
            service_class=client["service_class"],
            budget_cap=int(client["budget_cap_micros"]),
            revision=int(revision["revision"]),
            family=revision["family"],
            slack=order.due_slot - day,
        ))
    return admissible, rejected, deferred


def tier_for(index, bounds):
    for tier, bound in enumerate(bounds):
        if index < bound:
            return tier
    return len(bounds)


def offering_sequence(items):
    """capacity_policy.md: descending dispatch weight, then ascending identifier."""
    return sorted(items, key=lambda item: (-item.order.weight, item.order.order_id))


def settle_admission(corpus, admissible, site_names):
    """Drive congestion and admission to the one assignment stable under both."""
    room = {row["name"]: int(row["capacity_slots"]) for row in corpus.sites}
    sequence = offering_sequence(admissible)
    tiers = {name: 0 for name in site_names}
    passes = 0

    while passes < 64:
        passes += 1
        taken = {}
        used = {name: 0 for name in site_names}
        admitted = set()
        for item in sequence:
            ceiling = (corpus.base_ceiling[item.service_class]
                       * corpus.tier_factor[str(tiers[item.site])]) // 100
            so_far = taken.get(item.client_id, 0)
            if so_far + item.billable_slots > ceiling:
                continue
            taken[item.client_id] = so_far + item.billable_slots
            used[item.site] += item.billable_slots
            admitted.add(item.order.order_id)

        indexes = {name: (1000 * used[name]) // room[name] for name in site_names}
        fresh = {name: tier_for(indexes[name], corpus.tier_bounds) for name in site_names}
        raised = {name: max(tiers[name], fresh[name]) for name in site_names}
        if raised == tiers:
            if fresh != tiers:
                raise SettlementError("congestion did not settle")
            return admitted, tiers, indexes, passes
        tiers = raised

    raise SettlementError("admission did not reach a stable state")


# --------------------------------------------------------------------------
# Placement.
# --------------------------------------------------------------------------


def contention_sequence(items):
    """dispatch_policy.md: larger remaining slack keeps the lane, then larger
    billable slot count, then the identifier that sorts first."""
    return sorted(items, key=lambda item: (-item.slack, -item.billable_slots,
                                           item.order.order_id))


def lane_accepts(lane, item):
    if lane.class_lock and lane.class_lock != item.service_class:
        return False
    if lane.exclusive_client and lane.exclusive_client != item.client_id:
        return False
    return True


def place_one_site(corpus, site, items):
    """Find the cheapest feasible placement of one site's admitted work.

    Lanes are tried cheapest first and, at equal rate, by identifier; orders are
    offered in the contention order the dispatch policy fixes.  Because a leaf
    is kept only when it beats the incumbent strictly, the placement returned is
    the first cheapest one in that order, which is what the contention rule
    describes when two orders want the same last slots.
    """
    lanes = sorted((lane for lane in corpus.lanes if lane.site == site),
                   key=lambda lane: (lane.rate, lane.lane_id))
    spare = [lane for lane in lanes
             if lane.slot_capacity == 0 and not lane.class_lock
             and not lane.exclusive_client]
    if len(spare) != 1:
        raise SettlementError("site %r has no single relief lane" % site)
    relief = spare[0].lane_id

    queue = contention_sequence(items)
    total = len(queue)
    if not total:
        return {}, 0, 0, 0

    cheapest = []
    for item in queue:
        rates = [lane.rate for lane in lanes if lane_accepts(lane, item)]
        if not rates:
            raise SettlementError("an admitted order matches no lane at its site")
        cheapest.append(item.billable_slots * min(rates))

    suffix_cost = [0] * (total + 1)
    suffix_slots = [0] * (total + 1)
    for i in range(total - 1, -1, -1):
        suffix_cost[i] = suffix_cost[i + 1] + cheapest[i]
        suffix_slots[i] = suffix_slots[i + 1] + queue[i].billable_slots

    occupied = {lane.lane_id: 0 for lane in lanes}
    families = {lane.lane_id: [] for lane in lanes}

    # A first-fit pass gives a feasible ceiling to prune against.
    ceiling = 0
    for item in queue:
        for lane in lanes:
            if not lane_accepts(lane, item):
                continue
            if lane.lane_id != relief:
                if occupied[lane.lane_id] + item.billable_slots > lane.slot_capacity:
                    continue
                if any((seen, item.family) in corpus.conflicts
                       for seen in families[lane.lane_id]):
                    continue
            occupied[lane.lane_id] += item.billable_slots
            families[lane.lane_id].append(item.family)
            ceiling += item.billable_slots * lane.rate
            break

    for lane_id in occupied:
        occupied[lane_id] = 0
        families[lane_id] = []

    def relaxed_tail(index):
        """Cheapest way to house the remaining slots ignoring every rule but room."""
        need = suffix_slots[index]
        bill = 0
        for lane in lanes:
            if need <= 0:
                break
            room = need if lane.lane_id == relief else lane.slot_capacity - occupied[lane.lane_id]
            if room <= 0:
                continue
            fits = room if room < need else need
            bill += fits * lane.rate
            need -= fits
        return bill

    best = {"cost": ceiling + 1, "plan": None, "leaves": 0}
    chosen = {}

    def descend(index, spent):
        bound = max(suffix_cost[index], relaxed_tail(index))
        if spent + bound >= best["cost"]:
            return
        if index == total:
            best["leaves"] += 1
            best["cost"] = spent
            best["plan"] = dict(chosen)
            return
        item = queue[index]
        for lane in lanes:
            if not lane_accepts(lane, item):
                continue
            if lane.lane_id != relief:
                if occupied[lane.lane_id] + item.billable_slots > lane.slot_capacity:
                    continue
                if any((seen, item.family) in corpus.conflicts
                       for seen in families[lane.lane_id]):
                    continue
            occupied[lane.lane_id] += item.billable_slots
            families[lane.lane_id].append(item.family)
            chosen[item.order.order_id] = lane.lane_id
            descend(index + 1, spent + item.billable_slots * lane.rate)
            del chosen[item.order.order_id]
            families[lane.lane_id].pop()
            occupied[lane.lane_id] -= item.billable_slots

    descend(0, 0)
    if best["plan"] is None:
        raise SettlementError("site %r admits no feasible placement" % site)
    displaced = sum(1 for lane_id in best["plan"].values() if lane_id == relief)
    return best["plan"], best["cost"], displaced, best["leaves"]


# --------------------------------------------------------------------------
# Money.
# --------------------------------------------------------------------------


def settle_money(corpus, admissible, admitted, placement, regions):
    """cost_policy.md: charge, rebate, then the per-client budget ceiling."""
    rate_of = {lane.lane_id: lane.rate for lane in corpus.lanes}
    spent = {}
    ledger = []
    for item in sorted((item for item in admissible if item.order.order_id in admitted),
                       key=lambda item: item.order.order_id):
        lane_id = placement[item.order.order_id]
        slots = item.billable_slots
        charge = slots * rate_of[lane_id]
        rebate = min(slots * corpus.rebate_band[str(item.order.dispatch_mode)], charge)
        net = charge - rebate
        headroom = item.budget_cap - spent.get(item.client_id, 0)
        capped = 0
        if net > headroom:
            capped = net - max(headroom, 0)
            net = max(headroom, 0)
        spent[item.client_id] = spent.get(item.client_id, 0) + net
        ledger.append(Placed(
            order_id=item.order.order_id,
            client_id=item.client_id,
            site=item.site,
            region=regions[item.site],
            service_class=item.service_class,
            lane_id=lane_id,
            program_id=item.order.program_id,
            revision=item.revision,
            billable_slots=slots,
            slack=item.slack,
            charge=charge,
            rebate=rebate,
            capped=capped,
            net=net,
        ))
    return ledger


# --------------------------------------------------------------------------
# Control figures and constant recovery.
# --------------------------------------------------------------------------


def control_figure(corpus, name, constants):
    """Reproduce one published control figure over the calibration population."""
    blocks = corpus.block_ids[CALIBRATION]

    if name == "payload_origin_total":
        total = 0
        for block_id in blocks:
            head = read_head(corpus, CALIBRATION, block_id, constants)
            payload = settled_payload(corpus, CALIBRATION, head, constants)
            total += int.from_bytes(payload[:4], "big")
        return total

    if name == "record_span_total":
        total = 0
        for block_id in blocks:
            head = read_head(corpus, CALIBRATION, block_id, constants)
            payload = settled_payload(corpus, CALIBRATION, head, constants)
            total += sum(1 for blob in carve(payload, head, constants)
                         if len(blob) == LONG_RECORD)
        return total

    if name == "calibration_order_total":
        return sum(read_head(corpus, CALIBRATION, block_id, constants).genuine_count
                   for block_id in blocks)

    if name == "island_field_total":
        total = 0
        for block_id in blocks:
            head = read_head(corpus, CALIBRATION, block_id, constants)
            total += head.lane_hint + head.horizon_slot + head.span_hint + head.seed_hint
        return total

    if name == "ordinal_position_checksum":
        total = 0
        for block_id in blocks:
            head = read_head(corpus, CALIBRATION, block_id, constants)
            if head.flags & FLAG_PERMUTATION:
                slots = travel_order(head.stored_count, constants["permute_rounds"],
                                     seed_of_block(head))
            else:
                slots = list(range(head.stored_count))
            total += sum((position + 1) * (ordinal + 1)
                         for position, ordinal in enumerate(slots))
        return total

    _, genuine, _ = decode_population(corpus, CALIBRATION, constants)

    if name == "masked_load_total":
        return sum(order.load_units for order in genuine)
    if name == "folded_slack_total":
        return sum(order.due_offset for order in genuine)
    if name == "delta_weight_total":
        return sum(order.weight for order in genuine)
    if name == "drift_day_total":
        return sum(order.submitted_day * (order.ordinal + 1) for order in genuine)
    if name == "canonical_client_total":
        total = 0
        for order in genuine:
            client = governing_client(corpus, order.alias_key)
            total += int(client["client_id"][3:]) * (order.ordinal + 1)
        return total
    if name == "backref_program_total":
        seat = {program_id: i for i, program_id in enumerate(corpus.program_order)}
        return sum(seat[order.program_id] * (order.ordinal + 1) for order in genuine)
    if name == "billable_slot_total":
        admissible, _, _ = sort_dispositions(corpus, genuine)
        return sum(bring_to_multiple(item.order.load_units, item.order.granularity,
                                     constants["quant_mode"])
                   for item in admissible)

    raise SettlementError("control figure %r is not one the slice publishes" % name)


def recover_constants(corpus):
    """Walk the resolution plan, pinning each constant against its own control.

    Constants not yet settled hold the lowest value their declared domain
    allows; the slice promises each control separates its own constant once
    every figure above it has been settled, so only the settled ones matter.
    """
    constants = {name: domain[0] for _, name, domain in RESOLUTION_PLAN}
    record = []

    for control, name, domain in RESOLUTION_PLAN:
        if control not in corpus.controls:
            raise SettlementError("the slice publishes no %r figure" % control)
        target = corpus.controls[control]
        verdicts = []
        survivors = []
        for candidate in domain:
            trial = dict(constants)
            trial[name] = candidate
            try:
                reproduced = control_figure(corpus, control, trial)
            except Exception:
                verdicts.append({"value": candidate, "verdict": "rejected"})
                continue
            if reproduced == target:
                survivors.append(candidate)
                verdicts.append({"value": candidate, "verdict": "accepted"})
            else:
                verdicts.append({"value": candidate, "verdict": "rejected"})
        if len(survivors) != 1:
            raise SettlementError(
                "control %s leaves %d candidates for %s"
                % (control, len(survivors), name))
        constants[name] = survivors[0]
        record.append({
            "parameter": name,
            "control": control,
            "domain_size": len(domain),
            "resolved": survivors[0],
            "rejected": len(domain) - 1,
            "verdicts": verdicts,
        })

    return constants, record


# --------------------------------------------------------------------------
# Whole-population settlement and the reports.
# --------------------------------------------------------------------------


def settle_population(corpus, population, constants, site_names):
    heads, genuine, everything = decode_population(corpus, population, constants)
    admissible, rejected, deferred = sort_dispositions(corpus, genuine)
    for item in admissible:
        item.billable_slots = bring_to_multiple(
            item.order.load_units, item.order.granularity, constants["quant_mode"])

    admitted, tiers, indexes, passes = settle_admission(corpus, admissible, site_names)

    regions = {row["name"]: row["region"].capitalize() for row in corpus.sites}
    placement = {}
    site_cost = {}
    displaced = 0
    leaves = 0
    for site in site_names:
        here = [item for item in admissible
                if item.site == site and item.order.order_id in admitted]
        plan, cost, pushed, seen = place_one_site(corpus, site, here)
        placement.update(plan)
        site_cost[site] = cost
        displaced += pushed
        leaves += seen

    ledger = settle_money(corpus, admissible, admitted, placement, regions)
    held = sorted(item.order.order_id for item in admissible
                  if item.order.order_id not in admitted)

    return {
        "genuine": genuine,
        "everything": everything,
        "admissible": admissible,
        "rejected": rejected,
        "deferred": deferred,
        "held": held,
        "tiers": tiers,
        "indexes": indexes,
        "passes": passes,
        "site_cost": site_cost,
        "displaced": displaced,
        "leaves": leaves,
        "ledger": ledger,
    }


def rollup(ledger, discriminator, value):
    picked = [row for row in ledger if getattr(row, discriminator) == value]
    return {
        discriminator: value,
        "order_count": len(picked),
        "orders": [
            {
                "order_id": row.order_id,
                "client_id": row.client_id,
                "lane_id": row.lane_id,
                "program_id": row.program_id,
                "revision": row.revision,
                "billable_slots": row.billable_slots,
                "slack": row.slack,
                "charge_micros": row.charge,
                "rebate_micros": row.rebate,
                "capped_micros": row.capped,
                "net_micros": row.net,
            }
            for row in picked
        ],
        "totals": {
            "billable_slots": sum(row.billable_slots for row in picked),
            "charge_micros": sum(row.charge for row in picked),
            "rebate_micros": sum(row.rebate for row in picked),
            "capped_micros": sum(row.capped for row in picked),
            "net_micros": sum(row.net for row in picked),
        },
    }


def lanes_within_capacity(corpus, ledger):
    limit = {lane.lane_id: lane.slot_capacity for lane in corpus.lanes}
    used = {}
    for row in ledger:
        used[row.lane_id] = used.get(row.lane_id, 0) + row.billable_slots
    return all(not limit.get(lane_id, 0) or total <= limit[lane_id]
               for lane_id, total in used.items())


def settle(source_dir):
    corpus = gather(source_dir)
    constants, candidate_space = recover_constants(corpus)

    site_names = sorted(row["name"] for row in corpus.sites)
    region_names = sorted({row["region"].capitalize() for row in corpus.sites})
    class_names = sorted({row["service_class"] for row in corpus.clients})

    season = settle_population(corpus, FIELD, constants, site_names)
    holdout = settle_population(corpus, CALIBRATION, constants, site_names)
    ledger = season["ledger"]

    regions = {name: rollup(ledger, "region", name) for name in region_names}
    segments = {name: rollup(ledger, "service_class", name) for name in class_names}

    net_total = sum(row.net for row in ledger)
    region_net = {name: regions[name]["totals"]["net_micros"] for name in region_names}
    segment_net = {name: segments[name]["totals"]["net_micros"] for name in class_names}

    rejected_ids = sorted(order.order_id for order in season["rejected"])
    deferred_ids = sorted([order.order_id for order in season["deferred"]]
                          + list(season["held"]))

    summary = {
        "order_rows": len(season["genuine"]),
        "decoded_rows": len(season["everything"]),
        "orders_scored": len(season["admissible"]),
        "orders_placed": len(ledger),
        "orders_deferred": len(deferred_ids),
        "orders_rejected": len(rejected_ids),
        "billable_slots_total": sum(row.billable_slots for row in ledger),
        "charge_micros_total": sum(row.charge for row in ledger),
        "rebate_micros_total": sum(row.rebate for row in ledger),
        "capped_micros_total": sum(row.capped for row in ledger),
        "net_micros_total": net_total,
        "lanes_used": len({row.lane_id for row in ledger}),
    }

    data_quality = {
        "order_rows": len(season["genuine"]),
        "decoded_rows": len(season["everything"]),
        "rejected_orders": rejected_ids,
        "deferred_orders": deferred_ids,
        "region_net_micros": region_net,
        "segment_net_micros": segment_net,
        "conservation_residual_micros": net_total - sum(region_net.values()),
        "segment_residual_micros": net_total - sum(segment_net.values()),
        "calibration_net_micros": sum(row.net for row in holdout["ledger"]),
        "invariants": {
            "region_partition_closed":
                sum(regions[name]["order_count"] for name in region_names) == len(ledger),
            "segment_partition_closed":
                sum(segments[name]["order_count"] for name in class_names) == len(ledger),
            "order_identity_unique":
                len({row.order_id for row in ledger}) == len(ledger),
            "capacity_respected": lanes_within_capacity(corpus, ledger),
        },
    }

    policy_audit = {
        "candidate_space": candidate_space,
        "resolved_parameters": {name: constants[name] for _, name, _ in RESOLUTION_PLAN},
        "calibration_comparison": [
            {
                "control": control,
                "published": corpus.controls[control],
                "reproduced": control_figure(corpus, control, constants),
            }
            for control, _, _ in RESOLUTION_PLAN
        ],
        "fixpoint": {
            "passes": season["passes"],
            "congestion_index": dict(season["indexes"]),
            "congestion_tier": dict(season["tiers"]),
        },
        "assignment_search": {
            "sites_searched": len(site_names),
            "feasible_leaves": season["leaves"],
            "displaced_orders": season["displaced"],
            "site_cost_micros": season["site_cost"],
        },
        "candidates_examined": sum(entry["domain_size"] for entry in candidate_space),
        "candidates_rejected": sum(entry["rejected"] for entry in candidate_space),
    }

    return {
        "summary": summary,
        "policy_audit": policy_audit,
        "data_quality": data_quality,
        "regions": regions,
        "segments": segments,
    }


def write_reports(result, target_dir):
    os.makedirs(target_dir, exist_ok=True)

    def emit(name, body):
        path = os.path.join(target_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(body, handle, indent=2, sort_keys=True)
            handle.write("\n")

    emit("summary.json", result["summary"])
    emit("policy_audit.json", result["policy_audit"])
    emit("data_quality.json", result["data_quality"])
    for name, body in result["regions"].items():
        emit("region_%s.json" % name, body)
    for name, body in result["segments"].items():
        emit("segment_%s.json" % name, body)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <input-directory> <output-directory>\n")
        return 2
    write_reports(settle(argv[1]), argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
