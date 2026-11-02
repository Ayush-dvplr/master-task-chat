"""Grading and corpus construction for 8fbe0e42-ced0-5847-bfb9-b793b4171c42.

This module builds every capture set the grader uses, derives the settlement
that the shipped engine rules imply, and compares the delivered program's
reports against it. It imports the standard library only.
"""

import ast
import hashlib
import json
import os
import pwd
import signal
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
import threading
from rewardkit import criteria, criterion

CHALLENGE_SEED = 71443
EVAL_SEED = 90227
HELD_OUT_HEFT = 40

WIRE_KEY = "MRD-2031".encode("ascii")
PAYLOAD_WIDTH = 12
TICK_FIELD = 65536
STATE_BOUND = 1 << 18
ECHO_MARK = 0xE0

CLASSES = ("peak", "steady", "burst", "latency")

LABELS = ("aegis", "banner", "cinder", "dagger", "ember", "falcon",
          "gale", "harrow", "ingot", "javelin", "kestrel", "lantern")

WORDS = ("aurochs", "basilisk", "cockatrice", "dryad", "ettin", "fenrir",
         "golem", "hydra", "ifrit", "jotun", "kelpie", "lamia",
         "manticore", "nixie", "ogre", "pegasus", "quasit", "roc",
         "sylph", "troll", "undine", "vodyanoi", "wyvern", "xorn")

CHARTERS = ("azure", "crimson", "gilded", "sable", "verdant")

BIT_SEALED = 0x0001
BIT_CHAINED = 0x0002
BIT_STEPPED = 0x0004
BIT_DRIFTED = 0x0008
BIT_WOVEN = 0x0010
BIT_ECHOED = 0x0020
BIT_FLIPPED = 0x0040
BIT_PADDED = 0x0080
BIT_SHADOWED = 0x0100
BIT_SPUN = 0x0200
BIT_ALIASED = 0x0400
BIT_WARDED = 0x0800
EVERY_BIT = 0x0FFF

TRUE_VALUES = {
    "frame_bias_limit": 9,
    "weave_seed_offset": 23,
    "sentinel_code_value": 214,
    "drift_modulus": 11,
    "seal_label_index": 5,
    "spin_modulus": 13,
    "shadow_pad_base": 7,
    "alias_donor_shift": 3,
    "echo_window_span": 6,
    "cadence_modulus": 4,
    "upkeep_target_scale": 17,
}

CANDIDATES = {
    "frame_bias_limit": tuple(range(4, 16)),
    "weave_seed_offset": tuple(range(17, 31)),
    "sentinel_code_value": tuple(range(200, 216)),
    "drift_modulus": tuple(range(5, 17)),
    "seal_label_index": tuple(range(0, 12)),
    "spin_modulus": tuple(range(7, 19)),
    "shadow_pad_base": tuple(range(3, 15)),
    "alias_donor_shift": tuple(range(1, 11)),
    "echo_window_span": tuple(range(2, 14)),
    "cadence_modulus": tuple(range(2, 12)),
    "upkeep_target_scale": tuple(range(11, 23)),
}

PIN_ORDER = ("frame_bias_limit", "weave_seed_offset", "sentinel_code_value",
             "drift_modulus", "seal_label_index", "spin_modulus",
             "shadow_pad_base", "alias_donor_shift", "echo_window_span",
             "cadence_modulus", "upkeep_target_scale")

CONTROL_NAMES = tuple("CTRL-" + chr(ord("A") + step) for step in range(11))
CONTROL_FOR = dict(zip(PIN_ORDER, CONTROL_NAMES))

CAPTURE_RING = (
    ("calib_wisent.rpl", 0, EVERY_BIT),
    ("sample_orchid.rpl", 1, 0x0000),
    ("sample_cobalt.rpl", 2, 0x0000),
    ("field_marrow.rpl", 3, EVERY_BIT),
    ("field_quarry.rpl", 4, EVERY_BIT),
    ("field_tundra.rpl", 5, EVERY_BIT),
)

RING_SIZE = len(CAPTURE_RING)

# Each damaged set breaks a few payloads of its own on purpose, so one decode
# rule for a `none` entry decides what the rest of the capture reads as.
DAMAGE_FLAGS = {
    "zero": BIT_WARDED | BIT_DRIFTED,
    "carry": BIT_CHAINED,
    "stepped": BIT_STEPPED,
    "index": BIT_ALIASED,
}


def wire_prf(label, *numbers):
    """Deterministic keyed digest over a label and a list of integers."""
    body = bytearray(WIRE_KEY)
    body += label.encode("ascii")
    for value in numbers:
        body += b":"
        body += str(int(value)).encode("ascii")
    return hashlib.sha256(bytes(body)).digest()


def digest_of(parts):
    """Short stable digest over a list of text fragments."""
    body = bytearray(WIRE_KEY)
    for part in parts:
        body += b"|"
        body += str(part).encode("utf-8")
    return hashlib.sha256(bytes(body)).hexdigest()[:12]


class Spinner:
    """Small deterministic pseudo random source."""

    def __init__(self, seed):
        self.state = (int(seed) * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)

    def next(self):
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return (self.state >> 17) & 0xFFFFFFFF

    def below(self, limit):
        return self.next() % int(limit)

    def between(self, low, high):
        return low + self.below(high - low + 1)

    def pick(self, seq):
        return seq[self.below(len(seq))]


def xorshift(seed):
    """Deterministic 32 bit stream used to derive block orderings."""
    state = (int(seed) * 2654435761 + 1013904223) & 0xFFFFFFFF
    if state == 0:
        state = 0x9E3779B9
    while True:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        yield state


def weave_order(offset, number, block, width):
    """Permutation applied to the payload lines inside one block."""
    stream = xorshift(int(offset) + 97 * int(number) + 7 * int(block))
    order = list(range(width))
    for position in range(width - 1, 0, -1):
        swap = next(stream) % (position + 1)
        order[position], order[swap] = order[swap], order[position]
    return order


def rotate_left(body, amount):
    amount = amount % len(body)
    return body[amount:] + body[:amount]


def entry_check(body):
    return wire_prf("entry", *list(body[:10]))[:2]


def pack_entry(tick, index, kind, amount, mark, flipped):
    """Build the twelve byte payload for one entry."""
    order = "little" if flipped else "big"
    body = bytearray()
    body += int(tick % TICK_FIELD).to_bytes(2, order)
    body += int(index).to_bytes(2, order)
    body += bytes([int(kind) & 0xFF])
    body += int(amount).to_bytes(4, order)
    body += bytes([int(mark) & 0xFF])
    body += entry_check(body)
    return bytes(body)


def unpack_entry(body, flipped):
    order = "little" if flipped else "big"
    if entry_check(body) != body[10:12]:
        return None
    return {
        "tick": int.from_bytes(body[0:2], order),
        "index": int.from_bytes(body[2:4], order),
        "kind": body[4],
        "amount": int.from_bytes(body[5:9], order),
        "mark": body[9],
    }


def escape_payload(body, sentinel):
    out = bytearray()
    for byte in body:
        out.append(byte)
        if byte == sentinel:
            out.append(byte)
    return bytes(out)


def unescape_payload(body, sentinel):
    out = bytearray()
    position = 0
    while position < len(body):
        byte = body[position]
        out.append(byte)
        position += 1
        if byte == sentinel:
            if position >= len(body) or body[position] != sentinel:
                return None
            position += 1
    return bytes(out)


def step_ticks(ticks):
    """Forward second difference over a tick sequence."""
    stored = []
    for position, tick in enumerate(ticks):
        if position == 0:
            stored.append(tick % TICK_FIELD)
        elif position == 1:
            stored.append((tick - ticks[0]) % TICK_FIELD)
        else:
            stored.append((tick - 2 * ticks[position - 1] + ticks[position - 2]) % TICK_FIELD)
    return stored


def unstep_ticks(stored):
    ticks = []
    for position, value in enumerate(stored):
        if position == 0:
            ticks.append(value % TICK_FIELD)
        elif position == 1:
            ticks.append((value + ticks[0]) % TICK_FIELD)
        else:
            ticks.append((value + 2 * ticks[position - 1] - ticks[position - 2]) % TICK_FIELD)
    return ticks


def donor_table(plan, number, shift):
    """Word table the aliased index of one capture is read against."""
    donor = plan["captures"][(number + shift) % RING_SIZE]
    table = list(donor["words"])
    return rotate_left(table, shift % len(table))


def _roster_rows(spinner, tweak):
    """Identity register rows: word, charter, opened, closed, successor."""
    rows = []
    for position, word in enumerate(WORDS):
        charter = CHARTERS[position % len(CHARTERS)]
        opened = spinner.between(40, 3600)
        rows.append({"word": word, "charter": charter, "opened": opened,
                     "closed": 0, "successor": ""})
    chains = ((3, 4), (8, 9), (9, 10), (13, 14), (14, 15), (15, 16), (20, 21))
    for head, heir in chains:
        rows[head]["closed"] = spinner.between(700, 900) + head * 30
        rows[head]["successor"] = rows[heir]["word"]
    for step in range(3):
        row = rows[2 + step * 7]
        row["closed"] = spinner.between(700, 2400)
    rows[11]["closed"] = 1500
    rows[11]["successor"] = rows[11]["word"]
    if tweak == "deepchain":
        rows[6]["closed"] = 800
        rows[6]["successor"] = rows[7]["word"]
        rows[7]["closed"] = 1200
        rows[7]["successor"] = rows[8]["word"]
        rows[8]["closed"] = 1600
        rows[8]["successor"] = rows[9]["word"]
    if tweak == "emptycharter":
        for row in rows:
            if row["charter"] == CHARTERS[4]:
                row["closed"] = 30
                row["successor"] = ""
    if tweak == "scale":
        for row in rows:
            row["opened"] = row["opened"] * 7
    return rows


def _schedule_rows(spinner, tweak):
    rows = []
    edge = 1
    for window in range(6):
        span = spinner.between(420, 700)
        rows.append({"window": "W%d" % (window + 1), "first_tick": edge,
                     "last_tick": edge + span, "live": 1})
        edge += span + spinner.between(3, 40)
    rows[4]["live"] = 0
    rows.append({"window": "W7", "first_tick": 3900, "last_tick": 3200, "live": 1})
    if tweak == "boundary":
        rows[0]["last_tick"] = rows[0]["last_tick"] + 1
    if tweak == "degenerate":
        rows[6]["first_tick"] = 2400
        rows[6]["last_tick"] = 3900
    if tweak == "deadwindow":
        rows[1]["live"] = 0
    return rows


def _draw_entries(spinner, count, tweak, echoed, heft=1):
    entries = []
    for position in range(count):
        entries.append({
            "tick": spinner.between(60, 3980),
            "unit": spinner.pick(WORDS),
            "kind": spinner.below(4),
            "amount": spinner.between(12, 400) * heft,
            "mark": spinner.below(3),
            "echo": False,
        })
    for position in range(len(entries)):
        if entries[position]["kind"] == 3 and position < 3:
            entries[position]["kind"] = spinner.below(3)
    if echoed:
        for position in range(5, len(entries), 6):
            entries[position]["echo"] = True
    if tweak == "cap":
        for position in range(0, len(entries), 3):
            if entries[position]["kind"] in (0, 2):
                entries[position]["amount"] = 60000
    if tweak == "reversalflip":
        for position in range(1, len(entries), 4):
            entries[position]["kind"] = 3
    if tweak == "tiebreak":
        for entry in entries:
            entry["mark"] = 0
    if tweak == "partition":
        for entry in entries:
            entry["tick"] = ((entry["tick"] * 3) % 3900) + 60
    if tweak == "newunit":
        for entry in entries:
            entry["unit"] = WORDS[WORDS.index(entry["unit"]) % 6]
    return entries


def _capture_widths(spinner, total, padded_slots):
    widths = []
    placed = 0
    while placed < total:
        width = min(spinner.between(5, 11), total - placed)
        widths.append(width)
        placed += width
    if not widths:
        widths = [0]
    widths[0] = widths[0] + padded_slots
    return widths


DRAW_ATTEMPTS = 24


def drawn_values(seed, attempt):
    """The eleven quantities one capture set is written with; held-out sets draw their own."""
    if int(seed) == CHALLENGE_SEED:
        return dict(TRUE_VALUES)
    values = {}
    for name in PIN_ORDER:
        digest = hashlib.sha256(("%d:%d:%s" % (int(seed), attempt, name)).encode("ascii")).hexdigest()
        values[name] = CANDIDATES[name][int(digest[:8], 16) % len(CANDIDATES[name])]
    return values


def pins_separate(plan):
    """Whether every live control picks its own quantity out of the published candidate set."""
    for position, name in enumerate(PIN_ORDER):
        settled = single_control(plan, plan["values"], position)
        matches = []
        for rival in CANDIDATES[name]:
            swapped = dict(plan["values"])
            swapped[name] = rival
            if single_control(plan, swapped, position) == settled:
                matches.append(rival)
        if matches != [plan["values"][name]] and len(matches) != len(CANDIDATES[name]):
            return False
    return True


def class_draws_renamed(plan, cadence):
    """Whether the graded class holds a short draw on a charter its unit was renamed into."""
    for row in plan["settled_rows"]:
        if plan["units"][row["unit"]]["cadence"] != cadence:
            continue
        if row["opening_charter"] != row["charter"] and row["settled_amount"] < row["amount"]:
            return True
    return False


def replay_plan(seed, tweak=None):
    """Build one capture set, redrawing held-out quantities until every live control separates them."""
    graded = tweak[1] if isinstance(tweak, tuple) and tweak[0] == "class" else None
    for attempt in range(DRAW_ATTEMPTS):
        plan = _replay_draw(seed, tweak, drawn_values(seed, attempt))
        if int(seed) == CHALLENGE_SEED:
            return plan
        if pins_separate(plan) and (graded is None or class_draws_renamed(plan, graded)):
            return plan
    raise AssertionError("no draw for seed %d separates every quantity; widen the candidate sets"
                         % int(seed))


def _replay_draw(seed, tweak, values):
    """Build one complete capture set and every visible companion table."""
    spinner = Spinner(seed)
    if isinstance(tweak, tuple) and tweak[0] == "value":
        values[tweak[1]] = tweak[2]
    plan = {"seed": int(seed), "tweak": tweak, "values": values}
    plan["roster"] = _roster_rows(spinner, tweak)
    plan["schedule"] = _schedule_rows(spinner, tweak)
    population = 34
    if tweak == "population":
        population = 58
    captures = []
    only = None
    if isinstance(tweak, tuple) and tweak[0] == "only":
        only = tweak[1]
    if isinstance(tweak, tuple) and tweak[0] == "damage":
        only = DAMAGE_FLAGS[tweak[1]]
    # Single-transform and damaged sets keep every charter far under its
    # allowance, so they grade the decode and not the allowance rules. The
    # tiebreak set stays light too, so the entry its reversal strikes is not
    # hidden behind an allowance that would have capped it anyway.
    light = only is not None or tweak == "tiebreak"
    heft = 1 if int(seed) == CHALLENGE_SEED or light else HELD_OUT_HEFT
    for name, number, flags in CAPTURE_RING:
        if only is not None and flags:
            flags = only
        count = population + spinner.below(5)
        entries = _draw_entries(spinner, count, tweak, bool(flags & BIT_ECHOED), heft)
        words = []
        for entry in entries:
            if entry["unit"] not in words:
                words.append(entry["unit"])
        for word in WORDS:
            if word not in words:
                words.append(word)
        if tweak == "donorretire":
            words = rotate_left(words, 5)
        captures.append({"name": name, "number": number, "flags": flags,
                         "entries": entries, "words": words})
    plan["captures"] = captures
    if _grades_order(plan):
        _plant_divergence(plan)
    _plant_tweak_seats(plan)
    _plant_damage(plan)
    for capture in captures:
        padded = values["shadow_pad_base"] - 3 if capture["flags"] & BIT_SHADOWED else 0
        capture["widths"] = _capture_widths(spinner, len(capture["entries"]), padded)
    _resolve_echoes(plan)
    _fit_plan(plan)
    if tweak == "split":
        _split_window(plan)
        _fit_plan(plan)
    if not _grades_order(plan):
        _settle_one_order(plan)
    if only is not None:
        _check_unbound(plan)
    plan["bench"] = _bench_rows(spinner, plan)
    for capture in captures:
        capture["text"] = encode_capture(plan, capture, values)
    if isinstance(tweak, tuple) and tweak[0] == "damage":
        _check_damage(plan)
    return plan


def _check_unbound(plan):
    """Bound: no charter allowance can bind, under any reading of whose allowance pays."""
    count = {}
    for row in plan["roster"]:
        count[row["charter"]] = count.get(row["charter"], 0) + 1
    for key in ("charter", "opening_charter"):
        drawn = {}
        for row in plan["live_rows"]:
            drawn[row[key]] = drawn.get(row[key], 0) + row["amount"]
        for charter, total in drawn.items():
            if total > plan["baseline"][charter] * count[charter]:
                raise AssertionError("seed %d: charter %s draws %d, over its allowance"
                                     % (plan["seed"], charter, total))


def _plant_damage(plan):
    """Named repair: break the payloads one damaged set is about.

    The index set writes some unit indices one to three list lengths too high.
    Every other damaged set marks two entries per flagged capture as ghosts:
    the encoder breaks their payloads so they read back as `none`, and they
    never reach the walk.
    """
    tweak = plan["tweak"]
    if not (isinstance(tweak, tuple) and tweak[0] == "damage"):
        return
    for capture in plan["captures"]:
        if not capture["flags"]:
            continue
        entries = capture["entries"]
        if tweak[1] == "index":
            for ordinal in range(3, len(entries), 4):
                entries[ordinal]["lap"] = 1 + ordinal % 3
            continue
        for ordinal in (4, len(entries) // 2 + 1):
            entries[ordinal]["ghost"] = True
            entries[ordinal]["echo"] = False


def _check_damage(plan):
    """Bound: every ghost decodes to `none` and every other entry to its own fields."""
    wanted = []
    for capture in plan["captures"]:
        if capture["flags"] & BIT_ECHOED and any(entry.get("ghost") for entry in capture["entries"]):
            raise AssertionError("seed %d: a ghost sits in an echoed capture" % plan["seed"])
        seats = []
        for entry in capture["entries"]:
            if entry.get("ghost"):
                seats.append("none")
            else:
                seats.append("%d/%s/%d/%d/%d" % (entry["tick"] % TICK_FIELD, entry["unit"],
                                                 entry["kind"], entry["amount"], entry["mark"]))
        wanted.append("%d:%s" % (capture["number"], ",".join(seats)))
    if _peel(plan, plan["values"], 9) != wanted:
        raise AssertionError("seed %d: the damaged captures do not decode as planted" % plan["seed"])


def _split_window(plan):
    """Split the live window holding the first short draw so a renewal lands on that tick."""
    tick = plan["short_ticks"][0]
    for row in plan["schedule"]:
        if row["live"] and row["first_tick"] < tick <= row["last_tick"]:
            plan["schedule"].append({"window": "W8", "first_tick": tick,
                                     "last_tick": row["last_tick"], "live": 1})
            row["last_tick"] = tick - 1
            return
    raise AssertionError("no live window holds the first short draw")


def _grades_order(plan):
    """The shipped set and the reversal density and tiebreak sets grade the cancellation order."""
    return plan["seed"] == CHALLENGE_SEED or plan["tweak"] in ("reversalflip", "tiebreak")


def _settle_one_order(plan):
    """Named repair: every other set settles alike under either cancellation order.

    The first reversal on which the two orders part becomes a plain entry of
    the kind it names, at its root slot so its echoes follow, until no reversal
    parts them.
    """
    span = plan["values"]["echo_window_span"]
    while plan["first_divergence"] >= 0:
        row = plan["live_rows"][plan["first_divergence"]]
        entries = [capture["entries"] for capture in plan["captures"]
                   if capture["number"] == row["number"]][0]
        position = row["ordinal"]
        while entries[position]["echo"]:
            position -= (position % (span - 1)) + 1
        entries[position]["kind"] = entries[position]["mark"]
        _resolve_echoes(plan)
        _fit_plan(plan)


def _plant_divergence(plan):
    """Named repair: force the two cancellation orders to part on one unit."""
    settled = None
    for row in plan["roster"]:
        if not row["closed"] and not row["successor"]:
            settled = row["word"]
            break
    if settled is None:
        return
    window = None
    for row in plan["schedule"]:
        if row["live"] and row["first_tick"] <= row["last_tick"] - 40:
            window = row
            break
    if window is None:
        return
    capture = plan["captures"][3]
    entries = capture["entries"]
    if len(entries) < 12:
        return
    seats = [len(entries) - 9, len(entries) - 7, len(entries) - 5, len(entries) - 3]
    amounts = [101, 202, 303, 1]
    kinds = [0, 0, 0, 3]
    for step, seat in enumerate(seats):
        entry = entries[seat]
        entry["echo"] = False
        entry["unit"] = settled
        entry["kind"] = kinds[step]
        entry["amount"] = amounts[step]
        entry["mark"] = 0
        entry["tick"] = window["last_tick"] - 18 + step * 4


def _plant_tweak_seats(plan):
    """Named repair: seat the entries two mutants need for their rule to matter.

    The tiebreak set gets two entries of one unit and kind at one tick in two
    captures, the lower capture holding the later entry ordinal, then a reversal
    of that kind, so only capture ordinal ahead of entry ordinal cancels the
    right one. The boundary set gets one entry on the moved window edge.
    """
    tweak = plan["tweak"]
    if tweak not in ("tiebreak", "boundary"):
        return
    settled = None
    for row in plan["roster"]:
        if not row["closed"] and not row["successor"]:
            settled = row["word"]
            break
    if settled is None:
        return

    def seat(number, position, tick, kind, amount, mark):
        entry = plan["captures"][number]["entries"][position]
        entry["echo"] = False
        entry["unit"] = settled
        entry["kind"] = kind
        entry["amount"] = amount
        entry["mark"] = mark
        entry["tick"] = tick

    if tweak == "tiebreak":
        seat(1, 2, 30, 2, 111, 0)
        seat(2, 0, 30, 2, 222, 0)
        seat(1, 3, 34, 3, 5, 2)
    else:
        seat(1, 0, plan["schedule"][0]["last_tick"], 0, 77, 0)


def _resolve_echoes(plan):
    """Give every echo slot the payload it inherits from earlier in its capture."""
    span = plan["values"]["echo_window_span"]
    for capture in plan["captures"]:
        entries = capture["entries"]
        for position, entry in enumerate(entries):
            if not entry["echo"]:
                continue
            distance = (position % (span - 1)) + 1
            if position - distance < 0:
                entry["echo"] = False
                continue
            source = entries[position - distance]
            entry["unit"] = source["unit"]
            entry["kind"] = source["kind"]
            entry["amount"] = source["amount"]
            entry["mark"] = source["mark"]


def encode_capture(plan, capture, values):
    """Render one capture to its wire text under the given constants."""
    number = capture["number"]
    flags = capture["flags"]
    entries = capture["entries"]
    widths = capture["widths"]
    blocks = len(widths)
    padded_slots = values["shadow_pad_base"] - 3 if flags & BIT_SHADOWED else 0
    ticks = []
    for entry in entries:
        if entry.get("ghost") and flags & BIT_STEPPED:
            # A ghost's tick is the one its stored 0 steps to.
            ticks.append(0 if not ticks else ticks[0] if len(ticks) == 1
                         else 2 * ticks[-1] - ticks[-2])
        else:
            ticks.append(entry["tick"])
    stored_ticks = step_ticks(ticks) if flags & BIT_STEPPED \
        else [tick % TICK_FIELD for tick in ticks]
    table = donor_table(plan, number, values["alias_donor_shift"]) \
        if flags & BIT_ALIASED else list(WORDS)
    flipped_block = number % blocks if flags & BIT_FLIPPED else -1

    placement = []
    cursor = 0
    for block, width in enumerate(widths):
        true_width = width - padded_slots if block == 0 else width
        placement.append((block, list(range(cursor, cursor + true_width))))
        cursor += true_width

    payloads = {}
    previous = (0, 0)
    for block, slots in placement:
        for ordinal in slots:
            entry = entries[ordinal]
            flip = block == flipped_block
            if entry["echo"]:
                body = pack_entry(stored_ticks[ordinal], 0, ECHO_MARK, 0, 0, flip)
            else:
                index = table.index(entry["unit"]) + len(table) * entry.get("lap", 0)
                body = pack_entry(stored_ticks[ordinal], index, entry["kind"],
                                  entry["amount"], entry["mark"], flip)
            if entry.get("ghost"):
                body = body[:11] + bytes([body[11] ^ 0xFF])
            keep = (int.from_bytes(body[0:2], "little" if flip else "big"),
                    int.from_bytes(body[5:9], "little" if flip else "big"))
            if flags & BIT_SPUN:
                body = rotate_left(body, ((ordinal + 1) * values["spin_modulus"]) % PAYLOAD_WIDTH)
            if flags & BIT_SEALED:
                pad = wire_prf(LABELS[values["seal_label_index"]], number, ordinal)[:PAYLOAD_WIDTH]
                body = bytes(a ^ b for a, b in zip(body, pad))
            if flags & BIT_CHAINED:
                pad = wire_prf("chain", number, previous[0], previous[1])[:PAYLOAD_WIDTH]
                body = bytes(a ^ b for a, b in zip(body, pad))
            previous = (0, 0) if entry.get("ghost") else keep
            payloads[ordinal] = (block, body, bool(entry.get("ghost")))

    lines = {}
    ghosts = 0
    for block, slots in placement:
        row = [payloads[ordinal][1:] for ordinal in slots]
        if block == 0 and padded_slots:
            for filler in range(padded_slots):
                row.append((wire_prf("filler", number, filler)[:PAYLOAD_WIDTH], False))
        dressed = []
        for body, ghost in row:
            if flags & BIT_DRIFTED:
                pad = wire_prf("drift", number, (block + 1 + 5 * number) % values["drift_modulus"])[:PAYLOAD_WIDTH]
                body = bytes(a ^ b for a, b in zip(body, pad))
            if flags & BIT_WARDED:
                body = escape_payload(body, values["sentinel_code_value"])
                if ghost:
                    # One ghost comes out short, the next holds a lone reserved byte.
                    ghosts += 1
                    body = body[:-1] if ghosts % 2 else body + bytes([values["sentinel_code_value"]])
            dressed.append(body)
        if flags & BIT_WOVEN:
            order = weave_order(values["weave_seed_offset"], number, block, len(dressed))
            woven = [None] * len(dressed)
            for position in range(len(dressed)):
                woven[position] = dressed[order[position]]
            dressed = woven
        lines[block] = dressed

    total_lines = sum(len(lines[block]) for block in range(blocks))
    bias = ((3 * number + 1) % values["frame_bias_limit"]) if flags & BIT_PADDED else 0
    seal = wire_prf("seal", number, len(entries)).hex()[:8]
    out = ["#RPL1 capture=%s number=%d flags=0x%04x blocks=%d frames=%d words=%s seal=%s"
           % (capture["name"].split(".")[0], number, flags, blocks,
              total_lines + bias, ",".join(capture["words"]), seal)]
    for block in range(blocks):
        check = "%04x" % int.from_bytes(wire_prf("check", number, block, widths[block])[:2], "big")
        out.append("B %d %d %s" % (block, widths[block], check))
        for body in lines[block]:
            out.append("R " + body.hex())
    return "\n".join(out) + "\n"


def parse_capture(text):
    """Read a capture back into its header fields and block line lists."""
    head = None
    blocks = []
    for line in text.splitlines():
        if line.startswith("#RPL1 "):
            head = {}
            for piece in line[6:].split(" "):
                key, _, value = piece.partition("=")
                head[key] = value
            continue
        if line.startswith("B "):
            _, ordinal, width, check = line.split(" ")
            blocks.append({"ordinal": int(ordinal), "width": int(width),
                           "check": check, "lines": []})
            continue
        if line.startswith("R "):
            blocks[-1]["lines"].append(bytes.fromhex(line[2:]))
    return {"number": int(head["number"]), "flags": int(head["flags"], 16),
            "blocks": int(head["blocks"]), "frames": int(head["frames"]),
            "words": head["words"].split(","), "seal": head["seal"],
            "body": blocks}


def _roster_map(plan):
    return {row["word"]: row for row in plan["roster"]}


def canonical_identity(table, word, tick):
    """Carry one recorded word to the identity in force at that tick."""
    current = word
    for _ in range(STATE_BOUND):
        row = table.get(current)
        if row is None:
            return None
        if row["successor"] == current:
            return (current, row["charter"])
        if row["closed"] == 0 or tick <= row["closed"]:
            return (current, row["charter"])
        if not row["successor"]:
            return None
        current = row["successor"]
    raise AssertionError("identity chase exceeded the state bound")


def settling_passes(rows):
    """Sweeps the register takes before no canonical charter is stale."""
    charter_of = {row["word"]: row["charter"] for row in rows}
    passes = 0
    while passes < STATE_BOUND:
        passes += 1
        changed = False
        for row in rows:
            heir = row["successor"]
            if heir and heir != row["word"] and charter_of[row["word"]] != charter_of[heir]:
                charter_of[row["word"]] = charter_of[heir]
                changed = True
        if not changed:
            return passes
    raise AssertionError("identity register did not settle")


def live_windows(plan):
    out = []
    for row in plan["schedule"]:
        if row["live"] and row["first_tick"] <= row["last_tick"]:
            out.append((row["first_tick"], row["last_tick"]))
    return out


def admits(windows, tick):
    for first, last in windows:
        if first <= tick <= last:
            return True
    return False


def walk_entries(plan):
    """Every decoded entry in tick, capture, ordinal order."""
    rows = []
    for capture in plan["captures"]:
        for ordinal, entry in enumerate(capture["entries"]):
            if entry.get("ghost"):
                continue
            rows.append({"tick": entry["tick"], "number": capture["number"],
                         "ordinal": ordinal, "word": entry["unit"],
                         "kind": entry["kind"], "amount": entry["amount"],
                         "mark": entry["mark"], "echo": entry["echo"]})
    rows.sort(key=lambda row: (row["tick"], row["number"], row["ordinal"]))
    return rows


def _fit_plan(plan):
    """Derive the settlement the engine rules imply for this capture set."""
    table = _roster_map(plan)
    windows = live_windows(plan)
    baseline = {}
    opened_count = {}
    for row in plan["roster"]:
        baseline[row["charter"]] = baseline.get(row["charter"], 0) + row["opened"]
        opened_count[row["charter"]] = opened_count.get(row["charter"], 0) + 1
    totalbase = sum(baseline.values())
    plan["baseline"] = baseline
    plan["totalbase"] = totalbase
    plan["settling_passes"] = settling_passes(plan["roster"])

    rows = walk_entries(plan)
    decoded_amount = sum(row["amount"] for row in rows)
    reversal_count = sum(1 for row in rows if row["kind"] == 3)

    dropped_retired = 0
    dropped_offwindow = 0
    dropped_amount = 0
    live_rows = []
    for row in rows:
        seat = canonical_identity(table, row["word"], row["tick"])
        if seat is None:
            dropped_retired += 1
            dropped_amount += row["amount"]
            continue
        if not admits(windows, row["tick"]):
            dropped_offwindow += 1
            dropped_amount += row["amount"]
            continue
        row["unit"] = seat[0]
        row["charter"] = seat[1]
        row["opening_charter"] = table[row["word"]]["charter"]
        live_rows.append(row)

    queues = {}
    promoted = 0
    first_divergence = -1
    shadow_queues = {}
    for position, row in enumerate(live_rows):
        row["settled_kind"] = None
        if row["kind"] == 3:
            key = (row["unit"], row["mark"])
            queue = queues.get(key)
            if queue:
                victim = queue.pop(0)
                victim["settled_kind"] = None
                victim["cancelled"] = True
            else:
                promoted += 1
                row["settled_kind"] = row["mark"]
                queues.setdefault(key, []).append(row)
        else:
            row["settled_kind"] = row["kind"]
            queues.setdefault((row["unit"], row["kind"]), []).append(row)
    mirror = {}
    for position, row in enumerate(live_rows):
        if row["kind"] == 3:
            key = (row["unit"], row["mark"])
            early = shadow_queues.get(key)
            late = mirror.get(key)
            taken = early.pop(0) if early else None
            other = late.pop() if late else None
            if taken is not other and first_divergence < 0:
                first_divergence = position
            if taken is None:
                shadow_queues.setdefault(key, []).append(row)
            if other is None:
                mirror.setdefault(key, []).append(row)
        else:
            shadow_queues.setdefault((row["unit"], row["kind"]), []).append(row)
            mirror.setdefault((row["unit"], row["kind"]), []).append(row)
    plan["reversal_count"] = reversal_count
    plan["promoted_reversal_count"] = promoted
    plan["first_divergence"] = first_divergence

    settled = [row for row in live_rows if row["settled_kind"] is not None]
    allowance = {name: Fraction(baseline[name] * opened_count[name]) for name in baseline}
    openings = sorted(first for first, _ in windows)
    remaining = {}
    short_draws = 0
    plan["short_ticks"] = []
    units = {}
    for row in settled:
        epoch = max(first for first in openings if first <= row["tick"])
        key = (row["charter"], epoch)
        left = remaining.get(key, allowance[row["charter"]])
        amount = min(Fraction(row["amount"]), left)
        remaining[key] = left - amount
        if amount < row["amount"]:
            short_draws += 1
            plan["short_ticks"].append(row["tick"])
        row["settled_amount"] = amount
        seat = units.setdefault(row["unit"], {
            "unit": row["unit"], "charter": row["charter"],
            "tick_total": 0, "amount_total": Fraction(0),
            "kind_totals": [Fraction(0), Fraction(0), Fraction(0)]})
        seat["charter"] = row["charter"]
        seat["tick_total"] += row["tick"]
        seat["amount_total"] += amount
        seat["kind_totals"][row["settled_kind"]] += amount

    settled_amount = sum((row["settled_amount"] for row in settled), Fraction(0))
    plan["settled_rows"] = settled
    plan["short_draws"] = short_draws
    plan["live_rows"] = live_rows
    plan["units"] = units
    plan["decoded_amount"] = Fraction(decoded_amount)
    plan["settled_amount"] = settled_amount
    plan["dropped_amount"] = Fraction(dropped_amount)
    plan["dropped_retired"] = dropped_retired
    plan["dropped_offwindow"] = dropped_offwindow
    plan["entry_total"] = len(rows)
    plan["settled_total"] = len(settled)

    flow = {}
    for row in settled:
        if row["settled_kind"] != 1:
            continue
        giver = row["opening_charter"]
        taker = row["charter"]
        if giver == taker:
            continue
        flow[(giver, taker)] = flow.get((giver, taker), Fraction(0)) + row["settled_amount"]
    charters = sorted(baseline)
    share = {}
    for giver in charters:
        for taker in charters:
            if giver == taker:
                continue
            share[(giver, taker)] = flow.get((giver, taker), Fraction(0)) / Fraction(totalbase)
    plan["share"] = share
    plan["charters"] = charters
    plan["stocks"] = _exact_stocks(charters, baseline, share)

    span = plan["values"]["cadence_modulus"]
    for seat in units.values():
        seat["cadence"] = CLASSES[(seat["tick_total"] // span) % 4]

    depth = {}
    for row in plan["roster"]:
        chase = 0
        current = row["word"]
        while True:
            node = table[current]
            if node["successor"] and node["successor"] != current and node["closed"]:
                chase += 1
                current = node["successor"]
                if chase > STATE_BOUND:
                    raise AssertionError("identity chase exceeded the state bound")
                continue
            break
        depth[row["word"]] = chase
    deepest = min(sorted(depth), key=lambda word: (-depth[word], word))
    plan["deepest_identity"] = deepest
    plan["deepest_depth"] = depth[deepest]

    echo_census = sum(1 for capture in plan["captures"]
                      for entry in capture["entries"] if entry["echo"])
    plan["echo_census"] = echo_census
    return plan


def _exact_stocks(charters, baseline, share):
    """Solve the coupled charter relations exactly."""
    size = len(charters)
    index = {name: position for position, name in enumerate(charters)}
    matrix = []
    for taker in charters:
        row = [Fraction(0)] * (size + 1)
        row[index[taker]] = Fraction(1)
        for giver in charters:
            if giver == taker:
                continue
            row[index[giver]] -= share[(giver, taker)]
        row[size] = Fraction(baseline[taker])
        matrix.append(row)
    for column in range(size):
        pivot = None
        for candidate in range(column, size):
            if matrix[candidate][column] != 0:
                pivot = candidate
                break
        if pivot is None:
            raise AssertionError("the charter relations admit no unique assignment")
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        lead = matrix[column][column]
        matrix[column] = [value / lead for value in matrix[column]]
        for other in range(size):
            if other == column:
                continue
            factor = matrix[other][column]
            if factor == 0:
                continue
            matrix[other] = [a - factor * b for a, b in zip(matrix[other], matrix[column])]
    return {name: matrix[index[name]][size] for name in charters}


def _bench_rows(spinner, plan):
    """Bench candidate list whose one exact subset meets the upkeep target."""
    target = plan["values"]["upkeep_target_scale"] * plan["totalbase"]
    low = max(1, target // 14)
    high = max(low + 1, target // 6)
    names = ["bench-%02d" % (position + 1) for position in range(16)]
    upkeep = [spinner.between(low, high) for _ in range(16)]
    picked = []
    while len(picked) < 6:
        choice = spinner.below(16)
        if choice not in picked:
            picked.append(choice)
    picked.sort()
    rest = sum(upkeep[position] for position in picked[:-1])
    upkeep[picked[-1]] = target - rest
    for _ in range(400):
        if upkeep[picked[-1]] > 0 and _subset_count(upkeep, target) == 1:
            break
        free = [position for position in range(16) if position not in picked]
        upkeep[free[spinner.below(len(free))]] += 1
        rest = sum(upkeep[position] for position in picked[:-1])
        upkeep[picked[-1]] = target - rest
    if upkeep[picked[-1]] <= 0 or _subset_count(upkeep, target) != 1:
        raise AssertionError("the bench candidate list admits no single exact subset; "
                             "plant a separating upkeep figure")
    return [{"word": names[position], "upkeep": upkeep[position]} for position in range(16)]


def _subset_count(values, target):
    reach = {0: 1}
    for value in values:
        nxt = dict(reach)
        for total, count in reach.items():
            step = total + value
            if step <= target:
                nxt[step] = nxt.get(step, 0) + count
        reach = nxt
        if len(reach) > STATE_BOUND:
            raise AssertionError("subset search exceeded the state bound")
    return reach.get(target, 0)


def bench_pick(rows, target):
    """The one candidate subset whose upkeep meets the target exactly."""
    values = [row["upkeep"] for row in rows]
    reach = {0: []}
    for position, value in enumerate(values):
        nxt = dict(reach)
        for total, chosen in reach.items():
            step = total + value
            if step <= target and step not in nxt:
                nxt[step] = chosen + [position]
        reach = nxt
    if target not in reach:
        raise AssertionError("no bench subset meets the upkeep target")
    return sorted(rows[position]["word"] for position in reach[target])


def fraction_text(value):
    value = Fraction(value)
    return "%d/%d" % (value.numerator, value.denominator)


def _peel(plan, values, depth):
    """Partial decode of every capture down to one rung of the pinning ladder."""
    marks = []
    for capture in plan["captures"]:
        parsed = parse_capture(capture["text"])
        number = parsed["number"]
        flags = parsed["flags"]
        if depth == 1:
            bias = ((3 * number + 1) % values["frame_bias_limit"]) if flags & BIT_PADDED else 0
            marks.append("%d:%d" % (number, bias))
            continue
        blocks = []
        for block in parsed["body"]:
            lines = list(block["lines"])
            if flags & BIT_WOVEN:
                order = weave_order(values["weave_seed_offset"], number,
                                    block["ordinal"], len(lines))
                plain = [None] * len(lines)
                for position in range(len(lines)):
                    plain[order[position]] = lines[position]
                lines = plain
            blocks.append(lines)
        if depth == 2:
            marks.append("%d:%s" % (number, ",".join(b.hex() for row in blocks for b in row)))
            continue
        opened = []
        for row in blocks:
            out = []
            for body in row:
                if flags & BIT_WARDED:
                    body = unescape_payload(body, values["sentinel_code_value"])
                    if body is None or len(body) != PAYLOAD_WIDTH:
                        body = bytes(PAYLOAD_WIDTH)
                out.append(body)
            opened.append(out)
        if depth == 3:
            marks.append("%d:%s" % (number, ",".join(b.hex() for row in opened for b in row)))
            continue
        eased = []
        for ordinal, row in enumerate(opened):
            out = []
            for body in row:
                if flags & BIT_DRIFTED:
                    pad = wire_prf("drift", number,
                                   (ordinal + 1 + 5 * number) % values["drift_modulus"])[:PAYLOAD_WIDTH]
                    body = bytes(a ^ b for a, b in zip(body, pad))
                out.append(body)
            eased.append(out)
        if depth == 4:
            marks.append("%d:%s" % (number, ",".join(b.hex() for row in eased for b in row)))
            continue
        head = eased[0][0]
        if flags & BIT_CHAINED:
            pad = wire_prf("chain", number, 0, 0)[:PAYLOAD_WIDTH]
            head = bytes(a ^ b for a, b in zip(head, pad))
        if flags & BIT_SEALED:
            pad = wire_prf(LABELS[values["seal_label_index"]], number, 0)[:PAYLOAD_WIDTH]
            head = bytes(a ^ b for a, b in zip(head, pad))
        if depth == 5:
            marks.append("%d:%s" % (number, head.hex()))
            continue
        lead = head
        if flags & BIT_SPUN:
            lead = rotate_left(lead, PAYLOAD_WIDTH - (values["spin_modulus"] % PAYLOAD_WIDTH))
        flip = bool(flags & BIT_FLIPPED) and (0 == number % parsed["blocks"])
        seat = unpack_entry(lead, flip)
        if depth == 6:
            marks.append("%d:%s" % (number, "none" if seat is None else
                                    "%d/%d/%d/%d/%d" % (seat["tick"], seat["index"],
                                                        seat["kind"], seat["amount"],
                                                        seat["mark"])))
            continue
        slots = values["shadow_pad_base"] - 3 if flags & BIT_SHADOWED else 0
        stream = []
        for ordinal, row in enumerate(eased):
            keep = list(row)
            if ordinal == 0 and slots:
                keep = keep[:max(0, len(keep) - slots)]
            for body in keep:
                stream.append((ordinal, body))
        decoded = []
        previous = (0, 0)
        for index, pair in enumerate(stream):
            block_ordinal, body = pair
            if flags & BIT_CHAINED:
                pad = wire_prf("chain", number, previous[0], previous[1])[:PAYLOAD_WIDTH]
                body = bytes(a ^ b for a, b in zip(body, pad))
            if flags & BIT_SEALED:
                pad = wire_prf(LABELS[values["seal_label_index"]], number, index)[:PAYLOAD_WIDTH]
                body = bytes(a ^ b for a, b in zip(body, pad))
            if flags & BIT_SPUN:
                turn = ((index + 1) * values["spin_modulus"]) % PAYLOAD_WIDTH
                body = rotate_left(body, PAYLOAD_WIDTH - turn)
            flip = bool(flags & BIT_FLIPPED) and (block_ordinal == number % parsed["blocks"])
            seat = unpack_entry(body, flip)
            if seat is None:
                decoded.append(None)
                previous = (0, 0)
                continue
            previous = (seat["tick"], seat["amount"])
            decoded.append(seat)
        if depth == 7:
            marks.append("%d:%s" % (number, ",".join(
                "none" if seat is None else "%d/%d/%d/%d/%d"
                % (seat["tick"], seat["index"], seat["kind"], seat["amount"], seat["mark"])
                for seat in decoded)))
            continue
        stored = [0 if seat is None else seat["tick"] for seat in decoded]
        ticks = unstep_ticks(stored) if flags & BIT_STEPPED else stored
        table = donor_table(plan, number, values["alias_donor_shift"]) \
            if flags & BIT_ALIASED else list(WORDS)
        lifted = []
        for position, seat in enumerate(decoded):
            if seat is None:
                lifted.append(None)
                continue
            lifted.append({"tick": ticks[position],
                           "word": table[seat["index"] % len(table)],
                           "kind": seat["kind"], "amount": seat["amount"],
                           "mark": seat["mark"]})
        if depth == 8:
            marks.append("%d:%s" % (number, ",".join(
                "none" if seat is None else "%d/%s/%d/%d/%d"
                % (seat["tick"], seat["word"], seat["kind"], seat["amount"], seat["mark"])
                for seat in lifted)))
            continue
        span = values["echo_window_span"]
        for position, seat in enumerate(lifted):
            if seat is None or seat["kind"] != ECHO_MARK:
                continue
            distance = (position % (span - 1)) + 1
            source = lifted[position - distance] if position - distance >= 0 else None
            if source is None:
                continue
            seat["word"] = source["word"]
            seat["kind"] = source["kind"]
            seat["amount"] = source["amount"]
            seat["mark"] = source["mark"]
        marks.append("%d:%s" % (number, ",".join(
            "none" if seat is None else "%d/%s/%d/%d/%d"
            % (seat["tick"], seat["word"], seat["kind"], seat["amount"], seat["mark"])
            for seat in lifted)))
    return marks


def control_figures(plan, values=None):
    """The eleven published control figures for one capture set."""
    values = plan["values"] if values is None else values
    out = {}
    for depth in range(1, 10):
        out[CONTROL_NAMES[depth - 1]] = digest_of(_peel(plan, values, depth))
    span = values["cadence_modulus"]
    marks = []
    for word in sorted(plan["units"]):
        seat = plan["units"][word]
        marks.append("%s:%s" % (word, CLASSES[(seat["tick_total"] // span) % 4]))
    out[CONTROL_NAMES[9]] = digest_of(marks)
    out[CONTROL_NAMES[10]] = digest_of([fraction_text(values["upkeep_target_scale"] * plan["totalbase"])])
    return out


def single_control(plan, values, position):
    """One published control figure, without computing the other ten."""
    if position < 9:
        return digest_of(_peel(plan, values, position + 1))
    if position == 9:
        span = values["cadence_modulus"]
        marks = []
        for word in sorted(plan["units"]):
            seat = plan["units"][word]
            marks.append("%s:%s" % (word, CLASSES[(seat["tick_total"] // span) % 4]))
        return digest_of(marks)
    return digest_of([fraction_text(values["upkeep_target_scale"] * plan["totalbase"])])


def expected_reports(plan):
    """Every report the engine rules imply for this capture set."""
    values = plan["values"]
    units = plan["units"]
    ordered = [units[word] for word in sorted(units)]
    whole = {
        "capture_count": len(plan["captures"]),
        "entry_total": plan["entry_total"],
        "settled_total": plan["settled_total"],
        "units": [{
            "unit": seat["unit"],
            "charter": seat["charter"],
            "tick_total": seat["tick_total"],
            "amount_total": fraction_text(seat["amount_total"]),
            "cadence": seat["cadence"],
            "kind_totals": [fraction_text(part) for part in seat["kind_totals"]],
        } for seat in ordered],
    }
    reports = {"scenario_visible.json": whole}
    for name in CLASSES:
        members = [seat for seat in ordered if seat["cadence"] == name]
        reports["scenario_%s.json" % name] = {
            "cadence": name,
            "unit_count": len(members),
            "amount_total": fraction_text(sum((seat["amount_total"] for seat in members),
                                              Fraction(0))),
            "units": [{
                "unit": seat["unit"],
                "charter": seat["charter"],
                "tick_total": seat["tick_total"],
                "amount_total": fraction_text(seat["amount_total"]),
            } for seat in members],
        }
    reports["perf_report.json"] = {
        "charter_stocks": [{"charter": name, "stock": fraction_text(plan["stocks"][name])}
                           for name in plan["charters"]],
        "settled_total": fraction_text(plan["settled_amount"]),
        "decoded_total": fraction_text(plan["decoded_amount"]),
        "reversal_count": plan["reversal_count"],
        "promoted_reversal_count": plan["promoted_reversal_count"],
    }
    target = values["upkeep_target_scale"] * plan["totalbase"]
    bench = bench_pick(plan["bench"], target)
    carried = sum(row["upkeep"] for row in plan["bench"] if row["word"] in bench)
    reports["recommendations.json"] = {
        "target": fraction_text(target),
        "bench": bench,
        "bench_upkeep": fraction_text(carried),
        "residual_after_bench": fraction_text(target - carried),
    }
    reports["data_quality.json"] = {
        "dropped_retired": plan["dropped_retired"],
        "dropped_offwindow": plan["dropped_offwindow"],
        "dropped_amount_total": fraction_text(plan["dropped_amount"]),
        "decoded_amount_total": fraction_text(plan["decoded_amount"]),
        "settled_amount_total": fraction_text(plan["settled_amount"]),
        "conservation_residual": fraction_text(
            plan["decoded_amount"] - plan["settled_amount"] - plan["dropped_amount"]),
    }
    return reports


def record_schema_ok(record):
    """Whether the delivered derivation record carries the declared schema."""
    if not isinstance(record, dict):
        return False
    for key in ("quantities", "settling_passes", "calibration_table"):
        if key not in record:
            return False
    if not isinstance(record["settling_passes"], int):
        return False
    rows = record["quantities"]
    if not isinstance(rows, list) or len(rows) != len(PIN_ORDER):
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        for key in ("name", "value", "control", "rejected"):
            if key not in row:
                return False
        if not isinstance(row["rejected"], list):
            return False
        for item in row["rejected"]:
            if not isinstance(item, dict) or "candidate" not in item or "falsifier" not in item:
                return False
    table = record["calibration_table"]
    if not isinstance(table, list) or len(table) != len(CONTROL_NAMES):
        return False
    for row in table:
        if not isinstance(row, dict):
            return False
        for key in ("control", "published", "produced"):
            if key not in row:
                return False
    return True


def _roster_text(plan):
    out = ["word,charter,opened,closed,successor"]
    for row in plan["roster"]:
        out.append("%s,%s,%d,%s,%s" % (row["word"], row["charter"], row["opened"],
                                       "" if not row["closed"] else str(row["closed"]),
                                       row["successor"]))
    return "\n".join(out) + "\n"


def _schedule_text(plan):
    out = ["window,first_tick,last_tick,live"]
    for row in plan["schedule"]:
        out.append("%s,%d,%d,%d" % (row["window"], row["first_tick"],
                                    row["last_tick"], row["live"]))
    return "\n".join(out) + "\n"


def _bench_text(plan):
    out = ["word,upkeep"]
    for row in plan["bench"]:
        out.append("%s,%d" % (row["word"], row["upkeep"]))
    return "\n".join(out) + "\n"


CONTROL_PROSE = {
    "CTRL-A": "the frame bias the capture headers carry",
    "CTRL-B": "the payload line order inside every block",
    "CTRL-C": "the payload bytes once the reserved byte is unwrapped",
    "CTRL-D": "the payload bytes once the block mask is lifted",
    "CTRL-E": "the opening payload of every capture once the label mask is lifted",
    "CTRL-F": "the opening entry of every capture once its bytes are set straight",
    "CTRL-G": "every entry of every capture once the padding is set aside",
    "CTRL-H": "every entry once the recorded words are read against the right table",
    "CTRL-I": "every entry once the repeated slots take the payload they inherit",
    "CTRL-J": "the cadence class every surviving unit falls in",
    "CTRL-K": "the upkeep target the engine settles against",
}


FRAGMENT_RECIPE = [
    "",
    "## Fragments each control reads",
    "",
    "A control figure is stamped over the list of fragments its row below names, in",
    "the order given there.",
    "",
    "For CTRL-A through CTRL-I the list holds one fragment for every capture of the",
    "set, the captures whose flag word is zero included, in ascending capture",
    "ordinal. Each such fragment is the capture ordinal in decimal, a colon, and the",
    "body the row names. A step that undoes a transform acts only on a capture whose",
    "flag word sets that transform's bit; a capture with the bit clear passes",
    "through that step unchanged. Every quantity a step reads takes the value the",
    "figures ahead of it pinned, and the quantity the row pins takes the candidate",
    "under test.",
    "",
    "Terms used in the rows:",
    "",
    "- A payload list is the payload of every entry line of the capture, block by",
    "  block in the order the block lines appear and line by line inside each",
    "  block, every declared line counted, filler included. Each payload is written",
    "  in lowercase hexadecimal, two digits per byte, and the payloads are joined",
    "  by commas with no spaces.",
    "- To unpack a twelve-byte payload is to read it with the layout in the format",
    "  note: big endian, except that every multi-byte field is little endian inside",
    "  the flipped block of a flipped capture. A payload whose check field does not",
    "  match the ten bytes before it unpacks to nothing.",
    "- An entry text is the tick, the unit index, the kind, the amount and the mark",
    "  of an unpacked payload, each in decimal, joined by solidi with no spaces, as",
    "  in `40/3/1/2400/9`. A payload that unpacks to nothing is written `none`.",
    "- A word entry text is an entry text with the unit word in place of the unit",
    "  index, as in `40/hydra/1/2400/9`.",
    "",
    "Each capture's fragment body for CTRL-A through CTRL-I is the following.",
    "",
    "- CTRL-A: The frame bias: three times the capture ordinal plus one, taken",
    "  against `frame_bias_limit`, for a padded capture, and `0` for any other. An",
    "  unpadded capture of ordinal 1 gives `1:0`.",
    "",
    "- CTRL-B: The payload list once the woven lines of each block stand back in",
    "  place: the line read at restated position p moves to the position the",
    "  finished order records at p. A doubled reserved byte is still written twice.",
    "",
    "- CTRL-C: The CTRL-B payload list with every doubled reserved byte written",
    "  once. A payload that holds the reserved byte once on its own, or that does",
    "  not come out at twelve bytes, is written as twenty four zero digits.",
    "",
    "- CTRL-D: The CTRL-C payload list with every payload combined by exclusive or",
    "  with its block key, the `drift` mask over the capture ordinal and then the",
    "  block counter.",
    "",
    "- CTRL-E: One payload in lowercase hexadecimal: the first payload of block 0",
    "  in the CTRL-D list, combined by exclusive or with the `chain` mask over the",
    "  capture ordinal, 0 and 0 when the capture is chained, and with the mask of",
    "  the label word `seal_label_index` names over the capture ordinal and 0 when",
    "  it is sealed. Its rotation is not undone.",
    "",
    "- CTRL-F: One entry text: the CTRL-E payload rotated right by `spin_modulus`",
    "  taken against twelve when the capture is spun, then unpacked as if it stood",
    "  in block 0. The tick is the field as stored, a second difference in a",
    "  stepped capture.",
    "",
    "- CTRL-G: The entry text of every entry, joined by commas in entry ordinal",
    "  order. The entries are the CTRL-D payloads block by block, less the filler",
    "  of a shadowed capture, which is the last `shadow_pad_base` less three",
    "  payloads of block 0 (all of block 0 when it holds no more), and entry",
    "  ordinals count them from zero. Each payload in turn is combined by exclusive",
    "  or with the `chain` mask over the capture ordinal and the stored tick and",
    "  amount of the entry before it (0 and 0 for the first entry and for an entry",
    "  after a `none`), then with the mask of the label word `seal_label_index`",
    "  names over the capture ordinal and the entry ordinal, then rotated right by",
    "  the entry ordinal plus one times `spin_modulus` taken against twelve, then",
    "  unpacked in the block it came from. Ticks stand as stored and echoes stand",
    "  as written.",
    "",
    "- CTRL-H: The word entry text of every CTRL-G entry, joined by commas in entry",
    "  ordinal order. In a stepped capture the ticks are restored from the stored",
    "  series, a `none` entry counting as a stored 0: the first tick as stored, the",
    "  second the stored value plus the first tick, every later one the stored",
    "  value plus twice the tick before it less the tick before that, each wrapped",
    "  at 65536. The unit index, taken against the length of the list, selects a",
    "  word from the donor capture's header word list rotated left by",
    "  `alias_donor_shift` in an aliased capture, and from the twenty four unit",
    "  words of the charter notes in any other. A `none` entry stays `none`.",
    "",
    "- CTRL-I: The CTRL-H word entry texts once every echo, an entry of kind 224,",
    "  is resolved in entry ordinal order. An echo's distance is its entry ordinal",
    "  taken against one less than `echo_window_span`, plus one. It keeps its own",
    "  tick and takes the word, the kind, the amount and the mark of the entry that",
    "  distance earlier, as that entry stands once the echoes before it are",
    "  resolved. An echo whose distance reaches before the first entry, or lands on",
    "  a `none` entry, stays as written.",
    "",
    "CTRL-J reads one fragment per surviving canonical unit, in ascending order of",
    "the unit word by character code: the word, a colon and the name of its cadence",
    "class, as in `hydra:steady`.",
    "",
    "CTRL-K reads one fragment: the upkeep target written as the charter notes render",
    "a rational, numerator, solidus and denominator in lowest terms, as in `98472/1`.",
]


def _calibration_text(plan):
    figures = control_figures(plan)
    out = ["# Calibration slice", "",
           "The engine writes eleven quantities into its captures that no shipped file",
           "states. For each one the set of values it may take is published here, together",
           "with one control figure. The figures are published in an order in which each is",
           "fixed by the quantities the figures ahead of it pin, together with one further",
           "quantity. At least one value of that further quantity reproduces the figure, and",
           "the value the engine used is one of them.", "",
           "Every control figure is the twelve-character digest this engine stamps over the",
           "material the row names.", ""]
    out.append("| quantity | candidate values | control | the control reads |")
    out.append("| --- | --- | --- | --- |")
    for name in PIN_ORDER:
        values = CANDIDATES[name]
        out.append("| `%s` | %d through %d | %s | %s |"
                   % (name, values[0], values[-1], CONTROL_FOR[name],
                      CONTROL_PROSE[CONTROL_FOR[name]]))
    out.append("")
    out.append("| control | published figure |")
    out.append("| --- | --- |")
    for name in CONTROL_NAMES:
        out.append("| %s | `%s` |" % (name, figures[name]))
    out.append("")
    out.append("A candidate is rejected against the first control figure in the order above")
    out.append("that separates it from the value the engine used.")
    out.extend(FRAGMENT_RECIPE)
    return "\n".join(out) + "\n"


def _example_text(plan):
    sample = {
        "cadence": "peak",
        "unit_count": 0,
        "amount_total": "0/1",
        "units": [],
    }
    return json.dumps(sample, indent=2, sort_keys=False) + "\n"


STATIC_NOTES = (
    "replay-format.md",
    "engine-rules.md",
    "charter-scale.md",
    "report-schema.md",
)

STATIC_NOTE_TEXT = {}

STATIC_NOTE_TEXT["replay-format.md"] = """\
# RPL1 capture container

Ninefold Marches writes one capture file per match. A capture is ASCII text with line feed endings
and carries the entries the simulation recorded while the match ran.

## Header

The first line of a capture is the header. It begins with `#RPL1` and then carries space-separated
`key=value` fields.

- `capture` is the capture stem.
- `number` is the capture ordinal. Captures form a ring and the ordinal is that ring position.
- `flags` is a four-digit hexadecimal word. Each bit of it names one space-saving transform that the
  shipping serializer applied to this capture. A bit that is clear means the transform was skipped.
  The twelve transforms are described below, one per bit, in bit order from the least significant.
- `blocks` is the number of block lines the capture carries.
- `frames` is the entry count the serializer declared.
- `words` is a comma-separated list of unit words. It is always plaintext and it is always this
  capture's own list.
- `seal` is a digest over the capture ordinal and the number of entries the capture truly carries.

## Blocks and entries

After the header the capture alternates block lines and entry lines. A block line begins with `B`
and carries the block ordinal, a declared width and a block check word. The declared width is the
number of entry lines that follow before the next block line or the end of the file. Block ordinals
count from zero.

An entry line begins with `R` and carries one hexadecimal payload.

The block check word is a digest over the capture ordinal, the block ordinal and the declared width.
It reads nothing from the payloads, so a transform that rewrites a payload or restates a count leaves
every block check word untouched.

## Entry payload

An entry payload that has had every transform undone is twelve bytes:

| offset | width | field |
|---|---|---|
| 0 | 2 | tick |
| 2 | 2 | unit index |
| 4 | 1 | kind |
| 5 | 4 | amount |
| 9 | 1 | mark |
| 10 | 2 | check |

Multi-byte fields are big endian unless a transform says otherwise. The check field is a digest over
the ten bytes that precede it.

`kind` is zero, one or two for an ordinary entry and three for a reversal. `mark` is scenery on an
ordinary entry and names the kind being reversed on a reversal.

A payload whose kind byte reads two hundred and twenty four is not an ordinary entry. It is an echo,
and its unit index, amount and mark fields are written as zero.

`unit index` selects a unit word. Which list it indexes into is settled by the transforms below.

## The twelve transforms

Bit zero, **sealed**. Every payload of the capture is masked by a keystream. The keystream is drawn
from one of the twelve published label words together with the capture ordinal and the entry ordinal.

Bit one, **chained**. Every payload of the capture is masked a second time, and that mask is drawn
from the capture ordinal together with the tick and the amount of the entry that settled immediately
before it. The first entry of a capture uses zero for both.

Bit two, **stepped**. The tick field does not hold the tick. It holds the second difference of the
tick series across the capture. The first entry holds its tick, the second holds the difference
against the first, and every later entry holds the difference of differences. The field wraps at two
to the sixteen.

Bit three, **drifted**. Every payload of a block is masked by a block key. The block key is drawn
from the capture ordinal together with a counter, and the counter is the block ordinal advanced by
one and advanced again by five for every step of the capture ordinal, wrapped at the drift modulus.

Bit four, **woven**. The entry lines inside each block are restated in a permuted order. The
permutation is a Fisher and Yates shuffle whose seed is fixed by the weave seed offset, the capture
ordinal and the block ordinal, and it runs over the declared width of that block.

The shuffle reads from a counter. The counter is seeded with the weave seed offset advanced by 97
for every step of the capture ordinal and by 7 for every step of the block ordinal. That seed is
multiplied by 2654435761, advanced by 1013904223 and held to thirty two bits, and a seed that lands
on zero is replaced by 2654435769. Every draw folds the counter three times, exclusive or against
itself shifted left by 13, then against itself shifted right by 17, then against itself shifted left
by 5, holding to thirty two bits after each fold, and hands back the folded counter. The shuffle
starts an order that lists the block positions in their natural sequence, walks the positions from
the last down to the second, and at each position swaps the entry of the order there with the entry
of the order at the draw taken against that position advanced by one. The line standing in a given
position of the restated block is the line that stood in the position the finished order records for
it.

Bit five, **echoed**. Some entries are echoes. An echo reaches a distance back into the entries
already settled in this capture and takes the unit, the kind, the amount and the mark of the entry
that distance earlier, while keeping its own tick. The distance is the entry ordinal taken against
one less than the echo window span and then advanced by one, so it is at least one and never reaches
the echo window span.

Bit six, **flipped**. Inside exactly one block of the capture the multi-byte fields are little endian
rather than big endian. That block is the one whose ordinal equals the capture ordinal taken against
the block count.

Bit seven, **padded**. The declared frame count overstates the number of entry lines the capture
carries. The overstatement is three times the capture ordinal plus one, taken against the frame bias
limit.

Bit eight, **shadowed**. The opening block of the capture declares a width larger than its true
width, and the surplus entry lines at the end of that block are filler. Their count is three fewer
than the shadow pad base. Filler payloads are drawn from the capture ordinal and the filler ordinal
and are shaped exactly like real payloads.

Bit nine, **spun**. Every payload of the capture is restated with its twelve bytes rotated left. The
rotation amount is the entry ordinal advanced by one, multiplied by the spin modulus, and taken
against twelve.

Bit ten, **aliased**. The unit index does not index this capture's own word list. It indexes the word
list published in the header of the donor capture, which is the capture whose ring ordinal sits the
alias donor shift ahead of this one, counted around the ring of six, and that list is read after it
has been rotated left by the alias donor shift. A capture that is not aliased indexes the twenty four
unit words published in the charter notes.

Bit eleven, **warded**. One reserved byte value is escaped inside every payload of the capture by
writing it twice. The reserved value is the sentinel code value, and the escape marker is that same
value.

## Tiers

Two captures in the shipped set carry a flag word of zero. Nothing was done to them, so their
payloads are already the twelve-byte form above and they can be read directly. They are there so the
base layout can be confirmed before anything harder is attempted. They reveal nothing about which
label word, which seed, which span or which reserved value the transformed captures use.

Entry ordinals count true entries of the capture from zero and ignore filler.
"""

STATIC_NOTE_TEXT["engine-rules.md"] = """\
# Ninefold Marches simulation rules

These are the rules the simulation applies to the entries a capture records. They are listed by
subsystem in the order the design documents number the subsystems, which is not the order in which
the simulation consults them.

## Identity

Every unit word belongs to a roster row. A row names the charter the word serves, the tick at which
the word opened, the tick at which it closed, and the word that succeeds it.

A row whose successor column names the row itself is a cycle, and that question is settled before
any other. A unit standing in a cycle is held at its opening charter and its entries settle under
that charter.

A closing tick of zero means the word never closed, and such a word is in force for every entry that
names it.

A word that carries a closing tick is in force for an entry when the entry tick does not stand past
that closing tick. The opening tick sizes the charter baseline and takes no part in this question,
so an entry whose tick falls before the opening tick still settles under the word it names.

When an entry tick stands past the closing tick of the word the entry names, the entry belongs to
the successor of that word, and the same question is asked again of the successor.

A word whose successor column is empty and whose closing tick the entry tick stands past is retired.
An entry that reaches a retired word leaves the simulation.

A word whose successor serves a different charter is a merge. An entry that passes through a merge
serves the charter of the successor.

## Windows

The tick schedule divides the match into windows. A window names its first tick, its last tick and
whether it is live.

An entry survives the window filter when its tick lies inside a live window.

The identity question is asked before the window filter, so an entry that reaches a retired word
counts as retired even when no live window admits it.

A window whose first tick exceeds its last tick is degenerate and admits no entry.

The first tick of every live window renews each charter allowance to its full size before any entry
at that tick draws. A degenerate window renews nothing.

## Charters

Each charter carries a baseline. Each charter also draws a transfer from every other charter, and
the size of that transfer is fixed by the settled flow of kind one entries running between the two
charters.

The stock a charter holds is its baseline together with everything it draws from the other charters.
Because every charter gives away strictly less than it holds, a unique stable assignment of stocks
exists.

A charter with no surviving unit contributes its baseline to the system and draws nothing.

A settled entry draws its amount on the allowance of the charter it serves, and the part it cannot
draw is surplus, counted into the reconciliation residual rather than discarded.

## Cadence

Every surviving unit carries a settled tick total, which is the sum of the ticks of the entries that
settled under it.

A unit's cadence class is its settled tick total divided by the cadence modulus and then taken
against four. The four cadence classes are peak, steady, burst and latency, in that index order.

## Upkeep

The upkeep target is the sum of the charter baselines multiplied by the upkeep target scale.

Exactly one set drawn from the bench candidates carries a settled upkeep that meets the target
exactly. A unit's settled upkeep is its settled amount total.

## Reconciliation

Every amount a capture decodes is settled, dropped, held as surplus beyond an allowance, or carried
by a cancelled entry or the reversal that cancels it. The reconciliation residual is what remains
once the settled amounts and the dropped amounts are taken away from the decoded amounts.

## Reversals

A reversal entry names a kind in its mark field.

A reversal entry cancels the earliest still uncancelled entry of the same kind recorded by that unit,
not the latest one, and when no uncancelled entry of that kind remains the reversal itself counts as
an entry of that kind.

A reversal is matched against the entries of the canonical unit the reversal resolves to, not against
the entries of the word the reversal names on the wire.

Reversal matching walks a unit's surviving entries by tick, then by capture ordinal, then by the
ordinal the entry holds inside its capture.

A cancelled entry, and the reversal that cancels it, contribute nothing to any settled total. A
reversal that cancels nothing contributes as an ordinary entry of the kind its mark names.

Counting the reversals that cancelled nothing is how a run learns whether it read the cancellation
order the engine uses.
"""

STATIC_NOTE_TEXT["charter-scale.md"] = """\
# Charter scale notes

These notes fix the arithmetic conventions the settlement uses. They describe
quantities and conventions only. They carry no figure taken from any capture.

## Published word tables

The twenty four unit words, in the order the engine publishes them, are
`aurochs`, `basilisk`, `cockatrice`, `dryad`, `ettin`, `fenrir`, `golem`,
`hydra`, `ifrit`, `jotun`, `kelpie`, `lamia`, `manticore`, `nixie`, `ogre`,
`pegasus`, `quasit`, `roc`, `sylph`, `troll`, `undine`, `vodyanoi`, `wyvern`,
`xorn`.

The twelve label words, in the order the engine publishes them, are `aegis`,
`banner`, `cinder`, `dagger`, `ember`, `falcon`, `gale`, `harrow`, `ingot`,
`javelin`, `kestrel`, `lantern`. A label is named by its position in this list,
counted from zero.

The five charters are `azure`, `crimson`, `gilded`, `sable` and `verdant`.

The four cadence classes, in index order, are `peak`, `steady`, `burst` and
`latency`.

Every keyed mask this engine stamps is a SHA two five six digest over the engine
key `MRD-2031`, then the label of the mask, then each number the mask covers
written in decimal and each preceded by a colon. A mask takes the first twelve
bytes of that digest. Beside the twelve label words the mask labels the engine
uses are `entry`, `seal`, `check`, `chain`, `drift` and `filler`.

A published control figure is stamped a different way. It is the first twelve
characters of the hexadecimal SHA two five six digest over the engine key
`MRD-2031` followed by every fragment the control reads, where each fragment is
preceded by a vertical bar and written in its UTF-8 form.

## Exact arithmetic

Every monetary quantity in this engine is a rational number. Stocks, amounts,
upkeep targets and residuals are held exactly. A quantity is rendered as the
numerator, a solidus, and the denominator, in lowest terms, with the
denominator written even when it is one. A negative quantity carries the sign
on the numerator. Binary floating point is not a faithful carrier for these
quantities and a run that routes them through it will disagree with the engine
on the low digits.

## Charter baselines

The roster register names the charter every unit was opened under. The baseline
of a charter is the sum over the units the register opens under that charter of
the unit's opening tick, taken as an exact integer. The baseline is a property
of the register alone. It does not read any capture, it does not change when a
unit retires, and it does not change when a unit is carried to a successor.

## Transfer between charters

Two charters are linked when a settled entry of kind one is recorded by a unit
whose canonical charter differs from the charter the register opened that unit
under. The share the opening charter gives to the canonical charter is the
settled kind one amount recorded across that pair, divided by the sum of every
charter baseline. The engine builds one share per ordered pair of distinct
charters and no share from a charter to itself.

The stock of a charter is its baseline plus the sum over the other charters of
that other charter's stock multiplied by the share it gives away. Every charter
gives away strictly less than the whole in total, so the assignment of stocks
that satisfies every one of these relations at once exists and is unique. It is
an assignment to be solved for, not a sequence to be walked.

## Caps

A charter cap is the charter baseline multiplied by the number of units the
register opens under that charter. Each charter holds an allowance the size of
its cap. The settled entries that serve a charter draw on its allowance one at
a time, in the walk order the reversal rules use. An entry draws its whole
amount while the allowance left covers it, and otherwise draws what is left,
which can be nothing. What an entry draws is its settled amount. The part it
cannot draw is surplus and the surplus is carried into the reconciliation
residual rather than into any stock. An entry that draws nothing still
settles. Reversal matching is complete before any entry draws, so a cancelled
entry never draws.

## Cadence scale

The cadence modulus is one of the withheld quantities. The candidate values it
may take are published with the control figures. Dividing a settled tick total
by the cadence modulus uses integer division that discards the remainder.

## Upkeep scale

The upkeep target scale is one of the withheld quantities. The candidate values
it may take are published with the control figures. The upkeep target is the
scale multiplied by the sum of every charter baseline. It is an exact integer.

## Bench candidates

The bench candidate list names units by word and gives each a whole upkeep
figure. Exactly one subset of the candidate list has upkeep summing to the
upkeep target exactly. The empty subset is a subset and is eligible when the
target is zero. Two subsets with the same sum would leave the answer ambiguous,
and the list is drawn so that this does not happen. A bench entry is reported by
the candidate word, and the bench is reported with its words in ascending order.

## Counting conventions

A settling pass over the identity register is one complete sweep that reads every
roster row once and rewrites every canonical charter that the sweep finds stale.
The sweep that finds nothing stale is the pass that proves stability and it counts
as a pass.

A candidate is one value from the published set for one withheld quantity. The
falsifier for a rejected candidate is the name of the control figure that the
candidate failed to reproduce, and a candidate is rejected against the first
control figure in published order that separates it.
"""

STATIC_NOTE_TEXT["report-schema.md"] = """\
# Report schema

Every report this engine emits is a JSON object. This note lists the field names
each report carries, the type each field holds, and the ordering of each array.
It carries no figure derived from any capture, register or schedule.

A field typed `rational` holds a string of the form numerator, solidus,
denominator, in lowest terms, with the denominator written even when it is one.
A field typed `count` holds a JSON integer. A field typed `word` holds a lower
case name. A field typed `cadence` holds one of `peak`, `steady`, `burst` or
`latency`.

The decoded fields, `entry_total`, `decoded_total` and `decoded_amount_total`,
count every entry the captures decode, before unit identity, live windows and
cancellation are applied.

## The whole scenario report

Written as `scenario_visible.json`.

| field | type | note |
| --- | --- | --- |
| `capture_count` | count | how many captures the set holds |
| `entry_total` | count | decoded entries across the set |
| `settled_total` | count | entries that survive settlement |
| `units` | array | one object per surviving canonical unit, ascending by `unit` |

Each entry of `units` carries:

| field | type | note |
| --- | --- | --- |
| `unit` | word | the canonical word |
| `charter` | word | the canonical charter |
| `tick_total` | count | settled tick total for the unit |
| `amount_total` | rational | settled amount total for the unit |
| `cadence` | cadence | the class the unit falls in |
| `kind_totals` | array | three rationals, for kind zero, kind one and kind two, in that order |

## The per cadence reports

Written as `scenario_peak.json`, `scenario_steady.json`, `scenario_burst.json`
and `scenario_latency.json`, one file per class.

One report is emitted for each cadence class, whether or not the class holds a
unit. Each carries:

| field | type | note |
| --- | --- | --- |
| `cadence` | cadence | the class this report covers |
| `unit_count` | count | surviving units in the class |
| `amount_total` | rational | settled amount total across the class |
| `units` | array | one object per unit in the class, ascending by `unit` |

Each entry of `units` carries `unit`, `charter`, `tick_total` and
`amount_total`, with the same types as above.

## The settlement report

Written as `perf_report.json`.

| field | type | note |
| --- | --- | --- |
| `charter_stocks` | array | one object per charter, ascending by `charter` |
| `settled_total` | rational | settled amount across the set |
| `decoded_total` | rational | decoded amount across the set |
| `reversal_count` | count | reversal entries the set holds after decoding |
| `promoted_reversal_count` | count | reversals that cancelled nothing |

Each entry of `charter_stocks` carries `charter` as a word and `stock` as a
rational.

## The derivation record

Written as `bottleneck_analysis.json`.

| field | type | note |
| --- | --- | --- |
| `quantities` | array | one object per withheld quantity, in published order |
| `settling_passes` | count | passes the identity register took to stabilise |
| `calibration_table` | array | one object per control figure, in published order |

Each entry of `quantities` carries `name` as the published quantity name,
`value` as a count, `control` as the published control name, and `rejected` as
an array holding one object per rejected candidate in ascending candidate order.
Each entry of `rejected` carries `candidate` as a count and `falsifier` as the
name of the control figure that rejected it.

Each entry of `calibration_table` carries `control` as the published control
name, `published` as the figure the notes publish, and `produced` as the figure
the run reproduced. Both are strings.

## The bench report

Written as `recommendations.json`.

| field | type | note |
| --- | --- | --- |
| `target` | rational | the upkeep target |
| `bench` | array | candidate words, ascending |
| `bench_upkeep` | rational | upkeep the bench carries |
| `residual_after_bench` | rational | target less bench upkeep |

## The quality report

Written as `data_quality.json`.

| field | type | note |
| --- | --- | --- |
| `dropped_retired` | count | entries dropped because the unit had retired |
| `dropped_offwindow` | count | entries dropped because no live window admits them |
| `dropped_amount_total` | rational | amount carried by dropped entries |
| `decoded_amount_total` | rational | amount across every decoded entry |
| `settled_amount_total` | rational | amount across every settled entry |
| `conservation_residual` | rational | decoded less settled less dropped |

## The reusable program

The program is delivered as Python source. It takes the directory holding the
capture set as its first argument and the directory to write into as its second.
It writes every report named above and nothing else.
"""


def _spec_notes():
    return STATIC_NOTE_TEXT


def _shipped_notes():
    here = Path(__file__).resolve().parent.parent / "environment" / "data"
    loaded = {}
    for name in STATIC_NOTES:
        source = here / name
        if source.is_file():
            loaded[name] = source.read_text(encoding="utf-8")
    return loaded


def _notes_match_shipped():
    shipped = _shipped_notes()
    if len(shipped) != len(STATIC_NOTES):
        return None
    return all(shipped[name] == STATIC_NOTE_TEXT[name] for name in STATIC_NOTES)


def assert_postconditions(plan):
    """Every property the corpus must hold, each with a named repair."""
    for capture in plan["captures"]:
        if capture["name"].startswith("sample_") and capture["flags"]:
            raise AssertionError("a sample capture enables a transform; clear its flag word")
    flagged = [capture for capture in plan["captures"] if capture["flags"]]
    if not flagged:
        raise AssertionError("no capture carries a transform; enable the flag word")
    for shift in range(12):
        bit = 1 << shift
        present = sum(1 for capture in flagged if capture["flags"] & bit)
        if present * 100 < 85 * len(flagged):
            raise AssertionError("transform bit 0x%04x sits below the presence floor; "
                                 "inject the flag" % bit)
    for name, values in CANDIDATES.items():
        if len(values) < 8:
            raise AssertionError("candidate set for %s is below the floor; widen the range" % name)
    for capture in plan["captures"]:
        if len(capture["words"]) < 14:
            raise AssertionError("capture %s publishes too short a word table; widen it"
                                 % capture["name"])
    for giver in plan["charters"]:
        away = sum(plan["share"][(giver, taker)]
                   for taker in plan["charters"] if taker != giver)
        if away >= 1:
            raise AssertionError("charter %s gives away the whole; scale the recorded amounts"
                                 % giver)
    if not plan["units"]:
        raise AssertionError("no unit survives settlement; widen the live windows")
    if plan["promoted_reversal_count"] < 1:
        raise AssertionError("no reversal is promoted; plant an unmatched reversal")
    if _grades_order(plan) and plan["first_divergence"] < 0:
        raise AssertionError("the two cancellation orders never part; plant a divergence")
    if not _grades_order(plan) and plan["first_divergence"] >= 0:
        raise AssertionError("the two cancellation orders part outside the sets that grade them")
    if plan["echo_census"] < 1:
        raise AssertionError("no repeated slot is planted; inject an echo")
    target = plan["values"]["upkeep_target_scale"] * plan["totalbase"]
    if _subset_count([row["upkeep"] for row in plan["bench"]], target) != 1:
        raise AssertionError("the bench list admits no single exact subset; plant an upkeep figure")
    graded = set()
    for report in expected_reports(plan).values():
        graded |= _key_names(report)
    visible = _visible_text(plan)
    for key in sorted(graded):
        if key not in visible:
            raise AssertionError("graded key %s appears in no visible file; add it to the notes"
                                 % key)
    return plan


def _key_names(node):
    out = set()
    if isinstance(node, dict):
        for key, value in node.items():
            out.add(key)
            out |= _key_names(value)
    elif isinstance(node, list):
        for value in node:
            out |= _key_names(value)
    return out


def _visible_text(plan):
    parts = [STATIC_NOTE_TEXT[name] for name in STATIC_NOTES]
    parts.append(_calibration_text(plan))
    parts.append(_roster_text(plan))
    parts.append(_schedule_text(plan))
    parts.append(_bench_text(plan))
    parts.append(_example_text(plan))
    return "\n".join(parts)


def _emit_corpus(root, plan, specs):
    root.mkdir(parents=True, exist_ok=True)
    for capture in plan["captures"]:
        (root / capture["name"]).write_text(capture["text"], encoding="utf-8", newline="\n")
    (root / "roster-register.csv").write_text(_roster_text(plan), encoding="utf-8", newline="\n")
    (root / "tick-schedule.csv").write_text(_schedule_text(plan), encoding="utf-8", newline="\n")
    (root / "bench-candidates.csv").write_text(_bench_text(plan), encoding="utf-8", newline="\n")
    (root / "calibration.md").write_text(_calibration_text(plan), encoding="utf-8", newline="\n")
    (root / "example-scenario-report.json").write_text(_example_text(plan),
                                                       encoding="utf-8", newline="\n")
    for name, text in specs.items():
        (root / name).write_text(text, encoding="utf-8", newline="\n")


def _write_corpus(destination, seed=None, tweak=None):
    root = Path(destination)
    if root.name != "data":
        root = root / "data"
    plan = replay_plan(CHALLENGE_SEED if seed is None else seed, tweak)
    assert_postconditions(plan)
    _emit_corpus(root, plan, _spec_notes())
    return plan


_STAGE_CACHE = {}
_PLAN_CACHE = {}


def _out_root():
    return Path("/" + "app") / "out"


def _delivered_program():
    return _out_root() / "optimize.py"


def _relax(path):
    for current, folders, files in os.walk(path):
        os.chmod(current, 0o755)
        for name in folders:
            os.chmod(os.path.join(current, name), 0o755)
        for name in files:
            os.chmod(os.path.join(current, name), 0o644)


def _grant_read(program):
    """Open the delivered tree to the unprivileged user; an editor can leave it at mode 0600."""
    root = _out_root()
    for current, folders, files in os.walk(root):
        os.chmod(current, os.stat(current).st_mode | 0o555)
        for name in files:
            leaf = os.path.join(current, name)
            if not os.path.islink(leaf):
                os.chmod(leaf, os.stat(leaf).st_mode | 0o444)
    for parent in Path(program).parents:
        if parent == root.parent:
            os.chmod(parent, os.stat(parent).st_mode | 0o555)
            break


def _unprivileged():
    if os.name != "posix" or os.geteuid() != 0:
        return []
    for drop in ("/usr/bin/setpriv", "/bin/setpriv"):
        if os.path.exists(drop):
            return [drop, "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
    raise AssertionError("setpriv is unavailable, refusing to run delivered code as root")


LAUNCH_SECONDS = 120


def _kill_group(proc):
    """Kill the whole process group the delivered program was started in."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        return


def _reap_strays():
    """Kill every process still running as the unprivileged grading user."""
    if os.name != "posix" or os.geteuid() != 0:
        return
    try:
        stray = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return
    for name in sorted(os.listdir("/proc")):
        if not name.isdigit():
            continue
        try:
            if os.stat("/proc/" + name).st_uid == stray:
                os.kill(int(name), signal.SIGKILL)
        except OSError:
            continue


def _launch(argv, cwd):
    """Run the delivered program in its own session; nothing it starts outlives the call."""
    proc = subprocess.Popen(_unprivileged() + argv, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, cwd=cwd,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=LAUNCH_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        _reap_strays()
        out, err = proc.communicate()
        err = "%s\nthe delivered program ran past %d seconds" % (err, LAUNCH_SECONDS)
    finally:
        _kill_group(proc)
        _reap_strays()
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def _stage(key, seed, tweak):
    if key in _STAGE_CACHE:
        return _STAGE_CACHE[key]
    room = tempfile.mkdtemp(prefix="replay-")
    os.chmod(room, 0o755)
    corpus = Path(room) / "data"
    result = Path(room) / "out"
    result.mkdir(parents=True, exist_ok=True)
    plan = replay_plan(seed, tweak)
    _emit_corpus(corpus, plan, _spec_notes())
    expectation = expected_reports(plan)
    _relax(room)
    os.chmod(result, 0o777)
    program = _delivered_program()
    if not program.exists():
        raise AssertionError("no settlement program was delivered")
    _grant_read(program)
    outcome = _launch([sys.executable, "-I", "-S", str(program), str(corpus), str(result)], room)
    bundle = {"room": room, "corpus": corpus, "result": result, "plan": plan,
              "expect": expectation, "code": outcome.returncode,
              "stderr": outcome.stderr[-600:]}
    _STAGE_CACHE[key] = bundle
    return bundle


def _produced(bundle, name):
    if bundle["code"] != 0:
        raise AssertionError("the delivered program exited %d: %s"
                             % (bundle["code"], bundle["stderr"]))
    target = bundle["result"] / name
    if not target.exists():
        raise AssertionError("the delivered program wrote no %s" % name)
    return json.loads(target.read_text(encoding="utf-8"))


def _restage_under(bundle, folder):
    room = Path(bundle["room"])
    moved = room / folder
    moved.mkdir(parents=True, exist_ok=True)
    for item in sorted(bundle["corpus"].iterdir()):
        if item.is_file():
            (moved / item.name).write_bytes(item.read_bytes())
    landing = room / (folder + "-out")
    landing.mkdir(parents=True, exist_ok=True)
    _relax(room)
    os.chmod(landing, 0o777)
    program = _delivered_program()
    _grant_read(program)
    outcome = _launch([sys.executable, "-I", "-S", str(program), str(moved), str(landing)], room)
    if outcome.returncode != 0:
        return None
    target = landing / "scenario_visible.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def _shipped_text(name):
    target = _out_root() / name
    if not target.exists():
        raise AssertionError("no %s was delivered" % name)
    return target.read_text(encoding="utf-8")


def _shipped(name):
    return json.loads(_shipped_text(name))


def _shipped_plan():
    if "plan" not in _PLAN_CACHE:
        _PLAN_CACHE["plan"] = replay_plan(CHALLENGE_SEED, None)
    return _PLAN_CACHE["plan"]


def _shipped_expectation():
    if "shipped" not in _PLAN_CACHE:
        _PLAN_CACHE["shipped"] = expected_reports(_shipped_plan())
    return _PLAN_CACHE["shipped"]


def corpus_seed(tag):
    digest = hashlib.sha256(tag.encode("ascii")).hexdigest()[:8]
    return EVAL_SEED + int(digest, 16) % 900000


def _mutant(tag):
    return _stage(tag, corpus_seed(tag), tag)


def _trap_only(tag, bit):
    return _stage("trap-" + tag, corpus_seed(tag), ("only", bit))


def _damaged(rule):
    return _stage("damage-" + rule, corpus_seed("damage-" + rule), ("damage", rule))


def _held_out(tag):
    # A per cadence set grades the class its tag names, so that class must draw on a renamed charter.
    return _stage(tag, corpus_seed(tag), ("class", tag.split("-")[1]))


def _settled_view(report):
    """The whole scenario report less the capture count and each unit's cadence class."""
    view = {key: value for key, value in report.items() if key != "capture_count"}
    view["units"] = [{key: value for key, value in unit.items() if key != "cadence"}
                     for unit in report["units"]]
    return view


def _first_difference(produced, wanted, path="$"):
    """The first path at which two reports part, with both values there."""
    if isinstance(wanted, dict) and isinstance(produced, dict):
        for key in list(wanted) + [key for key in produced if key not in wanted]:
            if key not in produced or key not in wanted:
                return "%s.%s present in only one report" % (path, key)
            found = _first_difference(produced[key], wanted[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(wanted, list) and isinstance(produced, list):
        for index, (left, right) in enumerate(zip(produced, wanted)):
            found = _first_difference(left, right, "%s[%d]" % (path, index))
            if found:
                return found
        if len(produced) != len(wanted):
            return "%s holds %d items, wanted %d" % (path, len(produced), len(wanted))
        return None
    if produced != wanted or type(produced) is not type(wanted):
        return "%s is %r, wanted %r" % (path, produced, wanted)
    return None


def _dropped_view(report):
    """The quality report with its retired and off-window drop counts summed.

    The single-transform sets grade the decode, so the order in which the two
    drop rules are checked is left to the tests that own it.
    """
    view = {key: value for key, value in report.items()
            if key not in ("dropped_retired", "dropped_offwindow")}
    view["dropped_count"] = report["dropped_retired"] + report["dropped_offwindow"]
    return view


def _compare(bundle, name, view=None):
    produced = _produced(bundle, name)
    wanted = bundle["expect"][name]
    if view is not None:
        produced, wanted = view(produced), view(wanted)
    if name == "scenario_visible.json":
        # Cadence and the capture count are graded by their own checks.
        produced, wanted = _settled_view(produced), _settled_view(wanted)
    difference = _first_difference(produced, wanted)
    if difference is not None:
        raise AssertionError("%s disagrees with the settled capture set: %s" % (name, difference))


INSTANCE_REPORTS = ("scenario_visible.json", "perf_report.json",
                    "recommendations.json", "data_quality.json")


def _match_shipped(name):
    text = _shipped_text(name)
    value = json.loads(text)
    wanted = _shipped_expectation()[name]
    difference = _first_difference(value, wanted)
    if difference is not None:
        raise AssertionError("%s disagrees with the settled capture set: %s" % (name, difference))


def record_derivation_ok(record, plan):
    """Whether the delivered record holds the values, rejections and figures the slice fixes."""
    if not record_schema_ok(record):
        return False
    if type(record["settling_passes"]) is not int or record["settling_passes"] != plan["settling_passes"]:
        return False
    figures = control_figures(plan)
    for row, name in zip(record["quantities"], PIN_ORDER):
        control = CONTROL_FOR[name]
        if row["name"] != name or row["control"] != control:
            return False
        if type(row["value"]) is not int or row["value"] != plan["values"][name]:
            return False
        wanted = [value for value in CANDIDATES[name] if value != plan["values"][name]]
        got = [item["candidate"] for item in row["rejected"]]
        if any(type(value) is not int for value in got) or got != wanted:
            return False
        if any(item["falsifier"] != control for item in row["rejected"]):
            return False
    for row, control in zip(record["calibration_table"], CONTROL_NAMES):
        if row["control"] != control:
            return False
        if row["published"] != figures[control] or row["produced"] != figures[control]:
            return False
    return True


def test_format_program_delivered():
    """POSITIVE: the delivered settlement program exists and parses."""
    program = _delivered_program()
    if not program.exists():
        raise AssertionError("no settlement program was delivered")
    compile(program.read_text(encoding="utf-8"), "optimize.py", "exec")


def test_record_derivation_matches():
    """POSITIVE: on a fresh capture set the derivation record holds the recovered values, rejections, figures and passes."""
    # The deep chain set settles in five passes where the shipped set takes four.
    bundle = _mutant("deepchain")
    if not record_derivation_ok(_produced(bundle, "bottleneck_analysis.json"), bundle["plan"]):
        raise AssertionError("the derivation record disagrees with the calibration slice")


NAMED_REPORTS = ("bottleneck_analysis.json", "data_quality.json", "perf_report.json",
                 "recommendations.json", "scenario_burst.json", "scenario_latency.json",
                 "scenario_peak.json", "scenario_steady.json", "scenario_visible.json")


def test_format_writes_only_named_reports():
    """POSITIVE: on a fresh capture set the program writes the nine named reports and nothing else."""
    bundle = _held_out("cadence-peak")
    if bundle["code"] != 0:
        raise AssertionError("the delivered program exited %d: %s" % (bundle["code"], bundle["stderr"]))
    written = sorted(os.listdir(bundle["result"]))
    if written != list(NAMED_REPORTS):
        raise AssertionError("the report directory holds %r, wanted %r" % (written, list(NAMED_REPORTS)))


def test_instance_scenario_visible():
    """POSITIVE: the shipped scenario report matches the shipped capture set."""
    _match_shipped("scenario_visible.json")


def test_instance_perf_report():
    """POSITIVE: the shipped settlement report matches the shipped capture set."""
    _match_shipped("perf_report.json")


def test_instance_recommendations():
    """POSITIVE: the shipped bench report matches the shipped capture set."""
    _match_shipped("recommendations.json")


def test_instance_data_quality():
    """POSITIVE: the shipped quality report matches the shipped capture set."""
    _match_shipped("data_quality.json")


def test_instance_report_serialization():
    """POSITIVE: the four shipped reports are written in the example report's serialization."""
    for name in INSTANCE_REPORTS:
        text = _shipped_text(name)
        value = json.loads(text)
        if not isinstance(value, dict) or not value:
            raise AssertionError("%s is not a report object" % name)
        if text != json.dumps(value, indent=2) + "\n":
            raise AssertionError("%s does not follow the example report's serialization" % name)


def test_general_scenario_peak():
    """POSITIVE: on a fresh capture set the whole peak cadence document matches its settlement."""
    _compare(_held_out("cadence-peak"), "scenario_peak.json")


def test_general_scenario_steady():
    """POSITIVE: on a fresh capture set the whole steady cadence document matches its settlement."""
    _compare(_held_out("cadence-steady"), "scenario_steady.json")


def test_general_scenario_latency():
    """POSITIVE: on a fresh capture set the whole latency cadence document matches its settlement."""
    _compare(_held_out("cadence-latency"), "scenario_latency.json")


def test_trap_sealed_inverse():
    """POSITIVE: a fresh capture set carrying only the label mask settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("sealed", BIT_SEALED), "scenario_visible.json")


def test_trap_chained_inverse():
    """POSITIVE: a fresh capture set carrying only the carried mask settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("chained", BIT_CHAINED), "scenario_visible.json")


def test_trap_stepped_inverse():
    """POSITIVE: a fresh capture set carrying only stored tick differences settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("stepped", BIT_STEPPED), "scenario_visible.json")


def test_trap_drifted_inverse():
    """POSITIVE: a fresh capture set carrying only the per block mask settles to its whole settlement report."""
    _compare(_trap_only("drifted", BIT_DRIFTED), "perf_report.json")


def test_trap_woven_inverse():
    """POSITIVE: a fresh capture set carrying only the shuffled line order settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("woven", BIT_WOVEN), "scenario_visible.json")


def test_trap_echoed_inverse():
    """POSITIVE: a fresh capture set carrying only repeated slots settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("echoed", BIT_ECHOED), "scenario_visible.json")


def test_trap_flipped_inverse():
    """POSITIVE: a fresh capture set carrying only the reversed byte order island settles to its whole quality report, the two drop counts summed."""
    _compare(_trap_only("flipped", BIT_FLIPPED), "data_quality.json", _dropped_view)


def test_trap_padded_inverse():
    """POSITIVE: a fresh capture set carrying only the biased frame count settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("padded", BIT_PADDED), "scenario_visible.json")


def test_trap_shadowed_inverse():
    """POSITIVE: a fresh capture set carrying only the opening block filler settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("shadowed", BIT_SHADOWED), "scenario_visible.json")


def test_trap_spun_inverse():
    """POSITIVE: a fresh capture set carrying only the rotated payload bytes settles to its whole settlement report."""
    _compare(_trap_only("spun", BIT_SPUN), "perf_report.json")


def test_trap_aliased_inverse():
    """POSITIVE: a fresh capture set carrying only donor table word indexes settles to its whole scenario report, cadence and capture count aside."""
    _compare(_trap_only("aliased", BIT_ALIASED), "scenario_visible.json")


def test_trap_warded_inverse():
    """POSITIVE: a fresh capture set carrying only the doubled reserved byte settles to its whole quality report, the two drop counts summed."""
    _compare(_trap_only("warded", BIT_WARDED), "data_quality.json", _dropped_view)


def test_trap_zeroed_payload_inverse():
    """POSITIVE: a doubled-byte, drifted capture set with short and lone-reserved-byte payloads settles to its whole scenario report, cadence and capture count aside."""
    _compare(_damaged("zero"), "scenario_visible.json")


def test_trap_carry_reset_inverse():
    """POSITIVE: a chained capture set with broken payloads, each followed by an entry masked from 0 and 0, settles to its whole scenario report, cadence and capture count aside."""
    _compare(_damaged("carry"), "scenario_visible.json")


def test_trap_stepped_gap_inverse():
    """POSITIVE: a stepped capture set with broken payloads that count as a stored 0 settles to its whole scenario report, cadence and capture count aside."""
    _compare(_damaged("stepped"), "scenario_visible.json")


def test_trap_index_lap_inverse():
    """POSITIVE: an aliased capture set whose unit indices run past the list length settles to its whole scenario report, cadence and capture count aside."""
    _compare(_damaged("index"), "scenario_visible.json")


def test_general_deep_identity_chain():
    """POSITIVE: a fresh capture set with a three deep succession chain settles to its whole scenario report, cadence and capture count aside."""
    _compare(_mutant("deepchain"), "scenario_visible.json")


def test_general_charter_cap_surplus():
    """POSITIVE: a fresh capture set whose amounts outrun the charter allowances settles to its whole quality report."""
    _compare(_mutant("cap"), "data_quality.json")


def test_general_empty_charter():
    """POSITIVE: a fresh capture set with a charter that keeps no unit settles to its whole settlement report."""
    _compare(_mutant("emptycharter"), "perf_report.json")


def test_general_window_boundary_shift():
    """POSITIVE: a fresh capture set with a window edge moved by one tick settles to its whole scenario report, cadence and capture count aside."""
    _compare(_mutant("boundary"), "scenario_visible.json")


def test_general_degenerate_window_live():
    """POSITIVE: a fresh capture set whose late window is ordered settles to its whole scenario report, cadence and capture count aside."""
    _compare(_mutant("degenerate"), "scenario_visible.json")


def test_general_dead_window():
    """POSITIVE: a fresh capture set with a window taken out of service settles to its whole quality report."""
    _compare(_mutant("deadwindow"), "data_quality.json")


def test_general_reversal_density():
    """POSITIVE: a fresh capture set dense in reversals settles to its whole settlement report."""
    _compare(_mutant("reversalflip"), "perf_report.json")


def test_general_population_scale():
    """POSITIVE: a larger fresh capture set settles to its whole scenario report, cadence and capture count aside."""
    _compare(_mutant("population"), "scenario_visible.json")


def test_general_baseline_scale():
    """POSITIVE: a fresh capture set with baselines an order of magnitude apart settles to its whole bench report."""
    _compare(_mutant("scale"), "recommendations.json")


def test_general_reversal_tiebreak():
    """POSITIVE: a fresh capture set whose reversals aim at one kind settles to its whole settlement report."""
    _compare(_mutant("tiebreak"), "perf_report.json")


def test_general_cadence_partition():
    """POSITIVE: a fresh capture set with a redistributed cadence partition settles to its whole burst cadence document."""
    _compare(_mutant("partition"), "scenario_burst.json")


def test_general_fixpoint_new_unit():
    """POSITIVE: a fresh capture set with a narrowed unit set settles to its whole settlement report."""
    _compare(_mutant("newunit"), "perf_report.json")


def test_general_donor_table_rotation():
    """POSITIVE: a fresh capture set with a rotated donor word table settles to its whole scenario report, cadence and capture count aside."""
    _compare(_mutant("donorretire"), "scenario_visible.json")


def _mutation_pair(tag, tweak):
    seed = corpus_seed(tag)
    return _stage(tag + "-base", seed, None), _stage(tag, seed, tweak)


def _cadence_marks(report):
    return [(unit["unit"], unit["cadence"]) for unit in report["units"]]


def test_mutation_cadence_modulus_moves_only_classes():
    """POSITIVE: a changed cadence modulus moves the cadence classes the engine reports, and only those."""
    base, moved = _mutation_pair("cadence-modulus", ("value", "cadence_modulus", 7))
    if (_settled_view(base["expect"]["scenario_visible.json"])
            != _settled_view(moved["expect"]["scenario_visible.json"])):
        raise AssertionError("the fixture moved more than the cadence classes")
    for bundle in (base, moved):
        produced = _cadence_marks(_produced(bundle, "scenario_visible.json"))
        wanted = _cadence_marks(bundle["expect"]["scenario_visible.json"])
        if produced != wanted:
            raise AssertionError("cadence classes disagree with the settled capture set: %s"
                                 % _first_difference(produced, wanted))


def test_mutation_window_split_moves_only_amounts():
    """POSITIVE: a live window split in two at the same admitted ticks moves the settlement report as the engine's does."""
    base, moved = _mutation_pair("window-split", "split")
    if (_cadence_marks(base["expect"]["scenario_visible.json"])
            != _cadence_marks(moved["expect"]["scenario_visible.json"])
            or base["expect"]["perf_report.json"] == moved["expect"]["perf_report.json"]):
        raise AssertionError("the fixture does not move the settled amounts alone")
    for bundle in (base, moved):
        _compare(bundle, "perf_report.json")


def _executable_source():
    program = _delivered_program()
    if not program.exists():
        return ""
    text = program.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    literals = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    literals.append(value.value)
    kept = [line.split("#", 1)[0] for line in text.splitlines()]
    joined = "\n".join(kept)
    for doc in literals:
        joined = joined.replace(doc, " ")
    return joined


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when settled figures are baked in as literals."""
    source = _executable_source()
    want = _shipped_expectation()
    marks = 0
    for text in (want["perf_report.json"]["settled_total"],
                 want["perf_report.json"]["decoded_total"],
                 want["recommendations.json"]["target"],
                 want["data_quality.json"]["conservation_residual"]):
        if text in source:
            marks += 1
    if marks < 2:
        raise AssertionError("no baked in settled figures were found")


def test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: fires when output depends on the staged directory name."""
    first = _stage("steady-one", CHALLENGE_SEED, None)
    second = _stage("steady-two", CHALLENGE_SEED, None)
    if first["code"] != 0 or second["code"] != 0:
        raise AssertionError("the delivered program did not complete")
    baseline = _produced(first, "scenario_visible.json")
    if _produced(second, "scenario_visible.json") != baseline:
        raise AssertionError("two identical runs already disagree")
    moved = _restage_under(first, "captures")
    if moved is None:
        raise AssertionError("the delivered program did not complete")
    if moved == baseline:
        raise AssertionError("the directory name changed nothing")


def _decoy(value, marks):
    """Swap every rational figure of an expected report for a planted figure no capture yields."""
    if isinstance(value, dict):
        return {key: _decoy(item, marks) for key, item in value.items()}
    if isinstance(value, list):
        return [_decoy(item, marks) for item in value]
    if isinstance(value, str) and "/" in value:
        mark = "%d/9973" % (9000000 + 7 * len(marks))
        marks.append(mark)
        return mark
    return value


def test_negative_weight_reads_supplied_answer_data_at_runtime():
    """NEGATIVE: fires when a fresh run copies figures planted in the reports under /app/out."""
    root = _out_root()
    keep = Path(tempfile.mkdtemp(prefix="decoy-keep-"))
    marks = []
    saved = []
    try:
        for name, report in _shipped_expectation().items():
            target = root / name
            if not root.is_dir() or name == "bottleneck_analysis.json":
                continue
            if target.is_file() and not target.is_symlink():
                target.replace(keep / name)
                saved.append(name)
            elif target.exists() or target.is_symlink():
                continue
            else:
                saved.append("+" + name)
            target.write_text(json.dumps(_decoy(report, marks), indent=2), encoding="utf-8")
            os.chmod(target, 0o644)
        bundle = _stage("decoy-planted", CHALLENGE_SEED, None)
    finally:
        for name in saved:
            if name.startswith("+"):
                (root / name[1:]).unlink()
            else:
                (keep / name).replace(root / name)
        os.rmdir(keep)
    if bundle["code"] != 0:
        raise AssertionError("the delivered program did not complete")
    for written in bundle["result"].rglob("*"):
        if written.is_file():
            text = written.read_text(encoding="utf-8", errors="replace")
            if any(mark in text for mark in marks):
                return
    raise AssertionError("the fresh run reproduced no planted figure")


def test_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: fires when the program reaches into the grading machinery."""
    source = _executable_source()
    for token in ("/" + "tests", "test" + "_output", "/" + "logs" + "/verifier"):
        if token in source:
            return
    raise AssertionError("the program names no part of the grading machinery")


def _pin_witnesses(seed):
    """Separating witness per rival candidate, accumulated over one capture set."""
    plan = replay_plan(seed, None)
    assert_postconditions(plan)
    report = []
    for position, name in enumerate(PIN_ORDER):
        control = CONTROL_NAMES[position]
        settled = single_control(plan, plan["values"], position)
        unwitnessed = []
        for rival in CANDIDATES[name]:
            if rival == plan["values"][name]:
                continue
            swapped = dict(plan["values"])
            swapped[name] = rival
            if single_control(plan, swapped, position) == settled:
                unwitnessed.append(rival)
        if unwitnessed:
            raise AssertionError("constant %s has no witness separating rivals %s under "
                                 "control %s; plant the separating evidence"
                                 % (name, unwitnessed, control))
        report.append("%-22s %-7s %2d rivals separated"
                      % (name, control, len(CANDIDATES[name]) - 1))
    return report


# rewardkit checks. Each one runs the original test above; it passes when that test
# raises nothing, and a failing check prints its first differing path. One lock runs the checks one at a time, as the old grader did,
# because rewardkit calls checks from parallel worker threads.
_GRADE_LOCK = threading.Lock()


def _passes(test) -> bool:
    with _GRADE_LOCK:
        try:
            test()
        except BaseException as error:
            print("[check] %s: %s: %s" % (test.__name__, type(error).__name__, str(error)[:400]))
            return False
        return True


@criterion(description="the delivered settlement program exists and parses.")
def format_program_delivered(workspace: Path) -> bool:
    return _passes(test_format_program_delivered)


@criterion(description="on a fresh capture set the derivation record holds the recovered values, rejections, figures and passes.")
def record_derivation_matches(workspace: Path) -> bool:
    return _passes(test_record_derivation_matches)


@criterion(description="on a fresh capture set the program writes the nine named reports and nothing else.")
def format_writes_only_named_reports(workspace: Path) -> bool:
    return _passes(test_format_writes_only_named_reports)


@criterion(description="the shipped scenario report matches the shipped capture set.")
def instance_scenario_visible(workspace: Path) -> bool:
    return _passes(test_instance_scenario_visible)


@criterion(description="the shipped settlement report matches the shipped capture set.")
def instance_perf_report(workspace: Path) -> bool:
    return _passes(test_instance_perf_report)


@criterion(description="the shipped bench report matches the shipped capture set.")
def instance_recommendations(workspace: Path) -> bool:
    return _passes(test_instance_recommendations)


@criterion(description="the shipped quality report matches the shipped capture set.")
def instance_data_quality(workspace: Path) -> bool:
    return _passes(test_instance_data_quality)


@criterion(description="the four shipped reports are written in the example report's serialization.")
def instance_report_serialization(workspace: Path) -> bool:
    return _passes(test_instance_report_serialization)


@criterion(description="on a fresh capture set the whole peak cadence document matches its settlement.")
def general_scenario_peak(workspace: Path) -> bool:
    return _passes(test_general_scenario_peak)


@criterion(description="on a fresh capture set the whole steady cadence document matches its settlement.")
def general_scenario_steady(workspace: Path) -> bool:
    return _passes(test_general_scenario_steady)


@criterion(description="on a fresh capture set the whole latency cadence document matches its settlement.")
def general_scenario_latency(workspace: Path) -> bool:
    return _passes(test_general_scenario_latency)


@criterion(description="a fresh capture set carrying only the label mask settles to its whole scenario report, cadence and capture count aside.")
def trap_sealed_inverse(workspace: Path) -> bool:
    return _passes(test_trap_sealed_inverse)


@criterion(description="a fresh capture set carrying only the carried mask settles to its whole scenario report, cadence and capture count aside.")
def trap_chained_inverse(workspace: Path) -> bool:
    return _passes(test_trap_chained_inverse)


@criterion(description="a fresh capture set carrying only stored tick differences settles to its whole scenario report, cadence and capture count aside.")
def trap_stepped_inverse(workspace: Path) -> bool:
    return _passes(test_trap_stepped_inverse)


@criterion(description="a fresh capture set carrying only the per block mask settles to its whole settlement report.")
def trap_drifted_inverse(workspace: Path) -> bool:
    return _passes(test_trap_drifted_inverse)


@criterion(description="a fresh capture set carrying only the shuffled line order settles to its whole scenario report, cadence and capture count aside.")
def trap_woven_inverse(workspace: Path) -> bool:
    return _passes(test_trap_woven_inverse)


@criterion(description="a fresh capture set carrying only repeated slots settles to its whole scenario report, cadence and capture count aside.")
def trap_echoed_inverse(workspace: Path) -> bool:
    return _passes(test_trap_echoed_inverse)


@criterion(description="a fresh capture set carrying only the reversed byte order island settles to its whole quality report, the two drop counts summed.")
def trap_flipped_inverse(workspace: Path) -> bool:
    return _passes(test_trap_flipped_inverse)


@criterion(description="a fresh capture set carrying only the biased frame count settles to its whole scenario report, cadence and capture count aside.")
def trap_padded_inverse(workspace: Path) -> bool:
    return _passes(test_trap_padded_inverse)


@criterion(description="a fresh capture set carrying only the opening block filler settles to its whole scenario report, cadence and capture count aside.")
def trap_shadowed_inverse(workspace: Path) -> bool:
    return _passes(test_trap_shadowed_inverse)


@criterion(description="a fresh capture set carrying only the rotated payload bytes settles to its whole settlement report.")
def trap_spun_inverse(workspace: Path) -> bool:
    return _passes(test_trap_spun_inverse)


@criterion(description="a fresh capture set carrying only donor table word indexes settles to its whole scenario report, cadence and capture count aside.")
def trap_aliased_inverse(workspace: Path) -> bool:
    return _passes(test_trap_aliased_inverse)


@criterion(description="a fresh capture set carrying only the doubled reserved byte settles to its whole quality report, the two drop counts summed.")
def trap_warded_inverse(workspace: Path) -> bool:
    return _passes(test_trap_warded_inverse)


@criterion(description="a doubled-byte, drifted capture set with short and lone-reserved-byte payloads settles to its whole scenario report, cadence and capture count aside.")
def trap_zeroed_payload_inverse(workspace: Path) -> bool:
    return _passes(test_trap_zeroed_payload_inverse)


@criterion(description="a chained capture set with broken payloads, each followed by an entry masked from 0 and 0, settles to its whole scenario report, cadence and capture count aside.")
def trap_carry_reset_inverse(workspace: Path) -> bool:
    return _passes(test_trap_carry_reset_inverse)


@criterion(description="a stepped capture set with broken payloads that count as a stored 0 settles to its whole scenario report, cadence and capture count aside.")
def trap_stepped_gap_inverse(workspace: Path) -> bool:
    return _passes(test_trap_stepped_gap_inverse)


@criterion(description="an aliased capture set whose unit indices run past the list length settles to its whole scenario report, cadence and capture count aside.")
def trap_index_lap_inverse(workspace: Path) -> bool:
    return _passes(test_trap_index_lap_inverse)


@criterion(description="a fresh capture set with a three deep succession chain settles to its whole scenario report, cadence and capture count aside.")
def general_deep_identity_chain(workspace: Path) -> bool:
    return _passes(test_general_deep_identity_chain)


@criterion(description="a fresh capture set whose amounts outrun the charter allowances settles to its whole quality report.")
def general_charter_cap_surplus(workspace: Path) -> bool:
    return _passes(test_general_charter_cap_surplus)


@criterion(description="a fresh capture set with a charter that keeps no unit settles to its whole settlement report.")
def general_empty_charter(workspace: Path) -> bool:
    return _passes(test_general_empty_charter)


@criterion(description="a fresh capture set with a window edge moved by one tick settles to its whole scenario report, cadence and capture count aside.")
def general_window_boundary_shift(workspace: Path) -> bool:
    return _passes(test_general_window_boundary_shift)


@criterion(description="a fresh capture set whose late window is ordered settles to its whole scenario report, cadence and capture count aside.")
def general_degenerate_window_live(workspace: Path) -> bool:
    return _passes(test_general_degenerate_window_live)


@criterion(description="a fresh capture set with a window taken out of service settles to its whole quality report.")
def general_dead_window(workspace: Path) -> bool:
    return _passes(test_general_dead_window)


@criterion(description="a fresh capture set dense in reversals settles to its whole settlement report.")
def general_reversal_density(workspace: Path) -> bool:
    return _passes(test_general_reversal_density)


@criterion(description="a larger fresh capture set settles to its whole scenario report, cadence and capture count aside.")
def general_population_scale(workspace: Path) -> bool:
    return _passes(test_general_population_scale)


@criterion(description="a fresh capture set with baselines an order of magnitude apart settles to its whole bench report.")
def general_baseline_scale(workspace: Path) -> bool:
    return _passes(test_general_baseline_scale)


@criterion(description="a fresh capture set whose reversals aim at one kind settles to its whole settlement report.")
def general_reversal_tiebreak(workspace: Path) -> bool:
    return _passes(test_general_reversal_tiebreak)


@criterion(description="a fresh capture set with a redistributed cadence partition settles to its whole burst cadence document.")
def general_cadence_partition(workspace: Path) -> bool:
    return _passes(test_general_cadence_partition)


@criterion(description="a fresh capture set with a narrowed unit set settles to its whole settlement report.")
def general_fixpoint_new_unit(workspace: Path) -> bool:
    return _passes(test_general_fixpoint_new_unit)


@criterion(description="a fresh capture set with a rotated donor word table settles to its whole scenario report, cadence and capture count aside.")
def general_donor_table_rotation(workspace: Path) -> bool:
    return _passes(test_general_donor_table_rotation)


@criterion(description="mutation: a changed cadence modulus moves the reported cadence classes and only those.")
def mutation_cadence_modulus_moves_only_classes(workspace: Path) -> bool:
    return _passes(test_mutation_cadence_modulus_moves_only_classes)


@criterion(description="mutation: a live window split at the same admitted ticks moves the settlement report as the engine's does.")
def mutation_window_split_moves_only_amounts(workspace: Path) -> bool:
    return _passes(test_mutation_window_split_moves_only_amounts)


@criterion(description="fires when settled figures are baked in as literals.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_hardcoded_sample_answers)


@criterion(description="fires when output depends on the staged directory name.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_filename_dependent_behaviour)


@criterion(description="fires when a fresh run copies figures planted in the reports under /app/out.")
def negative_reads_supplied_answer_data_at_runtime(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_reads_supplied_answer_data_at_runtime)


@criterion(description="fires when the program reaches into the grading machinery.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    # True means the cheat happened; the negative weight applies.
    return _passes(test_negative_weight_rebinds_verifier_dependencies)


criteria.format_program_delivered(weight=1)
criteria.record_derivation_matches(weight=3)
criteria.format_writes_only_named_reports(weight=1)
criteria.instance_scenario_visible(weight=1)
criteria.instance_perf_report(weight=1)
criteria.instance_recommendations(weight=1)
criteria.instance_data_quality(weight=1)
criteria.instance_report_serialization(weight=1)
criteria.general_scenario_peak(weight=5)
criteria.general_scenario_steady(weight=5)
criteria.general_scenario_latency(weight=5)
criteria.trap_sealed_inverse(weight=5)
criteria.trap_chained_inverse(weight=5)
criteria.trap_stepped_inverse(weight=5)
criteria.trap_drifted_inverse(weight=5)
criteria.trap_woven_inverse(weight=5)
criteria.trap_echoed_inverse(weight=5)
criteria.trap_flipped_inverse(weight=5)
criteria.trap_padded_inverse(weight=5)
criteria.trap_shadowed_inverse(weight=5)
criteria.trap_spun_inverse(weight=5)
criteria.trap_aliased_inverse(weight=5)
criteria.trap_warded_inverse(weight=5)
criteria.trap_zeroed_payload_inverse(weight=3)
criteria.trap_carry_reset_inverse(weight=3)
criteria.trap_stepped_gap_inverse(weight=3)
criteria.trap_index_lap_inverse(weight=3)
criteria.general_deep_identity_chain(weight=5)
criteria.general_charter_cap_surplus(weight=5)
criteria.general_empty_charter(weight=5)
criteria.general_window_boundary_shift(weight=5)
criteria.general_degenerate_window_live(weight=5)
criteria.general_dead_window(weight=5)
criteria.general_reversal_density(weight=5)
criteria.general_population_scale(weight=5)
criteria.general_baseline_scale(weight=5)
criteria.general_reversal_tiebreak(weight=5)
criteria.general_cadence_partition(weight=5)
criteria.general_fixpoint_new_unit(weight=5)
criteria.general_donor_table_rotation(weight=5)
criteria.mutation_cadence_modulus_moves_only_classes(weight=5)
criteria.mutation_window_split_moves_only_amounts(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_supplied_answer_data_at_runtime(weight=-5)
criteria.negative_rebinds_verifier_dependencies(weight=-5)




if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "emit"
    if mode == "pins":
        for tag in sys.argv[2:] or [str(CHALLENGE_SEED)]:
            for row in _pin_witnesses(int(tag)):
                print("seed %s  %s" % (tag, row))
    elif mode == "notes":
        print("all embedded notes match shipped: %s" % _notes_match_shipped())
    else:
        _write_corpus(Path(sys.argv[2] if len(sys.argv) > 2 else "environment"))
