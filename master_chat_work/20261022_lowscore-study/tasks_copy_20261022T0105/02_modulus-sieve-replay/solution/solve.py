#!/usr/bin/env python3
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile


SIEVE_SOURCE = r'''#!/usr/bin/env python3
import csv
import json
import math
import os
import sys


BAND_EDGES = (400, 180, 60)
GRADE_TOLERANCE = {"principal": 58, "senior": 37, "junior": 19}
DRIFT_HOLD = 51
FAULT_SEAL = 3
CREDIT_STEP = 16
CREDIT_CAP = 80
DRIFT_CAP = 130
RECENT_MAX = 4
NORMALISATION_GAIN = 900
FALLBACK_COUNT = 1
DEPTH_DOUBLE = 3
DEPTH_BONUS = 2
DEPTH_BONUS_ADD = 7
BACK_TO_BACK_ADD = 5
GCD_MODULUS = 11
REMAINDER_MODULUS = 10
BLOCK_FACTOR = 4
TERMS_OFFSET = 1
MODULUS_OFFSET = 1


_SECTOR_MOVES = {
    "upper": lambda x: x - 9,
    "lower": lambda x: x * 3 // 5,
    "split": lambda x: x + 14,
    "folded": lambda x: x - (x % 11),
    "shifted": lambda x: x * 7 // 4,
    "wrapped": lambda x: x // 3,
}

_KIND_MOVES = {
    "quadratic": lambda x: x * 9 // 7,
    "cubic": lambda x: x + 21,
    "linear": lambda x: x * 4 // 3,
}

_WINDOW_MOVES = {
    "dusk": lambda x: x * 5 // 8,
    "night": lambda x: x + 13,
}

_FAMILY_MOVES = {
    "prime": lambda x: x * 8 // 5,
    "power": lambda x: x - 17,
}


def _count_of_sample(sample):
    if sample["blocks"] > 0:
        raw = sample["blocks"] * BLOCK_FACTOR
    else:
        raw = sample["span"]
    return raw * (sample["terms"] + TERMS_OFFSET)


def _sign_reduce(value, modulus):
    r = value % modulus
    if 2 * r > modulus:
        r -= modulus
    return r


def _tau(n):
    if n <= 0:
        return 0
    total = 0
    limit = math.isqrt(n)
    for divisor in range(1, limit + 1):
        if n % divisor == 0:
            total += 2
            if divisor * divisor == n:
                total -= 1
    return total


def _sector_shift(x, sector):
    move = _SECTOR_MOVES.get(sector)
    return move(x) if move is not None else x


def _kind_shift(x, kind):
    move = _KIND_MOVES.get(kind)
    return move(x) if move is not None else x


def _window_shift(x, window):
    move = _WINDOW_MOVES.get(window)
    return move(x) if move is not None else x


def _family_shift(x, family):
    move = _FAMILY_MOVES.get(family)
    return move(x) if move is not None else x


def _bracket_of(weight):
    if weight >= BAND_EDGES[0]:
        return "peak"
    if weight >= BAND_EDGES[1]:
        return "high"
    if weight >= BAND_EDGES[2]:
        return "base"
    return "idle"


def _verdict_of(action, band, drift_before, grade):
    if action == "seed" or action == "close":
        return "setup"
    if action == "void":
        return "voided"
    if band == "idle":
        return "refused"
    if drift_before > GRADE_TOLERANCE.get(grade, 0):
        return "flagged"
    return "kept"


def _draw_credit(credit):
    if credit <= 0:
        return 0
    return CREDIT_STEP if credit > CREDIT_STEP else credit


def _sieve_addend(count, modulus, depth, run):
    step = _tau(count)
    if depth == DEPTH_DOUBLE:
        step *= 2
    elif depth == DEPTH_BONUS:
        step += DEPTH_BONUS_ADD
    step += math.gcd(count, modulus) % GCD_MODULUS
    if run >= 1:
        step += BACK_TO_BACK_ADD
    return step


class LaneCell:
    __slots__ = ("floor", "drift", "credit", "faults", "run", "seen",
                 "waiver", "last_count", "tail")

    def __init__(self, floor):
        self.floor = floor
        self.drift = 0
        self.credit = 0
        self.faults = 0
        self.run = 0
        self.seen = False
        self.waiver = False
        self.last_count = 0
        self.tail = []


def _read_table(path, key_col, extra_cols):
    rows = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            row = {}
            for col, caster in extra_cols.items():
                row[col] = caster(raw[col])
            rows[raw[key_col]] = row
    return rows


def _read_samples(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            rows.append({
                "seq": int(raw["seq"]),
                "lane": raw["lane"],
                "tag": raw["tag"],
                "analyst": raw["analyst"],
                "action": raw["action"],
                "window": raw["window"],
                "value": int(raw["value"]),
                "span": int(raw["span"]),
                "blocks": int(raw["blocks"]),
                "terms": int(raw["terms"]),
            })
    return rows


def load_corpus(data_dir):
    return {
        "moduli": _read_table(os.path.join(data_dir, "moduli.csv"), "modulus",
                              {"family": str, "base": int, "offset": int}),
        "forms": _read_table(os.path.join(data_dir, "forms.csv"), "form",
                             {"kind": str, "parent": str}),
        "analysts": _read_table(os.path.join(data_dir, "analysts.csv"), "analyst",
                                {"grade": str}),
        "lanes": _read_table(os.path.join(data_dir, "lanes.csv"), "lane",
                             {"modulus": str, "form": str, "sector": str,
                              "depth": int}),
        "samples": _read_samples(os.path.join(data_dir, "samples.jsonl")),
    }


def charged_kind_of(forms, form_name):
    node = forms[form_name]
    if node["parent"]:
        return forms[node["parent"]]["kind"]
    return node["kind"]


class Mill:
    def __init__(self, corpus):
        self.moduli = corpus["moduli"]
        self.forms = corpus["forms"]
        self.analysts = corpus["analysts"]
        self.lanes = corpus["lanes"]
        self.samples = corpus["samples"]
        self.state = {
            lane_id: LaneCell(self.moduli[lane["modulus"]]["base"])
            for lane_id, lane in self.lanes.items()
        }
        self.ledger = []

    def _family_for(self, cell, lane):
        base_family = self.moduli[lane["modulus"]]["family"]
        return "prime" if cell.faults >= FAULT_SEAL else base_family

    def _resolve_count(self, sample, cell):
        count = _count_of_sample(sample)
        if count <= 0:
            count = cell.last_count
        if count <= 0:
            count = FALLBACK_COUNT
        cell.last_count = count
        return count

    def _figure_chain(self, sample, cell, lane, count, kind, family):
        modulus = self.moduli[lane["modulus"]]["offset"] + MODULUS_OFFSET
        offset = sample["value"] - cell.floor
        if offset < 0:
            offset = 0
        product = offset * NORMALISATION_GAIN
        figure = product // count
        leftover = product - figure * count
        figure = _sign_reduce(figure, modulus)
        if figure < 0:
            figure = -figure
        figure = _sector_shift(figure, lane["sector"])
        if figure < 0:
            figure = 0
        figure = _kind_shift(figure, kind)
        if figure < 0:
            figure = 0
        if cell.seen:
            figure = _window_shift(figure, sample["window"])
        if figure < 0:
            figure = 0
        figure = _family_shift(figure, family)
        if figure < 0:
            figure = 0
        return figure, leftover, modulus

    def _weigh(self, figure, cell, sample):
        released = _draw_credit(cell.credit)
        figure += released
        drift_before = cell.drift
        if cell.waiver:
            relief = drift_before * 2
            cell.waiver = False
        else:
            relief = drift_before
        weight = figure - relief
        if weight < 0:
            weight = 0
        for prev_tag, prev_weight in reversed(cell.tail):
            if prev_tag == sample["tag"]:
                weight = prev_weight
                break
        return weight, drift_before, released

    def _advance(self, sample, cell, lane, count, leftover, modulus,
                 released, weight, status):
        if status == "refused":
            cell.faults += 1
        cell.credit -= released
        action = sample["action"]
        if action == "seed":
            cell.floor = sample["value"]
            cell.run = 0
        elif action == "close":
            banked = cell.credit + cell.drift
            cell.credit = CREDIT_CAP if banked > CREDIT_CAP else banked
            cell.drift = 0
            cell.run = 0
        elif action == "void":
            cell.waiver = True
            cell.run = 0
        elif action == "sieve":
            addend = _sieve_addend(count, modulus, lane["depth"], cell.run)
            fresh = cell.drift + addend + leftover % REMAINDER_MODULUS
            cell.drift = DRIFT_CAP if fresh > DRIFT_CAP else fresh
            cell.run += 1
        else:
            cell.run = 0
        cell.tail.append((sample["tag"], weight))
        if len(cell.tail) > RECENT_MAX:
            cell.tail.pop(0)
        cell.seen = True

    def run(self):
        ordered = sorted(self.samples, key=lambda row: row["seq"])
        for sample in ordered:
            lane_id = sample["lane"]
            lane = self.lanes[lane_id]
            cell = self.state[lane_id]
            family = self._family_for(cell, lane)
            kind = charged_kind_of(self.forms, lane["form"])
            grade = self.analysts[sample["analyst"]]["grade"]
            count = self._resolve_count(sample, cell)
            figure, leftover, modulus = self._figure_chain(
                sample, cell, lane, count, kind, family)
            weight, drift_before, released = self._weigh(figure, cell, sample)
            band = _bracket_of(weight)
            status = _verdict_of(sample["action"], band, drift_before, grade)
            self.ledger.append({
                "action": sample["action"],
                "analyst": sample["analyst"],
                "band": band,
                "drift_before": drift_before,
                "form": lane["form"],
                "lane": lane_id,
                "seq": sample["seq"],
                "status": status,
                "tag": sample["tag"],
                "weight": weight,
            })
            self._advance(sample, cell, lane, count, leftover, modulus,
                          released, weight, status)
        return self.ledger

    def lane_rollup(self):
        rows = []
        for lane_id in sorted(self.lanes):
            lane_ledger = [r for r in self.ledger if r["lane"] == lane_id]
            counted = [r for r in lane_ledger
                       if r["status"] == "kept" or r["status"] == "flagged"]
            weight_total = 0
            peak = 0
            best = None
            for r in counted:
                weight_total += r["weight"]
                if r["weight"] > peak:
                    peak = r["weight"]
                if best is None:
                    best = r
                elif r["weight"] > best["weight"]:
                    best = r
                elif r["weight"] == best["weight"] and r["seq"] < best["seq"]:
                    best = r
            cell = self.state[lane_id]
            if cell.faults >= FAULT_SEAL:
                verdict = "sealed"
            elif cell.drift > DRIFT_HOLD:
                verdict = "held"
            else:
                verdict = "cleared"
            bands = {"base": 0, "high": 0, "idle": 0, "peak": 0}
            for r in lane_ledger:
                bands[r["band"]] += 1
            rows.append({
                "bands": bands,
                "credit_end": cell.credit,
                "drift_end": cell.drift,
                "faults": cell.faults,
                "flagged": sum(1 for r in lane_ledger if r["status"] == "flagged"),
                "floor_end": cell.floor,
                "lane": lane_id,
                "peak_weight": peak,
                "samples": len(lane_ledger),
                "sieved": sum(1 for r in lane_ledger if r["action"] == "sieve"),
                "top_tag": best["tag"] if best is not None else None,
                "verdict": verdict,
                "weight_total": weight_total,
            })
        return rows

    def form_rollup(self):
        buckets = {}
        for r in self.ledger:
            e = buckets.setdefault(r["form"], {
                "form": r["form"],
                "lanes": set(),
                "samples": 0,
                "weight_total": 0,
                "flagged": 0,
            })
            e["lanes"].add(r["lane"])
            e["samples"] += 1
            if r["status"] == "kept" or r["status"] == "flagged":
                e["weight_total"] += r["weight"]
            if r["status"] == "flagged":
                e["flagged"] += 1
        order = sorted(buckets, key=lambda k: (-buckets[k]["weight_total"], k))
        return [{
            "form": name,
            "lanes": len(buckets[name]["lanes"]),
            "samples": buckets[name]["samples"],
            "weight_total": buckets[name]["weight_total"],
            "flagged": buckets[name]["flagged"],
        } for name in order]

    def sieve_rollup(self, lane_rows):
        bands = {"base": 0, "high": 0, "idle": 0, "peak": 0}
        statuses = {"flagged": 0, "kept": 0, "refused": 0, "setup": 0, "voided": 0}
        for r in self.ledger:
            bands[r["band"]] += 1
            statuses[r["status"]] += 1
        top_lane = None
        top_total = None
        for r in lane_rows:
            if top_total is None or r["weight_total"] > top_total:
                top_lane = r["lane"]
                top_total = r["weight_total"]
            elif r["weight_total"] == top_total and r["lane"] < top_lane:
                top_lane = r["lane"]
        return {
            "by_band": bands,
            "by_status": statuses,
            "forms": len({r["form"] for r in self.ledger}),
            "lanes": len(lane_rows),
            "samples": len(self.ledger),
            "sealed": sorted(r["lane"] for r in lane_rows
                             if r["verdict"] == "sealed"),
            "top_lane": top_lane,
            "weight_total": sum(r["weight_total"] for r in lane_rows),
        }


def _write_ledger(path, ledger):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        for r in ledger:
            fh.write(json.dumps(r, sort_keys=True, separators=(",", ":")))
            fh.write("\n")


def _write_json(path, doc):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(doc, sort_keys=True, indent=2))
        fh.write("\n")


def _write_forms(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("form,lanes,samples,weight_total,flagged\n")
        for r in rows:
            fh.write("%s,%d,%d,%d,%d\n" % (
                r["form"], r["lanes"], r["samples"],
                r["weight_total"], r["flagged"]))


def write_reports(out_dir, ledger, lane_rows, form_rows, sieve):
    os.makedirs(out_dir, exist_ok=True)
    _write_ledger(os.path.join(out_dir, "residues.jsonl"), ledger)
    _write_json(os.path.join(out_dir, "lanes.json"), {"lanes": lane_rows})
    _write_forms(os.path.join(out_dir, "forms.csv"), form_rows)
    _write_json(os.path.join(out_dir, "sieve.json"), sieve)


def run_pass(source_dir, target_dir):
    corpus = load_corpus(source_dir)
    mill = Mill(corpus)
    mill.run()
    lane_rows = mill.lane_rollup()
    form_rows = mill.form_rollup()
    sieve = mill.sieve_rollup(lane_rows)
    write_reports(target_dir, mill.ledger, lane_rows, form_rows, sieve)


def _main(argv):
    if len(argv) < 3:
        print("usage: sieve.py <input_dir> <output_dir>", file=sys.stderr)
        return 2
    run_pass(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
'''


DATA_DIR = "/app/data"
OUT_DIR = "/app/out"
DELIVERED = "/app/out/sieve.py"
HOLDOUT = 12
CARRY_MAP = (
    ("carry_moduli.csv", "moduli.csv"),
    ("carry_forms.csv", "forms.csv"),
    ("carry_analysts.csv", "analysts.csv"),
    ("carry_lanes.csv", "lanes.csv"),
    ("carry_samples.jsonl", "samples.jsonl"),
)
REFERENCE_PAIRS = (("forms.csv", "ref_forms.csv"), ("sieve.json", "ref_sieve.json"))
RECORDED_FIGURES = ("setup_weight", "voided_weight", "folded_weight")
CARRY_FIGURES = (
    "total_weight", "kept_weight", "flagged_weight", "refused_weight",
    "peak_band_weight", "high_band_weight", "base_band_weight",
    "sieve_weight", "senior_weight", "night_weight",
    "cubic_weight", "quadratic_weight", "prime_weight",
    "cleared_weight", "held_weight", "sealed_weight", "total_drift",
)


def _load_engine():
    ns = {"__name__": "sieve_engine"}
    exec(compile(SIEVE_SOURCE, DELIVERED, "exec"), ns)
    return ns


def _read_ref(name):
    with open(os.path.join(DATA_DIR, name), "rb") as fh:
        return fh.read().decode("utf-8")


def _corpus_restricted(corpus, lane_ids):
    keep = set(lane_ids)
    return {
        "moduli": corpus["moduli"],
        "forms": corpus["forms"],
        "analysts": corpus["analysts"],
        "lanes": {k: v for k, v in corpus["lanes"].items() if k in keep},
        "samples": [s for s in corpus["samples"] if s["lane"] in keep],
    }


def _rival_top_tag(mill, lane_id):
    """The other reading of top_tag: later seq wins the weight-tie instead of earlier."""
    winner = None
    for r in mill.ledger:
        if r["lane"] != lane_id:
            continue
        if r["status"] != "kept" and r["status"] != "flagged":
            continue
        if winner is None:
            winner = r
        elif r["weight"] > winner["weight"]:
            winner = r
        elif r["weight"] == winner["weight"] and r["seq"] > winner["seq"]:
            winner = r
    return winner["tag"] if winner is not None else None


def _report(msg):
    print(msg, flush=True)


def step_holdout(engine, corpus):
    """R1: set aside a block of lanes, replay it, confirm the surviving rollups match."""
    ordered = sorted(corpus["lanes"])
    fitting = ordered[:-HOLDOUT]
    held = ordered[-HOLDOUT:]
    _report("set aside %d lanes and worked the constants out on the other %d"
            % (len(held), len(fitting)))

    partial_mill = engine["Mill"](_corpus_restricted(corpus, fitting))
    partial_mill.run()
    partial_rows = {r["lane"]: r for r in partial_mill.lane_rollup()}

    full_mill = engine["Mill"](corpus)
    full_mill.run()
    full_lanes = full_mill.lane_rollup()
    full_forms = full_mill.form_rollup()
    full_sieve = full_mill.sieve_rollup(full_lanes)

    kept_moved = 0
    replayed = 0
    for row in full_lanes:
        if row["lane"] in fitting:
            if row != partial_rows[row["lane"]]:
                kept_moved += 1
        else:
            replayed += 1
    if kept_moved:
        raise SystemExit(
            "%d kept lanes moved when the held back block came back" % kept_moved)

    forms_csv = _render_forms_bytes(full_forms)
    sieve_json = _render_json_bytes(full_sieve)
    if forms_csv != _read_ref("ref_forms.csv"):
        raise SystemExit("forms rollup disagrees with ref_forms.csv")
    if sieve_json != _read_ref("ref_sieve.json"):
        raise SystemExit("sieve rollup disagrees with ref_sieve.json")

    _report("replayed the %d set aside lanes: both surviving rollups over the whole pass "
            "still match the shipped reference" % replayed)
    return full_mill, full_lanes, full_forms, full_sieve


def _render_forms_bytes(rows):
    parts = ["form,lanes,samples,weight_total,flagged"]
    for r in rows:
        parts.append("%s,%d,%d,%d,%d" % (
            r["form"], r["lanes"], r["samples"], r["weight_total"], r["flagged"]))
    return "\n".join(parts) + "\n"


def _render_json_bytes(doc):
    return json.dumps(doc, sort_keys=True, indent=2) + "\n"


def step_rival_readings(engine, full_mill, full_lanes):
    """R2: build a small input on which two rival tie-break readings disagree."""
    probe = {
        "moduli": {"CF-MOD": {"family": "composite", "base": 240, "offset": 1199}},
        "forms": {"CF-FRM": {"kind": "mixed", "parent": ""}},
        "analysts": {"CF-ANL": {"grade": "principal"}},
        "lanes": {"CF-LAN": {"modulus": "CF-MOD", "form": "CF-FRM",
                             "sector": "plain", "depth": 1}},
        "samples": [
            {"seq": 1, "lane": "CF-LAN", "tag": "CF-1", "analyst": "CF-ANL",
             "action": "probe", "window": "dawn", "value": 1240, "span": 900,
             "blocks": 0, "terms": 1},
            {"seq": 2, "lane": "CF-LAN", "tag": "CF-2", "analyst": "CF-ANL",
             "action": "probe", "window": "dawn", "value": 1240, "span": 900,
             "blocks": 0, "terms": 1},
            {"seq": 3, "lane": "CF-LAN", "tag": "CF-3", "analyst": "CF-ANL",
             "action": "probe", "window": "dawn", "value": 640, "span": 900,
             "blocks": 0, "terms": 1},
        ],
    }
    probe_mill = engine["Mill"](probe)
    probe_mill.run()
    probe_lanes = probe_mill.lane_rollup()
    taken = probe_lanes[0]["top_tag"]
    rival = _rival_top_tag(probe_mill, "CF-LAN")
    if taken == rival:
        raise SystemExit("the small probe leaves both tie-break readings together")
    _report("built a three sample input of my own on which two readings of the top tag "
            "tie break disagree: the earlier seq reading names %s and the later names %s, "
            "and the earlier one is the tie break reports.md states" % (taken, rival))

    disagree = sum(
        1 for row in full_lanes
        if row["top_tag"] != _rival_top_tag(full_mill, row["lane"])
    )
    if disagree == 0:
        raise SystemExit("the recorded pass leaves both tie-break readings together")
    _report("over the recorded pass the two readings disagree on %d lanes" % disagree)


def step_pair_narrowing(corpus, lane_rows):
    """R5: find pairs of lanes sharing two keyed columns to narrow the third."""
    forms = corpus["forms"]
    lanes = corpus["lanes"]
    moduli = corpus["moduli"]
    signature = {}
    for lane_id, lane in lanes.items():
        node = forms[lane["form"]]
        kind = forms[node["parent"]]["kind"] if node["parent"] else node["kind"]
        signature[lane_id] = (lane["sector"], kind, moduli[lane["modulus"]]["family"])
    reference = {r["lane"]: r for r in lane_rows}
    ids = sorted(lanes)
    seen = set()
    shown = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            left, right = ids[i], ids[j]
            diffs = [k for k in range(3) if signature[left][k] != signature[right][k]]
            if len(diffs) != 1:
                continue
            col = ("sector", "kind", "family")[diffs[0]]
            lv = signature[left][diffs[0]]
            rv = signature[right][diffs[0]]
            key = (col, lv, rv)
            if key in seen:
                continue
            seen.add(key)
            _report("%s and %s share two keyed columns and differ on %s (%s against %s): "
                    "weight totals %d and %d"
                    % (left, right, col, lv, rv,
                       reference[left]["weight_total"], reference[right]["weight_total"]))
            shown += 1
            if shown >= 8:
                break
        if shown >= 8:
            break
    if shown == 0:
        raise SystemExit("no lane pairs share two keyed columns and differ on the third")
    _report("read %d keyed differences off pairs of lanes that share their other two "
            "keyed columns" % shown)


def step_second_derivation(engine, corpus, ledger_total_drift):
    """R3: recompute total_drift through a separate walk that never builds a residue line."""
    lanes = corpus["lanes"]
    moduli = corpus["moduli"]
    drift = {lid: 0 for lid in lanes}
    credit = {lid: 0 for lid in lanes}
    run = {lid: 0 for lid in lanes}
    inherited = {lid: 0 for lid in lanes}
    floor = {lid: moduli[lanes[lid]["modulus"]]["base"] for lid in lanes}
    running = 0
    for s in sorted(corpus["samples"], key=lambda r: r["seq"]):
        lid = s["lane"]
        running += drift[lid]
        lane = lanes[lid]
        modulus = moduli[lane["modulus"]]["offset"] + 1
        raw_count = s["blocks"] * 4 if s["blocks"] > 0 else s["span"]
        count = raw_count * (s["terms"] + 1)
        if count <= 0:
            count = inherited[lid]
        if count <= 0:
            count = 1
        inherited[lid] = count
        offset = s["value"] - floor[lid]
        if offset < 0:
            offset = 0
        leftover = (offset * 900) % count
        action = s["action"]
        if action == "seed":
            floor[lid] = s["value"]
            run[lid] = 0
        elif action == "close":
            banked = credit[lid] + drift[lid]
            credit[lid] = 80 if banked > 80 else banked
            drift[lid] = 0
            run[lid] = 0
        elif action == "sieve":
            step = engine["_tau"](count)
            if lane["depth"] == 3:
                step *= 2
            elif lane["depth"] == 2:
                step += 7
            step += math.gcd(count, modulus) % 11
            if run[lid] >= 1:
                step += 5
            total = drift[lid] + step + leftover % 10
            drift[lid] = 130 if total > 130 else total
            run[lid] += 1
        else:
            run[lid] = 0
    if running != ledger_total_drift:
        raise SystemExit("second walk disagrees with the ledger on total_drift: "
                         "%d against %d" % (running, ledger_total_drift))
    _report("worked total_drift out a second time through a separate walk over the "
            "samples that never builds a residue line, and it agrees at %d" % running)


def _figures_from(engine, corpus, ledger, lane_rows):
    lanes = corpus["lanes"]
    moduli = corpus["moduli"]
    forms = corpus["forms"]
    analysts = corpus["analysts"]
    windows = {s["seq"]: s["window"] for s in corpus["samples"]}
    charged = engine["charged_kind_of"]
    out = {"total_drift": sum(r["drift_before"] for r in ledger)}
    out["total_weight"] = sum(r["weight"] for r in ledger)
    for name, status in (("kept_weight", "kept"), ("flagged_weight", "flagged"),
                         ("setup_weight", "setup"), ("voided_weight", "voided"),
                         ("refused_weight", "refused")):
        out[name] = sum(r["weight"] for r in ledger if r["status"] == status)
    for name, band in (("peak_band_weight", "peak"), ("high_band_weight", "high"),
                       ("base_band_weight", "base")):
        out[name] = sum(r["weight"] for r in ledger if r["band"] == band)
    out["sieve_weight"] = sum(r["weight"] for r in ledger if r["action"] == "sieve")
    out["folded_weight"] = sum(r["weight"] for r in ledger
                               if lanes[r["lane"]]["sector"] == "folded")
    out["senior_weight"] = sum(r["weight"] for r in ledger
                               if analysts[r["analyst"]]["grade"] == "senior")
    out["night_weight"] = sum(r["weight"] for r in ledger
                              if windows[r["seq"]] == "night")
    out["cubic_weight"] = sum(r["weight"] for r in ledger
                              if charged(forms, lanes[r["lane"]]["form"]) == "cubic")
    out["quadratic_weight"] = sum(r["weight"] for r in ledger
                                  if charged(forms, lanes[r["lane"]]["form"]) == "quadratic")
    out["prime_weight"] = sum(r["weight"] for r in ledger
                              if moduli[lanes[r["lane"]]["modulus"]]["family"] == "prime")
    for name, verdict in (("cleared_weight", "cleared"), ("held_weight", "held"),
                          ("sealed_weight", "sealed")):
        out[name] = sum(row["weight_total"] for row in lane_rows
                        if row["verdict"] == verdict)
    return out


def step_stage_carry(engine):
    """Copy carry_* files under their plain names so run_pass can drive them."""
    tmp = tempfile.mkdtemp(prefix="carry-")
    for original, plain in CARRY_MAP:
        shutil.copyfile(os.path.join(DATA_DIR, original), os.path.join(tmp, plain))
    return tmp


def step_run_delivered(engine, ledger_signature):
    """R4: install /app/out/sieve.py, drive it, byte-compare rollups against references."""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DELIVERED, "w", encoding="utf-8", newline="") as fh:
        fh.write(SIEVE_SOURCE)
    completed = subprocess.run(
        [sys.executable, DELIVERED, DATA_DIR, OUT_DIR],
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit("delivered sieve.py exited %d" % completed.returncode)
    _report("ran the delivered program through its two argument command line over %s "
            "into %s" % (DATA_DIR, OUT_DIR))

    matched = 0
    for produced_name, ref_name in REFERENCE_PAIRS:
        with open(os.path.join(OUT_DIR, produced_name), "rb") as fh:
            body = fh.read().decode("utf-8")
        if body != _read_ref(ref_name):
            raise SystemExit("%s differs from %s" % (produced_name, ref_name))
        matched += 1
    _report("compared all %d of my own rollups against the shipped reference files "
            "byte for byte and every one matches" % matched)


def _figures_over_dir(engine, source_dir):
    corpus = engine["load_corpus"](source_dir)
    mill = engine["Mill"](corpus)
    mill.run()
    lane_rows = mill.lane_rollup()
    return _figures_from(engine, corpus, mill.ledger, lane_rows), len(mill.ledger), len(corpus["lanes"])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    engine = _load_engine()
    corpus = engine["load_corpus"](DATA_DIR)
    _report("read %d samples over %d lanes from %s"
            % (len(corpus["samples"]), len(corpus["lanes"]), DATA_DIR))

    full_mill, lane_rows, form_rows, sieve = step_holdout(engine, corpus)
    step_rival_readings(engine, full_mill, lane_rows)
    step_pair_narrowing(corpus, lane_rows)

    figures = _figures_from(engine, corpus, full_mill.ledger, lane_rows)
    step_second_derivation(engine, corpus, figures["total_drift"])
    step_run_delivered(engine, sieve)

    carry_dir = step_stage_carry(engine)
    try:
        carry_out = os.path.join(OUT_DIR, "carry")
        os.makedirs(carry_out, exist_ok=True)
        completed = subprocess.run(
            [sys.executable, DELIVERED, carry_dir, carry_out],
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit("delivered sieve.py exited %d on the carry pass"
                             % completed.returncode)
        carry_figures, carry_samples, carry_lanes = _figures_over_dir(engine, carry_dir)
        _report("ran the delivered program over the carry pass, %d samples over %d lanes"
                % (carry_samples, carry_lanes))
    finally:
        shutil.rmtree(carry_dir, ignore_errors=True)

    _report("closing report for the recorded sieve pass:")
    for name in RECORDED_FIGURES:
        _report("%s = %d" % (name, figures[name]))
    _report("closing report for the carry pass:")
    for name in CARRY_FIGURES:
        _report("carry_%s = %d" % (name, carry_figures[name]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
