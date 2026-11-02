"""Lane dispatch settlement engine."""

import csv
import hashlib
import hmac
import json
import os
import struct
import sys
import zlib

FLAG_LANE_MASK = 0x001
FLAG_SLACK_FOLD = 0x002
FLAG_DELTA2 = 0x004
FLAG_KEY_DRIFT = 0x008
FLAG_PERMUTE = 0x010
FLAG_BACKREF = 0x020
FLAG_ENDIAN_ISLAND = 0x040
FLAG_SHADOW_LEN = 0x080
FLAG_ALIAS_ROTOR = 0x100
FLAG_ROTATE = 0x200
FLAG_COUNT_BIAS = 0x400

MAGIC = 0x4C44
HEADER_LEN = 24
BASE_RECORD_LEN = 13
BASE_KEY = "meridian-corridor-authority".encode("ascii")
GRANULARITY = [5, 10, 25, 50]
DAY_MODULUS = 251
SITES = ["Basin", "Harbor", "Ridge", "Summit"]
REGIONS = ["East", "North", "South", "West"]
CLASSES = ["commercial", "public"]
STREAM_LABELS = ["arc", "beam", "cinder", "drift", "ember"]
QUANT_MODES = ["band", "ceil", "floor", "nearest"]

PARAMETER_ORDER = [
    "rotate_step",
    "shadow_bias",
    "count_bias",
    "island_offset",
    "permute_rounds",
    "stream_label",
    "chain_seed",
    "delta_span",
    "drift_modulus",
    "alias_rotor",
    "window_span",
    "quant_mode",
]

PARAMETER_DOMAINS = {
    "rotate_step": list(range(1, 8)),
    "shadow_bias": list(range(0, 16)),
    "count_bias": list(range(0, 8)),
    "island_offset": [8, 10, 12, 14],
    "permute_rounds": [1, 2, 3, 4],
    "stream_label": list(STREAM_LABELS),
    "chain_seed": list(range(0, 256)),
    "delta_span": list(range(2, 10)),
    "drift_modulus": [97, 101, 103, 107, 109],
    "alias_rotor": list(range(1, 8)),
    "window_span": list(range(2, 9)),
    "quant_mode": list(QUANT_MODES),
}

CONTROL_FOR = {
    "rotate_step": "payload_origin_total",
    "shadow_bias": "record_span_total",
    "count_bias": "calibration_order_total",
    "island_offset": "island_field_total",
    "permute_rounds": "ordinal_position_checksum",
    "stream_label": "masked_load_total",
    "chain_seed": "folded_slack_total",
    "delta_span": "delta_weight_total",
    "drift_modulus": "drift_day_total",
    "alias_rotor": "canonical_client_total",
    "window_span": "backref_program_total",
    "quant_mode": "billable_slot_total",
}

CONTROL_ORDER = [CONTROL_FOR[name] for name in PARAMETER_ORDER]

DEFAULT_PARAMS = {
    "rotate_step": 1,
    "shadow_bias": 0,
    "count_bias": 0,
    "island_offset": 8,
    "permute_rounds": 1,
    "stream_label": STREAM_LABELS[0],
    "chain_seed": 0,
    "delta_span": 2,
    "drift_modulus": 97,
    "alias_rotor": 1,
    "window_span": 2,
    "quant_mode": "floor",
}


class DecodeError(Exception):
    pass


def u16(buf, off):
    return (buf[off] << 8) | buf[off + 1]


def u16le(buf, off):
    return (buf[off + 1] << 8) | buf[off]


def u32(buf, off):
    return (buf[off] << 24) | (buf[off + 1] << 16) | (buf[off + 2] << 8) | buf[off + 3]


def xorshift64(state):
    state &= 0xFFFFFFFFFFFFFFFF
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state & 0xFFFFFFFFFFFFFFFF


def block_seed(block_id, lane_hint, horizon_slot, span_hint, seed_hint):
    material = b"block|" + struct.pack(
        ">HHHHH", block_id & 0xFFFF, lane_hint & 0xFFFF, horizon_slot & 0xFFFF,
        span_hint & 0xFFFF, seed_hint & 0xFFFF)
    digest = hmac.new(BASE_KEY, material, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big") or 1


def build_permutation(size, rounds, seed):
    order = list(range(size))
    state = seed & 0xFFFFFFFFFFFFFFFF
    if state == 0:
        state = 1
    for _ in range(rounds):
        for index in range(size - 1, 0, -1):
            state = xorshift64(state)
            pick = state % (index + 1)
            order[index], order[pick] = order[pick], order[index]
    return order


def keystream(label, block_id, ordinal, width):
    material = label.encode("utf-8") + b"|" + struct.pack(">HH", block_id & 0xFFFF, ordinal & 0xFFFF)
    return hmac.new(BASE_KEY, material, hashlib.sha256).digest()[:width]


def modinv(value, modulus):
    value %= modulus
    if value == 0:
        raise DecodeError("day multiplier is singular")
    return pow(value, modulus - 2, modulus)


def rotate_left(data, amount):
    if not data:
        return data
    amount %= len(data)
    return data[amount:] + data[:amount]


def rotate_right(data, amount):
    if not data:
        return data
    amount %= len(data)
    if amount == 0:
        return data
    return data[-amount:] + data[:-amount]


def quantise(value, granularity, mode):
    whole, remainder = divmod(value, granularity)
    if remainder == 0:
        return value
    if mode == "floor":
        return whole * granularity
    if mode == "ceil":
        return (whole + 1) * granularity
    if mode == "nearest":
        return (whole + 1) * granularity if remainder * 2 >= granularity else whole * granularity
    if mode == "band":
        return (whole + 1) * granularity if remainder * 4 >= granularity * 3 else whole * granularity
    raise DecodeError("unknown quantisation mode %s" % mode)


def read_csv(path):
    # utf-8-sig drops a byte order mark; names and cells are compared trimmed.
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle)]


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def parse_controls(body):
    controls = {}
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("- ") or "=" not in line:
            continue
        name, _, value = line[2:].partition("=")
        name = name.strip()
        value = value.strip()
        try:
            controls[name] = int(value)
        except ValueError:
            continue
    return controls


def parse_settings(body):
    settings = {}
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        name, _, value = line[2:].partition(":")
        settings[name.strip()] = value.strip()
    return settings


def parse_int_list(text):
    return [int(part.strip()) for part in text.split(",") if part.strip()]


def parse_int_map(text):
    mapping = {}
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        mapping[key.strip()] = int(value.strip())
    return mapping


def parse_pairs(text):
    pairs = []
    for part in text.split(","):
        part = part.strip()
        if not part or "|" not in part:
            continue
        left, _, right = part.partition("|")
        pairs.append((left.strip(), right.strip()))
    return pairs


def load_corpus(data_dir):
    def path(name):
        return os.path.join(data_dir, name)

    clients = read_csv(path("client_directory.csv"))
    programs = read_csv(path("program_registry.csv"))
    lanes = read_csv(path("lane_roster.csv"))
    sites = read_csv(path("site_directory.csv"))
    manifest = read_csv(path("block_manifest.csv"))

    payloads = {}
    for population, name in (
            ("calibration", "calibration_orders.csv"),
            ("field", "field_orders.csv"),
            ("probe", "reference_probe.csv")):
        for row in read_csv(path(name)):
            payloads[(population, int(row["block_id"]))] = bytes.fromhex(row["payload_hex"])

    headers = {}
    order = {"calibration": [], "field": [], "probe": []}
    for row in manifest:
        population = row["population"]
        block_id = int(row["block_id"])
        headers[(population, block_id)] = bytes.fromhex(row["header_hex"])
        order.setdefault(population, []).append(block_id)

    capacity = parse_settings(read_text(path("capacity_policy.md")))
    dispatch = parse_settings(read_text(path("dispatch_policy.md")))
    cost = parse_settings(read_text(path("cost_policy.md")))
    controls = parse_controls(read_text(path("calibration_slice.md")))

    alias_table = [row["alias_key"] for row in clients]
    program_ids = sorted({row["program_id"] for row in programs})

    return {
        "clients": clients,
        "programs": programs,
        "lanes": lanes,
        "sites": sites,
        "headers": headers,
        "payloads": payloads,
        "order": order,
        "alias_table": alias_table,
        "program_ids": program_ids,
        "controls": controls,
        "tier_bounds": parse_int_list(capacity["congestion_bounds"]),
        "base_ceiling": parse_int_map(capacity["base_ceiling"]),
        "tier_factor": parse_int_map(capacity["tier_factor"]),
        "rebate_band": parse_int_map(cost["rebate_band"]),
        "family_conflicts": parse_pairs(dispatch["incompatible_families"]),
    }


def block_view(corpus, population, block_id, params):
    header = corpus["headers"][(population, block_id)]
    if len(header) != HEADER_LEN:
        raise DecodeError("block header length is wrong")
    if zlib.crc32(header[:20]) & 0xFFFFFFFF != u32(header, 20):
        raise DecodeError("block header checksum disagrees")
    if u16(header, 0) != MAGIC:
        raise DecodeError("block magic disagrees")
    flags = u16(header, 6)
    aux = {}
    for offset in (8, 10, 12, 14):
        if flags & FLAG_ENDIAN_ISLAND and offset == params["island_offset"]:
            aux[offset] = u16le(header, offset)
        else:
            aux[offset] = u16(header, offset)
    stored_count = u16(header, 4)
    bias = params["count_bias"] if flags & FLAG_COUNT_BIAS else 0
    true_count = stored_count - bias
    if true_count < 1 or true_count > stored_count:
        raise DecodeError("block record count is out of range")
    return {
        "block_id": block_id,
        "flags": flags,
        "stored_count": stored_count,
        "true_count": true_count,
        "lane_hint": aux[8],
        "horizon_slot": aux[10],
        "span_hint": aux[12],
        "seed_hint": aux[14],
        "payload_crc": u32(header, 16),
    }


def payload_amount(view, payload, params):
    if not view["flags"] & FLAG_ROTATE or not payload:
        return 0
    return (view["block_id"] * params["rotate_step"]) % len(payload)


def split_records(payload, view, params):
    records = []
    cursor = 0
    shadow = params["shadow_bias"] if view["flags"] & FLAG_SHADOW_LEN else 0
    for _ in range(view["stored_count"]):
        if cursor >= len(payload):
            raise DecodeError("record cursor ran past the payload")
        len_code = ((payload[cursor] >> 4) & 0x0F) ^ shadow
        if len_code == 0:
            width = BASE_RECORD_LEN
        elif len_code == 1:
            width = BASE_RECORD_LEN + 2
        else:
            raise DecodeError("record length code is out of range")
        if cursor + width > len(payload):
            raise DecodeError("record extends past the payload")
        records.append(payload[cursor:cursor + width])
        cursor += width
    if cursor != len(payload):
        raise DecodeError("payload holds trailing bytes")
    return records


def logical_records(records, view, params):
    if not view["flags"] & FLAG_PERMUTE:
        return list(records)
    seed = block_seed(view["block_id"], view["lane_hint"], view["horizon_slot"],
                      view["span_hint"], view["seed_hint"])
    order = build_permutation(len(records), params["permute_rounds"], seed)
    logical = [None] * len(records)
    for physical, ordinal in enumerate(order):
        logical[ordinal] = records[physical]
    return logical


def decode_block(corpus, population, block_id, params, state):
    view = block_view(corpus, population, block_id, params)
    wire = corpus["payloads"][(population, block_id)]
    if zlib.crc32(wire) & 0xFFFFFFFF != view["payload_crc"]:
        raise DecodeError("payload checksum disagrees")
    payload = rotate_right(wire, payload_amount(view, wire, params))
    physical = split_records(payload, view, params)
    ordered = logical_records(physical, view, params)

    flags = view["flags"]
    alias_count = len(corpus["alias_table"])
    program_count = len(corpus["program_ids"])
    previous_due = params["chain_seed"] if flags & FLAG_SLACK_FOLD else 0
    weights = []
    decoded = []

    for ordinal, raw in enumerate(ordered):
        ctrl = raw[0]
        mode = ctrl & 0x0F
        if mode > 3:
            raise DecodeError("dispatch mode is out of range")
        load = u32(raw, 3)
        if flags & FLAG_LANE_MASK:
            mask = keystream(params["stream_label"], block_id, ordinal, 4)
            load ^= int.from_bytes(mask, "big")
        due_off = u16(raw, 7)
        if flags & FLAG_SLACK_FOLD:
            due_off = (due_off - previous_due) & 0xFFFF
            previous_due = due_off
        stored_weight = u16(raw, 9)
        if flags & FLAG_DELTA2:
            position = ordinal % params["delta_span"]
            if position == 0:
                weight = stored_weight
            elif position == 1:
                weight = (weights[-1] + stored_weight) & 0xFFFF
            else:
                weight = (2 * weights[-1] - weights[-2] + stored_weight) & 0xFFFF
        else:
            weight = stored_weight
        weights.append(weight)
        gran_code = raw[11]
        if gran_code > 3:
            raise DecodeError("granularity code is out of range")
        day = raw[12]
        if flags & FLAG_KEY_DRIFT:
            factor = 1 + (state["load_sum"] % (params["drift_modulus"] - 1))
            day = (day * modinv(factor, DAY_MODULUS)) % DAY_MODULUS
        slack_ext = u16(raw, 13) if len(raw) == BASE_RECORD_LEN + 2 else 0

        alias_index = raw[1]
        if flags & FLAG_ALIAS_ROTOR:
            alias_index -= params["alias_rotor"]
        alias_index %= alias_count

        program_ref = raw[2]
        if program_ref >= 0xF0 and flags & FLAG_BACKREF:
            back = ((program_ref - 0xF0) % params["window_span"]) + 1
            if back > ordinal:
                raise DecodeError("back reference points before the block")
            program_id = decoded[ordinal - back]["program_id"]
        else:
            program_id = corpus["program_ids"][program_ref % program_count]

        entry = {
            "order_id": "W%04d%02d" % (block_id, ordinal),
            "block_id": block_id,
            "ordinal": ordinal,
            "dispatch_mode": mode,
            "alias_key": corpus["alias_table"][alias_index],
            "program_id": program_id,
            "load_units": load,
            "due_slot": view["horizon_slot"] + due_off + slack_ext,
            "due_offset": due_off,
            "weight": weight,
            "granularity": GRANULARITY[gran_code],
            "submitted_day": day,
            "extended": len(raw) == BASE_RECORD_LEN + 2,
        }
        decoded.append(entry)
        if ordinal < view["true_count"]:
            state["load_sum"] += load

    return view, decoded


def decode_population(corpus, population, params):
    state = {"load_sum": 0}
    views = {}
    kept = []
    raw_records = []
    for block_id in corpus["order"][population]:
        view, decoded = decode_block(corpus, population, block_id, params, state)
        views[block_id] = view
        raw_records.extend(decoded)
        kept.extend(decoded[:view["true_count"]])
    return {"views": views, "records": kept, "raw_records": raw_records}


def resolve_client(corpus, alias_key):
    by_alias = {row["alias_key"]: row for row in corpus["clients"]}
    by_id = {row["client_id"]: row for row in corpus["clients"]}
    current = by_alias.get(alias_key)
    if current is None:
        raise DecodeError("alias key is absent from the directory")
    seen = [current["client_id"]]
    while current.get("merged_into"):
        nxt = by_id.get(current["merged_into"])
        if nxt is None:
            break
        if nxt["client_id"] in seen:
            return by_id[min(seen)]
        seen.append(nxt["client_id"])
        current = nxt
    return current


def governing_revision(corpus, program_id, day):
    best = None
    for row in corpus["programs"]:
        if row["program_id"] != program_id:
            continue
        start = int(row["effective_from"])
        end = int(row["effective_to"])
        if start <= day < end:
            if best is None or int(row["revision"]) > int(best["revision"]):
                best = row
    return best


def classify(corpus, records):
    scored = []
    rejected = []
    deferred = []
    for record in records:
        client = resolve_client(corpus, record["alias_key"])
        day = record["submitted_day"]
        retired = client.get("retired_on") or ""
        effective = int(client.get("effective_from") or 0)
        if retired and day >= int(retired):
            rejected.append(dict(record, client_id=client["client_id"], reason="retired"))
            continue
        revision = governing_revision(corpus, record["program_id"], day)
        if revision is None:
            rejected.append(dict(record, client_id=client["client_id"], reason="no_revision"))
            continue
        if day < effective:
            deferred.append(dict(record, client_id=client["client_id"], reason="pre_effective"))
            continue
        scored.append(dict(
            record,
            client_id=client["client_id"],
            site=client["site"],
            service_class=client["service_class"],
            budget_cap_micros=int(client["budget_cap_micros"]),
            revision=int(revision["revision"]),
            family=revision["family"],
            slack=record["due_slot"] - day,
        ))
    return scored, rejected, deferred


def apply_quantisation(scored, mode):
    for item in scored:
        item["billable_slots"] = quantise(item["load_units"], item["granularity"], mode)


def admission_order(items):
    return sorted(items, key=lambda item: (-item["weight"], item["order_id"]))


def congestion_tier(index, bounds):
    for tier, bound in enumerate(bounds):
        if index < bound:
            return tier
    return len(bounds)


def settle_admission(corpus, scored):
    capacity = {row["name"]: int(row["capacity_slots"]) for row in corpus["sites"]}
    bounds = corpus["tier_bounds"]
    tiers = {site: 0 for site in SITES}
    passes = 0
    admitted = set()
    indexes = {site: 0 for site in SITES}
    ordered = admission_order(scored)
    for _ in range(32):
        passes += 1
        used = {site: 0 for site in SITES}
        spent = {}
        admitted = set()
        for item in ordered:
            site = item["site"]
            factor = corpus["tier_factor"][str(tiers[site])]
            ceiling = corpus["base_ceiling"][item["service_class"]] * factor // 100
            taken = spent.get(item["client_id"], 0)
            if taken + item["billable_slots"] > ceiling:
                continue
            spent[item["client_id"]] = taken + item["billable_slots"]
            used[site] += item["billable_slots"]
            admitted.add(item["order_id"])
        indexes = {site: (1000 * used[site]) // capacity[site] for site in SITES}
        fresh = {site: congestion_tier(indexes[site], bounds) for site in SITES}
        raised = {site: max(tiers[site], fresh[site]) for site in SITES}
        if raised == tiers:
            if fresh != tiers:
                raise DecodeError("congestion did not settle")
            return admitted, tiers, indexes, passes
        tiers = raised
    raise DecodeError("admission did not settle")


def conflict_pairs(corpus):
    pairs = set()
    for left, right in corpus["family_conflicts"]:
        pairs.add((left, right))
        pairs.add((right, left))
    return pairs


def lane_eligible(lane, item):
    if lane["class_lock"] and lane["class_lock"] != item["service_class"]:
        return False
    if lane["exclusive_client"] and lane["exclusive_client"] != item["client_id"]:
        return False
    return True


def counterfactual_key(item):
    return (-item["slack"], -item["billable_slots"], item["order_id"])


def place_site(corpus, site, items, conflicts):
    lanes = [row for row in corpus["lanes"] if row["site"] == site]
    lanes = [dict(row,
                  slot_capacity=int(row["slot_capacity"]),
                  rate_micros=int(row["rate_micros"])) for row in lanes]
    lanes.sort(key=lambda row: (row["rate_micros"], row["lane_id"]))
    relief = [row for row in lanes
              if row["slot_capacity"] == 0 and not row["class_lock"] and not row["exclusive_client"]]
    if len(relief) != 1:
        raise DecodeError("the site has no single relief lane")
    relief_id = relief[0]["lane_id"]
    ordered = sorted(items, key=counterfactual_key)
    count = len(ordered)
    if count == 0:
        return {}, 0, 0, 0

    floors = []
    for item in ordered:
        rates = [row["rate_micros"] for row in lanes if lane_eligible(row, item)]
        if not rates:
            raise DecodeError("an admitted order matches no lane")
        floors.append(item["billable_slots"] * min(rates))
    tail = [0] * (count + 1)
    tail_slots = [0] * (count + 1)
    for index in range(count - 1, -1, -1):
        tail[index] = tail[index + 1] + floors[index]
        tail_slots[index] = tail_slots[index + 1] + ordered[index]["billable_slots"]

    seed_used = {row["lane_id"]: 0 for row in lanes}
    seed_families = {row["lane_id"]: [] for row in lanes}
    seed_cost = 0
    for item in ordered:
        for lane in lanes:
            if not lane_eligible(lane, item):
                continue
            lane_id = lane["lane_id"]
            if lane_id != relief_id:
                if seed_used[lane_id] + item["billable_slots"] > lane["slot_capacity"]:
                    continue
                if any((family, item["family"]) in conflicts
                       for family in seed_families[lane_id]):
                    continue
            seed_used[lane_id] += item["billable_slots"]
            seed_families[lane_id].append(item["family"])
            seed_cost += item["billable_slots"] * lane["rate_micros"]
            break

    best = {"cost": seed_cost + 1, "assignment": None, "leaves": 0}
    used = {row["lane_id"]: 0 for row in lanes}
    families = {row["lane_id"]: [] for row in lanes}
    current = {}

    def relaxed(index):
        need = tail_slots[index]
        total = 0
        for lane in lanes:
            if need <= 0:
                break
            lane_id = lane["lane_id"]
            if lane_id == relief_id:
                room = need
            else:
                room = lane["slot_capacity"] - used[lane_id]
            if room <= 0:
                continue
            take = room if room < need else need
            total += take * lane["rate_micros"]
            need -= take
        return total

    def walk(index, cost):
        floor_cost = tail[index]
        relaxed_cost = relaxed(index)
        if relaxed_cost > floor_cost:
            floor_cost = relaxed_cost
        if cost + floor_cost >= best["cost"]:
            return
        if index == count:
            best["leaves"] += 1
            best["cost"] = cost
            best["assignment"] = dict(current)
            return
        item = ordered[index]
        for lane in lanes:
            if not lane_eligible(lane, item):
                continue
            lane_id = lane["lane_id"]
            if lane_id != relief_id:
                if used[lane_id] + item["billable_slots"] > lane["slot_capacity"]:
                    continue
                clash = False
                for family in families[lane_id]:
                    if (family, item["family"]) in conflicts:
                        clash = True
                        break
                if clash:
                    continue
            used[lane_id] += item["billable_slots"]
            families[lane_id].append(item["family"])
            current[item["order_id"]] = lane_id
            walk(index + 1, cost + item["billable_slots"] * lane["rate_micros"])
            del current[item["order_id"]]
            families[lane_id].pop()
            used[lane_id] -= item["billable_slots"]

    walk(0, 0)
    if best["assignment"] is None:
        raise DecodeError("the site admits no feasible lane assignment")
    displaced = sum(1 for lane_id in best["assignment"].values() if lane_id == relief_id)
    return best["assignment"], best["cost"], displaced, best["leaves"]


def settle_schedule(corpus, scored, admitted):
    conflicts = conflict_pairs(corpus)
    placements = {}
    stats = {"feasible_leaves": 0, "displaced": 0, "site_cost": {}}
    for site in SITES:
        items = [item for item in scored
                 if item["site"] == site and item["order_id"] in admitted]
        assignment, cost, displaced, leaves = place_site(corpus, site, items, conflicts)
        placements.update(assignment)
        stats["site_cost"][site] = cost
        stats["displaced"] += displaced
        stats["feasible_leaves"] += leaves
    return placements, stats


def settle_costs(corpus, scored, admitted, placements):
    rates = {row["lane_id"]: int(row["rate_micros"]) for row in corpus["lanes"]}
    regions = region_of(corpus)
    rows = []
    spent = {}
    for item in sorted((item for item in scored if item["order_id"] in admitted),
                       key=lambda item: item["order_id"]):
        lane_id = placements[item["order_id"]]
        slots = item["billable_slots"]
        charge = slots * rates[lane_id]
        rebate = min(slots * corpus["rebate_band"][str(item["dispatch_mode"])], charge)
        net = charge - rebate
        taken = spent.get(item["client_id"], 0)
        room = item["budget_cap_micros"] - taken
        capped = 0
        if net > room:
            capped = net - max(room, 0)
            net = max(room, 0)
        spent[item["client_id"]] = taken + net
        rows.append({
            "order_id": item["order_id"],
            "client_id": item["client_id"],
            "site": item["site"],
            "region": regions[item["site"]],
            "service_class": item["service_class"],
            "lane_id": lane_id,
            "program_id": item["program_id"],
            "revision": item["revision"],
            "billable_slots": slots,
            "slack": item["slack"],
            "charge_micros": charge,
            "rebate_micros": rebate,
            "capped_micros": capped,
            "net_micros": net,
        })
    return rows


def capacity_respected(corpus, rows):
    limits = {}
    for lane in corpus["lanes"]:
        limits[lane["lane_id"]] = int(lane["slot_capacity"])
    used = {}
    for row in rows:
        used[row["lane_id"]] = used.get(row["lane_id"], 0) + row["billable_slots"]
    for lane_id, total in used.items():
        limit = limits.get(lane_id, 0)
        if limit and total > limit:
            return False
    return True


def control_value(corpus, name, params):
    population = "calibration"
    if name == "payload_origin_total":
        total = 0
        for block_id in corpus["order"][population]:
            view = block_view(corpus, population, block_id, params)
            wire = corpus["payloads"][(population, block_id)]
            payload = rotate_right(wire, payload_amount(view, wire, params))
            total += int.from_bytes(payload[:4], "big")
        return total
    if name == "record_span_total":
        total = 0
        for block_id in corpus["order"][population]:
            view = block_view(corpus, population, block_id, params)
            wire = corpus["payloads"][(population, block_id)]
            payload = rotate_right(wire, payload_amount(view, wire, params))
            for record in split_records(payload, view, params):
                if len(record) == BASE_RECORD_LEN + 2:
                    total += 1
        return total
    if name == "calibration_order_total":
        total = 0
        for block_id in corpus["order"][population]:
            total += block_view(corpus, population, block_id, params)["true_count"]
        return total
    if name == "island_field_total":
        total = 0
        for block_id in corpus["order"][population]:
            view = block_view(corpus, population, block_id, params)
            total += view["lane_hint"] + view["horizon_slot"] + view["span_hint"] + view["seed_hint"]
        return total
    if name == "ordinal_position_checksum":
        total = 0
        for block_id in corpus["order"][population]:
            view = block_view(corpus, population, block_id, params)
            size = view["stored_count"]
            if view["flags"] & FLAG_PERMUTE:
                seed = block_seed(view["block_id"], view["lane_hint"], view["horizon_slot"],
                                  view["span_hint"], view["seed_hint"])
                order = build_permutation(size, params["permute_rounds"], seed)
            else:
                order = list(range(size))
            for physical, ordinal in enumerate(order):
                total += (physical + 1) * (ordinal + 1)
        return total

    decoded = decode_population(corpus, population, params)
    records = decoded["records"]
    if name == "masked_load_total":
        return sum(record["load_units"] for record in records)
    if name == "folded_slack_total":
        return sum(record["due_offset"] for record in records)
    if name == "delta_weight_total":
        return sum(record["weight"] for record in records)
    if name == "drift_day_total":
        return sum(record["submitted_day"] * (record["ordinal"] + 1) for record in records)
    if name == "canonical_client_total":
        total = 0
        for record in records:
            client = resolve_client(corpus, record["alias_key"])
            total += int(client["client_id"][3:]) * (record["ordinal"] + 1)
        return total
    if name == "backref_program_total":
        index = {program_id: pos for pos, program_id in enumerate(corpus["program_ids"])}
        return sum(index[record["program_id"]] * (record["ordinal"] + 1) for record in records)
    if name == "billable_slot_total":
        scored, _, _ = classify(corpus, records)
        apply_quantisation(scored, params["quant_mode"])
        return sum(item["billable_slots"] for item in scored)
    raise DecodeError("unknown control figure %s" % name)


def recover_parameters(corpus):
    params = dict(DEFAULT_PARAMS)
    audit = []
    for name in PARAMETER_ORDER:
        control = CONTROL_FOR[name]
        if control not in corpus["controls"]:
            raise DecodeError("control figure %s is absent" % control)
        target = corpus["controls"][control]
        survivors = []
        for candidate in PARAMETER_DOMAINS[name]:
            trial = dict(params)
            trial[name] = candidate
            try:
                if control_value(corpus, control, trial) == target:
                    survivors.append(candidate)
            except (DecodeError, IndexError, KeyError, ValueError, ZeroDivisionError):
                continue
        if len(survivors) != 1:
            raise DecodeError(
                "control %s leaves %d candidates for %s" % (control, len(survivors), name))
        params[name] = survivors[0]
        audit.append({
            "parameter": name,
            "control": control,
            "domain_size": len(PARAMETER_DOMAINS[name]),
            "resolved": survivors[0],
        })
    return params, audit


def region_of(corpus):
    return {row["name"]: row["region"].capitalize() for row in corpus["sites"]}


def rollup(rows, key, value):
    picked = [row for row in rows if row[key] == value]
    return {
        key: value,
        "order_count": len(picked),
        "orders": [
            {
                "order_id": row["order_id"],
                "client_id": row["client_id"],
                "lane_id": row["lane_id"],
                "program_id": row["program_id"],
                "revision": row["revision"],
                "billable_slots": row["billable_slots"],
                "slack": row["slack"],
                "charge_micros": row["charge_micros"],
                "rebate_micros": row["rebate_micros"],
                "capped_micros": row["capped_micros"],
                "net_micros": row["net_micros"],
            }
            for row in picked
        ],
        "totals": {
            "billable_slots": sum(row["billable_slots"] for row in picked),
            "charge_micros": sum(row["charge_micros"] for row in picked),
            "rebate_micros": sum(row["rebate_micros"] for row in picked),
            "capped_micros": sum(row["capped_micros"] for row in picked),
            "net_micros": sum(row["net_micros"] for row in picked),
        },
    }


def settle_population(corpus, population, params):
    decoded = decode_population(corpus, population, params)
    scored, rejected, deferred = classify(corpus, decoded["records"])
    apply_quantisation(scored, params["quant_mode"])
    admitted, tiers, indexes, passes = settle_admission(corpus, scored)
    placements, stats = settle_schedule(corpus, scored, admitted)
    rows = settle_costs(corpus, scored, admitted, placements)
    held = [item["order_id"] for item in scored if item["order_id"] not in admitted]
    return {
        "decoded": decoded,
        "scored": scored,
        "rejected": rejected,
        "deferred": deferred,
        "held": sorted(held),
        "admitted": admitted,
        "tiers": tiers,
        "indexes": indexes,
        "passes": passes,
        "placements": placements,
        "stats": stats,
        "rows": rows,
    }


def derive(data_dir):
    corpus = load_corpus(data_dir)
    params, audit = recover_parameters(corpus)
    field = settle_population(corpus, "field", params)
    calib = settle_population(corpus, "calibration", params)
    rows = field["rows"]

    region_reports = {name: rollup(rows, "region", name) for name in REGIONS}
    segment_reports = {name: rollup(rows, "service_class", name) for name in CLASSES}

    net_total = sum(row["net_micros"] for row in rows)
    region_net = {name: region_reports[name]["totals"]["net_micros"] for name in REGIONS}
    segment_net = {name: segment_reports[name]["totals"]["net_micros"] for name in CLASSES}

    deferred_ids = sorted(
        [item["order_id"] for item in field["deferred"]] + list(field["held"]))
    rejected_ids = sorted(item["order_id"] for item in field["rejected"])

    summary = {
        "order_rows": len(field["decoded"]["records"]),
        "decoded_rows": len(field["decoded"]["raw_records"]),
        "orders_scored": len(field["scored"]),
        "orders_placed": len(rows),
        "orders_deferred": len(deferred_ids),
        "orders_rejected": len(rejected_ids),
        "billable_slots_total": sum(row["billable_slots"] for row in rows),
        "charge_micros_total": sum(row["charge_micros"] for row in rows),
        "rebate_micros_total": sum(row["rebate_micros"] for row in rows),
        "capped_micros_total": sum(row["capped_micros"] for row in rows),
        "net_micros_total": net_total,
        "lanes_used": len({row["lane_id"] for row in rows}),
    }

    policy_audit = {
        "candidate_space": [
            {
                "parameter": entry["parameter"],
                "control": entry["control"],
                "domain_size": entry["domain_size"],
                "resolved": entry["resolved"],
                "rejected": entry["domain_size"] - 1,
            }
            for entry in audit
        ],
        "resolved_parameters": {name: params[name] for name in PARAMETER_ORDER},
        "calibration_comparison": [
            {
                "control": CONTROL_FOR[name],
                "published": corpus["controls"][CONTROL_FOR[name]],
                "reproduced": control_value(corpus, CONTROL_FOR[name], params),
            }
            for name in PARAMETER_ORDER
        ],
        "fixpoint": {
            "passes": field["passes"],
            "congestion_index": {site: field["indexes"][site] for site in SITES},
            "congestion_tier": {site: field["tiers"][site] for site in SITES},
        },
        "assignment_search": {
            "sites_searched": len(SITES),
            "feasible_leaves": field["stats"]["feasible_leaves"],
            "displaced_orders": field["stats"]["displaced"],
            "site_cost_micros": field["stats"]["site_cost"],
        },
        "candidates_examined": sum(entry["domain_size"] for entry in audit),
        "candidates_rejected": sum(entry["domain_size"] - 1 for entry in audit),
    }

    data_quality = {
        "order_rows": len(field["decoded"]["records"]),
        "decoded_rows": len(field["decoded"]["raw_records"]),
        "rejected_orders": rejected_ids,
        "deferred_orders": deferred_ids,
        "region_net_micros": region_net,
        "segment_net_micros": segment_net,
        "conservation_residual_micros": net_total - sum(region_net.values()),
        "segment_residual_micros": net_total - sum(segment_net.values()),
        "calibration_net_micros": sum(row["net_micros"] for row in calib["rows"]),
        "invariants": {
            "region_partition_closed": sum(
                region_reports[name]["order_count"] for name in REGIONS) == len(rows),
            "segment_partition_closed": sum(
                segment_reports[name]["order_count"] for name in CLASSES) == len(rows),
            "order_identity_unique": len({row["order_id"] for row in rows}) == len(rows),
            "capacity_respected": capacity_respected(corpus, rows),
        },
    }

    return {
        "params": params,
        "summary": summary,
        "policy_audit": policy_audit,
        "data_quality": data_quality,
        "regions": region_reports,
        "segments": segment_reports,
        "field": field,
        "calibration": calib,
        "corpus": corpus,
    }


def write_outputs(result, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    def dump(name, payload):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    dump("summary.json", result["summary"])
    dump("policy_audit.json", result["policy_audit"])
    dump("data_quality.json", result["data_quality"])
    for name in REGIONS:
        dump("region_%s.json" % name, result["regions"][name])
    for name in CLASSES:
        dump("segment_%s.json" % name, result["segments"][name])


# ---------------------------------------------------------------------------
# corpus generator
# ---------------------------------------------------------------------------

SAMPLE_SEED = 0x7A3E1B9C4D2F60A8
CHALLENGE_SEED = 0x1F8C5D2E9B47A063
EVAL_SEED = 0x6D04B9E13C8A2F57


class Rng(object):
    def __init__(self, seed):
        self.state = (seed & 0xFFFFFFFFFFFFFFFF) or 1

    def next(self):
        self.state = xorshift64(self.state)
        return self.state

    def below(self, bound):
        if bound <= 0:
            return 0
        return self.next() % bound

    def between(self, low, high):
        if high <= low:
            return low
        return low + self.below(high - low + 1)

    def pick(self, seq):
        return seq[self.below(len(seq))]


ALL_FLAGS = 0x7FF

BASE_SPEC = {
    "hidden": {
        "rotate_step": 5,
        "shadow_bias": 11,
        "count_bias": 3,
        "island_offset": 12,
        "permute_rounds": 3,
        "stream_label": "cinder",
        "chain_seed": 173,
        "delta_span": 6,
        "drift_modulus": 103,
        "alias_rotor": 4,
        "window_span": 5,
        "quant_mode": "band",
    },
    "sites": [
        ["Basin", "north", 1400, 140],
        ["Harbor", "east", 1250, 150],
        ["Ridge", "west", 1000, 135],
        ["Summit", "south", 1500, 145],
    ],
    "lanes": [
        ["BSN-A", "Basin", "", "", 240, 38],
        ["BSN-B", "Basin", "public", "", 180, 46],
        ["BSN-C", "Basin", "", "", 200, 53],
        ["BSN-Z", "Basin", "", "", 0, 140],
        ["HBR-A", "Harbor", "", "", 260, 35],
        ["HBR-B", "Harbor", "commercial", "", 200, 44],
        ["HBR-C", "Harbor", "", "", 190, 57],
        ["HBR-Z", "Harbor", "", "", 0, 150],
        ["RDG-A", "Ridge", "", "", 210, 40],
        ["RDG-B", "Ridge", "public", "", 170, 48],
        ["RDG-C", "Ridge", "", "", 180, 55],
        ["RDG-Z", "Ridge", "", "", 0, 135],
        ["SMT-A", "Summit", "", "", 230, 37],
        ["SMT-B", "Summit", "", "CL-0007", 190, 45],
        ["SMT-C", "Summit", "", "", 175, 56],
        ["SMT-Z", "Summit", "", "", 0, 145],
    ],
    "clients": [
        ["CL-0001", "AK7", "Aldermoor Kilns", "Basin", "commercial", 26400, "", "", 0],
        ["CL-0002", "BR2", "Bracken Rolling", "Basin", "public", 21600, "", "", 0],
        ["CL-0003", "CV9", "Calder Vats", "Basin", "commercial", 24000, "CL-0001", "", 0],
        ["CL-0004", "DM4", "Dunmore Presses", "Harbor", "public", 31200, "", "", 0],
        ["CL-0005", "EF6", "Elmfield Grinders", "Harbor", "commercial", 28800, "", "", 0],
        ["CL-0006", "FH1", "Fallhaven Anneal", "Harbor", "public", 19200, "CL-0004", "", 0],
        ["CL-0007", "GT8", "Garrowton Tools", "Summit", "public", 36000, "", "", 0],
        ["CL-0008", "HL3", "Havelock Lathes", "Summit", "commercial", 22800, "", "", 0],
        ["CL-0009", "IW5", "Ironwell Casting", "Ridge", "commercial", 30000, "", "", 0],
        ["CL-0010", "JP0", "Jarrow Plating", "Ridge", "public", 20400, "", "150", 0],
        ["CL-0011", "KD7", "Kestrel Drawworks", "Ridge", "commercial", 25200, "CL-0009", "", 0],
        ["CL-0012", "LM2", "Longmarsh Mills", "Summit", "commercial", 27600, "", "", 140],
        ["CL-0013", "NR4", "Northreach Forge", "Basin", "public", 21120, "CL-0003", "", 0],
        ["CL-0014", "PS9", "Pellston Shears", "Harbor", "commercial", 23520, "", "", 0],
        ["CL-0015", "QV6", "Quarrybank Vessels", "Ridge", "public", 33600, "", "", 0],
        ["CL-0016", "RT1", "Redthorn Tempering", "Summit", "commercial", 26400, "CL-0008", "", 0],
    ],
    "programs": [
        ["PG-ANNEAL", 1, 0, 96, "thermal"],
        ["PG-ANNEAL", 2, 96, 256, "thermal"],
        ["PG-BLAST", 1, 0, 256, "abrasive"],
        ["PG-CURING", 1, 0, 72, "thermal"],
        ["PG-CURING", 2, 72, 184, "solvent"],
        ["PG-CURING", 3, 184, 256, "solvent"],
        ["PG-DEGREASE", 1, 0, 60, "solvent"],
        ["PG-DEGREASE", 2, 120, 256, "solvent"],
        ["PG-ETCHING", 1, 0, 140, "solvent"],
        ["PG-ETCHING", 2, 140, 256, "abrasive"],
        ["PG-FORMING", 1, 0, 256, "inert"],
        ["PG-GRINDING", 1, 0, 108, "abrasive"],
        ["PG-GRINDING", 2, 108, 256, "abrasive"],
        ["PG-HONING", 1, 0, 256, "inert"],
        ["PG-LAPPING", 1, 0, 200, "abrasive"],
        ["PG-LAPPING", 2, 200, 256, "inert"],
        ["PG-PICKLING", 1, 0, 256, "solvent"],
        ["PG-TEMPER", 1, 0, 164, "thermal"],
        ["PG-TEMPER", 2, 164, 256, "thermal"],
    ],
    "family_conflicts": [["thermal", "solvent"], ["abrasive", "inert"]],
    "base_ceiling": {"commercial": 320, "public": 260},
    "tier_factor": {"0": 100, "1": 118, "2": 134, "3": 152},
    "tier_bounds": [400, 700, 900],
    "rebate_band": {"0": 0, "1": 4, "2": 9, "3": 15},
    "calibration_blocks": 8,
    "field_blocks": 10,
    "probe_blocks": 2,
    "calibration_flags": [ALL_FLAGS, ALL_FLAGS, 0x575, 0x59B, ALL_FLAGS, 0x7AF, ALL_FLAGS, 0x7DF],
    "field_flags": [ALL_FLAGS, 0x7DF, ALL_FLAGS, 0x575, ALL_FLAGS, 0x7AF, ALL_FLAGS, 0x59B,
                    ALL_FLAGS, ALL_FLAGS],
    "records_low": 10,
    "records_high": 14,
    "probe_records": 6,
    "load_low": 20,
    "load_high": 140,
    "day_low": 8,
    "day_high": 210,
    "seed": CHALLENGE_SEED,
}


def spec_tables(spec):
    clients = [
        {
            "client_id": row[0],
            "alias_key": row[1],
            "display_name": row[2],
            "site": row[3],
            "service_class": row[4],
            "budget_cap_micros": row[5],
            "merged_into": row[6],
            "retired_on": row[7],
            "effective_from": row[8],
        }
        for row in spec["clients"]
    ]
    programs = [
        {
            "program_id": row[0],
            "revision": row[1],
            "effective_from": row[2],
            "effective_to": row[3],
            "family": row[4],
        }
        for row in spec["programs"]
    ]
    lanes = [
        {
            "lane_id": row[0],
            "site": row[1],
            "class_lock": row[2],
            "exclusive_client": row[3],
            "slot_capacity": row[4],
            "rate_micros": row[5],
        }
        for row in spec["lanes"]
    ]
    sites = [
        {
            "name": row[0],
            "region": row[1],
            "capacity_slots": row[2],
            "penalty_rate_micros": row[3],
        }
        for row in spec["sites"]
    ]
    return clients, programs, lanes, sites


def logical_values(spec, rng, plan, alias_count, program_count, probe):
    hidden = spec["hidden"]
    flags = plan["flags"]
    rows = []
    for ordinal in range(plan["stored_count"]):
        gran_code = rng.below(4)
        granularity = GRANULARITY[gran_code]
        if probe:
            load = granularity * rng.between(3, 18)
        else:
            load = rng.between(spec["load_low"], spec["load_high"])
        extended = rng.below(3) == 0
        alias_index = rng.below(alias_count)
        row = {
            "ordinal": ordinal,
            "filler": ordinal >= plan["true_count"],
            "mode": rng.below(4),
            "extended": extended,
            "alias_index": alias_index,
            "program_index": rng.below(program_count),
            "backref": False,
            "back": 0,
            "load": load,
            "due_off": rng.between(0, 120),
            "weight": rng.between(1, 999),
            "gran_code": gran_code,
            "day": rng.between(spec["day_low"], spec["day_high"]),
            "slack_ext": rng.between(0, 40) if extended else 0,
        }
        if flags & FLAG_BACKREF and ordinal >= 4 and rng.below(2) == 0:
            row["backref"] = True
            row["back"] = rng.between(1, min(hidden["window_span"], ordinal))
        rows.append(row)
    return rows


def encode_block(spec, rng, plan, rows, state, alias_count, program_count):
    hidden = spec["hidden"]
    flags = plan["flags"]
    encoded = []
    previous_due = hidden["chain_seed"] if flags & FLAG_SLACK_FOLD else 0
    weights = []

    for row in rows:
        ordinal = row["ordinal"]
        len_code = 1 if row["extended"] else 0
        nibble = len_code ^ (hidden["shadow_bias"] if flags & FLAG_SHADOW_LEN else 0)
        ctrl = ((nibble & 0x0F) << 4) | row["mode"]

        stored_load = row["load"]
        if flags & FLAG_LANE_MASK:
            mask = keystream(hidden["stream_label"], plan["block_id"], ordinal, 4)
            stored_load ^= int.from_bytes(mask, "big")

        if flags & FLAG_SLACK_FOLD:
            stored_due = (row["due_off"] + previous_due) & 0xFFFF
            previous_due = row["due_off"]
        else:
            stored_due = row["due_off"]

        weight = row["weight"]
        if flags & FLAG_DELTA2:
            position = ordinal % hidden["delta_span"]
            if position == 0:
                stored_weight = weight
            elif position == 1:
                stored_weight = (weight - weights[-1]) & 0xFFFF
            else:
                stored_weight = (weight - 2 * weights[-1] + weights[-2]) & 0xFFFF
        else:
            stored_weight = weight
        weights.append(weight)

        day = row["day"]
        if flags & FLAG_KEY_DRIFT:
            factor = 1 + (state["load_sum"] % (hidden["drift_modulus"] - 1))
            stored_day = (day * factor) % DAY_MODULUS
        else:
            stored_day = day

        wanted_alias = row["alias_index"]
        if flags & FLAG_ALIAS_ROTOR:
            wanted_alias = (wanted_alias + hidden["alias_rotor"]) % alias_count
        spread = rng.below(max(1, (240 - wanted_alias) // alias_count))
        alias_byte = wanted_alias + alias_count * spread

        if row["backref"]:
            span = hidden["window_span"]
            reach = rng.below(((15 - (row["back"] - 1)) // span) + 1)
            program_byte = 0xF0 + (row["back"] - 1) + span * reach
        else:
            limit = max(1, (0xEF - row["program_index"]) // program_count)
            program_byte = row["program_index"] + program_count * rng.below(limit)

        blob = bytearray()
        blob.append(ctrl & 0xFF)
        blob.append(alias_byte & 0xFF)
        blob.append(program_byte & 0xFF)
        blob += struct.pack(">I", stored_load & 0xFFFFFFFF)
        blob += struct.pack(">H", stored_due & 0xFFFF)
        blob += struct.pack(">H", stored_weight & 0xFFFF)
        blob.append(row["gran_code"] & 0xFF)
        blob.append(stored_day & 0xFF)
        if row["extended"]:
            blob += struct.pack(">H", row["slack_ext"] & 0xFFFF)
        encoded.append(bytes(blob))

        if not row["filler"]:
            state["load_sum"] += row["load"]

    if flags & FLAG_PERMUTE:
        seed = block_seed(plan["block_id"], plan["lane_hint"], plan["horizon_slot"],
                          plan["span_hint"], plan["seed_hint"])
        order = build_permutation(len(encoded), hidden["permute_rounds"], seed)
        physical = [encoded[ordinal] for ordinal in order]
    else:
        physical = list(encoded)

    payload = b"".join(physical)
    if flags & FLAG_ROTATE and payload:
        amount = (plan["block_id"] * hidden["rotate_step"]) % len(payload)
    else:
        amount = 0
    wire = rotate_left(payload, amount)

    header = bytearray(HEADER_LEN)
    struct.pack_into(">H", header, 0, MAGIC)
    struct.pack_into(">H", header, 2, plan["block_id"])
    struct.pack_into(">H", header, 4, plan["stored_count"])
    struct.pack_into(">H", header, 6, flags)
    aux = {8: plan["lane_hint"], 10: plan["horizon_slot"],
           12: plan["span_hint"], 14: plan["seed_hint"]}
    for offset, value in aux.items():
        if flags & FLAG_ENDIAN_ISLAND and offset == hidden["island_offset"]:
            struct.pack_into("<H", header, offset, value)
        else:
            struct.pack_into(">H", header, offset, value)
    struct.pack_into(">I", header, 16, zlib.crc32(wire) & 0xFFFFFFFF)
    struct.pack_into(">I", header, 20, zlib.crc32(bytes(header[:20])) & 0xFFFFFFFF)
    return bytes(header), wire


def build_population(spec, rng, population, count, flag_list, alias_count, program_count,
                     probe=False):
    hidden = spec["hidden"]
    state = {"load_sum": 0}
    headers = []
    payloads = []
    for index in range(count):
        block_id = index + 1
        flags = 0 if probe else flag_list[index % len(flag_list)]
        if probe:
            true_count = spec["probe_records"]
        else:
            true_count = rng.between(spec["records_low"], spec["records_high"])
        bias = hidden["count_bias"] if flags & FLAG_COUNT_BIAS else 0
        plan = {
            "block_id": block_id,
            "flags": flags,
            "true_count": true_count,
            "stored_count": true_count + bias,
            "lane_hint": rng.between(1, 4000),
            "horizon_slot": rng.between(160, 320),
            "span_hint": rng.between(1, 4000),
            "seed_hint": rng.between(1, 4000),
        }
        for key in ("lane_hint", "horizon_slot", "span_hint", "seed_hint"):
            while (plan[key] >> 8) == (plan[key] & 0xFF):
                plan[key] = rng.between(1, 4000)
        rows = logical_values(spec, rng, plan, alias_count, program_count, probe)
        header, wire = encode_block(spec, rng, plan, rows, state, alias_count, program_count)
        headers.append((population, block_id, header.hex()))
        payloads.append((block_id, wire.hex()))
    return headers, payloads


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_text(path, body):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body.rstrip("\n") + "\n")


# ---------------------------------------------------------------------------
# shipped specification bodies
# ---------------------------------------------------------------------------

PACKET_ENCODING = """# Work order packet encoding

The dispatch authority receives work orders as binary packets. Three populations
travel over the same wire: a calibration population that the authority has already
settled and published control figures for, a field population that awaits
settlement, and a reference probe that the authority publishes untransformed
alongside its decoded values.

Every population is presented as block headers and block payloads. A payload holds
all of the records of one block concatenated end to end with no separators and no
padding. The tables that carry the headers, the payloads and the directories are
UTF-8 comma separated text with one header row, and spaces around a header name or
a cell are not part of it. A table may begin with a UTF-8 byte order mark. Numeric
block identifiers may carry leading zeroes and are compared by numeric value.

## Block header

A block header is twenty four bytes. Multi byte header words are big endian unless
the byte order transform below applies.

| Offset | Width | Meaning |
| --- | --- | --- |
| 0 | 2 | magic word, always 0x4C44 |
| 2 | 2 | block identifier |
| 4 | 2 | stored record count |
| 6 | 2 | transform flag word |
| 8 | 2 | lane hint |
| 10 | 2 | horizon slot |
| 12 | 2 | span hint |
| 14 | 2 | seed hint |
| 16 | 4 | payload checksum, CRC32 of the payload exactly as it travels |
| 20 | 4 | header checksum, CRC32 of header bytes 0 through 19 |

## Work order record

A record is thirteen bytes, or fifteen bytes when it carries the extended slack
field. Multi byte record fields are big endian.

| Offset | Width | Meaning |
| --- | --- | --- |
| 0 | 1 | control byte: the high nibble is the length code, the low nibble is the dispatch mode |
| 1 | 1 | alias index byte |
| 2 | 1 | programme reference byte |
| 3 | 4 | load units |
| 7 | 2 | due offset |
| 9 | 2 | dispatch weight |
| 11 | 1 | granularity code |
| 12 | 1 | submission day |
| 13 | 2 | extended slack, present only when the length code is one |

A length code of zero means a thirteen byte record. A length code of one means a
fifteen byte record. The dispatch mode is a value between zero and three. The
granularity code selects a granularity from the list 5, 10, 25, 50 by position.
The submission day is a value below 251.

The alias index byte selects an entry of the client directory: reduce it modulo the
number of directory entries and take the entry at that position in file order. The
programme reference byte selects an entry of the ascending list of distinct
programme identifiers in the same way, except that a value of 0xF0 or above is a
backward reference to an earlier record in the same block rather than a programme
selection, and the referring record inherits the programme of the record it points
at.

The due slot of a record is the horizon slot of its block plus the due offset plus
the extended slack. The remaining slack of a work order is its due slot minus its
submission day.

## Transform flag word

The flag word declares which wire transforms are live for that block. Each
transform is governed by a constant that the authority withholds. The published
control figures are the only place those constants are observable.

| Bit | Name | Withheld constant | Constant range |
| --- | --- | --- | --- |
| 0x001 | load mask | stream label | arc, beam, cinder, drift, ember |
| 0x002 | slack fold | chain seed | 0 through 255 |
| 0x004 | weight difference | delta span | 2 through 9 |
| 0x008 | day drift | drift modulus | 97, 101, 103, 107, 109 |
| 0x010 | block permutation | permute rounds | 1 through 4 |
| 0x020 | backward reference | window span | 2 through 8 |
| 0x040 | byte order island | island offset | 8, 10, 12, 14 |
| 0x080 | length shadow | shadow bias | 0 through 15 |
| 0x100 | alias rotor | alias rotor | 1 through 7 |
| 0x200 | payload rotation | rotate step | 1 through 7 |
| 0x400 | count bias | count bias | 0 through 7 |

Bits at 0x800 and above are reserved and are always clear.

## Transform semantics

- Load mask. The load units field travels exclusively ored with the first four
  bytes of HMAC-SHA256 over the key `meridian-corridor-authority` and the message
  formed by the stream label in UTF-8, a vertical bar, the block identifier as a
  big endian sixteen bit word, and the logical ordinal as a big endian sixteen bit
  word.
- Slack fold. The due offset field travels as the sum modulo 65536 of its own value
  and the due offset of the record one logical ordinal earlier. At the first
  logical ordinal of a block the earlier value is the chain seed.
- Weight difference. Dispatch weights travel as second order differences modulo
  65536 within groups of consecutive logical ordinals. A group holds delta span
  ordinals and the first group starts at logical ordinal zero. The first ordinal of
  a group carries its weight, the second carries the difference from the first, and
  every later ordinal carries the difference of differences.
- Day drift. The submission day travels as its own value multiplied by a drifting
  factor modulo 251. The factor is one plus the running sum of the load units of
  every genuine record decoded so far in that population, taken modulo one less
  than the drift modulus. The running sum starts at zero for each population and
  carries across block boundaries.
- Block permutation. Records travel in a permuted order. The permutation is a
  Fisher-Yates shuffle of the stored record count, applied repeatedly for permute
  rounds passes, walking indices downward from the last to the second and swapping
  each with an index drawn as the shuffle state modulo one plus the current index.
  The shuffle state starts at the block seed and advances by xorshift64 before each
  draw, where xorshift64 shifts left by 13, right by 7 and left by 17 within
  sixty four bits. The block seed is the first eight bytes, big endian, of
  HMAC-SHA256 over the key `meridian-corridor-authority` and the message formed by the
  ASCII text `block|` followed by the block identifier, lane hint, horizon slot,
  span hint and seed hint as five big endian sixteen bit words. The value at
  physical position p of the permutation is the logical ordinal of the record that
  travels at that position.
- Backward reference. A programme reference byte of 0xF0 or above names a record
  earlier in logical order. Subtract 0xF0, reduce modulo the window span, and add
  one to obtain how many logical ordinals back the referenced record sits.
- Byte order island. Exactly one of the four auxiliary header words at offsets 8,
  10, 12 and 14 travels little endian. The island offset names which one.
- Length shadow. The length code nibble travels exclusively ored with the shadow
  bias.
- Alias rotor. The alias index byte travels with the alias rotor added to the
  directory position modulo the number of directory entries.
- Payload rotation. The payload travels rotated left by the block identifier
  multiplied by the rotate step, reduced modulo the payload length. The payload
  checksum is taken over the payload exactly as it travels.
- Count bias. The stored record count exceeds the genuine record count by the count
  bias. The surplus records occupy the last logical ordinals of the block, are
  filler, and are no part of the settled population.

The reference probe carries a clear flag word in every block and is published
together with its decoded values.
"""

IDENTITY_POLICY = """# Client identity

Work orders name a client by alias key. The client directory lists one row per
client with its alias key, its home site, its service class, its budget ceiling in
micro units, an optional merge target, an optional retirement day and the first day
on which the client may hold work.

- An alias key names exactly one directory row.
- A row that carries a merge target has been absorbed by the row it names. Work
  that arrives under the absorbed alias belongs to the absorbing client. Merge
  targets chain, and the chain is followed to its end.
- Where a chain of merge targets closes on itself, the client whose identifier
  sorts first among every identifier visited from the starting alias, including
  any lead-in before the repeated identifier, governs the work.
- A client that carries a retirement day holds no work on that day or after it.
  Work that arrives on or after the retirement day of its governing client is
  rejected and settles nowhere.
- A client whose first active day is later than the submission day of the work is
  unable to accept it. Such work is deferred rather than rejected. Apply these
  status checks in order: retirement, revision-gap rejection, then not-yet-active
  deferral; a rejection or deferral ends processing for that order.
- The home site and service class of a work order are those of its governing
  client, never those of the alias it arrived under.
"""

REVISION_POLICY = """# Programme revisions

The programme registry lists one row per revision of a programme. Each row carries
the programme identifier, the revision number, the first day on which the revision
takes effect, the first day on which it stops taking effect, and the process family
the revision belongs to.

- A revision governs a submission day when the day sits at or after the first day
  of effect and strictly before the day the revision stops taking effect.
- A programme may carry days that no revision governs. Work whose submission day
  falls in such a gap is rejected and settles nowhere.
- The process family of a work order is the family of the revision that governs it,
  which may differ between two orders naming the same programme.
"""

CAPACITY_POLICY = """# Site capacity and admission

Each site publishes a slot capacity. Admission of work to a site is governed by the
congestion the site is under, and the congestion a site is under is governed by the
work admitted to it. Exactly one congestion assignment over the four sites is
stable under the rules below, and the settled schedule is the one that assignment
produces.

- The congestion index of a site is one thousand multiplied by the billable slots
  admitted at that site, divided by the slot capacity of the site, taken as whole
  units with the remainder discarded.
- congestion_bounds: @@TIER_BOUNDS@@
- A congestion index below the first bound places the site in tier zero, below the
  second bound in tier one, below the third bound in tier two, and otherwise in
  tier three.
- A pass is one offering of the whole admission order at the tiers standing when
  that offering begins. The first pass is offered with every site at tier zero.
  The settlement is complete on the first pass that leaves every tier where it
  found it, and that confirming pass is counted along with the passes that moved
  a tier.
- base_ceiling: @@BASE_CEILING@@
- tier_factor: @@TIER_FACTOR@@
- The admission ceiling of a client is the base ceiling of its service class
  multiplied by the tier factor of the tier its home site sits in, divided by one
  hundred, taken as whole units with the remainder discarded.
- Work is offered for admission in descending order of dispatch weight.
- An order whose billable slots would carry the running admitted total of its
  governing client past that client admission ceiling is held back. A held order is
  deferred, keeps its place in no lane, and settles no value.
- The billable slots of an order are its load units brought to a whole multiple of
  the granularity the record declares. The authority withholds which of the four
  quantisation modes it applies: discard the remainder, advance to the next
  multiple, take the closer multiple with the midpoint advancing, or discard the
  remainder unless the remainder reaches three quarters of the granularity.
- Report mode labels are `floor`, `ceil`, `nearest`, and `band`, in that order.
"""

DISPATCH_POLICY = """# Lane dispatch

Every admitted work order occupies exactly one lane at the home site of its
governing client. The lane roster lists one row per lane with its site, an optional
class lock, an optional exclusive client, a slot capacity and a rate in micro units
per billable slot.

- A lane that declares a class lock accepts work of that service class alone.
- A lane that names an exclusive client accepts work of that client alone.
- The billable slots resting on a lane may reach the slot capacity of that lane and
  may go no further.
- incompatible_families: @@FAMILY_CONFLICTS@@
- Two orders whose governing revisions belong to an incompatible pair of process
  families share no lane.
- Every site holds one lane that declares no class lock, names no exclusive client
  and publishes a slot capacity of zero. That lane is relief capacity: it accepts
  any quantity of work of any class from any client at the penalty rate its site
  publishes, and the incompatible family rule is no bar to it.
- The schedule the authority settles is the one whose total of billable slots
  multiplied by lane rate, summed over every admitted order at a site, is smallest.
- Eligible lanes are ordered by rate ascending and then lane identifier ascending.
  Among schedules with the same minimum cost, compare lane identifiers in the
  contention order of the orders and keep the lexicographically first sequence.
  Zero-slot work follows this rule too, so it takes the first compatible lane.

## Contention

Where two admitted orders contend for the last slots of the cheapest lane both are
eligible for, the order carrying the LARGER remaining slack keeps the lane and the
order carrying the tighter remaining slack yields. This is the settled practice of
this authority and it reverses the habit of favouring the tighter deadline: an
order with room to spare is the one that holds cheap capacity here, and the urgent
order is the one that moves. Where remaining slack is equal, the order whose
identifier sorts first keeps the lane.
"""

COST_POLICY = """# Settlement value

- The charge of a placed order is its billable slots multiplied by the rate of the
  lane it rests on.
- rebate_band: @@REBATE_BAND@@
- The rebate of a placed order is its billable slots multiplied by the rebate its
  dispatch mode earns.
- The net value of a placed order is its charge less its rebate.
- Each client publishes a budget ceiling in micro units. Net value accumulates
  against that ceiling across the orders of the client taken in ascending order of
  identifier. Where an order would carry the running total past the ceiling, the
  part that would pass the ceiling is recorded as capped value and the order
  settles the remainder.
- Every monetary figure is a whole number of micro units and stays a whole number
  at every step.
"""

GLOBAL_INVARIANTS = """# Global invariants

The settled schedule satisfies all of the following at once.

- Conservation. The net value of the settled schedule equals the sum of the net
  value reported for the four regions and equals the sum of the net value reported
  for the two service classes. Both residuals are zero.
- Partition closure. Every placed order appears in exactly one region report and in
  exactly one service class report, and the two partitions cover the same set of
  orders. The region of an order is the region the site directory gives for the home
  site of its governing client.
- Identity uniqueness. No order identifier appears twice in the settled schedule.
- Capacity. No lane that publishes a positive slot capacity carries billable slots
  beyond it.
- Referential closure. Every placed order names a lane on the roster, a client in
  the directory and a programme revision in the registry.
- Idempotence. Settling the same population twice yields the same schedule byte for
  byte.
- Population separation. The calibration population is settled under the same rules
  as the field population and appears in no region report and in no service class
  report.
"""

REPORT_SCHEMA = """# Settlement report schema

This document fixes the names and the value types of every field the settlement
reports carry. It fixes no value: every number and every identifier below is yours
to derive from the corpus you are given. Where a field's meaning depends on a rule,
the rule lives in the policy document named beside it.

Every monetary field is a whole number of micro units. Every count is a whole
number. Region rollups and service segment rollups share one shape, given by the
worked probe rollup that ships with the corpus.

## summary.json

One object with exactly these twelve fields.

- order_rows: the count of genuine work order records in the field population, once
  filler has been discarded (packet_encoding.md, count bias).
- decoded_rows: the count of records decoded from the field population before filler
  is discarded.
- orders_scored: the count of field orders that reach admission, meaning those
  neither rejected nor deferred by the identity and revision policies.
- orders_placed: the count of field orders that end up resting on a lane.
- orders_deferred: the count of field orders that settle nowhere but are not
  rejected. This is one figure covering both deferral routes together: work whose
  governing client is not yet active (identity_policy.md) and work held back by a
  client admission ceiling (capacity_policy.md).
- orders_rejected: the count of field orders rejected outright, meaning work on or
  after its governing client's retirement day (identity_policy.md) and work whose
  submission day no revision governs (revision_policy.md).
- billable_slots_total: the sum of billable slots over the placed orders.
- charge_micros_total: the sum of charges over the placed orders (cost_policy.md).
- rebate_micros_total: the sum of rebates over the placed orders.
- capped_micros_total: the sum of capped value over the placed orders.
- net_micros_total: the sum of net value over the placed orders.
- lanes_used: the count of distinct lanes carrying at least one placed order.

## data_quality.json

One object with exactly these ten fields.

- order_rows: as in summary.json.
- decoded_rows: as in summary.json.
- rejected_orders: an array of the rejected order identifiers, ascending.
- deferred_orders: an array of the deferred order identifiers, ascending, covering
  both deferral routes exactly as orders_deferred does.
- region_net_micros: an object keyed by the four region names as they appear in your
  region rollup file names, each holding that region's net value.
- segment_net_micros: an object keyed by the two service class names as they appear
  in your segment rollup file names, each holding that segment's net value.
- conservation_residual_micros: the net value of the schedule less the sum of the
  four region net values (global_invariants.md, conservation).
- segment_residual_micros: the net value of the schedule less the sum of the two
  segment net values.
- calibration_net_micros: the net value of the calibration population, settled under
  the same rules as the field population. It appears in no rollup.
- invariants: an object holding exactly these four booleans, one verdict per
  invariant named in global_invariants.md: region_partition_closed,
  segment_partition_closed, order_identity_unique, capacity_respected.

## Region and segment rollups

Each rollup carries order_count, orders, totals, and one discriminator field naming
what the rollup covers. A region rollup's discriminator field is called region. A
segment rollup's discriminator field is called service_class, and its value is the
service class as the client directory spells it. Everything else matches the worked
probe rollup: the per-order fields and the totals fields are the same in both kinds.
The orders array runs in ascending order of order identifier.

## policy_audit.json

One object with exactly these six fields. This file records the derivation, not the
settlement.

- candidate_space: an array with one entry per withheld constant, in the order the
  constants resolve. Each entry carries parameter (the constant's name as listed
  under resolved_parameters), control (the published control figure that resolves
  it, spelled as calibration_slice.md spells it), domain_size (the count of
  candidate values in that constant's declared range), resolved (the value you
  settled on), rejected (the count of candidate values you ruled out) and verdicts
  (an array holding one entry per candidate value in that constant's declared
  range, each carrying value, the candidate you tried, and verdict, the string
  "accepted" or "rejected"). The control that resolves a constant is the control
  that eliminated every candidate the entry rejects, so the entry names it once.
- resolved_parameters: an object holding your settled value for each of the twelve
  withheld constants, keyed exactly: rotate_step, shadow_bias, count_bias,
  island_offset, permute_rounds, stream_label, chain_seed, delta_span,
  drift_modulus, alias_rotor, window_span, quant_mode. The stream label and the
  quantisation mode are strings; the other ten are whole numbers.
- calibration_comparison: an array with one entry per published control figure, each
  carrying control (its name), published (the figure as published) and reproduced
  (the figure your settled constants reproduce).
- fixpoint: an object carrying passes (the count of admission passes, counted as
  capacity_policy.md counts them), congestion_index and congestion_tier, each an
  object keyed by the four site names as the site directory spells them.
- assignment_search: an object carrying sites_searched, feasible_leaves (a count
  describing the extent of your own search), displaced_orders (the count of admitted
  orders that end up on relief capacity) and site_cost_micros, an object keyed by
  site name holding each site's settled lane cost.
- candidates_examined and candidates_rejected: the totals across all twelve
  constants of the candidate values you examined and of those you ruled out.
"""


CALIBRATION_HEAD = """# Calibration slice

The calibration population is held out. It is settled under the same rules as the
field population and it appears in no region report and in no service class report.

The authority has already settled this population with the withheld packet
constants in place and publishes the control figures below. Exactly one assignment
of the withheld constants reproduces every figure at once.

## Control figures
"""

CALIBRATION_TAIL = """
Each figure is an exact whole number. A constant assignment that reproduces a
figure is separated from one that does not by that figure alone, once every figure
above it in this list has been settled.
"""

CONTROL_NOTES = {
    "payload_origin_total":
        "the sum, across the calibration blocks, of the first four bytes of each "
        "block payload read as one big endian word once that payload sits at its "
        "true origin",
    "record_span_total":
        "the count, across the calibration blocks, of records that carry the "
        "extended slack field",
    "calibration_order_total":
        "the count of genuine records across the calibration blocks once filler "
        "has been discarded",
    "island_field_total":
        "the sum, across the calibration blocks, of the four auxiliary header "
        "words read in their intended byte order",
    "ordinal_position_checksum":
        "the sum, across the calibration blocks, over every physical record "
        "position of one plus that position multiplied by one plus the logical "
        "ordinal that travels there",
    "masked_load_total":
        "the sum of load units over every genuine calibration record",
    "folded_slack_total":
        "the sum of due offsets over every genuine calibration record",
    "delta_weight_total":
        "the sum of dispatch weights over every genuine calibration record",
    "drift_day_total":
        "the sum over every genuine calibration record of its submission day "
        "multiplied by one plus its logical ordinal",
    "canonical_client_total":
        "the sum over every genuine calibration record of the numeric part of the "
        "identifier of its governing client multiplied by one plus its logical "
        "ordinal",
    "backref_program_total":
        "the sum over every genuine calibration record of the position of its "
        "programme within the ascending list of distinct programme identifiers "
        "multiplied by one plus its logical ordinal",
    "billable_slot_total":
        "the sum of billable slots over every calibration record that carries a "
        "governing programme revision and a client able to hold it",
}


def calibration_doc(controls):
    lines = [CALIBRATION_HEAD]
    for name in CONTROL_ORDER:
        lines.append("- %s = %d" % (name, controls[name]))
        lines.append("<!-- %s -->" % CONTROL_NOTES[name])
    lines.append(CALIBRATION_TAIL)
    return "\n".join(lines)


def render(body, spec):
    pairs = ", ".join("%s=%s" % (key, spec["base_ceiling"][key])
                      for key in sorted(spec["base_ceiling"]))
    factors = ", ".join("%s=%s" % (key, spec["tier_factor"][key])
                        for key in sorted(spec["tier_factor"]))
    rebates = ", ".join("%s=%s" % (key, spec["rebate_band"][key])
                        for key in sorted(spec["rebate_band"]))
    families = ", ".join("%s|%s" % (left, right) for left, right in spec["family_conflicts"])
    bounds = ", ".join(str(value) for value in spec["tier_bounds"])
    body = body.replace("@@TIER_BOUNDS@@", bounds)
    body = body.replace("@@BASE_CEILING@@", pairs)
    body = body.replace("@@TIER_FACTOR@@", factors)
    body = body.replace("@@REBATE_BAND@@", rebates)
    body = body.replace("@@FAMILY_CONFLICTS@@", families)
    return body


def generate(spec, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    clients, programs, lanes, sites = spec_tables(spec)
    alias_count = len(clients)
    program_count = len({row["program_id"] for row in programs})

    field_rng = Rng(spec["seed"])
    calibration_headers, calibration_payloads = build_population(
        spec, field_rng, "calibration", spec["calibration_blocks"],
        spec["calibration_flags"], alias_count, program_count)
    field_headers, field_payloads = build_population(
        spec, field_rng, "field", spec["field_blocks"],
        spec["field_flags"], alias_count, program_count)
    probe_rng = Rng(SAMPLE_SEED)
    probe_headers, probe_payloads = build_population(
        spec, probe_rng, "probe", spec["probe_blocks"], [0],
        alias_count, program_count, probe=True)

    for _, _, header_hex in probe_headers:
        if u16(bytes.fromhex(header_hex), 6) != 0:
            raise DecodeError("a reference probe block enabled a transform flag")

    def path(name):
        return os.path.join(out_dir, name)

    write_csv(path("client_directory.csv"),
              ["client_id", "alias_key", "display_name", "site", "service_class",
               "budget_cap_micros", "merged_into", "retired_on", "effective_from"],
              clients)
    write_csv(path("program_registry.csv"),
              ["program_id", "revision", "effective_from", "effective_to", "family"],
              programs)
    write_csv(path("lane_roster.csv"),
              ["lane_id", "site", "class_lock", "exclusive_client", "slot_capacity",
               "rate_micros"], lanes)
    write_csv(path("site_directory.csv"),
              ["name", "region", "capacity_slots", "penalty_rate_micros"], sites)
    write_csv(path("block_manifest.csv"), ["population", "block_id", "header_hex"],
              [{"population": population, "block_id": block_id, "header_hex": header_hex}
               for population, block_id, header_hex in
               calibration_headers + field_headers + probe_headers])
    for name, rows in (("calibration_orders.csv", calibration_payloads),
                       ("field_orders.csv", field_payloads),
                       ("reference_probe.csv", probe_payloads)):
        write_csv(path(name), ["block_id", "payload_hex"],
                  [{"block_id": block_id, "payload_hex": payload_hex}
                   for block_id, payload_hex in rows])

    write_text(path("packet_encoding.md"), render(PACKET_ENCODING, spec))
    write_text(path("identity_policy.md"), render(IDENTITY_POLICY, spec))
    write_text(path("revision_policy.md"), render(REVISION_POLICY, spec))
    write_text(path("capacity_policy.md"), render(CAPACITY_POLICY, spec))
    write_text(path("dispatch_policy.md"), render(DISPATCH_POLICY, spec))
    write_text(path("cost_policy.md"), render(COST_POLICY, spec))
    write_text(path("global_invariants.md"), render(GLOBAL_INVARIANTS, spec))
    write_text(path("report_schema.md"), REPORT_SCHEMA)
    write_text(path("calibration_slice.md"),
               calibration_doc({name: 0 for name in CONTROL_ORDER}))

    corpus = load_corpus(out_dir)
    hidden = dict(spec["hidden"])
    controls = {name: control_value(corpus, name, hidden) for name in CONTROL_ORDER}
    write_text(path("calibration_slice.md"), calibration_doc(controls))

    corpus = load_corpus(out_dir)
    recovered, _ = recover_parameters(corpus)
    for name in PARAMETER_ORDER:
        if recovered[name] != hidden[name]:
            raise DecodeError("control figures fail to pin %s" % name)

    probe = settle_population(corpus, "probe", hidden)
    answers = []
    for record in probe["decoded"]["records"]:
        client = resolve_client(corpus, record["alias_key"])
        answers.append({
            "block_id": record["block_id"],
            "logical_ordinal": record["ordinal"],
            "order_id": record["order_id"],
            "alias_key": record["alias_key"],
            "governing_client": client["client_id"],
            "program_id": record["program_id"],
            "load_units": record["load_units"],
            "due_slot": record["due_slot"],
            "dispatch_weight": record["weight"],
            "granularity": record["granularity"],
            "submitted_day": record["submitted_day"],
            "dispatch_mode": record["dispatch_mode"],
        })
    write_csv(path("reference_probe_answers.csv"),
              ["block_id", "logical_ordinal", "order_id", "alias_key", "governing_client",
               "program_id", "load_units", "due_slot", "dispatch_weight", "granularity",
               "submitted_day", "dispatch_mode"], answers)

    counts = {}
    for row in probe["rows"]:
        counts[row["region"]] = counts.get(row["region"], 0) + 1
    chosen = max(sorted(counts), key=lambda name: counts[name]) if counts else REGIONS[0]
    with open(path("probe_region_example.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(rollup(probe["rows"], "region", chosen), handle, indent=2, sort_keys=True)
        handle.write("\n")

    return controls


# ---------------------------------------------------------------------------
# verification harness
# ---------------------------------------------------------------------------

import copy
import ast
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path

from rewardkit import criteria, criterion

ARTIFACT_DIR = "/app/out"
DRIVER_NAME = "derive_report.py"

REGION_ARTIFACTS = ["region_%s.json" % name for name in REGIONS]
SEGMENT_ARTIFACTS = ["segment_%s.json" % name for name in CLASSES]
VALUE_ARTIFACTS = ["summary.json", "data_quality.json"] + REGION_ARTIFACTS + SEGMENT_ARTIFACTS
ALL_ARTIFACTS = ["policy_audit.json"] + VALUE_ARTIFACTS

ALL_ON = 0x7FF


def _spec(**overrides):
    spec = copy.deepcopy(BASE_SPEC)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(spec.get(key), dict):
            spec[key].update(value)
        else:
            spec[key] = value
    return spec


def _trap_spec(name, value):
    # One withheld constant moves, so the trap still fails exactly when its own
    # inverse is missing. The rebate band moves with it, which is strictly post
    # decode: it changes the settled money without touching decoding, admission or
    # placement. Without it, nine of the twelve trap corpora settle byte identically
    # to the shipped one, and a program that ignores its input and replays the
    # shipped answers passes them.
    spec = _spec(hidden={name: value})
    spec["rebate_band"] = {"0": 0, "1": 6, "2": 11, "3": 18}
    return spec


def _uniform_rates():
    spec = copy.deepcopy(BASE_SPEC)
    for lane in spec["lanes"]:
        if lane[4] > 0:
            lane[5] = 41
    return spec


def _tight_budgets():
    spec = copy.deepcopy(BASE_SPEC)
    for client in spec["clients"]:
        client[5] = int(client[5] * 2 // 5)
    return spec


def _empty_site():
    spec = copy.deepcopy(BASE_SPEC)
    for client in spec["clients"]:
        if client[3] == "Summit":
            client[7] = 1
    return spec


def _merge_cycle():
    spec = copy.deepcopy(BASE_SPEC)
    for client in spec["clients"]:
        if client[0] == "CL-0001":
            client[6] = "CL-0003"
        if client[0] == "CL-0009":
            client[6] = "CL-0011"
    return spec


def _boundary_shift():
    spec = copy.deepcopy(BASE_SPEC)
    moved = {96: 97, 72: 73, 184: 185, 140: 141, 108: 109, 164: 165, 200: 201, 60: 61, 120: 121}
    for revision in spec["programs"]:
        revision[2] = moved.get(revision[2], revision[2])
        revision[3] = moved.get(revision[3], revision[3])
    return spec


def _contention_tie():
    # Widen one constrained lane under ceiling quantisation so contention ordering
    # changes which work keeps ordinary capacity and which work uses relief capacity.
    spec = _trap_spec("quant_mode", "ceil")
    for row in spec["lanes"]:
        if row[0] == "SMT-C":
            row[4] = row[4] + 50
    return spec


def _revision_edges():
    # Two clauses of the revision policy have no falsifying case in any other
    # corpus: no population carries a submission day that lands on one of its
    # programme's boundaries, and no registry ever has two revisions of one
    # programme covering the same day. This corpus supplies both. PG-DEGREASE
    # revision one now stops taking effect on day 90, the submission day of field
    # order W000109, and revision two still starts at 120, so day 90 opens the
    # gap: the half-open reading rejects W000109 and an inclusive reading places
    # it under revision one, which changes the summary census. PG-TEMPER revision
    # one now runs past the start of revision two, so two revisions govern the
    # same day and the higher-numbered one has to win.
    spec = copy.deepcopy(BASE_SPEC)
    for row in spec["programs"]:
        if row[0] == "PG-DEGREASE" and int(row[1]) == 1:
            row[3] = 90
        if row[0] == "PG-TEMPER" and int(row[1]) == 1:
            row[3] = 175
    return spec


def _new_client():
    spec = copy.deepcopy(BASE_SPEC)
    spec["clients"] = spec["clients"] + [
        ["CL-0017", "SX2", "Stonewick Anodise", "Ridge", "public", 34800, "", "", 0],
        ["CL-0018", "TV4", "Thornvale Blasting", "Basin", "commercial", 29040, "", "", 0],
    ]
    return spec


def _lane_squeeze():
    spec = copy.deepcopy(BASE_SPEC)
    for lane in spec["lanes"]:
        if lane[4] > 0:
            lane[4] = lane[4] * 2 // 5
    return spec


def _resite():
    spec = copy.deepcopy(BASE_SPEC)
    swap = {"Basin": "Ridge", "Ridge": "Basin"}
    for client in spec["clients"]:
        client[3] = swap.get(client[3], client[3])
    return spec


def _conflict_pairs():
    spec = copy.deepcopy(BASE_SPEC)
    spec["family_conflicts"] = [["thermal", "inert"], ["abrasive", "solvent"]]
    return spec


# Held-out table-format variants. Each corpus is settled under the trap rebate
# band (so replaying the shipped answers fails it) and then has one file rewritten
# in a form that leaves its meaning unchanged; the reference reads every form.
def _format_spec():
    spec = _spec()
    spec["rebate_band"] = {"0": 0, "1": 6, "2": 11, "3": 18}
    return spec


def _rewrite_table(path, edit_header=None, edit_row=None, bom=False):
    import io
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    header, body = rows[0], rows[1:]
    if edit_row is not None:
        body = [edit_row(dict(zip(header, row)), header) for row in body]
    out = list(edit_header(header)) if edit_header is not None else header
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(out)
    writer.writerows(body)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(("\ufeff" if bom else "") + buffer.getvalue())


def _post_bom(data_dir):
    for name in ("client_directory.csv", "block_manifest.csv"):
        _rewrite_table(os.path.join(data_dir, name), bom=True)


def _post_header_pad(data_dir):
    _rewrite_table(os.path.join(data_dir, "lane_roster.csv"),
                   edit_header=lambda header: [" %s " % name for name in header])


def _post_cell_pad(data_dir):
    def edit(row, header):
        for key in ("alias_key", "site", "service_class"):
            row[key] = " %s " % row[key]
        return [row[name] for name in header]
    _rewrite_table(os.path.join(data_dir, "client_directory.csv"), edit_row=edit)


def _post_zero_pad(data_dir):
    def edit(row, header):
        row["block_id"] = "%03d" % int(row["block_id"])
        return [row[name] for name in header]
    _rewrite_table(os.path.join(data_dir, "field_orders.csv"), edit_row=edit)


def _post_region_case(data_dir):
    def edit(row, header):
        if row["region"].lower() in ("north", "west"):
            row["region"] = row["region"].upper()
        return [row[name] for name in header]
    _rewrite_table(os.path.join(data_dir, "site_directory.csv"), edit_row=edit)


def _post_draft_policy(data_dir):
    draft = _spec(tier_bounds=[220, 470, 690], base_ceiling={"commercial": 150, "public": 120})
    body = render(CAPACITY_POLICY, draft).replace(
        "# Site capacity and admission\n",
        "# Capacity amendment (draft)\n\nThis draft was circulated for comment and was "
        "never adopted. The capacity rules in force are the ones in capacity_policy.md.\n", 1)
    write_text(os.path.join(data_dir, "capacity_amendment_draft.md"), body)


def _post_archived_controls(data_dir):
    published = parse_controls(read_text(os.path.join(data_dir, "calibration_slice.md")))
    stale = {name: published[name] + 3 + index for index, name in enumerate(CONTROL_ORDER)}
    body = calibration_doc(stale).replace(
        "# Calibration slice\n",
        "# Archived calibration slice\n\nThese figures were published for an earlier "
        "season and are withdrawn. The figures in force are the ones in "
        "calibration_slice.md.\n", 1)
    write_text(os.path.join(data_dir, "archived_calibration_slice.md"), body)


FORMAT_POSTS = {
    "fmt_bom": _post_bom,
    "fmt_header_pad": _post_header_pad,
    "fmt_cell_pad": _post_cell_pad,
    "fmt_zero_pad": _post_zero_pad,
    "fmt_region_case": _post_region_case,
    "fmt_draft_policy": _post_draft_policy,
    "fmt_archived_controls": _post_archived_controls,
}


SPARSE_CALIBRATION = [0x603, 0x60C, 0x630, 0x6C0, 0x700, 0x605, 0x60A, 0x650]
SPARSE_FIELD = [0x603, 0x60C, 0x630, 0x6C0, 0x700, 0x605, 0x60A, 0x650, 0x618, 0x660]

FULL_HIDDEN = {
    "rotate_step": 2,
    "shadow_bias": 6,
    "count_bias": 5,
    "island_offset": 10,
    "permute_rounds": 4,
    "stream_label": "ember",
    "chain_seed": 42,
    "delta_span": 3,
    "drift_modulus": 109,
    "alias_rotor": 6,
    "window_span": 8,
    "quant_mode": "ceil",
}

EVAL_HIDDEN = {
    "rotate_step": 7,
    "shadow_bias": 2,
    "count_bias": 1,
    "island_offset": 14,
    "permute_rounds": 2,
    "stream_label": "arc",
    "chain_seed": 91,
    "delta_span": 8,
    "drift_modulus": 97,
    "alias_rotor": 2,
    "window_span": 3,
    "quant_mode": "nearest",
}

VARIANTS = {
    "shipped": BASE_SPEC,
    "fmt_bom": _format_spec(),
    "fmt_header_pad": _format_spec(),
    "fmt_cell_pad": _format_spec(),
    "fmt_zero_pad": _format_spec(),
    "fmt_region_case": _format_spec(),
    "fmt_draft_policy": _format_spec(),
    "fmt_archived_controls": _format_spec(),
    "trap_rotate_step": _trap_spec("rotate_step", 2),
    "trap_shadow_bias": _trap_spec("shadow_bias", 6),
    "trap_count_bias": _trap_spec("count_bias", 5),
    "trap_island_offset": _trap_spec("island_offset", 10),
    "trap_permute_rounds": _trap_spec("permute_rounds", 1),
    "trap_stream_label": _trap_spec("stream_label", "ember"),
    "trap_chain_seed": _trap_spec("chain_seed", 42),
    "trap_delta_span": _trap_spec("delta_span", 3),
    "trap_drift_modulus": _trap_spec("drift_modulus", 109),
    "trap_alias_rotor": _trap_spec("alias_rotor", 6),
    "trap_window_span": _trap_spec("window_span", 8),
    "trap_quant_mode": _trap_spec("quant_mode", "ceil"),
    "mut_hidden_full": _spec(hidden=FULL_HIDDEN),
    "mut_uniform_rates": _uniform_rates(),
    "mut_tight_budgets": _tight_budgets(),
    "mut_tier_bounds": _spec(
        tier_bounds=[220, 470, 690],
        tier_factor={"0": 100, "1": 126, "2": 145, "3": 170},
    ),
    "mut_empty_site": _empty_site(),
    "mut_merge_cycle": _merge_cycle(),
    "mut_boundary_shift": _boundary_shift(),
    "mut_revision_edges": _revision_edges(),
    "mut_contention_tie": _contention_tie(),
    "mut_new_client": _new_client(),
    "mut_lane_squeeze": _lane_squeeze(),
    "mut_slack_flip": _spec(day_low=118, day_high=244),
    "mut_resite": _resite(),
    "mut_scale": _spec(
        field_blocks=22,
        calibration_blocks=12,
        records_low=15,
        records_high=19,
        base_ceiling={"commercial": 95, "public": 80},
        calibration_flags=[ALL_ON, ALL_ON, 0x575, 0x59B, ALL_ON, 0x7AF, ALL_ON, 0x7DF,
                           ALL_ON, 0x6F7, ALL_ON, 0x7EB],
        field_flags=[ALL_ON, 0x7DF, ALL_ON, 0x575, ALL_ON, 0x7AF, ALL_ON, 0x59B,
                     ALL_ON, ALL_ON, 0x6F7, ALL_ON, 0x7EB, ALL_ON, 0x77F, ALL_ON,
                     0x7F7, ALL_ON, 0x5FB, ALL_ON, 0x7BF, ALL_ON],
    ),
    "mut_conflict_pairs": _conflict_pairs(),
    "mut_flags_sparse": _spec(
        calibration_flags=SPARSE_CALIBRATION,
        field_flags=SPARSE_FIELD,
    ),
    "mut_eval_seed": _spec(seed=EVAL_SEED, hidden=EVAL_HIDDEN),
    "mut_short_blocks": _spec(
        records_low=7,
        records_high=9,
        calibration_blocks=16,
        field_blocks=17,
        calibration_flags=[ALL_ON, ALL_ON, 0x575, 0x59B, ALL_ON, 0x7AF, ALL_ON, 0x7DF,
                           ALL_ON, 0x6F7, ALL_ON, 0x7EB, ALL_ON, 0x77F, ALL_ON, 0x5FB],
        field_flags=[ALL_ON, 0x7DF, ALL_ON, 0x575, ALL_ON, 0x7AF, ALL_ON, 0x59B,
                     ALL_ON, ALL_ON, 0x6F7, ALL_ON, 0x7EB, ALL_ON, 0x77F, ALL_ON, 0x5FB],
    ),
}

_CACHE = {}
_RUNS = {}


def _payloads(result):
    payload = {
        "summary.json": result["summary"],
        "policy_audit.json": result["policy_audit"],
        "data_quality.json": result["data_quality"],
    }
    for name in REGIONS:
        payload["region_%s.json" % name] = result["regions"][name]
    for name in CLASSES:
        payload["segment_%s.json" % name] = result["segments"][name]
    return payload


def _materialise(name):
    if name in _CACHE:
        return _CACHE[name]
    if name not in VARIANTS:
        raise AssertionError("unknown corpus variant %s" % name)
    root = tempfile.mkdtemp(prefix="lane-%s-" % name)
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    generate(VARIANTS[name], data_dir)
    if name in FORMAT_POSTS:
        FORMAT_POSTS[name](data_dir)
    expected = _payloads(derive(data_dir))
    _CACHE[name] = (data_dir, expected)
    return _CACHE[name]


def _driver_path():
    path = os.path.join(ARTIFACT_DIR, DRIVER_NAME)
    if not os.path.isfile(path):
        raise AssertionError("the reusable dispatch program is missing from %s" % ARTIFACT_DIR)
    if os.path.getsize(path) == 0:
        raise AssertionError("the reusable dispatch program is empty")
    return path


def _driver_source():
    with open(_driver_path(), "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _as_root():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _invoke(data_dir, out_dir):
    driver = _driver_path()
    os.makedirs(out_dir, exist_ok=True)
    # Run a private copy of the delivered program (and any sibling modules) from a
    # fresh 0755 directory as 0644 files, so the delivered files' own modes (for
    # example 0600) never decide whether the unprivileged run can read them.
    program_dir = tempfile.mkdtemp(prefix="lane-prog-")
    source_dir = os.path.dirname(driver)
    for name in sorted(os.listdir(source_dir)):
        if name.endswith(".py") and os.path.isfile(os.path.join(source_dir, name)):
            shutil.copyfile(os.path.join(source_dir, name), os.path.join(program_dir, name))
            os.chmod(os.path.join(program_dir, name), 0o644)
    os.chmod(program_dir, 0o755)
    program = os.path.join(program_dir, DRIVER_NAME)
    command = [sys.executable, program, data_dir, out_dir]
    if _as_root():
        for folder, dirs, files in os.walk(os.path.dirname(data_dir)):
            os.chmod(folder, 0o755)
            for name in files:
                os.chmod(os.path.join(folder, name), 0o644)
        os.chmod(out_dir, 0o777)
        command = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"] + command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=900)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, code = "", "the delivered program exceeded 900 s", -9
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            proc.kill()
        except OSError:
            pass
        proc.communicate()
    # A program that overruns the 900 s budget is an agent failure: it returns a
    # failed process here, so every check that needed it scores False rather than
    # aborting the whole grading run.
    return subprocess.CompletedProcess(command, code, stdout, stderr)


def _run_driver(name):
    if name in _RUNS:
        return _RUNS[name]
    data_dir, expected = _materialise(name)
    out_dir = tempfile.mkdtemp(prefix="lane-out-%s-" % name)
    proc = _invoke(data_dir, out_dir)
    produced = {}
    for artifact in ALL_ARTIFACTS:
        path = os.path.join(out_dir, artifact)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    produced[artifact] = json.load(handle)
            except Exception:
                produced[artifact] = None
    _RUNS[name] = (proc, produced, expected)
    return _RUNS[name]


def _delivered():
    payload = {}
    for artifact in ALL_ARTIFACTS:
        path = os.path.join(ARTIFACT_DIR, artifact)
        if not os.path.isfile(path):
            raise AssertionError("deliverable %s is missing" % artifact)
        if os.path.getsize(path) == 0:
            raise AssertionError("deliverable %s is empty" % artifact)
        with open(path, "r", encoding="utf-8") as handle:
            payload[artifact] = json.load(handle)
    return payload


def _shipped_expected():
    # Ground truth is regenerated inside this module, never read back from the
    # corpus mount: that mount belongs to the agent image and does not exist in
    # the verifier, and an expectation must never come from an agent-writable path.
    return _materialise("shipped")[1]


def _delivered_code():
    """The delivered program with comments and docstrings removed.

    Source-text detectors must read executable code only. A comment naming a
    shipped file or the corpus mount is honest documentation, not a runtime read,
    and firing on one penalises a correct program for explaining itself.
    """
    import io
    import tokenize

    source = _driver_source()
    kept = []
    previous = tokenize.INDENT
    try:
        stream = tokenize.generate_tokens(io.StringIO(source).readline)
        for kind, text, _start, _end, _line in stream:
            if kind == tokenize.COMMENT:
                continue
            if kind == tokenize.STRING and previous in (
                    tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL):
                previous = kind
                continue
            if kind not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                previous = kind
            kept.append(text)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source
    return "\n".join(kept)


def _strict_equal(actual, expected):
    """JSON equality that never treats booleans, integers and floats as interchangeable."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return (set(actual) == set(expected)
                and all(_strict_equal(actual[key], expected[key]) for key in actual))
    if isinstance(actual, list):
        return (len(actual) == len(expected)
                and all(_strict_equal(left, right)
                        for left, right in zip(actual, expected)))
    return actual == expected


def _compare(actual, expected, artifacts):
    for artifact in artifacts:
        if artifact not in actual or actual[artifact] is None:
            raise AssertionError("deliverable %s is missing or unreadable" % artifact)
        if not _strict_equal(actual[artifact], expected[artifact]):
            raise AssertionError(
                "deliverable %s disagrees with the settled reference" % artifact)


def _generalises(name, artifacts=None):
    proc, produced, expected = _run_driver(name)
    if proc.returncode != 0:
        raise AssertionError(
            "the delivered program failed on corpus %s: %s"
            % (name, proc.stderr.strip().splitlines()[-1:] or ""))
    if artifacts is not None:
        _compare(produced, expected, artifacts)
        return
    # Hidden corpora use the same independently named fact groups as the shipped
    # instance. This avoids making one unrelated leaf in one document erase every
    # point for a corpus while still checking the settlement, partitions and money.
    groups = (
        (_pick(produced["summary.json"], SUMMARY_COUNT_KEYS, "summary"),
         _pick(expected["summary.json"], SUMMARY_COUNT_KEYS, "summary"), "summary census"),
        (_pick(produced["summary.json"], SUMMARY_MONEY_KEYS, "summary"),
         _pick(expected["summary.json"], SUMMARY_MONEY_KEYS, "summary"), "summary money"),
        (_pick(produced["data_quality.json"], QUALITY_ROW_KEYS + QUALITY_SET_KEYS,
               "reconciliation report"),
         _pick(expected["data_quality.json"], QUALITY_ROW_KEYS + QUALITY_SET_KEYS,
               "reconciliation report"), "dispositions"),
        (_pick(produced["data_quality.json"], QUALITY_RESIDUAL_KEYS,
               "reconciliation report"),
         _pick(expected["data_quality.json"], QUALITY_RESIDUAL_KEYS,
               "reconciliation report"), "residuals"),
        (_rollup_totals(produced, REGION_ARTIFACTS),
         _rollup_totals(expected, REGION_ARTIFACTS), "region totals"),
        (_rollup_detail(produced, REGION_ARTIFACTS, "region"),
         _rollup_detail(expected, REGION_ARTIFACTS, "region"), "region details"),
        (_rollup_totals(produced, SEGMENT_ARTIFACTS),
         _rollup_totals(expected, SEGMENT_ARTIFACTS), "segment totals"),
        (_rollup_membership(produced, SEGMENT_ARTIFACTS, "service_class"),
         _rollup_membership(expected, SEGMENT_ARTIFACTS, "service_class"),
         "segment membership"),
    )
    for got, want, label in groups:
        _same(got, want, "%s for %s" % (label, name))


def _reconciled(payload):
    quality = payload["data_quality.json"]
    if quality["conservation_residual_micros"] != 0:
        raise AssertionError("the region conservation residual is non zero")
    if quality["segment_residual_micros"] != 0:
        raise AssertionError("the segment conservation residual is non zero")
    for name, value in quality["invariants"].items():
        if value is not True:
            raise AssertionError("global invariant %s is unsatisfied" % name)


def _consistent_delivery(artifacts=None):
    # Compares only the artifacts it is handed. The reconciliation verdicts belong
    # to the test named after them, so a correct schedule carrying one inconsistent
    # residual fails that test alone rather than every test in the tier.
    payload = _delivered()
    _compare(payload, _shipped_expected(), artifacts or VALUE_ARTIFACTS)
    return payload


QUALITY_SET_KEYS = ("rejected_orders", "deferred_orders")

# Fact groups. The instance tier asserts these separately so that one wrong fact
# costs about one fact's worth of reward. A single whole-object equality over these
# reports would settle several hundred independent facts at once, which makes an
# almost-correct settlement score the same as a wholly wrong one.

SUMMARY_COUNT_KEYS = ("order_rows", "decoded_rows", "orders_scored", "orders_placed",
                      "orders_deferred", "orders_rejected", "lanes_used")
SUMMARY_MONEY_KEYS = ("billable_slots_total", "charge_micros_total", "rebate_micros_total",
                      "capped_micros_total", "net_micros_total")
QUALITY_ROW_KEYS = ("order_rows", "decoded_rows")
QUALITY_NET_KEYS = ("region_net_micros", "segment_net_micros")
QUALITY_RESIDUAL_KEYS = ("conservation_residual_micros", "segment_residual_micros")


def _pick(obj, keys, what):
    if not isinstance(obj, dict):
        raise AssertionError("the delivered %s is not a JSON object" % what)
    return {key: obj.get(key) for key in keys}


def _same(got, want, what):
    if not _strict_equal(got, want):
        raise AssertionError("the delivered %s disagrees with the settled reference" % what)


def _rollup_totals(payload, artifacts):
    out = {}
    for artifact in artifacts:
        rollup = payload.get(artifact)
        if not isinstance(rollup, dict):
            raise AssertionError("deliverable %s is missing or unreadable" % artifact)
        out[artifact] = {"order_count": rollup.get("order_count"), "totals": rollup.get("totals")}
    return out


def _rollup_detail(payload, artifacts, key_field):
    out = {}
    for artifact in artifacts:
        rollup = payload.get(artifact)
        if not isinstance(rollup, dict):
            raise AssertionError("deliverable %s is missing or unreadable" % artifact)
        out[artifact] = {"orders": rollup.get("orders"), key_field: rollup.get(key_field)}
    return out


def _rollup_membership(payload, artifacts, key_field):
    """Membership only; region checks own the per-order settlement fields."""
    out = {}
    for artifact in artifacts:
        rollup = payload.get(artifact)
        if not isinstance(rollup, dict):
            raise AssertionError("deliverable %s is missing or unreadable" % artifact)
        rows = rollup.get("orders")
        if not isinstance(rows, list):
            raise AssertionError("deliverable %s has no order list" % artifact)
        out[artifact] = {
            key_field: rollup.get(key_field),
            "order_ids": [row.get("order_id") for row in rows],
        }
    return out


def _key_shape(value):
    """The field names of a report, with every value discarded.

    Lets one cheap test hold the "exactly these fields" promise report_schema.md
    makes, so the value tests can compare fact groups without also silently
    grading the presence of a stray extra key.
    """
    if isinstance(value, dict):
        return {key: _key_shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_key_shape(value[0])] if value else []
    return type(value).__name__



def _quality_without_sets(quality):
    return {key: value for key, value in quality.items() if key not in QUALITY_SET_KEYS}


# ---------------------------------------------------------------------------
# format tier
# ---------------------------------------------------------------------------


def _impl_test_format_deliverables_present():
    """POSITIVE: every declared deliverable exists, parses and carries content."""
    _driver_path()
    payload = _delivered()
    for artifact in ALL_ARTIFACTS:
        if not isinstance(payload[artifact], dict):
            raise AssertionError("deliverable %s is a JSON object" % artifact)


def _impl_test_format_driver_is_reusable():
    """POSITIVE: the delivered program takes an input directory and an output directory."""
    data_dir, _ = _materialise("shipped")
    out_dir = tempfile.mkdtemp(prefix="lane-reuse-")
    proc = _invoke(data_dir, out_dir)
    if proc.returncode != 0:
        raise AssertionError("the delivered program refused a fresh corpus directory")
    for artifact in ALL_ARTIFACTS:
        path = os.path.join(out_dir, artifact)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise AssertionError("the delivered program skipped %s" % artifact)


def _impl_test_format_policy_audit_schema():
    """POSITIVE: the derivation record carries the declared sections and field names."""
    payload = _delivered()
    audit = payload["policy_audit.json"]
    for key in ("candidate_space", "resolved_parameters", "calibration_comparison",
                "fixpoint", "assignment_search"):
        if key not in audit:
            raise AssertionError("the derivation record omits section %s" % key)
    if not isinstance(audit["candidate_space"], list) or not audit["candidate_space"]:
        raise AssertionError("the candidate space section is an empty list")
    for entry in audit["candidate_space"]:
        for key in ("parameter", "control", "domain_size", "resolved", "rejected",
                    "verdicts"):
            if key not in entry:
                raise AssertionError("a candidate space entry omits %s" % key)
        # Field names only, never a value: report_schema.md promises one verdict
        # per candidate value, and the rubric is what grades what those verdicts
        # say. Asserting a value here would grade the same observable twice.
        if not isinstance(entry["verdicts"], list) or not entry["verdicts"]:
            raise AssertionError(
                "the candidate space entry for %s carries no verdict list"
                % entry.get("parameter"))
        for verdict in entry["verdicts"]:
            for key in ("value", "verdict"):
                if key not in verdict:
                    raise AssertionError("a candidate verdict entry omits %s" % key)
    if not isinstance(audit["calibration_comparison"], list) or not audit["calibration_comparison"]:
        raise AssertionError("the calibration comparison section is an empty list")
    for entry in audit["calibration_comparison"]:
        for key in ("control", "published", "reproduced"):
            if key not in entry:
                raise AssertionError("a calibration comparison entry omits %s" % key)
    for key in ("passes", "congestion_index", "congestion_tier"):
        if key not in audit["fixpoint"]:
            raise AssertionError("the fixpoint section omits %s" % key)
    for key in ("sites_searched", "feasible_leaves", "displaced_orders", "site_cost_micros"):
        if key not in audit["assignment_search"]:
            raise AssertionError("the assignment search section omits %s" % key)
    params = audit.get("resolved_parameters")
    expected_names = set(PARAMETER_ORDER)
    if not isinstance(params, dict) or set(params) != expected_names:
        raise AssertionError("resolved_parameters must name every withheld constant")
    for key in ("candidates_examined", "candidates_rejected"):
        if not isinstance(audit.get(key), int) or isinstance(audit.get(key), bool):
            raise AssertionError("derivation record omits integer %s" % key)


def _impl_test_format_report_field_names():
    """POSITIVE: every report carries exactly the field names report_schema.md fixes."""
    payload = _delivered()
    expected = _shipped_expected()
    for artifact in VALUE_ARTIFACTS:
        if _key_shape(payload[artifact]) != _key_shape(expected[artifact]):
            raise AssertionError(
                "deliverable %s does not carry the field names report_schema.md fixes" % artifact)


# ---------------------------------------------------------------------------
# instance tier
# ---------------------------------------------------------------------------


def _impl_test_instance_summary_census():
    """POSITIVE: the delivered order census agrees with the settled reference."""
    payload = _delivered()
    expected = _shipped_expected()
    _same(_pick(payload["summary.json"], SUMMARY_COUNT_KEYS, "summary"),
          _pick(expected["summary.json"], SUMMARY_COUNT_KEYS, "summary"),
          "order census")
    _same(_pick(payload["data_quality.json"], QUALITY_ROW_KEYS, "reconciliation report"),
          _pick(expected["data_quality.json"], QUALITY_ROW_KEYS, "reconciliation report"),
          "record counts")
    if payload["summary.json"].get("orders_placed", 0) <= 0:
        raise AssertionError("the summary reports an empty schedule")


def _impl_test_instance_summary_money():
    """POSITIVE: the delivered monetary totals agree with the settled reference."""
    payload = _delivered()
    expected = _shipped_expected()
    _same(_pick(payload["summary.json"], SUMMARY_MONEY_KEYS, "summary"),
          _pick(expected["summary.json"], SUMMARY_MONEY_KEYS, "summary"),
          "monetary totals")


def _impl_test_instance_region_totals():
    """POSITIVE: every region rollup total agrees with the settled reference."""
    _same(_rollup_totals(_delivered(), REGION_ARTIFACTS),
          _rollup_totals(_shipped_expected(), REGION_ARTIFACTS),
          "region rollup totals")


def _impl_test_instance_region_detail():
    """POSITIVE: every placed order inside the region rollups agrees with the reference."""
    _same(_rollup_detail(_delivered(), REGION_ARTIFACTS, "region"),
          _rollup_detail(_shipped_expected(), REGION_ARTIFACTS, "region"),
          "region rollup orders")


def _impl_test_instance_segment_totals():
    """POSITIVE: every service class rollup total agrees with the settled reference."""
    _same(_rollup_totals(_delivered(), SEGMENT_ARTIFACTS),
          _rollup_totals(_shipped_expected(), SEGMENT_ARTIFACTS),
          "segment rollup totals")


def _impl_test_instance_segment_detail():
    """POSITIVE: every placed order belongs to the correct segment exactly once."""
    _same(_rollup_membership(_delivered(), SEGMENT_ARTIFACTS, "service_class"),
          _rollup_membership(_shipped_expected(), SEGMENT_ARTIFACTS, "service_class"),
          "segment membership")


def _impl_test_instance_net_breakdown():
    """POSITIVE: the per region and per segment net value agrees with the reference."""
    _same(_pick(_delivered()["data_quality.json"], QUALITY_NET_KEYS, "reconciliation report"),
          _pick(_shipped_expected()["data_quality.json"], QUALITY_NET_KEYS, "reconciliation report"),
          "per region and per segment net value")


def _impl_test_instance_reconciliation_residuals():
    """POSITIVE: the delivered conservation residuals are the settled ones and are zero."""
    payload = _delivered()
    _same(_pick(payload["data_quality.json"], QUALITY_RESIDUAL_KEYS, "reconciliation report"),
          _pick(_shipped_expected()["data_quality.json"], QUALITY_RESIDUAL_KEYS, "reconciliation report"),
          "conservation residuals")
    quality = payload["data_quality.json"]
    if quality.get("conservation_residual_micros") != 0:
        raise AssertionError("the region conservation residual is non zero")
    if quality.get("segment_residual_micros") != 0:
        raise AssertionError("the segment conservation residual is non zero")


def _impl_test_instance_reconciliation_invariants():
    """POSITIVE: the delivered invariant verdicts are the settled ones and all hold."""
    got = _delivered()["data_quality.json"].get("invariants")
    if not isinstance(got, dict):
        raise AssertionError("the reconciliation report carries no invariants object")
    _same(got, _shipped_expected()["data_quality.json"]["invariants"], "invariant verdicts")
    for name, value in sorted(got.items()):
        if value is not True:
            raise AssertionError("global invariant %s is unsatisfied" % name)


def _impl_test_instance_calibration_settlement():
    """POSITIVE: the delivered calibration net value agrees with the settled reference."""
    _same(_pick(_delivered()["data_quality.json"], ("calibration_net_micros",), "reconciliation report"),
          _pick(_shipped_expected()["data_quality.json"], ("calibration_net_micros",), "reconciliation report"),
          "calibration population net value")


def _impl_test_instance_disposition_sets():
    """POSITIVE: the rejected and deferred order sets agree with the settled reference."""
    _same(_pick(_delivered()["data_quality.json"], QUALITY_SET_KEYS, "reconciliation report"),
          _pick(_shipped_expected()["data_quality.json"], QUALITY_SET_KEYS, "reconciliation report"),
          "rejected and deferred order sets")


def _impl_test_instance_partition_closure():
    """POSITIVE: the region and segment partitions cover the placed schedule exactly once."""
    payload = _delivered()
    placed = payload["summary.json"]["orders_placed"]
    region_ids = []
    for artifact in REGION_ARTIFACTS:
        region_ids.extend(row["order_id"] for row in payload[artifact]["orders"])
    segment_ids = []
    for artifact in SEGMENT_ARTIFACTS:
        segment_ids.extend(row["order_id"] for row in payload[artifact]["orders"])
    if sorted(region_ids) != sorted(segment_ids):
        raise AssertionError("the region and segment partitions disagree on membership")
    if len(set(region_ids)) != len(region_ids) or len(region_ids) != placed:
        raise AssertionError("the region partition repeats or drops a placed order")


def _impl_test_instance_conservation_totals():
    """POSITIVE: the delivered rollup totals conserve the settled schedule value."""
    payload = _delivered()
    summary = payload["summary.json"]
    region_net = sum(payload[artifact]["totals"]["net_micros"] for artifact in REGION_ARTIFACTS)
    segment_net = sum(payload[artifact]["totals"]["net_micros"] for artifact in SEGMENT_ARTIFACTS)
    if region_net != summary["net_micros_total"] or segment_net != summary["net_micros_total"]:
        raise AssertionError("the rollup totals lose schedule value")
    region_slots = sum(payload[artifact]["totals"]["billable_slots"] for artifact in REGION_ARTIFACTS)
    if region_slots != summary["billable_slots_total"]:
        raise AssertionError("the rollup slot totals lose schedule volume")


# ---------------------------------------------------------------------------
# trap tier
# ---------------------------------------------------------------------------


def _impl_test_trap_payload_rotation_inverse():
    """POSITIVE: the payload rotation origin is recovered rather than assumed."""
    _generalises("trap_rotate_step")


def _impl_test_trap_length_shadow_inverse():
    """POSITIVE: the shadowed record length nibble is unmasked before the cursor advances."""
    _generalises("trap_shadow_bias")


def _impl_test_trap_count_bias_inverse():
    """POSITIVE: the biased block count is corrected and the filler tail is dropped."""
    _generalises("trap_count_bias")


def _impl_test_trap_endian_island_inverse():
    """POSITIVE: the reversed header field is located and read in its own byte order."""
    _generalises("trap_island_offset")


def _impl_test_trap_block_permutation_inverse():
    """POSITIVE: physical record order is mapped back to logical order before decoding."""
    _generalises("trap_permute_rounds")


def _impl_test_trap_keystream_label_inverse():
    """POSITIVE: the masked load field is unmasked with the recovered stream label."""
    _generalises("trap_stream_label")


def _impl_test_trap_chained_offset_inverse():
    """POSITIVE: the chained due offsets are unwound in strict logical sequence."""
    _generalises("trap_chain_seed")


def _impl_test_trap_second_difference_inverse():
    """POSITIVE: the second order weight differences are integrated over their own span."""
    _generalises("trap_delta_span")


def _impl_test_trap_drifting_day_inverse():
    """POSITIVE: the drifting submission day multiplier is inverted across blocks."""
    _generalises("trap_drift_modulus")


def _impl_test_trap_alias_rotor_inverse():
    """POSITIVE: the rotated alias index is realigned against the client directory."""
    _generalises("trap_alias_rotor")


def _impl_test_trap_back_reference_window_inverse():
    """POSITIVE: programme back references resolve against the recovered window span."""
    _generalises("trap_window_span")


def _impl_test_trap_quantisation_mode_inverse():
    """POSITIVE: billable slots follow the recovered quantisation mode."""
    _generalises("trap_quant_mode")


# ---------------------------------------------------------------------------
# generalisation tier
# ---------------------------------------------------------------------------


def _impl_test_generalises_full_parameter_change():
    """POSITIVE: a corpus with every withheld parameter changed still settles."""
    _generalises("mut_hidden_full")


def _impl_test_generalises_uniform_lane_rates():
    """POSITIVE: a corpus where every lane charges one rate still settles."""
    _generalises("mut_uniform_rates")


def _impl_test_generalises_binding_budgets():
    """POSITIVE: a corpus where budget ceilings bind everywhere still settles."""
    _generalises("mut_tight_budgets")


def _impl_test_generalises_shifted_tier_bounds():
    """POSITIVE: a corpus with different congestion bounds still reaches its fixpoint."""
    _generalises("mut_tier_bounds")


def _impl_test_generalises_empty_region_partition():
    """POSITIVE: a corpus that empties one region partition still settles."""
    _generalises("mut_empty_site")


def _impl_test_generalises_identity_cycle():
    """POSITIVE: a corpus carrying a merge cycle still canonicalises identity."""
    _generalises("mut_merge_cycle")


def _impl_test_generalises_shifted_revision_boundaries():
    """POSITIVE: a corpus with revision boundaries moved by one day still settles."""
    _generalises("mut_boundary_shift")


def _impl_test_generalises_contention_tie():
    """POSITIVE: a corpus with altered last-slot contention still settles."""
    _generalises("mut_contention_tie")


def _impl_test_generalises_revision_edges():
    """POSITIVE: a corpus whose revisions overlap and whose gap opens on a live day still settles."""
    _generalises("mut_revision_edges")


def _impl_test_generalises_added_clients():
    """POSITIVE: a corpus carrying additional clients still settles."""
    _generalises("mut_new_client")


def _impl_test_generalises_squeezed_lane_capacity():
    """POSITIVE: a corpus with reduced lane capacity still settles."""
    _generalises("mut_lane_squeeze")


def _impl_test_generalises_inverted_slack():
    """POSITIVE: a corpus whose slack ordering inverts still settles."""
    _generalises("mut_slack_flip")


def _impl_test_generalises_relocated_clients():
    """POSITIVE: a corpus that moves clients between sites still settles."""
    _generalises("mut_resite")


def _impl_test_generalises_scaled_population():
    """POSITIVE: a corpus about three times larger still settles."""
    _generalises("mut_scale")


def _impl_test_generalises_changed_conflict_families():
    """POSITIVE: a corpus with different incompatible families still settles."""
    _generalises("mut_conflict_pairs")


def _impl_test_generalises_sparse_flag_coverage():
    """POSITIVE: a corpus where each block carries few transforms still settles."""
    _generalises("mut_flags_sparse")


def _impl_test_generalises_held_out_seed():
    """POSITIVE: a held out corpus with its own parameters and content still settles."""
    _generalises("mut_eval_seed")


def _impl_test_generalises_short_blocks():
    """POSITIVE: a corpus of short blocks with more of them still settles."""
    _generalises("mut_short_blocks")



def _impl_test_format_byte_order_mark():
    """POSITIVE: tables that open with a UTF-8 byte order mark still settle."""
    _generalises("fmt_bom")


def _impl_test_format_padded_header_names():
    """POSITIVE: a table whose header names carry surrounding spaces still settles."""
    _generalises("fmt_header_pad")


def _impl_test_format_padded_cells():
    """POSITIVE: directory cells carrying surrounding spaces still settle."""
    _generalises("fmt_cell_pad")


def _impl_test_format_zero_padded_block_ids():
    """POSITIVE: payload block identifiers written with leading zeros still settle."""
    _generalises("fmt_zero_pad")


def _impl_test_format_region_name_case():
    """POSITIVE: region names written in another letter case land in their rollups."""
    _generalises("fmt_region_case")


def _impl_test_format_draft_policy_ignored():
    """POSITIVE: an unadopted draft policy document leaves the settlement unchanged."""
    _generalises("fmt_draft_policy")


def _impl_test_format_archived_controls_ignored():
    """POSITIVE: a withdrawn calibration slice leaves the recovered constants unchanged."""
    _generalises("fmt_archived_controls")


# ---------------------------------------------------------------------------
# negative detectors
# ---------------------------------------------------------------------------


def _impl_test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when the delivered program replays the shipped answers."""
    payload = _delivered()
    shipped = _shipped_expected()
    _compare(payload, shipped, VALUE_ARTIFACTS)
    for name in ("trap_quant_mode", "mut_eval_seed"):
        proc, produced, _ = _run_driver(name)
        if proc.returncode != 0:
            continue
        replayed = True
        for artifact in VALUE_ARTIFACTS:
            if produced.get(artifact) != shipped[artifact]:
                replayed = False
                break
        if replayed:
            return
    raise AssertionError("the delivered program derives its answers from the corpus it reads")


def _outputs_identical(left_dir, right_dir, artifacts=None):
    for artifact in artifacts or ALL_ARTIFACTS:
        left = os.path.join(left_dir, artifact)
        right = os.path.join(right_dir, artifact)
        if os.path.isfile(left) != os.path.isfile(right):
            return False
        if os.path.isfile(left):
            with open(left, "rb") as handle:
                one = handle.read()
            with open(right, "rb") as handle:
                two = handle.read()
            if one != two:
                return False
    return True


def _impl_test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: fires when the delivered program keys behaviour off directory names."""
    data_dir, _ = _materialise("shipped")
    renamed_root = tempfile.mkdtemp(prefix="lane-renamed-")
    renamed = os.path.join(renamed_root, "zzz_unrelated_name")
    shutil.copytree(data_dir, renamed)
    control_out = tempfile.mkdtemp(prefix="lane-name-control-")
    first_out = tempfile.mkdtemp(prefix="lane-name-a-")
    second_out = tempfile.mkdtemp(prefix="lane-name-b-")
    control = _invoke(data_dir, control_out)
    first = _invoke(data_dir, first_out)
    if control.returncode != 0 or first.returncode != 0:
        raise AssertionError("the delivered program failed on the shipped corpus")
    # Same-name control. A program that already disagrees with itself under one
    # unchanged directory name is nondeterministic, which its own detector owns;
    # firing here as well would charge one decision two penalties.
    if not _outputs_identical(control_out, first_out):
        raise AssertionError("the delivered program is unstable under one directory name")
    second = _invoke(renamed, second_out)
    if second.returncode != 0:
        return
    if not _outputs_identical(first_out, second_out):
        return
    raise AssertionError("the delivered program behaves the same under any directory name")


def _impl_test_negative_weight_reads_supplied_answer_data_at_runtime():
    """NEGATIVE: fires when the delivered program reaches for the shipped corpus path."""
    # Executable code only: comments and docstrings are stripped first, so a program
    # that merely documents where its inputs came from keeps its reward.
    source = _driver_source()
    pinned = "/" + "app" + "/" + "data"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        raise AssertionError("the delivered program cannot be parsed")
    readers = {"open", "listdir", "scandir", "walk", "glob", "iglob"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name not in readers:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and pinned in arg.value:
                return
    raise AssertionError("the delivered program reads only the directory it is given")


def _impl_test_negative_weight_nondeterministic_output():
    """NEGATIVE: fires when two runs over one corpus disagree."""
    data_dir, _ = _materialise("shipped")
    first_out = tempfile.mkdtemp(prefix="lane-det-a-")
    second_out = tempfile.mkdtemp(prefix="lane-det-b-")
    first = _invoke(data_dir, first_out)
    second = _invoke(data_dir, second_out)
    if first.returncode != 0 or second.returncode != 0:
        raise AssertionError("the delivered program failed on the shipped corpus")
    if not _outputs_identical(first_out, second_out):
        return
    raise AssertionError("the delivered program repeats itself exactly")


def _impl_test_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: fires when the delivered program leans on the labelled probe tier."""
    data_dir, _ = _materialise("shipped")
    stripped_root = tempfile.mkdtemp(prefix="lane-strip-")
    stripped = os.path.join(stripped_root, "data")
    shutil.copytree(data_dir, stripped)
    for name in ("reference_probe_answers.csv", "probe_region_example.json"):
        target = os.path.join(stripped, name)
        if os.path.isfile(target):
            os.remove(target)
    control_out = tempfile.mkdtemp(prefix="lane-train-control-")
    first_out = tempfile.mkdtemp(prefix="lane-train-a-")
    second_out = tempfile.mkdtemp(prefix="lane-train-b-")
    control = _invoke(data_dir, control_out)
    first = _invoke(data_dir, first_out)
    if control.returncode != 0 or first.returncode != 0:
        raise AssertionError("the delivered program failed on the shipped corpus")
    # Same-corpus control, for the reason given on the filename detector: an
    # unstable program is charged by the determinism detector and not again here.
    if not _outputs_identical(control_out, first_out, VALUE_ARTIFACTS):
        raise AssertionError("the delivered program is unstable on one unchanged corpus")
    second = _invoke(stripped, second_out)
    if second.returncode != 0:
        return
    if not _outputs_identical(first_out, second_out, VALUE_ARTIFACTS):
        return
    raise AssertionError("the delivered program derives its answers without the labelled tier")


def _impl_test_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: fires when the delivered program reaches into the grading machinery."""
    # Executable code only, for the reason given on the corpus-path detector.
    source = _driver_source()
    root = "/" + "tests"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        raise AssertionError("the delivered program cannot be parsed")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            if any(name in {"test_output", "test_weights"} or name.startswith("tests.")
                   for name in names):
                return
        if isinstance(node, ast.Call):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value == root or arg.value.startswith(root + "/"):
                        return
    raise AssertionError("the delivered program leaves the grading machinery alone")


# rewardkit calls checks from worker threads and aborts the whole reward on an
# uncaught exception. Checks run one at a time because the corpus and run caches
# and ARTIFACT_DIR are shared module state and every driver run is held to the
# same 600 s timeout; a raised assertion scores the check False.
_GRADE_LOCK = threading.Lock()


def _bind(workspace):
    global ARTIFACT_DIR
    ARTIFACT_DIR = os.path.join(str(workspace), "out")


def _pass(workspace, check):
    with _GRADE_LOCK:
        _bind(workspace)
        try:
            check()
            return True
        except Exception:
            return False


def _all(*checks):
    def run():
        for check in checks:
            check()
    return run


@criterion(description="every declared deliverable is present and the program takes an input and an output directory")
def test_format_deliverables_and_driver(workspace):
    return _pass(workspace, _all(_impl_test_format_deliverables_present, _impl_test_format_driver_is_reusable))


@criterion(description="the derivation record and every report carry the field names report_schema.md fixes")
def test_format_report_schemas(workspace):
    return _pass(workspace, _all(_impl_test_format_policy_audit_schema, _impl_test_format_report_field_names))


@criterion(description="the delivered order census and monetary totals agree with the settled reference")
def test_instance_summary(workspace):
    return _pass(workspace, _all(_impl_test_instance_summary_census, _impl_test_instance_summary_money))


@criterion(description="every region rollup, its totals and its placed orders, agrees with the reference")
def test_instance_region_rollups(workspace):
    return _pass(workspace, _all(_impl_test_instance_region_totals, _impl_test_instance_region_detail))


@criterion(description="every service class rollup, its totals and its placed orders, agrees with the reference")
def test_instance_segment_rollups(workspace):
    return _pass(workspace, _all(_impl_test_instance_segment_totals, _impl_test_instance_segment_detail))


@criterion(description="the net breakdown, residuals and invariant verdicts are the settled ones")
def test_instance_reconciliation(workspace):
    return _pass(workspace, _all(_impl_test_instance_reconciliation_residuals, _impl_test_instance_reconciliation_invariants))


@criterion(description="the calibration net value and the rejected and deferred sets agree with the reference")
def test_instance_calibration_and_dispositions(workspace):
    return _pass(workspace, _all(_impl_test_instance_calibration_settlement, _impl_test_instance_disposition_sets))


@criterion(description="the partitions cover the placed schedule once and the rollup totals conserve its value")
def test_instance_partition_conservation(workspace):
    return _pass(workspace, _all(_impl_test_instance_partition_closure, _impl_test_instance_conservation_totals))


@criterion(description="the payload rotation, length shadow and count bias constants are recovered and inverted")
def test_trap_rotation_shadow_count(workspace):
    return _pass(workspace, _all(_impl_test_trap_payload_rotation_inverse, _impl_test_trap_length_shadow_inverse, _impl_test_trap_count_bias_inverse))


@criterion(description="the byte order island, block permutation and keystream label constants are recovered and inverted")
def test_trap_island_permutation_keystream(workspace):
    return _pass(workspace, _all(_impl_test_trap_endian_island_inverse, _impl_test_trap_block_permutation_inverse, _impl_test_trap_keystream_label_inverse))


@criterion(description="the chained offset, second difference and drifting day constants are recovered and inverted")
def test_trap_chain_delta_drift(workspace):
    return _pass(workspace, _all(_impl_test_trap_chained_offset_inverse, _impl_test_trap_second_difference_inverse, _impl_test_trap_drifting_day_inverse))


@criterion(description="the alias rotor, back reference window and quantisation mode constants are recovered and applied")
def test_trap_rotor_window_quantisation(workspace):
    return _pass(workspace, _all(_impl_test_trap_alias_rotor_inverse, _impl_test_trap_back_reference_window_inverse, _impl_test_trap_quantisation_mode_inverse))


@criterion(description="corpora written with a full set of other constants and another seed still settle")
def test_generalises_held_out_parameters(workspace):
    return _pass(workspace, _all(_impl_test_generalises_full_parameter_change, _impl_test_generalises_held_out_seed))



@criterion(description="corpora with binding budgets or shifted tier bounds still settle")
def test_generalises_admission_rules(workspace):
    return _pass(workspace, _all(_impl_test_generalises_binding_budgets, _impl_test_generalises_shifted_tier_bounds))


@criterion(description="corpora with an empty region or relocated clients still settle")
def test_generalises_site_layout(workspace):
    return _pass(workspace, _all(_impl_test_generalises_empty_region_partition, _impl_test_generalises_relocated_clients))


@criterion(description="corpora with a merge cycle or added clients still settle")
def test_generalises_client_identity(workspace):
    return _pass(workspace, _all(_impl_test_generalises_identity_cycle, _impl_test_generalises_added_clients))


@criterion(description="corpora with shifted revision boundaries or revision edge days still settle")
def test_generalises_revision_windows(workspace):
    return _pass(workspace, _all(_impl_test_generalises_shifted_revision_boundaries, _impl_test_generalises_revision_edges))





@criterion(description="corpora with uniform lane rates, squeezed lane capacity or changed conflict families still settle")
def test_generalises_lane_rules(workspace):
    return _pass(workspace, _all(_impl_test_generalises_uniform_lane_rates, _impl_test_generalises_squeezed_lane_capacity, _impl_test_generalises_changed_conflict_families))

@criterion(description="corpora with altered lane contention or inverted slack still settle under the contention rule")
def test_generalises_placement_contention(workspace):
    return _pass(workspace, _all(_impl_test_generalises_contention_tie, _impl_test_generalises_inverted_slack))

@criterion(description="a larger population still settles")
def test_generalises_scaled_population(workspace):
    return _pass(workspace, _impl_test_generalises_scaled_population)

@criterion(description="a corpus with sparse transform flags still settles")
def test_generalises_sparse_flag_coverage(workspace):
    return _pass(workspace, _impl_test_generalises_sparse_flag_coverage)

@criterion(description="a corpus with short blocks still settles")
def test_generalises_short_blocks(workspace):
    return _pass(workspace, _impl_test_generalises_short_blocks)

@criterion(description="tables that open with a UTF-8 byte order mark still settle")
def test_format_byte_order_mark(workspace):
    return _pass(workspace, _impl_test_format_byte_order_mark)


@criterion(description="a table whose header names carry surrounding spaces still settles")
def test_format_padded_header_names(workspace):
    return _pass(workspace, _impl_test_format_padded_header_names)


@criterion(description="directory cells carrying surrounding spaces still settle")
def test_format_padded_cells(workspace):
    return _pass(workspace, _impl_test_format_padded_cells)


@criterion(description="payload block identifiers written with leading zeros still settle")
def test_format_zero_padded_block_ids(workspace):
    return _pass(workspace, _impl_test_format_zero_padded_block_ids)


@criterion(description="region names written in another letter case land in their rollups")
def test_format_region_name_case(workspace):
    return _pass(workspace, _impl_test_format_region_name_case)


@criterion(description="an unadopted draft policy document leaves the settlement unchanged")
def test_format_draft_policy_ignored(workspace):
    return _pass(workspace, _impl_test_format_draft_policy_ignored)


@criterion(description="a withdrawn calibration slice leaves the recovered constants unchanged")
def test_format_archived_controls_ignored(workspace):
    return _pass(workspace, _impl_test_format_archived_controls_ignored)


@criterion(description="the delivered program replays the shipped answers")
def negative_weight_hardcoded_sample_answers(workspace):
    return _pass(workspace, _impl_test_negative_weight_hardcoded_sample_answers)


@criterion(description="the delivered program keys behaviour off directory names")
def negative_weight_filename_dependent_behaviour(workspace):
    return _pass(workspace, _impl_test_negative_weight_filename_dependent_behaviour)


@criterion(description="the delivered program reaches for the shipped corpus path")
def negative_weight_reads_supplied_answer_data_at_runtime(workspace):
    return _pass(workspace, _impl_test_negative_weight_reads_supplied_answer_data_at_runtime)


@criterion(description="two runs over one corpus disagree")
def negative_weight_nondeterministic_output(workspace):
    return _pass(workspace, _impl_test_negative_weight_nondeterministic_output)


@criterion(description="the delivered program leans on the labelled probe tier")
def negative_weight_reads_training_corpus_at_runtime(workspace):
    return _pass(workspace, _impl_test_negative_weight_reads_training_corpus_at_runtime)


@criterion(description="the delivered program reaches into the grading machinery")
def negative_weight_rebinds_verifier_dependencies(workspace):
    return _pass(workspace, _impl_test_negative_weight_rebinds_verifier_dependencies)


criteria.test_format_deliverables_and_driver(weight=1)
criteria.test_format_report_schemas(weight=1)
criteria.test_instance_summary(weight=3)
criteria.test_instance_region_rollups(weight=5)
criteria.test_instance_segment_rollups(weight=5)
criteria.test_instance_reconciliation(weight=3)
criteria.test_instance_calibration_and_dispositions(weight=3)
criteria.test_instance_partition_conservation(weight=1)
criteria.test_trap_rotation_shadow_count(weight=5)
criteria.test_trap_island_permutation_keystream(weight=5)
criteria.test_trap_chain_delta_drift(weight=5)
criteria.test_trap_rotor_window_quantisation(weight=5)
criteria.test_generalises_held_out_parameters(weight=5)
criteria.test_generalises_lane_rules(weight=5)
criteria.test_generalises_admission_rules(weight=5)
criteria.test_generalises_site_layout(weight=5)
criteria.test_generalises_client_identity(weight=5)
criteria.test_generalises_revision_windows(weight=5)
criteria.test_generalises_placement_contention(weight=5)
criteria.test_generalises_scaled_population(weight=3)
criteria.test_generalises_sparse_flag_coverage(weight=1)
criteria.test_generalises_short_blocks(weight=1)
criteria.test_format_byte_order_mark(weight=3)
criteria.test_format_padded_header_names(weight=1)
criteria.test_format_padded_cells(weight=1)
criteria.test_format_zero_padded_block_ids(weight=3)
criteria.test_format_region_name_case(weight=3)
criteria.test_format_draft_policy_ignored(weight=1)
criteria.test_format_archived_controls_ignored(weight=3)
criteria.negative_weight_hardcoded_sample_answers(weight=-5)
criteria.negative_weight_filename_dependent_behaviour(weight=-5)
criteria.negative_weight_reads_supplied_answer_data_at_runtime(weight=-5)
criteria.negative_weight_nondeterministic_output(weight=-3)
criteria.negative_weight_reads_training_corpus_at_runtime(weight=-3)
criteria.negative_weight_rebinds_verifier_dependencies(weight=-3)
