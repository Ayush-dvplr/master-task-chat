"""Deterministic checks for modulus-sieve-replay.

The verifier holds no copy of the agent's input directory. Every pass the
delivered program is driven over is generated here from a seed, and the
expected reports come from the reference mill below, derived before the
program is launched.
"""

import ast
import csv
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from rewardkit import criteria, criterion


def _read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_corpus(data_dir):
    moduli = {}
    for row in _read_csv(os.path.join(data_dir, "moduli.csv")):
        moduli[row["modulus"]] = {
            "family": row["family"],
            "base": int(row["base"]),
            "offset": int(row["offset"]),
        }
    forms = {}
    for row in _read_csv(os.path.join(data_dir, "forms.csv")):
        forms[row["form"]] = {
            "kind": row["kind"],
            "parent": row["parent"],
        }
    analysts = {}
    for row in _read_csv(os.path.join(data_dir, "analysts.csv")):
        analysts[row["analyst"]] = {"grade": row["grade"]}
    lanes = {}
    for row in _read_csv(os.path.join(data_dir, "lanes.csv")):
        lanes[row["lane"]] = {
            "modulus": row["modulus"],
            "form": row["form"],
            "sector": row["sector"],
            "depth": int(row["depth"]),
        }
    samples = []
    for row in _read_jsonl(os.path.join(data_dir, "samples.jsonl")):
        samples.append({
            "seq": int(row["seq"]),
            "lane": row["lane"],
            "tag": row["tag"],
            "analyst": row["analyst"],
            "action": row["action"],
            "window": row["window"],
            "value": int(row["value"]),
            "span": int(row["span"]),
            "blocks": int(row["blocks"]),
            "terms": int(row["terms"]),
        })
    return {
        "moduli": moduli,
        "forms": forms,
        "analysts": analysts,
        "lanes": lanes,
        "samples": samples,
    }


def charged_kind(forms, form):
    entry = forms[form]
    parent = entry["parent"]
    if parent:
        return forms[parent]["kind"]
    return entry["kind"]


def sample_count(sample):
    if sample["blocks"] > 0:
        base = sample["blocks"] * 4
    else:
        base = sample["span"]
    return base * (sample["terms"] + 1)


def _least_residue(figure, modulus):
    residue = figure % modulus
    if residue * 2 > modulus:
        residue = residue - modulus
    return residue


def _adjust_sector(figure, sector):
    if sector == "upper":
        return figure - 9
    if sector == "lower":
        return figure * 3 // 5
    if sector == "split":
        return figure + 14
    if sector == "folded":
        return figure - (figure % 11)
    if sector == "shifted":
        return figure * 7 // 4
    if sector == "wrapped":
        return figure // 3
    return figure


def _adjust_kind(figure, kind):
    if kind == "quadratic":
        return figure * 9 // 7
    if kind == "cubic":
        return figure + 21
    if kind == "linear":
        return figure * 4 // 3
    return figure


def _adjust_window(figure, window):
    if window == "dusk":
        return figure * 5 // 8
    if window == "night":
        return figure + 13
    return figure


def _adjust_family(figure, family):
    if family == "prime":
        return figure * 8 // 5
    if family == "power":
        return figure - 17
    return figure


def _band(weight):
    if weight >= 400:
        return "peak"
    if weight >= 180:
        return "high"
    if weight >= 60:
        return "base"
    return "idle"


def _grade_limit(grade):
    if grade == "principal":
        return 58
    if grade == "senior":
        return 37
    if grade == "junior":
        return 19
    return 0


def _status(action, band, drift_before, grade):
    if action == "seed" or action == "close":
        return "setup"
    if action == "void":
        return "voided"
    if band == "idle":
        return "refused"
    if drift_before > _grade_limit(grade):
        return "flagged"
    return "kept"


def _divisor_count(figure):
    if figure <= 0:
        return 0
    total = 0
    root = math.isqrt(figure)
    step = 1
    while step <= root:
        if figure % step == 0:
            total = total + 2
            if step * step == figure:
                total = total - 1
        step = step + 1
    return total


def _drift_step(count, modulus, depth, run):
    step = _divisor_count(count)
    if depth == 3:
        step = step * 2
    elif depth == 2:
        step = step + 7
    step = step + math.gcd(count, modulus) % 11
    if run >= 1:
        step = step + 5
    return step


def _release(credit):
    if credit <= 0:
        return 0
    return 16 if credit > 16 else credit


def resolve(corpus):
    moduli = corpus["moduli"]
    forms = corpus["forms"]
    analysts = corpus["analysts"]
    lanes = corpus["lanes"]

    state = {}
    for lane_id, lane in lanes.items():
        state[lane_id] = {
            "floor": moduli[lane["modulus"]]["base"],
            "drift": 0,
            "credit": 0,
            "faults": 0,
            "run": 0,
            "seen": 0,
            "waiver": 0,
            "count": 0,
            "recent": [],
        }

    residues = []
    for sample in sorted(corpus["samples"], key=lambda row: row["seq"]):
        lane = lanes[sample["lane"]]
        cell = state[sample["lane"]]
        entry = moduli[lane["modulus"]]
        family = entry["family"]
        if cell["faults"] >= 3:
            family = "prime"
        modulus = entry["offset"] + 1
        kind = charged_kind(forms, lane["form"])
        grade = analysts[sample["analyst"]]["grade"]

        count = sample_count(sample)
        if count <= 0:
            count = cell["count"]
        if count <= 0:
            count = 1
        cell["count"] = count

        figure = sample["value"] - cell["floor"]
        if figure < 0:
            figure = 0
        product = figure * 900
        figure = product // count
        residue = product - figure * count
        figure = _least_residue(figure, modulus)
        if figure < 0:
            figure = -figure
        figure = _adjust_sector(figure, lane["sector"])
        if figure < 0:
            figure = 0
        figure = _adjust_kind(figure, kind)
        if figure < 0:
            figure = 0
        if cell["seen"]:
            figure = _adjust_window(figure, sample["window"])
        if figure < 0:
            figure = 0
        figure = _adjust_family(figure, family)
        if figure < 0:
            figure = 0
        released = _release(cell["credit"])
        figure = figure + released
        drift_before = cell["drift"]
        relief = drift_before
        if cell["waiver"]:
            relief = drift_before * 2
            cell["waiver"] = 0
        weight = figure - relief
        if weight < 0:
            weight = 0
        position = len(cell["recent"]) - 1
        while position >= 0:
            if cell["recent"][position][0] == sample["tag"]:
                weight = cell["recent"][position][1]
                break
            position = position - 1
        band = _band(weight)
        status = _status(sample["action"], band, drift_before, grade)

        residues.append({
            "action": sample["action"],
            "analyst": sample["analyst"],
            "band": band,
            "drift_before": drift_before,
            "form": lane["form"],
            "lane": sample["lane"],
            "seq": sample["seq"],
            "status": status,
            "tag": sample["tag"],
            "weight": weight,
        })

        if status == "refused":
            cell["faults"] = cell["faults"] + 1
        cell["credit"] = cell["credit"] - released
        if sample["action"] == "seed":
            cell["floor"] = sample["value"]
            cell["run"] = 0
        elif sample["action"] == "close":
            banked = cell["credit"] + cell["drift"]
            cell["credit"] = 80 if banked > 80 else banked
            cell["drift"] = 0
            cell["run"] = 0
        elif sample["action"] == "void":
            cell["waiver"] = 1
            cell["run"] = 0
        elif sample["action"] == "sieve":
            drift = cell["drift"] + _drift_step(count, modulus, lane["depth"], cell["run"])
            drift = drift + residue % 10
            if drift > 130:
                drift = 130
            cell["drift"] = drift
            cell["run"] = cell["run"] + 1
        else:
            cell["run"] = 0
        cell["recent"].append((sample["tag"], weight))
        if len(cell["recent"]) > 4:
            del cell["recent"][0]
        cell["seen"] = 1

    lane_rows = []
    for lane_id in sorted(lanes):
        rows = [row for row in residues if row["lane"] == lane_id]
        counted = [row for row in rows if row["status"] == "kept" or row["status"] == "flagged"]
        weight_total = 0
        peak_weight = 0
        best = None
        for row in counted:
            weight_total = weight_total + row["weight"]
            if row["weight"] > peak_weight:
                peak_weight = row["weight"]
            if best is None:
                best = row
            elif row["weight"] > best["weight"]:
                best = row
            elif row["weight"] == best["weight"] and row["seq"] < best["seq"]:
                best = row
        faults = state[lane_id]["faults"]
        drift_end = state[lane_id]["drift"]
        if faults >= 3:
            verdict = "sealed"
        elif drift_end > 51:
            verdict = "held"
        else:
            verdict = "cleared"
        bands = {"base": 0, "high": 0, "idle": 0, "peak": 0}
        for row in rows:
            bands[row["band"]] = bands[row["band"]] + 1
        lane_rows.append({
            "bands": bands,
            "credit_end": state[lane_id]["credit"],
            "drift_end": drift_end,
            "faults": faults,
            "flagged": sum(1 for row in rows if row["status"] == "flagged"),
            "floor_end": state[lane_id]["floor"],
            "lane": lane_id,
            "peak_weight": peak_weight,
            "samples": len(rows),
            "sieved": sum(1 for row in rows if row["action"] == "sieve"),
            "top_tag": best["tag"] if best is not None else None,
            "verdict": verdict,
            "weight_total": weight_total,
        })

    form_table = {}
    for row in residues:
        entry = form_table.setdefault(row["form"], {"form": row["form"], "lanes": set(),
                                                    "samples": 0, "weight_total": 0,
                                                    "flagged": 0})
        entry["lanes"].add(row["lane"])
        entry["samples"] = entry["samples"] + 1
        if row["status"] == "kept" or row["status"] == "flagged":
            entry["weight_total"] = entry["weight_total"] + row["weight"]
        if row["status"] == "flagged":
            entry["flagged"] = entry["flagged"] + 1
    form_rows = []
    for form_id in sorted(form_table,
                          key=lambda name: (-form_table[name]["weight_total"], name)):
        entry = form_table[form_id]
        form_rows.append({
            "form": form_id,
            "lanes": len(entry["lanes"]),
            "samples": entry["samples"],
            "weight_total": entry["weight_total"],
            "flagged": entry["flagged"],
        })

    by_band = {"base": 0, "high": 0, "idle": 0, "peak": 0}
    by_status = {"flagged": 0, "kept": 0, "refused": 0, "setup": 0, "voided": 0}
    for row in residues:
        by_band[row["band"]] = by_band[row["band"]] + 1
        by_status[row["status"]] = by_status[row["status"]] + 1

    top_lane = None
    top_total = None
    for row in lane_rows:
        if top_total is None or row["weight_total"] > top_total:
            top_lane = row["lane"]
            top_total = row["weight_total"]
        elif row["weight_total"] == top_total and row["lane"] < top_lane:
            top_lane = row["lane"]

    sieve = {
        "by_band": by_band,
        "by_status": by_status,
        "forms": len(form_rows),
        "lanes": len(lane_rows),
        "samples": len(residues),
        "sealed": sorted(row["lane"] for row in lane_rows if row["verdict"] == "sealed"),
        "top_lane": top_lane,
        "weight_total": sum(row["weight_total"] for row in lane_rows),
    }
    return residues, lane_rows, form_rows, sieve


def derive(data_dir):
    return resolve(load_corpus(data_dir))


def render_residues(residues):
    parts = []
    for row in residues:
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    return "".join(parts)


def render_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def render_forms(form_rows):
    parts = ["form,lanes,samples,weight_total,flagged"]
    for row in form_rows:
        parts.append("%s,%d,%d,%d,%d" % (row["form"], row["lanes"], row["samples"],
                                         row["weight_total"], row["flagged"]))
    return "\n".join(parts) + "\n"


def write_reports(out_dir, residues, lane_rows, form_rows, sieve):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "residues.jsonl"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_residues(residues))
    with open(os.path.join(out_dir, "lanes.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document({"lanes": lane_rows}))
    with open(os.path.join(out_dir, "forms.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_forms(form_rows))
    with open(os.path.join(out_dir, "sieve.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document(sieve))


_SECTORS = ["plain", "upper", "lower", "split", "folded", "shifted", "wrapped"]
_KINDS = ["mixed", "quadratic", "cubic", "linear"]
_WINDOWS = ["dawn", "dusk", "night"]
_FAMILIES = ["composite", "prime", "power"]
_GRADES = ["principal", "senior", "junior", "visiting"]
_AIMABLE = ("plain", "cubic", "power")
class _Rng:
    def __init__(self, seed):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def draw(self):
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self.state >> 33) & 0x7FFFFFFF

    def below(self, limit):
        return self.draw() % limit

    def between(self, low, high):
        return low + self.below(high - low + 1)

    def pick(self, items):
        return items[self.below(len(items))]


def mixed_triples():
    out = []
    for index in range(28):
        sector = _SECTORS[index % 7]
        wrap = index // 7
        if sector == "plain":
            kind = _KINDS[1 + (index + wrap) % 3]
            family = _FAMILIES[1 + (index + wrap) % 2]
        else:
            kind = _KINDS[(index * 3 + wrap) % 4]
            family = _FAMILIES[(index * 2 + wrap) % 3]
            if kind == "mixed" and family == "composite":
                family = _FAMILIES[1 + (index + wrap) % 2]
        triple = (sector, kind, family)
        if triple not in out:
            out.append(triple)
    return out


class _Case:
    def __init__(self):
        self.moduli = []
        self.forms = []
        self.analysts = []
        self.lanes = []
        self.samples = []
        self.seq = 0
        self.tag_no = 0
        self.state = {}
        self.lane_map = {}
        self.aimed = []

    def modulus(self, name, family, base, offset):
        self.moduli.append((name, family, base, offset))
        return name

    def form(self, name, kind, parent):
        self.forms.append((name, kind, parent))
        return name

    def analyst(self, name, grade):
        self.analysts.append((name, grade))
        return name

    def _row(self, table, name, index):
        for row in table:
            if row[0] == name:
                return row[index]
        raise KeyError(name)

    def _charged_kind(self, form):
        parent = self._row(self.forms, form, 2)
        if parent:
            return self._row(self.forms, parent, 1)
        return self._row(self.forms, form, 1)

    def lane(self, lane_id, modulus, form, sector, depth):
        self.lanes.append((lane_id, modulus, form, sector, depth))
        self.state[lane_id] = {
            "floor": self._row(self.moduli, modulus, 2),
            "modulus": self._row(self.moduli, modulus, 3) + 1,
            "family": self._row(self.moduli, modulus, 1),
            "kind": self._charged_kind(form),
            "sector": sector,
            "depth": depth,
            "drift": 0,
            "credit": 0,
            "faults": 0,
            "run": 0,
            "seen": 0,
            "waiver": 0,
            "count": 0,
            "recent": [],
        }
        self.lane_map[lane_id] = (modulus, form, sector, depth)
        return lane_id

    def _tag(self, lane_id):
        self.tag_no += 1
        return "T%04d" % self.tag_no

    def _figure(self, cell, window, value, count):
        figure = value - cell["floor"]
        if figure < 0:
            figure = 0
        product = figure * 900
        figure = product // count
        residue = product - figure * count
        modulus = cell["modulus"]
        reduced = figure % modulus
        if reduced * 2 > modulus:
            reduced = reduced - modulus
        figure = reduced
        if figure < 0:
            figure = -figure
        sector = cell["sector"]
        if sector == "upper":
            figure = figure - 9
        elif sector == "lower":
            figure = figure * 3 // 5
        elif sector == "split":
            figure = figure + 14
        elif sector == "folded":
            figure = figure - (figure % 11)
        elif sector == "shifted":
            figure = figure * 7 // 4
        elif sector == "wrapped":
            figure = figure // 3
        if figure < 0:
            figure = 0
        kind = cell["kind"]
        if kind == "quadratic":
            figure = figure * 9 // 7
        elif kind == "cubic":
            figure = figure + 21
        elif kind == "linear":
            figure = figure * 4 // 3
        if figure < 0:
            figure = 0
        if cell["seen"]:
            if window == "dusk":
                figure = figure * 5 // 8
            elif window == "night":
                figure = figure + 13
        if figure < 0:
            figure = 0
        family = cell["family"]
        if cell["faults"] >= 3:
            family = "prime"
        if family == "prime":
            figure = figure * 8 // 5
        elif family == "power":
            figure = figure - 17
        if figure < 0:
            figure = 0
        return figure, residue

    def sample(self, lane_name, analyst, action, window, value, span, blocks=0, terms=1,
               tag=None):
        cell = self.state[lane_name]
        self.seq += 1
        if tag is None:
            tag = self._tag(lane_name)
        self.samples.append({
            "seq": self.seq,
            "lane": lane_name,
            "tag": tag,
            "analyst": analyst,
            "action": action,
            "window": window,
            "value": value,
            "span": span,
            "blocks": blocks,
            "terms": terms,
        })
        count = (blocks * 4 if blocks > 0 else span) * (terms + 1)
        if count <= 0:
            count = cell["count"]
        if count <= 0:
            count = 1
        cell["count"] = count
        figure, residue = self._figure(cell, window, value, count)
        released = 0
        if cell["credit"] > 0:
            released = 16 if cell["credit"] > 16 else cell["credit"]
        figure = figure + released
        drift_before = cell["drift"]
        relief = drift_before
        if cell["waiver"]:
            relief = drift_before * 2
            cell["waiver"] = 0
        weight = figure - relief
        if weight < 0:
            weight = 0
        position = len(cell["recent"]) - 1
        while position >= 0:
            if cell["recent"][position][0] == tag:
                weight = cell["recent"][position][1]
                break
            position = position - 1
        if weight >= 400:
            band = "peak"
        elif weight >= 180:
            band = "high"
        elif weight >= 60:
            band = "base"
        else:
            band = "idle"
        limit = {"principal": 58, "senior": 37, "junior": 19}.get(
            self._row(self.analysts, analyst, 1), 0)
        if action == "seed" or action == "close":
            status = "setup"
        elif action == "void":
            status = "voided"
        elif band == "idle":
            status = "refused"
        elif drift_before > limit:
            status = "flagged"
        else:
            status = "kept"
        if status == "refused":
            cell["faults"] = cell["faults"] + 1
        cell["credit"] = cell["credit"] - released
        if action == "seed":
            cell["floor"] = value
            cell["run"] = 0
        elif action == "close":
            banked = cell["credit"] + cell["drift"]
            cell["credit"] = 80 if banked > 80 else banked
            cell["drift"] = 0
            cell["run"] = 0
        elif action == "void":
            cell["waiver"] = 1
            cell["run"] = 0
        elif action == "sieve":
            step = _divisor_count(count)
            if cell["depth"] == 3:
                step = step * 2
            elif cell["depth"] == 2:
                step = step + 7
            step = step + math.gcd(count, cell["modulus"]) % 11
            if cell["run"] >= 1:
                step = step + 5
            drift = cell["drift"] + step + residue % 10
            if drift > 130:
                drift = 130
            cell["drift"] = drift
            cell["run"] = cell["run"] + 1
        else:
            cell["run"] = 0
        cell["recent"].append((tag, weight))
        if len(cell["recent"]) > 4:
            del cell["recent"][0]
        cell["seen"] = 1
        return self.seq, weight

    def target(self, lane_name, analyst, action, weight, span, blocks=0, terms=1, tag=None,
               window="dawn"):
        cell = self.state[lane_name]
        floor = cell["floor"]
        count = (blocks * 4 if blocks > 0 else span) * (terms + 1)
        for step in range(0, 400001):
            got, _r = self._figure(cell, window, floor + step, count)
            relief = cell["drift"] * 2 if cell["waiver"] else cell["drift"]
            released = 0
            if cell["credit"] > 0:
                released = 16 if cell["credit"] > 16 else cell["credit"]
            settled = got + released - relief
            if settled < 0:
                settled = 0
            if settled == weight:
                seq, real = self.sample(lane_name, analyst, action, window, floor + step,
                                        span, blocks, terms, tag)
                self.aimed.append((seq, weight, real))
                return seq
        raise ValueError("no value on %s yields weight %d over span %d"
                         % (lane_name, weight, span))

    def strong(self, lane_name, analyst, action, span, want=200, blocks=0, terms=1, tag=None,
               window="dawn"):
        cell = self.state[lane_name]
        floor = cell["floor"]
        count = (blocks * 4 if blocks > 0 else span) * (terms + 1)
        for step in range(0, 400001):
            got, _r = self._figure(cell, window, floor + step, count)
            relief = cell["drift"] * 2 if cell["waiver"] else cell["drift"]
            released = 0
            if cell["credit"] > 0:
                released = 16 if cell["credit"] > 16 else cell["credit"]
            settled = got + released - relief
            if settled >= want:
                return self.sample(lane_name, analyst, action, window, floor + step,
                                   span, blocks, terms, tag)[0]
        raise ValueError("no value on %s reaches weight %d over span %d"
                         % (lane_name, want, span))

    def flat(self, lane_name, analyst, action, span=900, window="dawn", tag=None):
        return self.sample(lane_name, analyst, action, window,
                           self.state[lane_name]["floor"], span, 0, 1, tag)[0]


_S_MODULUS = {"composite": "SMD-1", "prime": "SMD-2", "power": "SMD-3"}
_S_FORM = {"mixed": "SFR-1", "quadratic": "SFR-2", "cubic": "SFR-3", "linear": "SFR-4"}
_S_ALIAS = {"mixed": "SFR-5", "quadratic": "SFR-6", "cubic": "SFR-7", "linear": "SFR-8"}


class _Layout:
    def __init__(self, case, seed, mod_of, form_of, alias_of, prefix):
        self.case = case
        self.rng = _Rng(seed)
        self.triples = mixed_triples()
        self.index = 0
        self.count = 0
        self.mod_of = mod_of
        self.form_of = form_of
        self.alias_of = alias_of
        self.prefix = prefix

    def next_lane(self, depth=None, triple=None, alias=False, name=None):
        if triple is None:
            triple = self.triples[self.index % len(self.triples)]
            self.index += 1
        sector, kind, family = triple
        self.count += 1
        lane_id = name if name is not None else "%s%02d" % (self.prefix, self.count)
        if depth is None:
            depth = (self.count % 3) + 1
        table = self.alias_of if alias else self.form_of
        self.case.lane(lane_id, self.mod_of[family], table[kind], sector, depth)
        return lane_id


def _band_block(case, lane, analyst):
    for weight in (400, 399, 180, 179, 60, 59):
        case.target(lane, analyst, "probe", weight, 900)


def _count_block(case, lane, analyst):
    for span, blocks, terms in ((900, 0, 1), (900, 0, 3), (0, 225, 1), (0, 225, 3), (0, 600, 2)):
        case.sample(lane, analyst, "probe", "dawn",
                    case.state[lane]["floor"] + 1300, span, blocks, terms)


_FINE_SPANS = [1, 2, 3, 5, 7, 1013, 1019, 1021, 1031, 1033, 1039, 1049, 1051, 1061, 1063]


def _tolerance_lanes(case, lay, analyst, limit):
    """One lane per drift figure around a grade tolerance, so the exact figure is pinned."""
    for wanted in (max(limit - 1, 0), limit, limit + 1, limit + 2, limit + 3):
        lane = lay.next_lane(1, _AIMABLE)
        if _threshold_lane(case, lane, analyst, wanted):
            case.strong(lane, analyst, "probe", 900, 60)


def _verdict_lanes(case, lay, analyst, limit):
    """One lane per drift figure around the holding threshold, so the exact figure is pinned.

    Without a lane resting on the figure itself the rollups cannot separate the
    threshold from the next figure up, and both readings reproduce every shipped
    row while disagreeing on lanes nobody has seen yet.
    """
    for wanted in (limit - 1, limit, limit + 1, limit + 2):
        lane = lay.next_lane(1, _AIMABLE)
        if _threshold_lane(case, lane, analyst, wanted):
            case.strong(lane, analyst, "probe", 900, 60)


def _threshold_lane(case, lane, analyst, wanted):
    """Drive the lane's drift to land exactly on a chosen figure.

    A sieve that directly follows another sieve carries the back to back extra,
    so the reachable steps differ between the first and the second, and a plain
    greedy climb can step straight over the figure it is aiming for. The search
    below tries one step, then every pair of steps, before falling back.
    """
    base = case.state[lane]["floor"]
    cell = case.state[lane]

    def snapshot():
        keep = dict(cell)
        keep["recent"] = list(cell["recent"])
        return keep, len(case.samples), case.seq

    def restore(mark):
        keep, length, seq = mark
        cell.clear()
        cell.update(keep)
        del case.samples[length:]
        case.seq = seq

    def step(span, extra):
        case.sample(lane, analyst, "sieve", "dawn", base + 1500 + extra, span, 0, 0)
        return cell["drift"]

    if cell["drift"] > wanted:
        case.flat(lane, analyst, "close")
    if cell["drift"] == wanted:
        return True

    plan = [(span, extra) for span in _FINE_SPANS for extra in range(0, 60)]

    guard = 0
    while wanted - cell["drift"] > 30 and guard < 60:
        best = None
        mark = snapshot()
        for move in plan:
            after = step(*move)
            restore(mark)
            if after <= wanted and (best is None or after > best[1]):
                best = (move, after)
        if best is None:
            break
        step(*best[0])
        guard = guard + 1
        if cell["drift"] == wanted:
            return True

    mark = snapshot()
    for first in plan:
        after = step(*first)
        if after == wanted:
            return True
        if after < wanted:
            inner = snapshot()
            for second in plan:
                if step(*second) == wanted:
                    return True
                restore(inner)
        restore(mark)
    return False


def _repeat_block(case, lane, analyst):
    case.strong(lane, analyst, "probe", 900, 300, tag="RPT-A")
    for _step in range(3):
        case.strong(lane, analyst, "probe", 900, 100)
    case.strong(lane, analyst, "probe", 900, 100, tag="RPT-A")
    case.strong(lane, analyst, "probe", 900, 120, tag="RPT-B")
    for _step in range(4):
        case.strong(lane, analyst, "probe", 900, 100)
    case.strong(lane, analyst, "probe", 900, 100, tag="RPT-B")


def _waiver_block(case, lane, analyst):
    base = case.state[lane]["floor"]
    for _step in range(3):
        case.sample(lane, analyst, "sieve", "dawn", base + 1500, 900, 0, 1)
    case.strong(lane, analyst, "probe", 900, 60)
    case.flat(lane, analyst, "void")
    case.strong(lane, analyst, "probe", 900, 60)
    case.strong(lane, analyst, "probe", 900, 60)
    case.flat(lane, analyst, "close")
    case.strong(lane, analyst, "probe", 900, 60)


def _fault_block(case, lane, analyst, faults=3):
    for _step in range(faults):
        case.flat(lane, analyst, "probe")
    for value in (1700, 2100, 2500):
        case.sample(lane, analyst, "probe", "dawn", case.state[lane]["floor"] + value, 900)


def _inherit_block(case, lane, analyst):
    base = case.state[lane]["floor"]
    case.sample(lane, analyst, "probe", "dawn", base + 1500, 900, 0, 1)
    case.sample(lane, analyst, "probe", "dawn", base + 1500, 0, 0, 1)
    case.sample(lane, analyst, "probe", "dawn", base + 1500, 500, 0, 2)
    case.sample(lane, analyst, "probe", "dawn", base + 1500, 0, 0, 3)


def _opening_block(case, lane, analyst):
    """A lane whose very first sample carries no count of its own.

    There is no previous sample to inherit from, so the fallback figure is the
    only thing the chain can divide by and the rollup row moves with it.
    """
    base = case.state[lane]["floor"]
    case.sample(lane, analyst, "probe", "dawn", base + 1500, 0, 0, 1)
    case.sample(lane, analyst, "probe", "dawn", base + 1900, 900, 0, 1)
    case.sample(lane, analyst, "probe", "dawn", base + 1500, 0, 0, 2)


def _gcd_block(case, lane, analyst):
    base = case.state[lane]["floor"]
    for span in (960, 840, 726, 605):
        case.sample(lane, analyst, "sieve", "dawn", base + 1403, span, 0, 1)
        case.strong(lane, analyst, "probe", 900, 60)


def _plain_lane(case, depth=1, family="composite", kind="mixed", sector="plain"):
    case.modulus("PMD-1", family, 240, 1199)
    case.form("PFR-0", "cubic", "")
    case.form("PFR-1", kind, "")
    case.form("PFR-2", "mixed", "PFR-0")
    case.analyst("PAN-1", "principal")
    case.lane("PLN-1", "PMD-1", "PFR-1", sector, depth)
    return "PLN-1"


def _probe_layout(case):
    case.modulus("PMD-3", "power", 300, 1439)
    case.form("PFR-3", "cubic", "")
    for index, grade in enumerate(_GRADES):
        case.analyst("PAN-%d" % (index + 1), grade)
    return _Layout(case, 0x7A11, {"power": "PMD-3"}, {"cubic": "PFR-3"}, {"cubic": "PFR-3"}, "PLN-")


def build_probe(name):
    case = _Case()
    if name == "gain":
        lane = _plain_lane(case)
        for value in (1120, 1560, 2000, 2440, 2880):
            case.sample(lane, "PAN-1", "probe", "dawn", value, 900)
        return case
    if name == "count_columns":
        lane = _plain_lane(case)
        _count_block(case, lane, "PAN-1")
        case.sample(lane, "PAN-1", "probe", "dawn", case.state[lane]["floor"] + 1300, 900, 150, 1)
        return case
    if name.startswith("sector_"):
        lane = _plain_lane(case, sector=name[7:])
        for value in (1310, 1750, 2190, 2630):
            case.sample(lane, "PAN-1", "probe", "dawn", value, 900)
        return case
    if name.startswith("kind_"):
        lane = _plain_lane(case, kind=name[5:])
        for value in (1310, 1750, 2190, 2630):
            case.sample(lane, "PAN-1", "probe", "dawn", value, 900)
        return case
    if name.startswith("family_"):
        lane = _plain_lane(case, family=name[7:])
        for value in (1310, 1750, 2190, 2630):
            case.sample(lane, "PAN-1", "probe", "dawn", value, 900)
        return case
    if name.startswith("window_"):
        lane = _plain_lane(case)
        for value in (1310, 1750, 2190, 2630):
            case.sample(lane, "PAN-1", "probe", name[7:], value, 900)
        return case
    if name == "least_residue":
        lane = _plain_lane(case)
        for value in (1000, 1150, 1300, 1450, 1600, 1750, 1900):
            case.sample(lane, "PAN-1", "probe", "dawn", value, 900)
        return case
    if name == "parent_kind":
        case.modulus("PMD-1", "composite", 240, 1199)
        case.form("PFR-0", "cubic", "")
        case.form("PFR-2", "mixed", "PFR-0")
        case.analyst("PAN-1", "principal")
        case.lane("PLN-1", "PMD-1", "PFR-2", "plain", 1)
        for value in (1310, 1750, 2190, 2630):
            case.sample("PLN-1", "PAN-1", "probe", "dawn", value, 900)
        return case
    if name == "repeat_tag":
        lane = _plain_lane(case)
        _repeat_block(case, lane, "PAN-1")
        return case
    if name == "waiver":
        lane = _plain_lane(case)
        _waiver_block(case, lane, "PAN-1")
        return case
    if name == "fault_family":
        lane = _plain_lane(case)
        _fault_block(case, lane, "PAN-1", 3)
        return case
    if name == "count_inherit":
        lane = _plain_lane(case)
        _opening_block(case, lane, "PAN-1")
        _inherit_block(case, lane, "PAN-1")
        return case
    if name.startswith("drift_depth_"):
        lane = _plain_lane(case, depth=int(name[12:]))
        base = case.state[lane]["floor"]
        for _step in range(3):
            case.sample(lane, "PAN-1", "sieve", "dawn", base + 1500, 900, 0, 1)
        case.strong(lane, "PAN-1", "probe", 900, 60)
        return case
    if name == "drift_gcd":
        lane = _plain_lane(case)
        _gcd_block(case, lane, "PAN-1")
        return case
    if name == "credit_release":
        lane = _plain_lane(case)
        case.strong(lane, "PAN-1", "sieve", 900, 60)
        case.strong(lane, "PAN-1", "sieve", 900, 60)
        case.flat(lane, "PAN-1", "close")
        for _step in range(4):
            case.strong(lane, "PAN-1", "probe", 900, 100)
        return case
    if name == "form_order":
        case.modulus("PMD-1", "composite", 240, 1199)
        case.form("PFR-1", "mixed", "")
        case.form("PFR-3", "cubic", "")
        case.analyst("PAN-1", "principal")
        case.lane("PLN-1", "PMD-1", "PFR-1", "plain", 1)
        case.lane("PLN-2", "PMD-1", "PFR-3", "plain", 1)
        for value in (1310, 1750):
            case.sample("PLN-1", "PAN-1", "probe", "dawn", value, 900)
        for value in (2400, 2800, 3200):
            case.sample("PLN-2", "PAN-1", "probe", "dawn", value, 900)
        return case
    if name == "band_edges":
        lane = _plain_lane(case)
        _band_block(case, lane, "PAN-1")
        return case
    if name == "tolerance":
        lay = _probe_layout(case)
        for analyst, limit in (("PAN-1", 58), ("PAN-2", 37), ("PAN-3", 19), ("PAN-4", 0)):
            _tolerance_lanes(case, lay, analyst, limit)
        return case
    if name == "lane_rollup":
        lay = _probe_layout(case)
        _verdict_lanes(case, lay, "PAN-1", 51)
        for faults in (3, 2):
            _fault_block(case, lay.next_lane(1, _AIMABLE), "PAN-1", faults)
        lane = lay.next_lane(1, _AIMABLE)
        for weight in (250, 250, 190):
            case.target(lane, "PAN-1", "probe", weight, 900)
        lane = lay.next_lane(1, _AIMABLE)
        case.target(lane, "PAN-1", "probe", 30, 900)
        case.target(lane, "PAN-1", "probe", 200, 900)
        base = case.state[lane]["floor"]
        case.sample(lane, "PAN-1", "sieve", "dawn", base + 1500, 900, 0, 1)
        case.strong(lane, "PAN-4", "probe", 900, 150)
        return case
    raise KeyError(name)


def build_empty():
    case = _Case()
    case.modulus("ZMD-1", "composite", 100, 1199)
    case.form("ZFR-1", "mixed", "")
    case.analyst("ZAN-1", "principal")
    return case


def build_unseen(seed, size=None):
    rng = _Rng(seed ^ 0x6D2B)
    case = _Case()
    for index, family in enumerate(_FAMILIES):
        case.modulus("SMD-%d" % (index + 1), family, rng.between(140, 320),
                     rng.between(1100, 1500))
    for index, kind in enumerate(_KINDS):
        case.form("SFR-%d" % (index + 1), kind, "")
    for index, kind in enumerate(_KINDS):
        case.form("SFR-%d" % (index + 5), _KINDS[(index + 2) % 4], "SFR-%d" % (index + 1))
    for index, grade in enumerate(_GRADES):
        case.analyst("SAN-%d" % (index + 1), grade)

    lay = _Layout(case, seed ^ 0x11C7, _S_MODULUS, _S_FORM, _S_ALIAS, "SLN-")
    triples = mixed_triples()

    count = size if size is not None else 9 + rng.below(4)
    for index in range(count):
        lane = lay.next_lane(index % 3 + 1, triples[(index * 5 + 1) % len(triples)],
                             index % 4 == 3)
        for step in range(4 + rng.below(4)):
            action = rng.pick(["sieve", "sieve", "probe", "probe", "close", "seed", "void"])
            window = _WINDOWS[(index + step) % 3]
            analyst = "SAN-%d" % (rng.below(4) + 1)
            value = case.state[lane]["floor"] + 30 * rng.between(10, 90)
            span = 60 * rng.between(6, 30)
            blocks = 0 if rng.below(3) else 15 * rng.between(4, 40)
            terms = rng.between(1, 3)
            if step % 7 == 6:
                span = 0
                blocks = 0
            case.sample(lane, analyst, action, window, value, span, blocks, terms)

    lane = lay.next_lane(1, _AIMABLE)
    _band_block(case, lane, "SAN-1")
    lane = lay.next_lane(1, _AIMABLE)
    _count_block(case, lane, "SAN-1")
    lane = lay.next_lane(1, _AIMABLE)
    _repeat_block(case, lane, "SAN-1")
    lane = lay.next_lane(1, _AIMABLE)
    _waiver_block(case, lane, "SAN-1")
    lane = lay.next_lane(1, _AIMABLE)
    _fault_block(case, lane, "SAN-1", 3)
    lane = lay.next_lane(1, _AIMABLE)
    _fault_block(case, lane, "SAN-1", 2)
    lane = lay.next_lane(1, _AIMABLE)
    _inherit_block(case, lane, "SAN-1")
    lane = lay.next_lane(1, _AIMABLE)
    _opening_block(case, lane, "SAN-1")
    lane = lay.next_lane(1, _AIMABLE)
    _gcd_block(case, lane, "SAN-1")
    lane = lay.next_lane(2, _AIMABLE)
    _gcd_block(case, lane, "SAN-1")

    for sector in _SECTORS:
        lane = lay.next_lane(1, (sector, "cubic", "power"))
        for value in (1310, 1750, 2190, 2630):
            case.sample(lane, "SAN-1", "probe", "dawn", value, 900)

    for kind in _KINDS:
        lane = lay.next_lane(1, ("upper", kind, "power"))
        for value in (1310, 1750, 2190, 2630):
            case.sample(lane, "SAN-1", "probe", "dawn", value, 900)

    for analyst, limit in (("SAN-1", 58), ("SAN-2", 37), ("SAN-3", 19), ("SAN-4", 0)):
        _tolerance_lanes(case, lay, analyst, limit)

    for depth in (1, 2, 3):
        for runs in (1, 2, 3):
            lane = lay.next_lane(depth, _AIMABLE)
            base = case.state[lane]["floor"]
            for _step in range(runs):
                case.sample(lane, "SAN-1", "sieve", "dawn", base + 1500, 900, 0, 1)
            case.strong(lane, "SAN-1", "probe", 900, 60)

    lane = lay.next_lane(1, _AIMABLE)
    for weight in (250, 250, 190):
        case.target(lane, "SAN-1", "probe", weight, 900)

    lane = lay.next_lane(3, _AIMABLE)
    for _step in range(5):
        case.strong(lane, "SAN-1", "sieve", 1800, 1)
    case.strong(lane, "SAN-1", "probe", 900, 60)

    for _pair in range(2):
        lane = lay.next_lane(1, _AIMABLE)
        for _step in range(15):
            case.target(lane, "SAN-1", "probe", 400, 900)
    return case


def _shuffled(samples, seed):
    order = list(samples)
    rng = _Rng(seed ^ 0x5A3D)
    index = len(order) - 1
    while index > 0:
        swap = rng.below(index + 1)
        order[index], order[swap] = order[swap], order[index]
        index -= 1
    return order


def write_case(root, case, seed=29):
    os.makedirs(root, exist_ok=True)

    def emit(name, text):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    rows = ["modulus,family,base,offset"]
    for name, family, base, offset in case.moduli:
        rows.append("%s,%s,%d,%d" % (name, family, base, offset))
    emit("moduli.csv", "\n".join(rows) + "\n")

    rows = ["form,kind,parent"]
    for name, kind, parent in case.forms:
        rows.append("%s,%s,%s" % (name, kind, parent))
    emit("forms.csv", "\n".join(rows) + "\n")

    rows = ["analyst,grade"]
    for name, grade in case.analysts:
        rows.append("%s,%s" % (name, grade))
    emit("analysts.csv", "\n".join(rows) + "\n")

    rows = ["lane,modulus,form,sector,depth"]
    for lane_id, modulus, form, sector, depth in case.lanes:
        rows.append("%s,%s,%s,%s,%d" % (lane_id, modulus, form, sector, depth))
    emit("lanes.csv", "\n".join(rows) + "\n")

    parts = []
    for row in _shuffled(case.samples, seed):
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    emit("samples.jsonl", "".join(parts))
    return case


FORM_HEADER = "form,lanes,samples,weight_total,flagged"
RESIDUE_KEYS = ["action", "analyst", "band", "drift_before", "form", "lane", "seq",
                "status", "tag", "weight"]
LANE_KEYS = ["bands", "credit_end", "drift_end", "faults", "flagged", "floor_end",
             "lane", "peak_weight", "samples", "sieved", "top_tag", "verdict",
             "weight_total"]
SIEVE_KEYS = ["by_band", "by_status", "forms", "lanes", "samples", "sealed",
              "top_lane", "weight_total"]
REPORT_NAMES = ("residues.jsonl", "lanes.json", "forms.csv", "sieve.json")

REPEAT_SEED = 7730003
PROBE_SEED = 11
CORPUS_SEEDS = [5510011, 5510022, 5510033, 5510044, 5510055, 5510066,
                5510077, 5510088, 5510099, 5510110]
UNSEEN = tuple("c%02d" % (index + 1) for index in range(len(CORPUS_SEEDS)))
RECORDED_LANES = frozenset("LAN-%02d" % number for number in range(1, 93))

WEIGHT_FIELDS = ("seq", "weight")
DRIFT_FIELDS = ("seq", "drift_before")
BAND_FIELDS = ("seq", "band")
STATUS_FIELDS = ("seq", "status")
VERDICT_FIELDS = ("lane", "verdict", "weight_total", "peak_weight", "top_tag")

_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}
_RUN_LOCKS = {}
_GUARD = threading.Lock()


def _script(workspace):
    return os.path.join(str(workspace), "out", "sieve.py")


def _grant_read(path):
    try:
        extra = 0o055 if os.path.isdir(path) else 0o044
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | extra)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, AttributeError):
        try:
            proc.kill()
        except OSError:
            pass


def _launch(argv, scratch, budget=300):
    """Run the delivered program unprivileged; a timeout reads as a failed run."""
    stdout_path = os.path.join(scratch, "stdout.txt")
    stderr_path = os.path.join(scratch, "stderr.txt")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    with open(stdout_path, "wb") as sink, open(stderr_path, "wb") as errsink:
        proc = subprocess.Popen(
            _demoted(argv),
            stdout=sink,
            stderr=errsink,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        try:
            return proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            _terminate(proc)
            return None


def _case_for(label):
    if label.startswith("probe:"):
        return build_probe(label[6:]), PROBE_SEED
    if label == "empty":
        return build_empty(), 0
    if label == "repeat":
        return build_unseen(REPEAT_SEED, size=2), REPEAT_SEED
    seed = CORPUS_SEEDS[UNSEEN.index(label)]
    return build_unseen(seed), seed


def _reference(data_dir):
    residues, lane_rows, form_rows, sieve = derive(data_dir)
    return {
        "residues.jsonl": render_residues(residues),
        "lanes.json": render_document({"lanes": lane_rows}),
        "forms.csv": render_forms(form_rows),
        "sieve.json": render_document(sieve),
    }


def _materialise(label):
    work = tempfile.mkdtemp(prefix="msr-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    case, seed = _case_for(label)
    write_case(data, case, seed)
    os.makedirs(out)
    os.makedirs(scratch)
    expected = _reference(data)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    for name in os.listdir(data):
        os.chmod(os.path.join(data, name), 0o644)
    return data, out, scratch, expected


def _lock_for(label):
    with _GUARD:
        return _RUN_LOCKS.setdefault(label, threading.Lock())


def _run(workspace, label):
    """Drive the delivered program once per pass label and cache what it wrote.

    rewardkit evaluates checks on worker threads, so the cache is guarded per
    label: two checks reading one pass share a single run of the program.
    """
    with _lock_for(label):
        if label not in _RUNS:
            script = _script(workspace)
            if not os.path.isfile(script):
                _RUNS[label] = None
            else:
                for path in (str(workspace), os.path.dirname(script), script):
                    _grant_read(path)
                data, out, scratch, expected = _materialise(label)
                code = _launch([sys.executable, script, data, out], scratch)
                _RUNS[label] = {"data": data, "out": out, "scratch": scratch,
                                "code": code, "expected": expected}
        return _RUNS[label]


def _report(run, name):
    try:
        with open(os.path.join(run["out"], name), "rb") as handle:
            return handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _clean(run):
    return run is not None and run["code"] == 0


def _same_reports(workspace, label, names):
    run = _run(workspace, label)
    if not _clean(run):
        return False
    return all(_report(run, name) == run["expected"][name] for name in names)


def _jsonl(text):
    if text is None:
        return None
    try:
        return [json.loads(line) for line in text.splitlines() if line]
    except ValueError:
        return None


def _projection(rows, fields):
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return None
    return json.dumps([[row.get(field) for field in fields] for row in rows])


def _residue_fields_match(workspace, label, fields):
    run = _run(workspace, label)
    if not _clean(run):
        return False
    got = _projection(_jsonl(_report(run, "residues.jsonl")), fields)
    want = _projection(_jsonl(run["expected"]["residues.jsonl"]), fields)
    return got is not None and got == want


def _probe(workspace, fields, *names):
    return all(_residue_fields_match(workspace, "probe:" + name, fields) for name in names)


def _lane_rows(text):
    try:
        document = json.loads(text)
    except (TypeError, ValueError):
        return None
    return document.get("lanes") if isinstance(document, dict) else None


def _form_column(text):
    if text is None:
        return None
    return [line.split(",")[0] for line in text.splitlines()[1:]]


def _guarded(check, *args):
    """A check must answer True or False; any exception on agent output is a False."""
    try:
        return bool(check(*args))
    except Exception:
        return False


def _delivered_source(workspace):
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _grant_read(script)
    with open(script, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def _writes_the_four_reports(workspace):
    run = _run(workspace, UNSEEN[0])
    if not _clean(run):
        return False
    rows = _jsonl(_report(run, "residues.jsonl"))
    if not rows or any(sorted(row) != RESIDUE_KEYS for row in rows):
        return False
    document = json.loads(_report(run, "lanes.json"))
    if sorted(document) != ["lanes"] or not document["lanes"]:
        return False
    if any(sorted(row) != LANE_KEYS for row in document["lanes"]):
        return False
    forms = _report(run, "forms.csv").splitlines()
    if not forms or forms[0] != FORM_HEADER or len(forms) < 2:
        return False
    return sorted(json.loads(_report(run, "sieve.json"))) == SIEVE_KEYS


def _byte_form(workspace):
    run = _run(workspace, UNSEEN[1])
    if not _clean(run):
        return False
    text = _report(run, "residues.jsonl")
    rows = _jsonl(text)
    if not rows or text != render_residues(rows):
        return False
    for name in ("lanes.json", "sieve.json"):
        body = _report(run, name)
        if body != render_document(json.loads(body)):
            return False
    body = _report(run, "forms.csv")
    if not body.endswith("\n") or "\r" in body:
        return False
    lines = body.splitlines()
    width = len(FORM_HEADER.split(","))
    return lines[0] == FORM_HEADER and all(len(line.split(",")) == width for line in lines[1:])


def _form_order(workspace):
    run = _run(workspace, "probe:form_order")
    if not _clean(run):
        return False
    got = _form_column(_report(run, "forms.csv"))
    return got is not None and got == _form_column(run["expected"]["forms.csv"])


def _lane_fields(workspace):
    run = _run(workspace, "probe:lane_rollup")
    if not _clean(run):
        return False
    got = _projection(_lane_rows(_report(run, "lanes.json")), VERDICT_FIELDS)
    want = _projection(_lane_rows(run["expected"]["lanes.json"]), VERDICT_FIELDS)
    return got is not None and got == want


def _hardcoded(workspace):
    source = _delivered_source(workspace)
    if source is None:
        return False
    literals = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
    return len(RECORDED_LANES & literals) >= 5


def _third_party(workspace):
    source = _delivered_source(workspace)
    if source is None:
        return False
    wanted = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            wanted.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            wanted.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in ("__import__", "import_module") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    wanted.add(first.value.split(".")[0])
    return bool(wanted - set(sys.stdlib_module_names))


def _nondeterministic(workspace):
    run = _run(workspace, "repeat")
    if not _clean(run):
        return False
    first = {name: _report(run, name) for name in REPORT_NAMES}
    for _attempt in range(4):
        if _launch([sys.executable, _script(workspace), run["data"], run["out"]],
                   run["scratch"]) != 0:
            return True
        if any(_report(run, name) != body for name, body in first.items()):
            return True
    return False


@criterion(description="driven with an input and an output directory the program writes the four documented reports with their documented keys")
def program_writes_the_four_reports(workspace: Path) -> bool:
    return _guarded(_writes_the_four_reports, workspace)


@criterion(description="each report file is the documented serialization of the content it carries")
def report_serialization_carries_the_documented_byte_form(workspace: Path) -> bool:
    return _guarded(_byte_form, workspace)


@criterion(description="a pass holding no lane and no sample writes the four documented empty reports")
def empty_pass_reports_are_written(workspace: Path) -> bool:
    return _guarded(_same_reports, workspace, "empty", REPORT_NAMES)


@criterion(description="the sample weights on a one lane probe across five values match the reference, pinning the normalisation gain")
def normalisation_gain(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "gain")


@criterion(description="the sample weights on a probe that varies span, blocks and terms match the reference")
def governing_count_columns(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "count_columns")


@criterion(description="the sample weights on a probe whose figures cross half the modulus match the reference")
def least_absolute_residue(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "least_residue")


@criterion(description="the sample weights on an upper sector probe match the reference")
def sector_adjustment_upper(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "sector_upper")


@criterion(description="the sample weights on a lower sector probe match the reference")
def sector_adjustment_lower(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "sector_lower")


@criterion(description="the sample weights on a split sector probe match the reference")
def sector_adjustment_split(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "sector_split")


@criterion(description="the sample weights on a folded sector probe match the reference")
def sector_adjustment_folded(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "sector_folded")


@criterion(description="the sample weights on a shifted sector probe match the reference")
def sector_adjustment_shifted(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "sector_shifted")


@criterion(description="the sample weights on a wrapped sector probe match the reference")
def sector_adjustment_wrapped(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "sector_wrapped")


@criterion(description="the sample weights on a cubic kind probe match the reference")
def kind_adjustment_cubic(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "kind_cubic")


@criterion(description="the sample weights on a quadratic kind probe and on a linear kind probe match the reference")
def kind_adjustments_quadratic_and_linear(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "kind_quadratic", "kind_linear")


@criterion(description="the sample weights on a lane whose form names a cubic parent match the reference")
def charged_kind_follows_the_parent_form(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "parent_kind")


@criterion(description="the sample weights on a dusk window probe and on a night window probe match the reference")
def window_adjustments_dusk_and_night(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "window_dusk", "window_night")


@criterion(description="the sample weights on a prime family probe match the reference")
def family_adjustment_prime(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "family_prime")


@criterion(description="the sample weights on a power family probe match the reference")
def family_adjustment_power(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "family_power")


@criterion(description="the sample weights after a lane's fault count reaches the sealing figure match the reference")
def faulted_lane_is_charged_at_the_promoted_family(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "fault_family")


@criterion(description="the weights a returning tag settles on match the reference on a probe that reuses two tags")
def repeated_tag_reuses_the_recorded_weight(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "repeat_tag")


@criterion(description="the sample weights around an abandoned sample match the reference")
def abandoned_sample_arms_a_doubled_drift_relief(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "waiver")


@criterion(description="the sample weights on a probe whose samples carry no count of their own match the reference")
def absent_count_columns_inherit_the_previous_count(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "count_inherit")


@criterion(description="the drift_before figures on a probe whose counts share different divisors with the modulus match the reference")
def drift_step_carries_the_common_divisor(workspace: Path) -> bool:
    return _guarded(_probe, workspace, DRIFT_FIELDS, "drift_gcd")


@criterion(description="the drift_before figures on a depth two probe and on a depth three probe match the reference")
def drift_step_by_depth(workspace: Path) -> bool:
    return _guarded(_probe, workspace, DRIFT_FIELDS, "drift_depth_2", "drift_depth_3")


@criterion(description="the sample weights while a banked credit is drawn down match the reference")
def credit_release_drawdown(workspace: Path) -> bool:
    return _guarded(_probe, workspace, WEIGHT_FIELDS, "credit_release")


@criterion(description="the bands of samples placed on either side of each band edge match the reference")
def band_edges(workspace: Path) -> bool:
    return _guarded(_probe, workspace, BAND_FIELDS, "band_edges")


@criterion(description="the statuses of samples resolved at drifts around each grade tolerance match the reference")
def grade_tolerances(workspace: Path) -> bool:
    return _guarded(_probe, workspace, STATUS_FIELDS, "tolerance")


@criterion(description="the order of the form rows matches the reference on a probe of two forms with unequal totals")
def form_rows_carry_the_documented_order(workspace: Path) -> bool:
    return _guarded(_form_order, workspace)


@criterion(description="the verdict, weight_total, peak_weight and top_tag of every lane on a verdict and tie probe match the reference")
def lane_verdicts_and_counted_totals(workspace: Path) -> bool:
    return _guarded(_lane_fields, workspace)


@criterion(description="residues.jsonl matches the reference byte for byte on all ten unseen sieve passes")
def residue_ledger_on_unseen_passes(workspace: Path) -> bool:
    return _guarded(lambda: all(_same_reports(workspace, label, ("residues.jsonl",)) for label in UNSEEN))


@criterion(description="lanes.json matches the reference byte for byte on all ten unseen sieve passes")
def lane_rollup_on_unseen_passes(workspace: Path) -> bool:
    return _guarded(lambda: all(_same_reports(workspace, label, ("lanes.json",)) for label in UNSEEN))


@criterion(description="forms.csv and sieve.json match the reference byte for byte on all ten unseen sieve passes")
def pass_rollups_on_unseen_passes(workspace: Path) -> bool:
    return _guarded(lambda: all(_same_reports(workspace, label, ("forms.csv", "sieve.json"))
                                for label in UNSEEN))


@criterion(description="the delivered program carries at least five of the recorded pass's lane identifiers as string literals")
def negative_hardcoded_recorded_lane_answers(workspace: Path) -> bool:
    # True when the cheat happened: the answers are keyed on recorded lane names.
    return _guarded(_hardcoded, workspace)


@criterion(description="the delivered program imports a module outside the Python standard library")
def negative_third_party_dependency(workspace: Path) -> bool:
    # True when the cheat happened: a non stdlib import or dynamic import is present.
    return _guarded(_third_party, workspace)


@criterion(description="repeated runs of the delivered program over one input directory write differing bytes or fail")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # True when the cheat happened: a rerun over the same input disagrees or exits nonzero.
    return _guarded(_nondeterministic, workspace)


criteria.program_writes_the_four_reports(weight=1)
criteria.report_serialization_carries_the_documented_byte_form(weight=1)
criteria.empty_pass_reports_are_written(weight=1)
criteria.normalisation_gain(weight=3)
criteria.governing_count_columns(weight=3)
criteria.least_absolute_residue(weight=3)
criteria.sector_adjustment_upper(weight=3)
criteria.sector_adjustment_lower(weight=3)
criteria.sector_adjustment_split(weight=3)
criteria.sector_adjustment_folded(weight=3)
criteria.sector_adjustment_shifted(weight=3)
criteria.sector_adjustment_wrapped(weight=3)
criteria.kind_adjustment_cubic(weight=3)
criteria.kind_adjustments_quadratic_and_linear(weight=3)
criteria.charged_kind_follows_the_parent_form(weight=3)
criteria.window_adjustments_dusk_and_night(weight=3)
criteria.family_adjustment_prime(weight=3)
criteria.family_adjustment_power(weight=3)
criteria.faulted_lane_is_charged_at_the_promoted_family(weight=3)
criteria.repeated_tag_reuses_the_recorded_weight(weight=3)
criteria.abandoned_sample_arms_a_doubled_drift_relief(weight=3)
criteria.absent_count_columns_inherit_the_previous_count(weight=3)
criteria.drift_step_carries_the_common_divisor(weight=3)
criteria.drift_step_by_depth(weight=3)
criteria.credit_release_drawdown(weight=3)
criteria.band_edges(weight=3)
criteria.grade_tolerances(weight=3)
criteria.form_rows_carry_the_documented_order(weight=3)
criteria.lane_verdicts_and_counted_totals(weight=3)
criteria.residue_ledger_on_unseen_passes(weight=5)
criteria.lane_rollup_on_unseen_passes(weight=5)
criteria.pass_rollups_on_unseen_passes(weight=5)
criteria.negative_hardcoded_recorded_lane_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
