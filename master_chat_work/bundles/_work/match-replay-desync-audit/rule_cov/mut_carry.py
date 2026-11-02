"""Settle a Ninefold Marches replay capture set into the reports its notes define.

Usage: optimize.py CAPTURE_DIR REPORT_DIR

The capture directory holds the captures, the roster register, the tick
schedule, the bench candidates and the calibration slice. Files are recognised
by what they contain, not by their names. The program pins the eleven withheld
quantities by stamping every published candidate against its control figure,
unwinds each capture through the transforms its flag word names, settles the
surviving entries under the engine rules in exact rational arithmetic, and
writes the eight settlement reports and the derivation record. Only the
standard library is used.
"""

import hashlib
import itertools
import json
import sys
from fractions import Fraction
from pathlib import Path

ENGINE_KEY = b"MRD-2031"
PAYLOAD = 12
TICK_SPAN = 1 << 16
ECHO_KIND = 224
REVERSAL_KIND = 3

UNIT_WORDS = (
    "aurochs", "basilisk", "cockatrice", "dryad", "ettin", "fenrir", "golem",
    "hydra", "ifrit", "jotun", "kelpie", "lamia", "manticore", "nixie", "ogre",
    "pegasus", "quasit", "roc", "sylph", "troll", "undine", "vodyanoi", "wyvern",
    "xorn",
)
LABEL_WORDS = (
    "aegis", "banner", "cinder", "dagger", "ember", "falcon", "gale", "harrow",
    "ingot", "javelin", "kestrel", "lantern",
)
CADENCE_CLASSES = ("peak", "steady", "burst", "latency")

# Bit order of the flag word, least significant first, as the container note lists it.
TRANSFORMS = ("sealed", "chained", "stepped", "drifted", "woven", "echoed",
              "flipped", "padded", "shadowed", "spun", "aliased", "warded")

# What each control reads, from the calibration slice: a ladder rung for the
# nine wire quantities, then the cadence classes, then the upkeep target.
RUNG_OF = {
    "frame_bias_limit": 1, "weave_seed_offset": 2, "sentinel_code_value": 3,
    "drift_modulus": 4, "seal_label_index": 5, "spin_modulus": 6,
    "shadow_pad_base": 7, "alias_donor_shift": 8, "echo_window_span": 9,
}
CADENCE_QUANTITY = "cadence_modulus"
UPKEEP_QUANTITY = "upkeep_target_scale"
RECORD_NAME = "bottleneck_analysis.json"


# ---------------------------------------------------------------- primitives

def keyed_mask(label, *numbers):
    """Twelve byte mask: SHA-256 over the engine key, the label and ':'-prefixed numbers."""
    body = ENGINE_KEY + label.encode("ascii")
    for number in numbers:
        body += b":" + str(int(number)).encode("ascii")
    return hashlib.sha256(body).digest()[:PAYLOAD]


def control_stamp(fragments):
    """Published control figure: first twelve hex characters over '|'-prefixed fragments."""
    body = ENGINE_KEY + b"".join(b"|" + str(part).encode("utf-8") for part in fragments)
    return hashlib.sha256(body).hexdigest()[:12]


def xor_bytes(body, pad):
    return bytes(left ^ right for left, right in zip(body, pad))


def turn_right(body, amount):
    """Undo a left rotation by `amount` bytes."""
    amount %= len(body)
    if not amount:
        return body
    return body[-amount:] + body[:-amount]


def shuffle_order(offset, number, block, width):
    """The Fisher and Yates order the woven transform used for one block."""
    counter = ((offset + 97 * number + 7 * block) * 2654435761 + 1013904223) & 0xFFFFFFFF
    if counter == 0:
        counter = 2654435769
    order = list(range(width))
    for position in range(width - 1, 0, -1):
        counter = (counter ^ (counter << 13)) & 0xFFFFFFFF
        counter = (counter ^ (counter >> 17)) & 0xFFFFFFFF
        counter = (counter ^ (counter << 5)) & 0xFFFFFFFF
        swap = counter % (position + 1)
        order[position], order[swap] = order[swap], order[position]
    return order


def collapse_doubles(body, reserved):
    """Turn every doubled reserved byte back into one; None when the escape is broken."""
    out = bytearray()
    index = 0
    while index < len(body):
        out.append(body[index])
        if body[index] == reserved:
            if index + 1 >= len(body) or body[index + 1] != reserved:
                return None
            index += 1
        index += 1
    return bytes(out)


def unpack(body, little):
    """Read the five fields of a twelve byte payload whose check holds, else None."""
    if body is None or len(body) != PAYLOAD:
        return None
    if keyed_mask("entry", *body[:10])[:2] != body[10:12]:
        return None
    order = "little" if little else "big"
    return (int.from_bytes(body[0:2], order), int.from_bytes(body[2:4], order),
            body[4], int.from_bytes(body[5:9], order), body[9])


def rational(value):
    value = Fraction(value)
    return "%d/%d" % (value.numerator, value.denominator)


def render_raw(fields):
    return "none" if fields is None else "%d/%d/%d/%d/%d" % fields


def render_entry(entry):
    if entry is None:
        return "none"
    return "%d/%s/%d/%d/%d" % (entry["tick"], entry["word"], entry["kind"],
                               entry["amount"], entry["mark"])


# ---------------------------------------------------------------- inputs

class Capture:
    """One RPL1 capture as written on the wire."""

    def __init__(self, text):
        self.header = {}
        self.blocks = []
        for line in text.splitlines():
            if line.startswith("#RPL1"):
                for field in line.split()[1:]:
                    key, _, value = field.partition("=")
                    self.header[key] = value
            elif line.startswith("B "):
                parts = line.split()
                self.blocks.append((int(parts[1]), []))
            elif line.startswith("R "):
                self.blocks[-1][1].append(bytes.fromhex(line[2:].strip()))
        self.number = int(self.header["number"])
        self.flags = int(self.header["flags"], 16)
        self.block_count = int(self.header["blocks"])
        self.words = self.header["words"].split(",")

    def applies(self, transform):
        return bool(self.flags >> TRANSFORMS.index(transform) & 1)


def read_inputs(folder):
    """Sort the files of a capture directory by what they hold."""
    inputs = {"captures": [], "roster": [], "schedule": [], "bench": [], "slice": None}
    for path in sorted(Path(folder).iterdir()):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        first = text.split("\n", 1)[0].strip()
        if first.startswith("#RPL1"):
            inputs["captures"].append(Capture(text))
        elif "| control | published figure |" in text:
            inputs["slice"] = read_slice(text)
        elif first.startswith("word,") and first.endswith(",successor"):
            inputs["roster"] = read_rows(text, roster_row)
        elif first.startswith("window,"):
            inputs["schedule"] = read_rows(text, window_row)
        elif first == "word,upkeep":
            inputs["bench"] = read_rows(text, bench_row)
    inputs["captures"].sort(key=lambda capture: capture.number)
    if inputs["slice"] is None:
        raise ValueError("no calibration slice in %s" % folder)
    return inputs


def read_rows(text, build):
    lines = [line for line in text.splitlines() if line.strip()]
    names = lines[0].split(",")
    return [build(dict(zip(names, line.split(",")))) for line in lines[1:]]


def roster_row(cells):
    return {"word": cells["word"], "charter": cells["charter"], "opened": int(cells["opened"]),
            "closed": int(cells["closed"]) if cells["closed"] else 0,
            "successor": cells["successor"]}


def window_row(cells):
    return {"first": int(cells["first_tick"]), "last": int(cells["last_tick"]),
            "live": cells["live"].strip() == "1"}


def bench_row(cells):
    return {"word": cells["word"], "upkeep": int(cells["upkeep"])}


def read_slice(text):
    """Quantities in published order with their candidates and controls, and the figures."""
    quantities = []
    figures = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].startswith("`") and " through " in cells[1]:
            low, _, high = cells[1].partition(" through ")
            quantities.append((cells[0].strip("`"), list(range(int(low), int(high) + 1)),
                               cells[2]))
        elif len(cells) == 2 and cells[0].startswith("CTRL-"):
            figures[cells[0]] = cells[1].strip("`")
    return {"quantities": quantities, "figures": figures}


# ---------------------------------------------------------------- unwinding

class Unwinder:
    """Undo one capture's transforms in the order the serializer stacked them.

    `rung` stops after the stage a control reads and returns that stage's
    fragment. Rung 9 also returns the decoded entries and the echo count.
    """

    def __init__(self, ring, values):
        self.values = values
        self.words_of = {capture.number: capture.words for capture in ring}
        self.ring_size = len(ring)

    def word_table(self, capture):
        if not capture.applies("aliased"):
            return list(UNIT_WORDS)
        shift = self.values["alias_donor_shift"]
        donor = list(self.words_of[(capture.number + shift) % self.ring_size])
        turn = shift % len(donor)
        return donor[turn:] + donor[:turn]

    def rung(self, capture, depth):
        values = self.values
        number = capture.number
        if depth == 1:
            bias = (3 * number + 1) % values["frame_bias_limit"] if capture.applies("padded") else 0
            return "%d:%d" % (number, bias), None

        blocks = []
        for ordinal, lines in capture.blocks:
            if capture.applies("woven"):
                order = shuffle_order(values["weave_seed_offset"], number, ordinal, len(lines))
                plain = [None] * len(lines)
                for position, line in enumerate(lines):
                    plain[order[position]] = line
                lines = plain
            blocks.append((ordinal, list(lines)))
        if depth == 2:
            return self.flat(number, blocks), None

        if capture.applies("warded"):
            reserved = values["sentinel_code_value"]
            blocks = [(ordinal, [collapse_doubles(line, reserved) for line in lines])
                      for ordinal, lines in blocks]
            # A lone reserved byte or a payload that is not twelve bytes reads as zeros.
            blocks = [(ordinal, [line if line is not None and len(line) == PAYLOAD else bytes(PAYLOAD)
                                 for line in lines]) for ordinal, lines in blocks]
        if depth == 3:
            return self.flat(number, blocks), None

        if capture.applies("drifted"):
            modulus = values["drift_modulus"]
            lifted = []
            for ordinal, lines in blocks:
                pad = keyed_mask("drift", number, (ordinal + 1 + 5 * number) % modulus)
                lifted.append((ordinal, [None if line is None else xor_bytes(line, pad)
                                         for line in lines]))
            blocks = lifted
        if depth == 4:
            return self.flat(number, blocks), None

        label = LABEL_WORDS[values["seal_label_index"]] if capture.applies("sealed") else None
        if depth in (5, 6):
            head = blocks[0][1][0] if blocks and blocks[0][1] else None
            if head is not None and capture.applies("chained"):
                head = xor_bytes(head, keyed_mask("chain", number, 0, 0))
            if head is not None and label is not None:
                head = xor_bytes(head, keyed_mask(label, number, 0))
            if depth == 5:
                return "%d:%s" % (number, "none" if head is None else head.hex()), None
            if head is not None and capture.applies("spun"):
                head = turn_right(head, values["spin_modulus"] % PAYLOAD)
            little = capture.applies("flipped") and number % capture.block_count == 0
            return "%d:%s" % (number, render_raw(unpack(head, little))), None

        filler = values["shadow_pad_base"] - 3 if capture.applies("shadowed") else 0
        stream = []
        for ordinal, lines in blocks:
            if ordinal == 0 and filler:
                lines = lines[:max(0, len(lines) - filler)]
            stream.extend((ordinal, line) for line in lines)

        flipped_block = number % capture.block_count if capture.applies("flipped") else None
        raw = []
        carry = (0, 0)
        for index, (ordinal, line) in enumerate(stream):
            body = line
            if body is not None and capture.applies("chained"):
                body = xor_bytes(body, keyed_mask("chain", number, carry[0], carry[1]))
            if body is not None and label is not None:
                body = xor_bytes(body, keyed_mask(label, number, index))
            if body is not None and capture.applies("spun"):
                body = turn_right(body, ((index + 1) * values["spin_modulus"]) % PAYLOAD)
            fields = unpack(body, ordinal == flipped_block)
            # The carried mask reads the stored tick and amount of the entry before it,
            # 0 and 0 for the first entry and after a none.
            carry = carry if fields is None else (fields[0], fields[3])
            raw.append(fields)
        if depth == 7:
            return "%d:%s" % (number, ",".join(render_raw(fields) for fields in raw)), None

        entries = self.lift(capture, raw)
        if depth == 8:
            return "%d:%s" % (number, ",".join(render_entry(entry) for entry in entries)), None

        echoes = sum(1 for entry in entries if entry is not None and entry["kind"] == ECHO_KIND)
        reach = values["echo_window_span"] - 1
        for position, entry in enumerate(entries):
            if entry is None or entry["kind"] != ECHO_KIND:
                continue
            origin = position - (position % reach + 1)
            if origin < 0 or entries[origin] is None:
                continue
            for field in ("word", "kind", "amount", "mark"):
                entry[field] = entries[origin][field]
        fragment = "%d:%s" % (number, ",".join(render_entry(entry) for entry in entries))
        return fragment, (entries, echoes)

    def lift(self, capture, raw):
        """Rebuild ticks and unit words for the decoded payloads."""
        table = self.word_table(capture)
        stepped = capture.applies("stepped")
        ticks = []
        for fields in raw:
            # A none entry counts as a stored 0 in the stepped series.
            stored = 0 if fields is None else fields[0]
            if not stepped or not ticks:
                ticks.append(stored % TICK_SPAN)
            elif len(ticks) == 1:
                ticks.append((stored + ticks[0]) % TICK_SPAN)
            else:
                ticks.append((stored + 2 * ticks[-1] - ticks[-2]) % TICK_SPAN)
        entries = []
        for fields, tick in zip(raw, ticks):
            if fields is None:
                entries.append(None)
                continue
            entries.append({"tick": tick, "word": table[fields[1] % len(table)], "kind": fields[2],
                            "amount": fields[3], "mark": fields[4]})
        return entries

    @staticmethod
    def flat(number, blocks):
        return "%d:%s" % (number, ",".join("none" if line is None else line.hex()
                                           for _, lines in blocks for line in lines))


def ladder_figure(ring, values, depth):
    walker = Unwinder(ring, values)
    return control_stamp([walker.rung(capture, depth)[0] for capture in ring])


def decode_all(ring, values):
    walker = Unwinder(ring, values)
    decoded = {}
    echoes = 0
    for capture in ring:
        entries, count = walker.rung(capture, 9)[1]
        decoded[capture.number] = entries
        echoes += count
    return decoded, echoes


# ---------------------------------------------------------------- settlement

class Register:
    """The roster register: who an entry belongs to, and how the charters settle."""

    def __init__(self, rows):
        self.rows = rows
        self.row_of = {row["word"]: row for row in rows}
        self.baseline = {}
        self.opened = {}
        for row in rows:
            self.baseline[row["charter"]] = self.baseline.get(row["charter"], 0) + row["opened"]
            self.opened[row["charter"]] = self.opened.get(row["charter"], 0) + 1

    def owner(self, word, tick):
        """The canonical (word, charter) for an entry, or None when it retired."""
        for _ in range(len(self.rows) + 1):
            row = self.row_of.get(word)
            if row is None:
                return None
            if row["successor"] == word or not row["closed"] or tick <= row["closed"]:
                return word, row["charter"]
            if not row["successor"]:
                return None
            word = row["successor"]
        raise ValueError("successor links loop for an entry at tick %d" % tick)

    def settling_passes(self):
        canonical = {row["word"]: row["charter"] for row in self.rows}
        for passes in range(1, len(self.rows) + 2):
            stale = 0
            for row in self.rows:
                heir = row["successor"]
                if heir and heir != row["word"] and canonical[row["word"]] != canonical[heir]:
                    canonical[row["word"]] = canonical[heir]
                    stale += 1
            if not stale:
                return passes
        raise ValueError("the register never settles")

    def depth(self, word):
        steps = 0
        while True:
            row = self.row_of[word]
            if not row["closed"] or not row["successor"] or row["successor"] == word:
                return steps
            word = row["successor"]
            steps += 1
            if steps > len(self.rows):
                raise ValueError("successor links loop from %s" % word)


def determinant(matrix):
    """Exact determinant by cofactor expansion, memoised on the remaining columns."""
    size = len(matrix)
    memo = {}

    def expand(row, columns):
        if row == size:
            return Fraction(1)
        if (row, columns) in memo:
            return memo[(row, columns)]
        total = Fraction(0)
        for place, column in enumerate(columns):
            cell = matrix[row][column]
            if cell:
                rest = columns[:place] + columns[place + 1:]
                total += (-1) ** place * cell * expand(row + 1, rest)
        memo[(row, columns)] = total
        return total

    return expand(0, tuple(range(size)))


def charter_stocks(charters, baseline, share):
    """Solve stock[t] = baseline[t] + sum over g of stock[g] * share[g -> t] by Cramer's rule."""
    system = [[Fraction(1) if giver == taker else -share.get((giver, taker), Fraction(0))
               for giver in charters] for taker in charters]
    whole = determinant(system)
    if whole == 0:
        raise ValueError("the charter relations have no single assignment")
    stocks = {}
    for place, name in enumerate(charters):
        swapped = [row[:place] + [Fraction(baseline[charters[index]])] + row[place + 1:]
                   for index, row in enumerate(system)]
        stocks[name] = determinant(swapped) / whole
    return stocks


def exact_bench(rows, target):
    """The one bench subset whose upkeep meets the target, found by meeting in the middle."""
    half = len(rows) // 2
    left, right = rows[:half], rows[half:]

    def subset_sums(part):
        sums = {}
        for size in range(len(part) + 1):
            for chosen in itertools.combinations(part, size):
                sums.setdefault(sum(row["upkeep"] for row in chosen), []).append(chosen)
        return sums

    right_sums = subset_sums(right)
    matches = []
    for total, picks in subset_sums(left).items():
        for other in right_sums.get(target - total, []):
            matches.extend(pick + other for pick in picks)
    if len(matches) != 1:
        raise ValueError("%d bench subsets meet the target, expected exactly one" % len(matches))
    return sorted(row["word"] for row in matches[0])


def settle(decoded, register, schedule):
    """Apply the engine rules to the decoded entries and collect every settled figure."""
    spans = [(row["first"], row["last"]) for row in schedule
             if row["live"] and row["first"] <= row["last"]]
    walk = sorted(((entry["tick"], number, ordinal, entry)
                   for number, entries in decoded.items()
                   for ordinal, entry in enumerate(entries) if entry is not None),
                  key=lambda item: item[:3])
    walk = [item[3] for item in walk]

    out = {"entry_total": len(walk), "reversal_count": 0, "dropped_retired": 0,
           "dropped_offwindow": 0, "decoded": Fraction(0), "dropped": Fraction(0)}
    live = []
    for entry in walk:
        out["decoded"] += entry["amount"]
        if entry["kind"] == REVERSAL_KIND:
            out["reversal_count"] += 1
        owner = register.owner(entry["word"], entry["tick"])
        if owner is None:
            out["dropped_retired"] += 1
            out["dropped"] += entry["amount"]
        elif not any(first <= entry["tick"] <= last for first, last in spans):
            out["dropped_offwindow"] += 1
            out["dropped"] += entry["amount"]
        else:
            live.append(dict(entry, unit=owner[0], charter=owner[1],
                             opening=register.row_of[entry["word"]]["charter"], kept=None))

    # Earliest-uncancelled matching per (canonical unit, kind). The two readings of
    # the rule first strike different entries where a queue holds two or more.
    pending = {}
    out["promoted"] = 0
    out["last_promotion"] = -1
    out["divergence"] = -1
    for position, entry in enumerate(live):
        if entry["kind"] != REVERSAL_KIND:
            entry["kept"] = entry["kind"]
            pending.setdefault((entry["unit"], entry["kind"]), []).append(entry)
            continue
        queue = pending.setdefault((entry["unit"], entry["mark"]), [])
        if out["divergence"] < 0 and len(queue) >= 2:
            out["divergence"] = position
        if queue:
            queue.pop(0)["kept"] = None
        else:
            out["promoted"] += 1
            out["last_promotion"] = position
            entry["kept"] = entry["mark"]
            queue.append(entry)
    out["divergence_tick"] = live[out["divergence"]]["tick"] if out["divergence"] >= 0 else 0

    # Matching is finished above, so only entries that stay settled draw. Each
    # charter allowance is renewed at the first tick of every live window.
    openings = sorted(first for first, _ in spans)
    left = {}
    units = {}
    flow = {}
    out["settled"] = Fraction(0)
    out["settled_total"] = 0
    for entry in live:
        if entry["kept"] is None:
            continue
        renewal = max(first for first in openings if first <= entry["tick"])
        charter = entry["charter"]
        if left.get(charter, (None,))[0] != renewal:
            left[charter] = (renewal, Fraction(register.baseline[charter] * register.opened[charter]))
        amount = min(Fraction(entry["amount"]), left[charter][1])
        left[charter] = (renewal, left[charter][1] - amount)
        out["settled"] += amount
        out["settled_total"] += 1
        seat = units.setdefault(entry["unit"], {
            "unit": entry["unit"], "charter": entry["charter"], "tick_total": 0,
            "amount_total": Fraction(0), "kind_totals": [Fraction(0)] * 3})
        seat["tick_total"] += entry["tick"]
        seat["amount_total"] += amount
        seat["kind_totals"][entry["kept"]] += amount
        if entry["kept"] == 1 and entry["opening"] != entry["charter"]:
            pair = (entry["opening"], entry["charter"])
            flow[pair] = flow.get(pair, Fraction(0)) + amount

    total_base = sum(register.baseline.values())
    charters = sorted(register.baseline)
    share = {pair: amount / total_base for pair, amount in flow.items()}
    out["units"] = units
    out["charters"] = charters
    out["stocks"] = charter_stocks(charters, register.baseline, share)
    out["total_base"] = total_base
    return out


def cadence_of(tick_total, modulus):
    return CADENCE_CLASSES[(tick_total // modulus) % 4]


def cadence_figure(fitted, modulus):
    return control_stamp(["%s:%s" % (word, cadence_of(fitted["units"][word]["tick_total"], modulus))
                          for word in sorted(fitted["units"])])


def upkeep_figure(fitted, scale):
    return control_stamp([rational(scale * fitted["total_base"])])


# ---------------------------------------------------------------- recovery

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


class Recovery:
    """Pin the withheld quantities in published order, logging every rejection as it happens."""

    def __init__(self, inputs, register, landing):
        self.inputs = inputs
        self.register = register
        self.landing = landing
        self.values = {}
        self.quantities = []
        self.fitted = None

    def save(self, table):
        write_json(self.landing / RECORD_NAME, {
            "quantities": self.quantities,
            "settling_passes": self.register.settling_passes(),
            "calibration_table": table})

    def figure(self, name, values):
        ring = self.inputs["captures"]
        if name in RUNG_OF:
            return ladder_figure(ring, values, RUNG_OF[name])
        if self.fitted is None:
            self.fitted = settle(decode_all(ring, values)[0], self.register,
                                 self.inputs["schedule"])
        if name == CADENCE_QUANTITY:
            return cadence_figure(self.fitted, values[name])
        if name == UPKEEP_QUANTITY:
            return upkeep_figure(self.fitted, values[name])
        raise ValueError("the calibration slice names an unknown quantity %s" % name)

    def run(self):
        figures = self.inputs["slice"]["figures"]
        for name, candidates, control in self.inputs["slice"]["quantities"]:
            row = {"name": name, "value": None, "control": control, "rejected": []}
            self.quantities.append(row)
            for candidate in candidates:
                trial = dict(self.values, **{name: candidate})
                if self.figure(name, trial) == figures[control]:
                    if row["value"] is None:
                        row["value"] = candidate
                    continue
                row["rejected"].append({"candidate": candidate, "falsifier": control})
                self.save([])
            if row["value"] is None:
                raise ValueError("no candidate of %s reproduces %s" % (name, control))
            self.values[name] = row["value"]
        table = []
        for name, _, control in self.inputs["slice"]["quantities"]:
            table.append({"control": control, "published": figures[control],
                          "produced": self.figure(name, self.values)})
        return table


# ---------------------------------------------------------------- reports

def build_reports(fitted, values, bench, capture_count):
    modulus = values[CADENCE_QUANTITY]
    ordered = [fitted["units"][word] for word in sorted(fitted["units"])]
    for seat in ordered:
        seat["cadence"] = cadence_of(seat["tick_total"], modulus)
    reports = {"scenario_visible.json": {
        "capture_count": capture_count,
        "entry_total": fitted["entry_total"],
        "settled_total": fitted["settled_total"],
        "units": [{"unit": seat["unit"], "charter": seat["charter"],
                   "tick_total": seat["tick_total"],
                   "amount_total": rational(seat["amount_total"]),
                   "cadence": seat["cadence"],
                   "kind_totals": [rational(part) for part in seat["kind_totals"]]}
                  for seat in ordered]}}
    for name in CADENCE_CLASSES:
        members = [seat for seat in ordered if seat["cadence"] == name]
        reports["scenario_%s.json" % name] = {
            "cadence": name,
            "unit_count": len(members),
            "amount_total": rational(sum((seat["amount_total"] for seat in members), Fraction(0))),
            "units": [{"unit": seat["unit"], "charter": seat["charter"],
                       "tick_total": seat["tick_total"],
                       "amount_total": rational(seat["amount_total"])} for seat in members]}
    reports["perf_report.json"] = {
        "charter_stocks": [{"charter": name, "stock": rational(fitted["stocks"][name])}
                           for name in fitted["charters"]],
        "settled_total": rational(fitted["settled"]),
        "decoded_total": rational(fitted["decoded"]),
        "reversal_count": fitted["reversal_count"],
        "promoted_reversal_count": fitted["promoted"]}
    target = values[UPKEEP_QUANTITY] * fitted["total_base"]
    chosen = exact_bench(bench, target)
    carried = sum(row["upkeep"] for row in bench if row["word"] in chosen)
    reports["recommendations.json"] = {
        "target": rational(target),
        "bench": chosen,
        "bench_upkeep": rational(carried),
        "residual_after_bench": rational(target - carried)}
    reports["data_quality.json"] = {
        "dropped_retired": fitted["dropped_retired"],
        "dropped_offwindow": fitted["dropped_offwindow"],
        "dropped_amount_total": rational(fitted["dropped"]),
        "decoded_amount_total": rational(fitted["decoded"]),
        "settled_amount_total": rational(fitted["settled"]),
        "conservation_residual": rational(fitted["decoded"] - fitted["settled"] - fitted["dropped"])}
    return reports


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py CAPTURE_DIR REPORT_DIR\n")
        return 2
    landing = Path(argv[2])
    landing.mkdir(parents=True, exist_ok=True)
    inputs = read_inputs(argv[1])
    register = Register(inputs["roster"])
    recovery = Recovery(inputs, register, landing)
    table = recovery.run()
    values = recovery.values
    decoded, echoes = decode_all(inputs["captures"], values)
    fitted = settle(decoded, register, inputs["schedule"])
    reports = build_reports(fitted, values, inputs["bench"], len(inputs["captures"]))
    for name, report in reports.items():
        write_json(landing / name, report)
    recovery.save(table)

    depths = {row["word"]: register.depth(row["word"]) for row in inputs["roster"]}
    deepest = min(depths, key=lambda word: (-depths[word], word))
    divergence_word = (fitted["divergence"], fitted["divergence_tick"])
    sys.stderr.write("settling passes %d, first divergence %d at tick %d, deepest identity %s "
                     "at depth %d, last promotion %d, echo census %d\n"
                     % (register.settling_passes(), divergence_word[0], divergence_word[1],
                        deepest, depths[deepest], fitted["last_promotion"], echoes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
