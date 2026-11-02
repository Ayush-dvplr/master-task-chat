#!/usr/bin/env python3
"""Ninefold Marches match record settlement.

Recovers the withheld engine quantities from the calibration notes that ship in
the capture directory, decodes the capture set, settles the match and writes the
reports.  Standard library only.

usage: optimize.py <capture-dir> <report-dir>
"""

import csv
import glob
import hashlib
import json
import os
import re
import sys
from fractions import Fraction

ENGINE_KEY = "MRD-2031"
PAYLOAD_LEN = 12
WORD_LEN = 24
QUANTITY_ORDER = [
    "frame_bias_limit", "weave_seed_offset", "sentinel_code_value",
    "drift_modulus", "seal_label_index", "spin_modulus", "shadow_pad_base",
    "alias_donor_shift", "echo_window_span", "cadence_modulus",
    "upkeep_target_scale",
]
UNIT_WORDS_FALLBACK = [
    "aurochs", "basilisk", "cockatrice", "dryad", "ettin", "fenrir", "golem",
    "hydra", "ifrit", "jotun", "kelpie", "lamia", "manticore", "nixie", "ogre",
    "pegasus", "quasit", "roc", "sylph", "troll", "undine", "vodyanoi",
    "wyvern", "xorn",
]
LABEL_WORDS_FALLBACK = [
    "aegis", "banner", "cinder", "dagger", "ember", "falcon", "gale", "harrow",
    "ingot", "javelin", "kestrel", "lantern",
]

UNIT_WORDS = UNIT_WORDS_FALLBACK
LABEL_WORDS = LABEL_WORDS_FALLBACK


# ---------------------------------------------------------------- primitives

def mask(label, numbers, length=PAYLOAD_LEN):
    text = ENGINE_KEY + label + "".join(":%d" % n for n in numbers)
    return hashlib.sha256(text.encode("utf-8")).digest()[:length]


def control_digest(fragments):
    text = ENGINE_KEY + "".join("|" + f for f in fragments)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def rot_right(data, n):
    n %= len(data)
    if n == 0:
        return bytes(data)
    return bytes(data[n:]) + bytes(data[:n])


def rational(value):
    return "%d/%d" % (value.numerator, value.denominator)


# ---------------------------------------------------------------- shipped data

def find_file(directory, name):
    path = os.path.join(directory, name)
    if os.path.exists(path):
        return path
    path = os.path.join("/app/data", name)
    if os.path.exists(path):
        return path
    return None


def parse_calibration(path):
    text = open(path, encoding="utf-8").read()
    quantities = []
    for name, lo, hi, control in re.findall(
            r"^\|\s*`([a-z_]+)`\s*\|\s*([0-9]+) through ([0-9]+)\s*\|"
            r"\s*(CTRL-[A-Z])\s*\|", text, re.M):
        quantities.append({"name": name, "lo": int(lo), "hi": int(hi),
                            "candidates": list(range(int(lo), int(hi) + 1)),
                            "control": control})
    quantities.sort(key=lambda q: QUANTITY_ORDER.index(q["name"]))
    order = [q["control"] for q in quantities]
    figures = {}
    for name, figure in re.findall(r"^\|\s*(CTRL-[A-Z])\s*\|\s*`([0-9a-f]{12})`\s*\|",
                                   text, re.M):
        if name in order:
            figures[name] = figure
    controls = [(name, figures[name]) for name in order if name in figures]
    return quantities, controls


def parse_word_tables(path):
    unit_words = UNIT_WORDS_FALLBACK
    label_words = LABEL_WORDS_FALLBACK
    text = open(path, encoding="utf-8").read()
    m = re.search(r"twenty four unit words.*?are\s+(.*?)\.", text, re.S)
    if m:
        words = re.findall(r"`([a-z]+)`", m.group(1))
        if len(words) >= WORD_LEN:
            unit_words = words[:WORD_LEN]
    m = re.search(r"twelve label words.*?are\s+(.*?)\.", text, re.S)
    if m:
        words = re.findall(r"`([a-z]+)`", m.group(1))
        if len(words) >= len(LABEL_WORDS_FALLBACK):
            label_words = words[:len(LABEL_WORDS_FALLBACK)]
    return unit_words, label_words


def parse_register(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({"word": row["word"].strip(),
                         "charter": row["charter"].strip(),
                         "opened": int(row["opened"]),
                         "closed": int(row["closed"] or 0),
                         "successor": row["successor"].strip()})
    return rows


def parse_windows(path):
    windows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            windows.append({"name": row["window"].strip(),
                            "first": int(row["first_tick"]),
                            "last": int(row["last_tick"]),
                            "live": int(row["live"])})
    return windows


def parse_bench(path):
    bench = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            bench.append((row["word"].strip(), int(row["upkeep"])))
    return bench


# ---------------------------------------------------------------- captures

class Capture(object):
    def __init__(self, path):
        lines = open(path, encoding="utf-8").read().splitlines()
        header = {}
        for field in lines[0].split()[1:]:
            key, _, value = field.partition("=")
            header[key] = value
        self.number = int(header["number"])
        self.flags = int(header["flags"], 16)
        self.words = header["words"].split(",")
        self.blocks = []
        index = 1
        while index < len(lines) and lines[index].startswith("B"):
            width = int(lines[index].split()[2])
            payloads = [bytes.fromhex(lines[index + 1 + step].split()[1])
                        for step in range(width)]
            self.blocks.append(payloads)
            index += 1 + width
        self.block_count = len(self.blocks)

    def has(self, bit):
        return (self.flags >> bit) & 1 == 1

    def flipped_block(self):
        """The ordinal of the one block whose multi byte fields are little endian,
        or -1 when the capture is not flipped."""
        if not self.has(6) or self.block_count == 0:
            return -1
        return self.number % self.block_count


def load_captures(directory):
    caps = [Capture(p) for p in sorted(glob.glob(os.path.join(directory, "*.rpl")))]
    caps.sort(key=lambda c: c.number)
    return caps


# ---------------------------------------------------------------- wire stages

def weave_order(width, seed):
    counter = seed & 0xFFFFFFFF
    if counter == 0:
        counter = 2654435769
    order = list(range(width))
    for pos in range(width - 1, 0, -1):
        counter ^= (counter << 13) & 0xFFFFFFFF
        counter &= 0xFFFFFFFF
        counter ^= counter >> 17
        counter ^= (counter << 5) & 0xFFFFFFFF
        counter &= 0xFFFFFFFF
        draw = counter % (pos + 1)
        order[pos], order[draw] = order[draw], order[pos]
    return order


def unweave(capture, offset):
    out = []
    for ordinal, block in enumerate(capture.blocks):
        if not capture.has(4):
            out.append(list(block))
            continue
        seed = (offset + 97 * capture.number + 7 * ordinal) & 0xFFFFFFFF
        seed = (seed * 2654435761 + 1013904223) & 0xFFFFFFFF
        order = weave_order(len(block), seed)
        restored = [None] * len(block)
        for pos in range(len(block)):
            restored[order[pos]] = block[pos]
        out.append(restored)
    return out


def unward(capture, blocks, sentinel):
    """Lift the warded transform.  A payload that holds the reserved byte once on
    its own, or that does not come out at twelve bytes, is the zero payload."""
    out = []
    for block in blocks:
        lines = []
        for payload in block:
            if not capture.has(11):
                lines.append(bytes(payload))
                continue
            seen = bytearray()
            index = 0
            broken = False
            while index < len(payload):
                if payload[index] == sentinel:
                    if index + 1 < len(payload) and payload[index + 1] == sentinel:
                        seen.append(sentinel)
                        index += 2
                        continue
                    broken = True
                    break
                seen.append(payload[index])
                index += 1
            lines.append(bytes(seen) if not broken and len(seen) == PAYLOAD_LEN
                         else bytes(PAYLOAD_LEN))
        out.append(lines)
    return out


def undrift(capture, blocks, modulus):
    out = []
    for ordinal, block in enumerate(blocks):
        if not capture.has(3):
            out.append(list(block))
            continue
        counter = (ordinal + 1 + 5 * capture.number) % modulus
        key = mask("drift", [capture.number, counter])
        out.append([xor_bytes(p, key) for p in block])
    return out


def masked_blocks(capture, q):
    """The payload lists of a capture with the weave, ward and drift lifted."""
    blocks = unweave(capture, q["weave_seed_offset"])
    blocks = unward(capture, blocks, q["sentinel_code_value"])
    blocks = undrift(capture, blocks, q["drift_modulus"])
    return blocks


def unpack(payload, little):
    if payload is None:
        return None
    if payload[10:12] != mask("entry", list(payload[:10]), 2):
        return None
    order = "little" if little else "big"
    return (int.from_bytes(payload[0:2], order),
            int.from_bytes(payload[2:4], order),
            payload[4],
            int.from_bytes(payload[5:9], order),
            payload[9])


def stored_entries(capture, blocks, q):
    """The entries of a capture, ticks as stored, echoes as written, filler
    dropped, entry ordinals counted from zero over the true entries."""
    entries = []
    previous = (0, 0)
    for ordinal, block in enumerate(blocks):
        lines = list(block)
        if ordinal == 0 and capture.has(8):
            filler = q["shadow_pad_base"] - 3
            lines = lines[:max(0, len(lines) - filler)]
        little = ordinal == capture.flipped_block()
        for payload in lines:
            data = payload
            if capture.has(1):
                data = xor_bytes(data, mask("chain", [capture.number, previous[0], previous[1]]))
            if capture.has(0):
                data = xor_bytes(data, mask(LABEL_WORDS[q["seal_label_index"]],
                                           [capture.number, len(entries)]))
            if capture.has(9):
                data = rot_right(data, (len(entries) + 1) * q["spin_modulus"])
            entry = unpack(data, little)
            if entry is None:
                previous = (0, 0)
                entries.append(None)
            else:
                previous = (entry[0], entry[3])
                entries.append(entry)
    return entries


def restored_ticks(capture, entries):
    ticks = []
    for index, entry in enumerate(entries):
        stored = 0 if entry is None else entry[0]
        if not capture.has(2) or index == 0:
            ticks.append(stored)
        elif index == 1:
            ticks.append((stored + ticks[0]) % 65536)
        else:
            ticks.append((stored + 2 * ticks[index - 1] - ticks[index - 2]) % 65536)
    return ticks


def word_entries(capture, entries, q, caps):
    """Ticks restored and unit words resolved."""
    ticks = restored_ticks(capture, entries)
    texts = []
    for index, entry in enumerate(entries):
        if entry is None:
            texts.append(None)
            continue
        if capture.has(10):
            donor = caps[(capture.number + q["alias_donor_shift"]) % len(caps)]
            words = donor.words[q["alias_donor_shift"]:] + \
                donor.words[:q["alias_donor_shift"]]
        else:
            words = UNIT_WORDS
        texts.append((ticks[index], words[entry[1] % len(words)],
                      entry[2], entry[3], entry[4]))
    return texts


def resolve_echoes(capture, texts, span):
    resolved = []
    for index, entry in enumerate(texts):
        if entry is not None and capture.has(5) and entry[2] == 224:
            distance = index % (span - 1) + 1
            target = index - distance
            if target >= 0 and resolved[target] is not None:
                source = resolved[target]
                resolved.append((entry[0], source[1], source[2], source[3], source[4]))
                continue
        resolved.append(entry)
    return resolved


def decode_entries(caps, q):
    """Every entry the captures decode: (capture, ordinal, tick, word, kind,
    amount, mark) with echoes resolved."""
    entries = []
    for capture in caps:
        blocks = masked_blocks(capture, q)
        stored = stored_entries(capture, blocks, q)
        texts = word_entries(capture, stored, q, caps)
        texts = resolve_echoes(capture, texts, q["echo_window_span"])
        for ordinal, text in enumerate(texts):
            if text is None:
                continue
            entries.append({"capture": capture.number, "ordinal": ordinal,
                            "tick": text[0], "word": text[1], "kind": text[2],
                            "amount": Fraction(text[3]), "mark": text[4],
                            "raw_kind": text[2]})
    return entries


# ---------------------------------------------------------------- control figures

def ctrl_a(caps, value):
    frags = []
    for cap in caps:
        bias = (3 * cap.number + 1) % value if cap.has(7) else 0
        frags.append("%d:%d" % (cap.number, bias))
    return control_digest(frags)


def ctrl_b(caps, value):
    frags = []
    for cap in caps:
        payloads = [p.hex() for block in unweave(cap, value) for p in block]
        frags.append("%d:%s" % (cap.number, ",".join(payloads)))
    return control_digest(frags)


def ctrl_c(caps, q, value):
    frags = []
    for cap in caps:
        blocks = unward(cap, unweave(cap, q["weave_seed_offset"]), value)
        payloads = [p.hex() if p is not None else "0" * 24
                    for block in blocks for p in block]
        frags.append("%d:%s" % (cap.number, ",".join(payloads)))
    return control_digest(frags)


def ctrl_d(caps, q, value):
    frags = []
    for cap in caps:
        blocks = unward(cap, unweave(cap, q["weave_seed_offset"]),
                        q["sentinel_code_value"])
        blocks = undrift(cap, blocks, value)
        payloads = [p.hex() if p is not None else "0" * 24
                    for block in blocks for p in block]
        frags.append("%d:%s" % (cap.number, ",".join(payloads)))
    return control_digest(frags)


def ctrl_e(caps, q, value):
    label = LABEL_WORDS[value]
    frags = []
    for cap in caps:
        blocks = masked_blocks(cap, q)
        payload = blocks[0][0]
        if cap.has(1):
            payload = xor_bytes(payload, mask("chain", [cap.number, 0, 0]))
        if cap.has(0):
            payload = xor_bytes(payload, mask(label, [cap.number, 0]))
        frags.append("%d:%s" % (cap.number, payload.hex()))
    return control_digest(frags)


def ctrl_f(caps, q, value):
    label = LABEL_WORDS[q["seal_label_index"]]
    frags = []
    for cap in caps:
        blocks = masked_blocks(cap, q)
        payload = blocks[0][0]
        if cap.has(1):
            payload = xor_bytes(payload, mask("chain", [cap.number, 0, 0]))
        if cap.has(0):
            payload = xor_bytes(payload, mask(label, [cap.number, 0]))
        if cap.has(9):
            payload = rot_right(payload, value)
        little = 0 == cap.flipped_block()
        entry = unpack(payload, little)
        frags.append("%d:%s" % (cap.number, "none" if entry is None else
                               "%d/%d/%d/%d/%d" % entry))
    return control_digest(frags)


def ctrl_g(caps, q, value):
    qq = dict(q)
    qq["shadow_pad_base"] = value
    frags = []
    for cap in caps:
        stored = stored_entries(cap, masked_blocks(cap, qq), qq)
        texts = ["none" if e is None else "%d/%d/%d/%d/%d" % e for e in stored]
        frags.append("%d:%s" % (cap.number, ",".join(texts)))
    return control_digest(frags)


def ctrl_h(caps, q, value):
    qq = dict(q)
    qq["alias_donor_shift"] = value
    frags = []
    for cap in caps:
        stored = stored_entries(cap, masked_blocks(cap, qq), qq)
        texts = word_entries(cap, stored, qq, caps)
        rendered = ["none" if t is None else "%d/%s/%d/%d/%d" % t for t in texts]
        frags.append("%d:%s" % (cap.number, ",".join(rendered)))
    return control_digest(frags)


def ctrl_i(caps, q, value):
    frags = []
    for cap in caps:
        stored = stored_entries(cap, masked_blocks(cap, q), q)
        texts = word_entries(cap, stored, q, caps)
        resolved = resolve_echoes(cap, texts, value)
        rendered = ["none" if t is None else "%d/%s/%d/%d/%d" % t for t in resolved]
        frags.append("%d:%s" % (cap.number, ",".join(rendered)))
    return control_digest(frags)


def ctrl_j(units, cadence_modulus, cadences):
    frags = []
    for unit in sorted(units):
        total = units[unit]["tick_total"]
        frags.append("%s:%s" % (unit, cadences[(total // cadence_modulus) % 4]))
    return control_digest(frags)


def ctrl_k(target):
    return control_digest([rational(target)])


# ---------------------------------------------------------------- settlement

def identity_settle(register):
    """The canonical charter of every roster word, and the passes it took."""
    canon = {row["word"]: row["charter"] for row in register}
    known = {row["word"] for row in register}
    passes = 0
    while True:
        passes += 1
        stale = False
        for row in register:
            word = row["word"]
            successor = row["successor"]
            target = canon[word]
            if successor and successor != word and successor in known:
                target = canon[successor]
            if canon[word] != target:
                canon[word] = target
                stale = True
        if not stale:
            return canon, passes


def chase(register_index, word, tick):
    """The word in force at a tick, or None when the entry retires."""
    if word not in register_index:
        return None
    steps = 0
    while True:
        row = register_index[word]
        successor = row["successor"]
        if successor == word or not row["closed"] or tick <= row["closed"]:
            return word
        if not successor or successor not in register_index:
            return None
        word = successor
        steps += 1
        if steps > 64:
            return None


def walk_key(entry):
    return (entry["tick"], entry["capture"], entry["ordinal"])


def settle(entries, register, canon, windows):
    index = {row["word"]: row for row in register}
    live_windows = [w for w in windows if w["live"] and w["first"] <= w["last"]]

    def in_window(tick):
        return any(w["first"] <= tick <= w["last"] for w in live_windows)

    retired, offwindow, live = [], [], []
    for entry in entries:
        unit = chase(index, entry["word"], entry["tick"])
        entry["unit"] = unit
        entry["charter"] = canon[unit] if unit else None
        if unit is None:
            retired.append(entry)
        elif not in_window(entry["tick"]):
            offwindow.append(entry)
        else:
            live.append(entry)
    live.sort(key=walk_key)

    cancelled = set()
    promoted = 0
    pool = {}
    for entry in live:
        if entry["raw_kind"] != 3:
            pool.setdefault((entry["unit"], entry["kind"]), []).append(entry)
            continue
        kind = entry["mark"]
        queue = pool.setdefault((entry["unit"], kind), [])
        if queue:
            victim = queue.pop(0)
            cancelled.add(id(victim))
            cancelled.add(id(entry))
        else:
            promoted += 1
            entry["kind"] = kind
            queue.append(entry)
    survivors = [e for e in live if id(e) not in cancelled]

    baselines, counts = {}, {}
    for row in register:
        baselines[row["charter"]] = baselines.get(row["charter"], 0) + row["opened"]
        counts[row["charter"]] = counts.get(row["charter"], 0) + 1
    total_baseline = sum(baselines.values())

    # each live window's first tick renews every allowance before any entry at
    # that tick draws; a degenerate window renews nothing
    renewals = sorted(set(w["first"] for w in live_windows))
    allowance = {c: Fraction(baselines[c] * counts[c]) for c in baselines}
    surplus = Fraction(0)
    next_renewal = 0
    for entry in survivors:
        while next_renewal < len(renewals) and renewals[next_renewal] <= entry["tick"]:
            allowance = {c: Fraction(baselines[c] * counts[c]) for c in baselines}
            next_renewal += 1
        left = allowance.get(entry["charter"], Fraction(0))
        drawn = left if left < entry["amount"] else entry["amount"]
        if drawn < 0:
            drawn = Fraction(0)
        allowance[entry["charter"]] = left - drawn
        surplus += entry["amount"] - drawn
        entry["settled"] = drawn

    return {"retired": retired, "offwindow": offwindow, "live": live,
            "survivors": survivors, "promoted": promoted,
            "baselines": baselines, "counts": counts,
            "total_baseline": total_baseline, "surplus": surplus}


def unit_totals(survivors):
    totals = {}
    for entry in survivors:
        record = totals.setdefault(entry["unit"], {
            "unit": entry["unit"], "charter": entry["charter"],
            "tick_total": 0, "amount_total": Fraction(0),
            "kind_totals": [Fraction(0), Fraction(0), Fraction(0)], "count": 0})
        record["tick_total"] += entry["tick"]
        record["amount_total"] += entry["settled"]
        record["count"] += 1
        if entry["kind"] < 3:
            record["kind_totals"][entry["kind"]] += entry["settled"]
    return totals


def charter_stocks(register, totals, baselines, total_baseline):
    """stock(B) = baseline(B) + sum over A of share(A->B) * stock(A)."""
    opened = {row["word"]: row["charter"] for row in register}
    share = {}
    for unit, record in totals.items():
        origin = opened.get(unit)
        if origin is None or origin == record["charter"]:
            continue
        share[(origin, record["charter"])] = \
            share.get((origin, record["charter"]), Fraction(0)) + record["kind_totals"][1]
    share = {k: v / total_baseline for k, v in share.items()}

    charters = sorted(baselines)
    n = len(charters)
    pos = {name: i for i, name in enumerate(charters)}
    matrix = [[Fraction(0)] * n for _ in range(n)]
    for i, name in enumerate(charters):
        matrix[i][i] = Fraction(1)
    for (a, b), value in share.items():
        if a in pos and b in pos and a != b:
            matrix[pos[b]][pos[a]] -= value
    vector = [Fraction(baselines[name]) for name in charters]
    solution = gauss(matrix, vector)
    return [{"charter": charters[i], "stock": solution[i]} for i in range(n)]


def gauss(matrix, vector):
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = None
        for row in range(col, n):
            if a[row][col] != 0:
                pivot = row
                break
        if pivot is None:
            continue
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        for k in range(col, n + 1):
            a[col][k] /= factor
        for row in range(n):
            if row != col and a[row][col] != 0:
                ratio = a[row][col]
                for k in range(col, n + 1):
                    a[row][k] -= ratio * a[col][k]
    return [a[i][n] for i in range(n)]


def bench_subset(bench, target):
    """The one subset of the bench whose upkeep meets the target exactly."""
    names = [name for name, _ in bench]
    values = [value for _, value in bench]
    half = len(values) // 2

    def sums(items):
        """Every subset sum of items, with the member lists that make it."""
        table = {0: [()]}
        for index, value in enumerate(items):
            for total, choices in list(table.items()):
                for members in choices:
                    table.setdefault(total + value, []).append(members + (index,))
        return table

    left = sums(values[:half])
    right = sums(values[half:])
    hits = []
    for total, members in left.items():
        rest = int(target) - total
        if rest in right:
            for one in members:
                for two in right[rest]:
                    hits.append(sorted([names[i] for i in one] +
                                        [names[half + i] for i in two]))
    unique = sorted({tuple(hit) for hit in hits})
    return list(unique[0]) if unique else []


# ---------------------------------------------------------------- calibration

def solve_quantities(caps, specs, controls, baselines):
    """Recover the quantities the calibration slice fixes before the match is
    settled: the nine decode quantities, then the upkeep target scale.

    Each candidate is tested against the control figures in published order and
    is rejected with the first figure that separates it, recorded at the moment
    it is discarded.
    """
    solved = {}
    published = [name for name, _ in controls]
    figures = dict(controls)
    rejected = {spec["name"]: [] for spec in specs}

    order = [name for name in QUANTITY_ORDER if name != "cadence_modulus"]
    by_name = {spec["name"]: spec for spec in specs}

    def figure_for(control, trial):
        if control == "CTRL-A":
            return ctrl_a(caps, trial["frame_bias_limit"])
        if control == "CTRL-B":
            return ctrl_b(caps, trial["weave_seed_offset"])
        if control == "CTRL-C":
            return ctrl_c(caps, trial, trial["sentinel_code_value"])
        if control == "CTRL-D":
            return ctrl_d(caps, trial, trial["drift_modulus"])
        if control == "CTRL-E":
            return ctrl_e(caps, trial, trial["seal_label_index"])
        if control == "CTRL-F":
            return ctrl_f(caps, trial, trial["spin_modulus"])
        if control == "CTRL-G":
            return ctrl_g(caps, trial, trial["shadow_pad_base"])
        if control == "CTRL-H":
            return ctrl_h(caps, trial, trial["alias_donor_shift"])
        if control == "CTRL-I":
            return ctrl_i(caps, trial, trial["echo_window_span"])
        if control == "CTRL-K":
            return ctrl_k(Fraction(trial["upkeep_target_scale"] *
                                   sum(baselines.values())))
        return None

    for name in order:
        spec = by_name.get(name)
        if spec is None:
            continue
        chosen = None
        for candidate in spec["candidates"]:
            trial = dict(solved)
            trial[name] = candidate
            falsifier = None
            for control in published:
                if control not in figures or not needed(control, trial):
                    continue
                produced = figure_for(control, trial)
                if produced is None:
                    continue
                if produced != figures[control]:
                    falsifier = control
                    break
            if falsifier is None:
                chosen = candidate
                break
            rejected[name].append({"candidate": candidate, "falsifier": falsifier})
        if chosen is None:
            raise SystemExit("no candidate reproduces the control for %s" % name)
        solved[name] = chosen
    return solved, rejected


def needed(control, quantities):
    """A control figure can be produced only once every quantity it reads,
    ahead of the one it pins, is known."""
    requires = {
        "CTRL-A": ["frame_bias_limit"],
        "CTRL-B": ["weave_seed_offset"],
        "CTRL-C": ["weave_seed_offset", "sentinel_code_value"],
        "CTRL-D": ["weave_seed_offset", "sentinel_code_value", "drift_modulus"],
        "CTRL-E": ["weave_seed_offset", "sentinel_code_value", "drift_modulus",
                   "seal_label_index"],
        "CTRL-F": ["weave_seed_offset", "sentinel_code_value", "drift_modulus",
                   "seal_label_index", "spin_modulus"],
        "CTRL-G": ["weave_seed_offset", "sentinel_code_value", "drift_modulus",
                   "seal_label_index", "spin_modulus", "shadow_pad_base"],
        "CTRL-H": ["weave_seed_offset", "sentinel_code_value", "drift_modulus",
                   "seal_label_index", "spin_modulus", "shadow_pad_base",
                   "alias_donor_shift"],
        "CTRL-I": ["weave_seed_offset", "sentinel_code_value", "drift_modulus",
                   "seal_label_index", "spin_modulus", "shadow_pad_base",
                   "alias_donor_shift", "echo_window_span"],
        "CTRL-K": ["upkeep_target_scale"],
    }
    if control not in requires:
        return False
    return all(q in quantities for q in requires[control])


# ---------------------------------------------------------------- reports

def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2))
        handle.write("\n")


def main(argv):
    global UNIT_WORDS, LABEL_WORDS
    capture_dir, report_dir = argv[1], argv[2]
    os.makedirs(report_dir, exist_ok=True)

    calibration = find_file(capture_dir, "calibration.md")
    if calibration is None:
        raise SystemExit("calibration notes not found")
    specs, controls = parse_calibration(calibration)

    charter_notes = find_file(capture_dir, "charter-scale.md")
    if charter_notes:
        UNIT_WORDS, LABEL_WORDS = parse_word_tables(charter_notes)
    register_path = find_file(capture_dir, "roster-register.csv")
    windows_path = find_file(capture_dir, "tick-schedule.csv")
    bench_path = find_file(capture_dir, "bench-candidates.csv")
    register = parse_register(register_path)
    windows = parse_windows(windows_path)
    bench = parse_bench(bench_path)

    caps = load_captures(capture_dir)

    baselines = {}
    counts = {}
    for row in register:
        baselines[row["charter"]] = baselines.get(row["charter"], 0) + row["opened"]
        counts[row["charter"]] = counts.get(row["charter"], 0) + 1
    total_baseline = sum(baselines.values())

    quantities, rejected = solve_quantities(caps, specs, controls, baselines)

    entries = decode_entries(caps, quantities)
    canon, passes = identity_settle(register)
    result = settle(entries, register, canon, windows)
    totals = unit_totals(result["survivors"])

    cadences = ["peak", "steady", "burst", "latency"]

    # cadence_modulus is pinned by CTRL-J against the settled classes
    ctrl_j_figure = dict(controls).get("CTRL-J")
    by_name = {spec["name"]: spec for spec in specs}
    chosen_cadence = None
    for candidate in by_name["cadence_modulus"]["candidates"]:
        if ctrl_j(totals, candidate, cadences) == ctrl_j_figure:
            chosen_cadence = candidate
            break
        rejected["cadence_modulus"].append({"candidate": candidate,
                                            "falsifier": "CTRL-J"})
    if chosen_cadence is None:
        raise SystemExit("no candidate reproduces CTRL-J")
    quantities["cadence_modulus"] = chosen_cadence
    for unit, record in totals.items():
        record["cadence"] = cadences[(record["tick_total"] // chosen_cadence) % 4]

    # upkeep_target_scale is pinned by CTRL-K against the upkeep target
    ctrl_k_figure = dict(controls).get("CTRL-K")
    chosen_scale = None
    for candidate in by_name["upkeep_target_scale"]["candidates"]:
        target = Fraction(candidate) * total_baseline
        if ctrl_k(target) == ctrl_k_figure:
            chosen_scale = candidate
            break
        rejected["upkeep_target_scale"].append({"candidate": candidate,
                                                "falsifier": "CTRL-K"})
    if chosen_scale is None:
        raise SystemExit("no candidate reproduces CTRL-K")
    quantities["upkeep_target_scale"] = chosen_scale
    target = Fraction(chosen_scale) * total_baseline

    stocks = charter_stocks(register, totals, baselines, total_baseline)
    bench_words = bench_subset(bench, target)
    bench_upkeep = Fraction(sum(dict(bench)[w] for w in bench_words))

    # ------------------------------------------------------------- reports
    visible = {
        "capture_count": len(caps),
        "entry_total": len(entries),
        "settled_total": len(result["survivors"]),
        "units": [],
    }
    for unit in sorted(totals):
        record = totals[unit]
        visible["units"].append({
            "unit": record["unit"],
            "charter": record["charter"],
            "tick_total": record["tick_total"],
            "amount_total": rational(record["amount_total"]),
            "cadence": record["cadence"],
            "kind_totals": [rational(v) for v in record["kind_totals"]],
        })
    write_json(os.path.join(report_dir, "scenario_visible.json"), visible)

    for cadence in cadences:
        members = [totals[u] for u in sorted(totals) if totals[u]["cadence"] == cadence]
        payload = {
            "cadence": cadence,
            "unit_count": len(members),
            "amount_total": rational(sum((m["amount_total"] for m in members),
                                         Fraction(0))),
            "units": [{
                "unit": m["unit"],
                "charter": m["charter"],
                "tick_total": m["tick_total"],
                "amount_total": rational(m["amount_total"]),
            } for m in members],
        }
        write_json(os.path.join(report_dir, "scenario_%s.json" % cadence), payload)

    decoded_amount = sum((e["amount"] for e in entries), Fraction(0))
    settled_amount = sum((e["settled"] for e in result["survivors"]), Fraction(0))
    dropped = result["retired"] + result["offwindow"]
    dropped_amount = sum((e["amount"] for e in dropped), Fraction(0))
    perf = {
        "charter_stocks": [{"charter": s["charter"], "stock": rational(s["stock"])}
                           for s in stocks],
        "settled_total": rational(settled_amount),
        "decoded_total": rational(decoded_amount),
        "reversal_count": sum(1 for e in entries if e["raw_kind"] == 3),
        "promoted_reversal_count": result["promoted"],
    }
    write_json(os.path.join(report_dir, "perf_report.json"), perf)

    quantity_rows = []
    for spec in specs:
        name = spec["name"]
        quantity_rows.append({
            "name": name,
            "value": quantities[name],
            "control": spec["control"],
            "rejected": [{"candidate": r["candidate"], "falsifier": r["falsifier"]}
                         for r in rejected[name]],
        })
    table = []
    for control, published in controls:
        if control == "CTRL-J":
            produced = ctrl_j(totals, chosen_cadence, cadences)
        elif control == "CTRL-K":
            produced = ctrl_k(target)
        else:
            produced = produce(caps, quantities, control)
        table.append({"control": control, "published": published,
                      "produced": produced})
    analysis = {
        "quantities": quantity_rows,
        "settling_passes": passes,
        "calibration_table": table,
    }
    write_json(os.path.join(report_dir, "bottleneck_analysis.json"), analysis)

    recommendations = {
        "target": rational(target),
        "bench": sorted(bench_words),
        "bench_upkeep": rational(bench_upkeep),
        "residual_after_bench": rational(target - bench_upkeep),
    }
    write_json(os.path.join(report_dir, "recommendations.json"), recommendations)

    quality = {
        "dropped_retired": len(result["retired"]),
        "dropped_offwindow": len(result["offwindow"]),
        "dropped_amount_total": rational(dropped_amount),
        "decoded_amount_total": rational(decoded_amount),
        "settled_amount_total": rational(settled_amount),
        "conservation_residual": rational(decoded_amount - settled_amount - dropped_amount),
    }
    write_json(os.path.join(report_dir, "data_quality.json"), quality)


def produce(caps, quantities, control):
    if control == "CTRL-A":
        return ctrl_a(caps, quantities["frame_bias_limit"])
    if control == "CTRL-B":
        return ctrl_b(caps, quantities["weave_seed_offset"])
    if control == "CTRL-C":
        return ctrl_c(caps, quantities, quantities["sentinel_code_value"])
    if control == "CTRL-D":
        return ctrl_d(caps, quantities, quantities["drift_modulus"])
    if control == "CTRL-E":
        return ctrl_e(caps, quantities, quantities["seal_label_index"])
    if control == "CTRL-F":
        return ctrl_f(caps, quantities, quantities["spin_modulus"])
    if control == "CTRL-G":
        return ctrl_g(caps, quantities, quantities["shadow_pad_base"])
    if control == "CTRL-H":
        return ctrl_h(caps, quantities, quantities["alias_donor_shift"])
    if control == "CTRL-I":
        return ctrl_i(caps, quantities, quantities["echo_window_span"])
    return None


if __name__ == "__main__":
    main(sys.argv)
