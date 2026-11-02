import ast
import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from rewardkit import criteria, criterion


FLAG_CHAIN_BLANK = 0x001
FLAG_DRIFT_ECHO = 0x002
FLAG_ROLE_LOOKBACK = 0x004
FLAG_BAND_TIER_SHIFT = 0x008
FLAG_EXPOSURE_FLOOR = 0x010
FLAG_PANEL_PARITY = 0x020
FLAG_BASELINE_DELTA = 0x040
FLAG_EXPOSURE_ORDER = 0x080
FLAG_MASK_ABSOLVES = 0x100
FLAG_COUNT_BIAS = 0x200
FLAG_MATRIX_ALIAS = 0x400
FLAG_QUARANTINE_SPAN = 0x800
ALL_FLAGS = 0xFFF

MATRIX_ORDER = ["buffer", "serum", "plasma", "lysate", "saliva", "urine", "media"]


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


def load_corpus(data_dir, prefix=""):
    with open(os.path.join(data_dir, prefix + "manifest.json"), "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    instruments = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "instruments.csv")):
        instruments[row["instrument"]] = {
            "model": row["model"],
            "baseline": int(row["baseline"]),
        }
    panels = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "panels.csv")):
        panels[row["panel"]] = {
            "family": row["family"],
            "replicates": int(row["replicates"]),
        }
    operators = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "operators.csv")):
        operators[row["operator"]] = {"role": row["role"]}
    plates = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "plates.csv")):
        plates[row["plate"]] = {
            "instrument": row["instrument"],
            "panel": row["panel"],
            "matrix": row["matrix"],
            "tier": int(row["tier"]),
        }
    reads = []
    for row in _read_jsonl(os.path.join(data_dir, prefix + "reads.jsonl")):
        reads.append({
            "seq": int(row["seq"]),
            "plate": row["plate"],
            "well": row["well"],
            "operator": row["operator"],
            "action": row["action"],
            "raw": int(row["raw"]),
            "exposure": int(row["exposure"]),
        })
    return {
        "mode": int(manifest["mode"]),
        "instruments": instruments,
        "panels": panels,
        "operators": operators,
        "plates": plates,
        "reads": reads,
    }


def _adjust_matrix(value, matrix):
    if matrix == "serum":
        return value - 4
    if matrix == "plasma":
        return value * 3 // 4
    if matrix == "lysate":
        return value + 6
    if matrix == "saliva":
        return value // 2
    if matrix == "urine":
        return value - (value % 5)
    if matrix == "media":
        return value * 5 // 4
    return value


def _adjust_family(value, family):
    if family == "pcr":
        return value * 9 // 10
    if family == "turbidity":
        return value + 12
    if family == "fluor":
        return value * 7 // 5
    return value


def _grade(value, lift):
    if value >= 240 + lift:
        return "high"
    if value >= 120 + lift:
        return "mid"
    if value >= 40 + lift:
        return "low"
    return "trace"


def _role_limit(role):
    if role == "scientist":
        return 40
    if role == "trainee":
        return 12
    if role == "service":
        return 0
    return 25


def _status(action, grade, drift_before, role):
    if action == "blank" or action == "recal":
        return "setup"
    if action == "mask":
        return "masked"
    if grade == "trace":
        return "reject"
    if drift_before > _role_limit(role):
        return "review"
    return "ok"


def _charge(exposure, tier):
    charge = exposure // 50
    if tier == 3:
        charge = charge * 2
    return charge


def _baselines(instruments, plates, mode):
    values = {}
    for name, row in instruments.items():
        values[name] = row["baseline"]
    carried = sorted({plate["instrument"] for plate in plates.values()})
    if mode & FLAG_BASELINE_DELTA and len(values) > 1 and carried:
        island = carried[-1]
        others = [values[name] for name in values if name != island]
        if others:
            values[island] = values[island] + min(others)
    return values


def _matrix_for(plate_id, plate, operator_count, mode):
    written = plate["matrix"]
    if not (mode & FLAG_MATRIX_ALIAS):
        return written
    if written not in MATRIX_ORDER:
        return written
    index = MATRIX_ORDER.index(written)
    return MATRIX_ORDER[(index + plate["tier"] + operator_count) % len(MATRIX_ORDER)]


def _family_for(panel, mode):
    if mode & FLAG_PANEL_PARITY and panel["replicates"] % 2 == 1:
        return "elisa"
    return panel["family"]


def _resolution_order(reads, plate_count, mode):
    order = sorted(reads, key=lambda r: r["seq"])
    if mode & FLAG_COUNT_BIAS:
        order = order[:-(1 + plate_count % 4)]
    if mode & FLAG_EXPOSURE_ORDER:
        order = sorted(order, key=lambda r: (r["exposure"], r["seq"]))
    return order


def resolve(corpus):
    mode = corpus["mode"]
    instruments = corpus["instruments"]
    panels = corpus["panels"]
    operators = corpus["operators"]
    plates = corpus["plates"]
    operator_count = len(operators)
    baselines = _baselines(instruments, plates, mode)

    order = _resolution_order(corpus["reads"], len(plates), mode)

    floors = {}
    if mode & FLAG_EXPOSURE_FLOOR:
        for read in order:
            current = floors.get(read["plate"])
            if current is None or read["exposure"] < current:
                floors[read["plate"]] = read["exposure"]

    state = {}
    latest = {}
    readings = []
    for read in order:
        plate_id = read["plate"]
        plate = plates[plate_id]
        if plate_id not in state:
            start = baselines[plate["instrument"]]
            previous = latest.get(plate["instrument"])
            if mode & FLAG_CHAIN_BLANK and previous is not None:
                start = state[previous]["blank"]
            state[plate_id] = {
                "blank": start,
                "drift": 0,
                "pending": 0,
                "strikes": 0,
                "operator": None,
                "previous": latest.get(plate["instrument"]),
            }
            latest[plate["instrument"]] = plate_id
        slot = state[plate_id]

        matrix = _matrix_for(plate_id, plate, operator_count, mode)
        family = _family_for(panels[plate["panel"]], mode)
        role = operators[read["operator"]]["role"]
        if mode & FLAG_ROLE_LOOKBACK and slot["operator"] is not None:
            role = operators[slot["operator"]]["role"]
        exposure = read["exposure"]
        if mode & FLAG_EXPOSURE_FLOOR:
            exposure = floors[plate_id]
        lift = plate["tier"] * 15 if mode & FLAG_BAND_TIER_SHIFT else 0

        signal = read["raw"] - slot["blank"]
        signal = signal * 1000 // exposure
        if signal < 0:
            signal = 0
        signal = _adjust_matrix(signal, matrix)
        if signal < 0:
            signal = 0
        signal = _adjust_family(signal, family)
        if signal < 0:
            signal = 0
        drift_before = slot["drift"]
        value = signal - drift_before
        if value < 0:
            value = 0
        grade = _grade(value, lift)
        status = _status(read["action"], grade, drift_before, role)

        readings.append({
            "action": read["action"],
            "drift_before": drift_before,
            "grade": grade,
            "operator": read["operator"],
            "plate": plate_id,
            "seq": read["seq"],
            "status": status,
            "value": value,
            "well": read["well"],
        })

        if status == "reject":
            slot["strikes"] = slot["strikes"] + 1
        if read["action"] == "mask" and mode & FLAG_MASK_ABSOLVES and slot["strikes"] > 0:
            slot["strikes"] = slot["strikes"] - 1
        slot["operator"] = read["operator"]

        charge = 0
        if read["action"] == "measure":
            charge = _charge(read["exposure"], plate["tier"])
        if mode & FLAG_DRIFT_ECHO:
            carried = slot["pending"]
            slot["pending"] = charge
        else:
            carried = charge
        if read["action"] == "blank":
            slot["blank"] = read["raw"]
        elif read["action"] == "recal":
            slot["drift"] = 0
            slot["pending"] = 0
            carried = 0
        drift = slot["drift"] + carried
        if drift > 90:
            drift = 90
        slot["drift"] = drift

    plate_rows = []
    for plate_id in sorted(plates):
        rows = [r for r in readings if r["plate"] == plate_id]
        slot = state.get(plate_id)
        counted = [r for r in rows if r["status"] == "ok" or r["status"] == "review"]
        value_total = 0
        peak = 0
        best = None
        for row in counted:
            value_total = value_total + row["value"]
            if row["value"] > peak:
                peak = row["value"]
            if best is None:
                best = row
            elif row["value"] > best["value"]:
                best = row
            elif row["value"] == best["value"] and row["seq"] > best["seq"]:
                best = row
        strikes = slot["strikes"] if slot else 0
        drift_end = slot["drift"] if slot else 0
        weighed = strikes
        if mode & FLAG_QUARANTINE_SPAN and slot is not None and slot["previous"] is not None:
            weighed = strikes + state[slot["previous"]]["strikes"]
        if weighed >= 3:
            disposition = "quarantine"
        elif drift_end > 30:
            disposition = "hold"
        else:
            disposition = "release"
        grades = {"high": 0, "low": 0, "mid": 0, "trace": 0}
        for row in rows:
            grades[row["grade"]] = grades[row["grade"]] + 1
        plate_rows.append({
            "blank_end": slot["blank"] if slot else baselines[plates[plate_id]["instrument"]],
            "disposition": disposition,
            "drift_end": drift_end,
            "grades": grades,
            "measured": sum(1 for r in rows if r["action"] == "measure"),
            "peak": peak,
            "plate": plate_id,
            "reads": len(rows),
            "rejects": strikes,
            "reviewed": sum(1 for r in rows if r["status"] == "review"),
            "top_well": best["well"] if best is not None else None,
            "value_total": value_total,
        })

    by_grade = {"high": 0, "low": 0, "mid": 0, "trace": 0}
    by_status = {"masked": 0, "ok": 0, "reject": 0, "review": 0, "setup": 0}
    for row in readings:
        by_grade[row["grade"]] = by_grade[row["grade"]] + 1
        by_status[row["status"]] = by_status[row["status"]] + 1

    top_plate = None
    top_value = None
    for row in plate_rows:
        if top_value is None or row["value_total"] > top_value:
            top_plate = row["plate"]
            top_value = row["value_total"]

    bench = {
        "by_grade": by_grade,
        "by_status": by_status,
        "plates": len(plate_rows),
        "quarantined": sorted(r["plate"] for r in plate_rows if r["disposition"] == "quarantine"),
        "reads": len(readings),
        "top_plate": top_plate,
        "value_total": sum(r["value_total"] for r in plate_rows),
    }
    return readings, plate_rows, bench


def derive(data_dir, prefix=""):
    return resolve(load_corpus(data_dir, prefix))


def render_readings(readings):
    parts = []
    for row in readings:
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    return "".join(parts)


def render_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def plate_digest(readings, plate_rows, plate_id):
    rows = [row for row in readings if row["plate"] == plate_id]
    body = render_readings(rows)
    for row in plate_rows:
        if row["plate"] == plate_id:
            body = body + render_document(row)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def run_digest(readings, plate_rows, bench):
    body = (render_readings(readings)
            + render_document({"plates": plate_rows})
            + render_document(bench))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_reports(out_dir, readings, plate_rows, bench):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "readings.jsonl"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_readings(readings))
    with open(os.path.join(out_dir, "plates.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document({"plates": plate_rows}))
    with open(os.path.join(out_dir, "bench.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document(bench))


SAMPLE_SEED = 5140719
EXAMPLE_A_SEED = 3310021
EXAMPLE_B_SEED = 3310042

_BASE_INSTRUMENTS = [("INS-A", "halo", 100), ("INS-B", "vertex", 60), ("INS-C", "spindle", 140)]
_BASE_PANELS = [
    ("PNL-EL1", "elisa", 2),
    ("PNL-EL2", "elisa", 3),
    ("PNL-PC1", "pcr", 2),
    ("PNL-PC2", "pcr", 5),
    ("PNL-TB1", "turbidity", 3),
    ("PNL-FL1", "fluor", 2),
    ("PNL-FL2", "fluor", 5),
]
_BASE_OPERATORS = [
    ("OP-01", "technician"),
    ("OP-02", "technician"),
    ("OP-03", "scientist"),
    ("OP-04", "trainee"),
    ("OP-05", "service"),
]
_MATRICES = ["buffer", "serum", "plasma", "lysate", "saliva", "urine", "media"]
_ROLES = ["technician", "scientist", "trainee", "service"]
_PROBE_RAWS = [303, 404, 507, 608]


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


class _Case:
    def __init__(self):
        self.instruments = list(_BASE_INSTRUMENTS)
        self.panels = list(_BASE_PANELS)
        self.operators = list(_BASE_OPERATORS)
        self.plates = []
        self.reads = []
        self.seq = 0
        self.state = {}
        self.wells = {}

    def baseline(self, instrument):
        for name, _model, value in self.instruments:
            if name == instrument:
                return value
        raise KeyError(instrument)

    def family(self, panel):
        for name, value, _replicates in self.panels:
            if name == panel:
                return value
        raise KeyError(panel)

    def plate(self, plate_id, instrument, panel, matrix, tier):
        self.plates.append((plate_id, instrument, panel, matrix, tier))
        self.state[plate_id] = {
            "blank": self.baseline(instrument),
            "drift": 0,
            "matrix": matrix,
            "family": self.family(panel),
            "tier": tier,
        }
        self.wells[plate_id] = 0
        return plate_id

    def _well(self, plate_id):
        index = self.wells[plate_id]
        self.wells[plate_id] = index + 1
        return "%s%02d" % ("ABCDEFGH"[index // 12], (index % 12) + 1)

    def read(self, plate_id, operator, action, raw, exposure):
        slot = self.state[plate_id]
        self.seq += 1
        self.reads.append({
            "seq": self.seq,
            "plate": plate_id,
            "well": self._well(plate_id),
            "operator": operator,
            "action": action,
            "raw": raw,
            "exposure": exposure,
        })
        if action == "blank":
            slot["blank"] = raw
        elif action == "recal":
            slot["drift"] = 0
        elif action == "measure":
            charge = exposure // 50
            if slot["tier"] == 3:
                charge = charge * 2
            drift = slot["drift"] + charge
            if drift > 90:
                drift = 90
            slot["drift"] = drift
        return self.seq

    def target(self, plate_id, operator, value, exposure, action="measure"):
        slot = self.state[plate_id]
        if slot["matrix"] != "buffer" or slot["family"] != "elisa":
            raise ValueError("target inversion is defined on a plain plate only")
        signal = value + slot["drift"]
        product = signal * exposure
        if product % 1000 != 0:
            raise ValueError("exposure %d cannot express signal %d exactly" % (exposure, signal))
        return self.read(plate_id, operator, action, slot["blank"] + product // 1000, exposure)

    def flat(self, plate_id, operator, action, exposure):
        return self.read(plate_id, operator, action, self.state[plate_id]["blank"], exposure)


def _spine(case):
    case.plate("PLT-01", "INS-A", "PNL-EL1", "buffer", 1)
    for value in (240, 239, 120, 119, 40, 39):
        case.target("PLT-01", "OP-01", value, 1000, "mask")
    case.target("PLT-01", "OP-01", 200, 1000)

    for plate_id, matrix in (
        ("PLT-02", "serum"),
        ("PLT-03", "plasma"),
        ("PLT-04", "lysate"),
        ("PLT-05", "saliva"),
        ("PLT-06", "urine"),
        ("PLT-07", "media"),
        ("PLT-08", "buffer"),
    ):
        case.plate(plate_id, "INS-A", "PNL-EL1", matrix, 1)
        for raw in _PROBE_RAWS:
            case.read(plate_id, "OP-01", "measure", raw, 1000)

    for plate_id, panel in (
        ("PLT-09", "PNL-PC1"),
        ("PLT-10", "PNL-TB1"),
        ("PLT-11", "PNL-FL1"),
        ("PLT-12", "PNL-EL2"),
        ("PLT-30", "PNL-PC2"),
        ("PLT-31", "PNL-FL2"),
    ):
        case.plate(plate_id, "INS-B", panel, "buffer", 1)
        for raw in _PROBE_RAWS:
            case.read(plate_id, "OP-01", "measure", raw - 40, 1000)

    case.plate("PLT-13", "INS-A", "PNL-EL2", "buffer", 1)
    case.target("PLT-13", "OP-01", 300, 2000)
    case.target("PLT-13", "OP-03", 100, 1000)
    case.flat("PLT-13", "OP-01", "recal", 1000)
    case.target("PLT-13", "OP-01", 300, 2050)
    case.target("PLT-13", "OP-03", 100, 1000)

    case.plate("PLT-14", "INS-A", "PNL-EL2", "buffer", 1)
    case.target("PLT-14", "OP-01", 200, 600)
    case.target("PLT-14", "OP-04", 100, 1000)
    case.flat("PLT-14", "OP-01", "recal", 1000)
    case.target("PLT-14", "OP-01", 200, 650)
    case.target("PLT-14", "OP-04", 100, 1000)

    case.plate("PLT-15", "INS-A", "PNL-EL2", "buffer", 1)
    case.target("PLT-15", "OP-05", 100, 1000)
    case.flat("PLT-15", "OP-01", "recal", 1000)
    case.target("PLT-15", "OP-01", 200, 50)
    case.target("PLT-15", "OP-05", 100, 1000)

    case.plate("PLT-16", "INS-A", "PNL-EL2", "buffer", 1)
    case.target("PLT-16", "OP-01", 300, 1250)
    case.target("PLT-16", "OP-02", 100, 1000)
    case.flat("PLT-16", "OP-01", "recal", 1000)
    case.target("PLT-16", "OP-01", 300, 1300)
    case.target("PLT-16", "OP-04", 100, 1000)

    case.plate("PLT-17", "INS-B", "PNL-EL2", "buffer", 1)
    for _step in range(3):
        case.flat("PLT-17", "OP-01", "measure", 1000)

    case.plate("PLT-18", "INS-B", "PNL-EL2", "buffer", 1)
    case.target("PLT-18", "OP-01", 300, 1550)

    case.plate("PLT-19", "INS-B", "PNL-EL2", "buffer", 1)
    case.target("PLT-19", "OP-01", 300, 1500)

    case.plate("PLT-20", "INS-B", "PNL-EL2", "buffer", 1)
    case.target("PLT-20", "OP-01", 300, 3000)
    case.target("PLT-20", "OP-01", 300, 3000)
    case.target("PLT-20", "OP-01", 100, 1000)

    case.plate("PLT-21", "INS-C", "PNL-EL2", "buffer", 3)
    case.target("PLT-21", "OP-01", 200, 1000)
    case.target("PLT-21", "OP-03", 100, 1000)

    case.plate("PLT-22", "INS-C", "PNL-EL2", "buffer", 2)
    case.target("PLT-22", "OP-01", 200, 1000)
    case.target("PLT-22", "OP-04", 100, 1000)

    case.plate("PLT-23", "INS-A", "PNL-EL2", "buffer", 1)
    case.flat("PLT-23", "OP-01", "recal", 1000)
    case.flat("PLT-23", "OP-01", "mask", 1000)
    case.target("PLT-23", "OP-01", 400, 1600)
    case.flat("PLT-23", "OP-01", "measure", 1000)
    case.target("PLT-23", "OP-01", 100, 1000)
    case.flat("PLT-23", "OP-02", "mask", 800)

    case.plate("PLT-24", "INS-A", "PNL-EL2", "buffer", 1)
    case.read("PLT-24", "OP-01", "blank", 150, 1000)
    case.target("PLT-24", "OP-01", 60, 1000)
    case.read("PLT-24", "OP-03", "blank", 220, 1000)
    case.target("PLT-24", "OP-01", 90, 1000)

    case.plate("PLT-25", "INS-A", "PNL-EL2", "buffer", 1)
    case.target("PLT-25", "OP-01", 150, 1000)
    case.target("PLT-25", "OP-01", 150, 1000)
    case.target("PLT-25", "OP-01", 100, 1000)

    for plate_id in ("PLT-26", "PLT-27"):
        case.plate(plate_id, "INS-A", "PNL-EL2", "buffer", 1)
        for value in (800, 880, 960, 1040):
            case.target(plate_id, "OP-02", value, 1000)

    case.plate("PLT-28", "INS-A", "PNL-EL1", "buffer", 1)
    case.read("PLT-28", "OP-01", "blank", 130, 1000)
    case.read("PLT-28", "OP-01", "mask", 300, 1000)

    case.plate("PLT-29", "INS-A", "PNL-EL1", "buffer", 1)
    for exposure in (500, 800, 1000, 2000, 2500):
        case.read("PLT-29", "OP-01", "mask", 300, exposure)

    case.plate("PLT-32", "INS-C", "PNL-EL2", "buffer", 2)
    case.flat("PLT-32", "OP-01", "measure", 1000)
    case.flat("PLT-32", "OP-05", "measure", 1200)
    case.target("PLT-32", "OP-01", 250, 1000)

    case.plate("PLT-33", "INS-C", "PNL-EL1", "serum", 1)
    case.read("PLT-33", "OP-02", "measure", 460, 900)
    case.read("PLT-33", "OP-04", "mask", 300, 1500)
    case.read("PLT-33", "OP-02", "measure", 520, 1100)

    case.plate("PLT-34", "INS-A", "PNL-EL2", "buffer", 1)
    for step in range(10):
        case.read("PLT-34", ("OP-01", "OP-03", "OP-04", "OP-05")[step % 4],
                  "measure", 500, 1000)

    case.plate("PLT-35", "INS-B", "PNL-EL2", "buffer", 1)
    for step in range(6):
        case.read("PLT-35", "OP-01", "measure" if step % 2 == 0 else "mask", 0, 1000)

    case.plate("PLT-36", "INS-B", "PNL-EL2", "buffer", 1)
    for _step in range(2):
        case.read("PLT-36", "OP-01", "measure", 0, 4000)

    case.plate("PLT-37", "INS-B", "PNL-EL2", "buffer", 1)
    case.read("PLT-37", "OP-01", "measure", 0, 4050)


def _extras(case, seed):
    rng = _Rng(seed ^ 0x5A17)
    for index in range(1 + rng.below(2)):
        case.instruments.append((
            "INS-%s" % chr(ord("P") + index),
            rng.pick(["halo", "vertex", "spindle"]),
            rng.between(40, 200),
        ))
    for index in range(1 + rng.below(3)):
        case.operators.append(("OP-%02d" % (20 + index), rng.pick(_ROLES)))

    instruments = [row[0] for row in case.instruments]
    panels = [row[0] for row in case.panels]
    operators = [row[0] for row in case.operators]
    for index in range(2 + rng.below(4)):
        plate_id = "PLT-%02d" % (40 + index)
        instrument = rng.pick(instruments)
        case.plate(plate_id, instrument, rng.pick(panels), rng.pick(_MATRICES), rng.between(1, 3))
        baseline = case.baseline(instrument)
        for _step in range(3 + rng.below(3)):
            case.read(
                plate_id,
                rng.pick(operators),
                rng.pick(["measure", "measure", "measure", "measure", "blank", "recal", "mask"]),
                baseline + rng.between(0, 300),
                50 * rng.between(20, 40),
            )


def build_case(seed, extra, keep=None, grow=0):
    case = _Case()
    _spine(case)
    if extra:
        _extras(case, seed)
    for index in range(grow):
        operator = "OP-%02d" % (30 + index)
        case.operators.append((operator, _ROLES[index % len(_ROLES)]))
        case.reads[-1 - index]["operator"] = operator
    if keep is not None:
        chosen = set(keep)
        case.plates = [row for row in case.plates if row[0] in chosen]
        case.reads = [row for row in case.reads if row["plate"] in chosen]
    return case


def _shuffled(reads, seed):
    order = list(reads)
    rng = _Rng(seed ^ 0x2C91)
    index = len(order) - 1
    while index > 0:
        swap = rng.below(index + 1)
        order[index], order[swap] = order[swap], order[index]
        index -= 1
    return order


def write_case(root, seed, mode, extra=True, keep=None, prefix="", grow=0):
    import json
    import os

    case = build_case(seed, extra, keep, grow)
    os.makedirs(root, exist_ok=True)

    def emit(name, text):
        with open(os.path.join(root, prefix + name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    lines = ["instrument,model,baseline"]
    for name, model, value in case.instruments:
        lines.append("%s,%s,%d" % (name, model, value))
    emit("instruments.csv", "\n".join(lines) + "\n")

    lines = ["panel,family,replicates"]
    for name, value, replicates in case.panels:
        lines.append("%s,%s,%d" % (name, value, replicates))
    emit("panels.csv", "\n".join(lines) + "\n")

    lines = ["operator,role"]
    for name, role in case.operators:
        lines.append("%s,%s" % (name, role))
    emit("operators.csv", "\n".join(lines) + "\n")

    lines = ["plate,instrument,panel,matrix,tier"]
    for plate_id, instrument, panel, matrix, tier in case.plates:
        lines.append("%s,%s,%s,%s,%d" % (plate_id, instrument, panel, matrix, tier))
    emit("plates.csv", "\n".join(lines) + "\n")

    parts = []
    for row in _shuffled(case.reads, seed):
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    emit("reads.jsonl", "".join(parts))

    header = {
        "run": "RUN-%d" % (seed % 1000000),
        "mode": mode,
        "declared_reads": len(case.reads),
        "plate_digests": {},
        "run_digest": "",
    }
    emit("manifest.json", json.dumps(header, sort_keys=True, indent=2) + "\n")

    readings, plate_rows, bench = resolve(load_corpus(root, prefix))
    header["plate_digests"] = {
        row[0]: plate_digest(readings, plate_rows, row[0]) for row in case.plates}
    header["run_digest"] = run_digest(readings, plate_rows, bench)
    emit("manifest.json", json.dumps(header, sort_keys=True, indent=2) + "\n")
    return case


APP_ROOT = os.environ.get("APP_ROOT", "/app")
OUT_DIR = os.path.join(APP_ROOT, "out")
SCRIPT = os.path.join(OUT_DIR, "triage.py")


def _bind(workspace):
    """Point OUT_DIR and SCRIPT at the rewardkit workspace (/app) for this run."""
    global OUT_DIR, SCRIPT
    OUT_DIR = os.path.join(str(workspace), "out")
    SCRIPT = os.path.join(OUT_DIR, "triage.py")


def _resolves(label, seed, mode, keep=None):
    """True when the delivered program reproduces the reference bytes for this run."""
    try:
        _matches(label, seed, mode, keep=keep)
        return True
    except Exception:
        return False

REPORTS = ("readings.jsonl", "plates.json", "bench.json")
RECORD_KEYS = ["action", "drift_before", "grade", "operator", "plate", "seq", "status", "value", "well"]
PLATE_KEYS = ["blank_end", "disposition", "drift_end", "grades", "measured", "peak", "plate",
              "reads", "rejects", "reviewed", "top_well", "value_total"]
BENCH_KEYS = ["by_grade", "by_status", "plates", "quarantined", "reads", "top_plate", "value_total"]

BASE_SEEDS = (6610011, 6610022)
BIT_SEEDS = (7710011, 7710022, 7710033, 7710044, 7710055, 7710066,
             7710077, 7710088, 7710099, 7710110, 7710121, 7710132)
EXCEPT_SEEDS = (8810011, 8810022, 8810033, 8810044, 8810055, 8810066)
FULL_SEEDS = (9910011, 9910022, 9910033, 9910044, 9910055, 9910066, 9910077, 9910088)
ALIAS_SEED = 9910099
ALIAS_GROWTH = 4
REPEAT_SEED = 4410011

MODE_BITS = [
    ("chain_blank", FLAG_CHAIN_BLANK),
    ("drift_echo", FLAG_DRIFT_ECHO),
    ("role_lookback", FLAG_ROLE_LOOKBACK),
    ("band_tier_shift", FLAG_BAND_TIER_SHIFT),
    ("exposure_floor", FLAG_EXPOSURE_FLOOR),
    ("panel_parity", FLAG_PANEL_PARITY),
    ("baseline_delta", FLAG_BASELINE_DELTA),
    ("exposure_order", FLAG_EXPOSURE_ORDER),
    ("mask_absolves", FLAG_MASK_ABSOLVES),
    ("count_bias", FLAG_COUNT_BIAS),
    ("matrix_alias", FLAG_MATRIX_ALIAS),
    ("quarantine_span", FLAG_QUARANTINE_SPAN),
]

_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}


def _inside_sandbox(path):
    resolved = os.path.realpath(path)
    return resolved != _TMP_ROOT and resolved.startswith(_TMP_ROOT + os.sep)


def _open_up(path):
    node = os.path.realpath(path)
    while _inside_sandbox(node):
        try:
            os.chmod(node, (os.stat(node).st_mode & 0o7777) | 0o111 | 0o044)
        except OSError:
            pass
        node = os.path.dirname(node)


def _grant_read(path):
    try:
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | 0o044)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    # start_new_session=True makes the child its own group leader, so its pid is the group id;
    # killing the group also reaps anything the program left running in the background.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    if proc.poll() is None:
        proc.kill()
        proc.wait()


def _launch(argv, scratch, budget=60):
    stdout_path = os.path.join(scratch, "stdout.txt")
    stderr_path = os.path.join(scratch, "stderr.txt")
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
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
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            raise AssertionError("the delivered program ran past its time budget")
        finally:
            _terminate(proc)
    with open(stderr_path, "rb") as handle:
        return code, handle.read().decode("utf-8", "replace")


def _run(label, seed, mode, extra=True, keep=None, grow=0):
    if label in _RUNS:
        return _RUNS[label]
    assert os.path.isfile(SCRIPT), "no reusable program was delivered"
    _open_up(SCRIPT)
    _grant_read(OUT_DIR)
    _grant_read(SCRIPT)
    work = tempfile.mkdtemp(prefix="apt-" + label + "-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    write_case(data, seed, mode, extra, keep, grow=grow)
    os.makedirs(out)
    os.makedirs(scratch)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    for name in os.listdir(data):
        os.chmod(os.path.join(data, name), 0o644)
    code, err = _launch([sys.executable, SCRIPT, data, out], scratch)
    _RUNS[label] = (data, out, scratch, code, err)
    return _RUNS[label]


def _expected(data):
    readings, plate_rows, bench = derive(data)
    return {
        "readings.jsonl": render_readings(readings),
        "plates.json": render_document({"plates": plate_rows}),
        "bench.json": render_document(bench),
    }


def _artifact(out, name):
    path = os.path.join(out, name)
    assert os.path.isfile(path), "the program wrote no %s" % name
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def _matches(label, seed, mode, names=REPORTS, extra=True, keep=None):
    data, out, _scratch, code, err = _run(label, seed, mode, extra, keep)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    expected = _expected(data)
    for name in names:
        assert _artifact(out, name) == expected[name], "%s disagrees on %s" % (name, label)


def _delivered_source():
    assert os.path.isfile(SCRIPT), "no reusable program was delivered"
    _grant_read(SCRIPT)
    with open(SCRIPT, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


@criterion(description="the reusable program sits at the requested path and parses as Python source")
def reusable_program_is_delivered(workspace):
    _bind(workspace)
    try:
        source = _delivered_source()
        if not source.strip():
            return False
        ast.parse(source)
        return True
    except Exception:
        return False


@criterion(description="a run whose mode word is clear resolves exactly like the worked example runs")
def untrapped_run_alpha_resolves(workspace):
    _bind(workspace)
    return _resolves("base-a", BASE_SEEDS[0], 0)


@criterion(description="a second run whose mode word is clear resolves through the base chain")
def untrapped_run_beta_resolves(workspace):
    _bind(workspace)
    return _resolves("base-b", BASE_SEEDS[1], 0)


@criterion(description="a run carrying only the first mode bit resolves exactly")
def mode_bit_chain_blank(workspace):
    _bind(workspace)
    return _resolves("bit-00", BIT_SEEDS[0], MODE_BITS[0][1])


@criterion(description="a run carrying only the second mode bit resolves exactly")
def mode_bit_drift_echo(workspace):
    _bind(workspace)
    return _resolves("bit-01", BIT_SEEDS[1], MODE_BITS[1][1])


@criterion(description="a run carrying only the third mode bit resolves exactly")
def mode_bit_role_lookback(workspace):
    _bind(workspace)
    return _resolves("bit-02", BIT_SEEDS[2], MODE_BITS[2][1])


@criterion(description="a run carrying only the fourth mode bit resolves exactly")
def mode_bit_band_tier_shift(workspace):
    _bind(workspace)
    return _resolves("bit-03", BIT_SEEDS[3], MODE_BITS[3][1])


@criterion(description="a run carrying only the fifth mode bit resolves exactly")
def mode_bit_exposure_floor(workspace):
    _bind(workspace)
    return _resolves("bit-04", BIT_SEEDS[4], MODE_BITS[4][1])


@criterion(description="a run carrying only the sixth mode bit resolves exactly")
def mode_bit_panel_parity(workspace):
    _bind(workspace)
    return _resolves("bit-05", BIT_SEEDS[5], MODE_BITS[5][1])


@criterion(description="a run carrying only the seventh mode bit resolves exactly")
def mode_bit_baseline_delta(workspace):
    _bind(workspace)
    return _resolves("bit-06", BIT_SEEDS[6], MODE_BITS[6][1])


@criterion(description="a run carrying only the eighth mode bit resolves exactly")
def mode_bit_exposure_order(workspace):
    _bind(workspace)
    return _resolves("bit-07", BIT_SEEDS[7], MODE_BITS[7][1])


@criterion(description="a run carrying only the ninth mode bit resolves exactly")
def mode_bit_mask_absolves(workspace):
    _bind(workspace)
    return _resolves("bit-08", BIT_SEEDS[8], MODE_BITS[8][1])


@criterion(description="a run carrying only the tenth mode bit resolves exactly")
def mode_bit_count_bias(workspace):
    _bind(workspace)
    return _resolves("bit-09", BIT_SEEDS[9], MODE_BITS[9][1])


@criterion(description="a run carrying only the eleventh mode bit resolves exactly")
def mode_bit_matrix_alias(workspace):
    _bind(workspace)
    return _resolves("bit-10", BIT_SEEDS[10], MODE_BITS[10][1])


@criterion(description="a run carrying only the twelfth mode bit resolves exactly")
def mode_bit_quarantine_span(workspace):
    _bind(workspace)
    return _resolves("bit-11", BIT_SEEDS[11], MODE_BITS[11][1])


@criterion(description="a run carrying every mode bit apart from the first resolves exactly")
def every_bit_except_chain_blank(workspace):
    _bind(workspace)
    return _resolves("except-00", EXCEPT_SEEDS[0], ALL_FLAGS & ~MODE_BITS[0][1])


@criterion(description="a run carrying every mode bit apart from the third resolves exactly")
def every_bit_except_role_lookback(workspace):
    _bind(workspace)
    return _resolves("except-02", EXCEPT_SEEDS[1], ALL_FLAGS & ~MODE_BITS[2][1])


@criterion(description="a run carrying every mode bit apart from the fifth resolves exactly")
def every_bit_except_exposure_floor(workspace):
    _bind(workspace)
    return _resolves("except-04", EXCEPT_SEEDS[2], ALL_FLAGS & ~MODE_BITS[4][1])


@criterion(description="a run carrying every mode bit apart from the seventh resolves exactly")
def every_bit_except_baseline_delta(workspace):
    _bind(workspace)
    return _resolves("except-06", EXCEPT_SEEDS[3], ALL_FLAGS & ~MODE_BITS[6][1])


@criterion(description="a run carrying every mode bit apart from the ninth resolves exactly")
def every_bit_except_mask_absolves(workspace):
    _bind(workspace)
    return _resolves("except-08", EXCEPT_SEEDS[4], ALL_FLAGS & ~MODE_BITS[8][1])


@criterion(description="a run carrying every mode bit apart from the eleventh resolves exactly")
def every_bit_except_matrix_alias(workspace):
    _bind(workspace)
    return _resolves("except-10", EXCEPT_SEEDS[5], ALL_FLAGS & ~MODE_BITS[10][1])


@criterion(description="a run carrying every mode bit resolves exactly")
def full_mode_run_alpha(workspace):
    _bind(workspace)
    return _resolves("full-a", FULL_SEEDS[0], ALL_FLAGS)


@criterion(description="a second run carrying every mode bit resolves exactly")
def full_mode_run_beta(workspace):
    _bind(workspace)
    return _resolves("full-b", FULL_SEEDS[1], ALL_FLAGS)


@criterion(description="a third run carrying every mode bit resolves exactly")
def full_mode_run_gamma(workspace):
    _bind(workspace)
    return _resolves("full-c", FULL_SEEDS[2], ALL_FLAGS)


@criterion(description="a fourth run carrying every mode bit resolves exactly")
def full_mode_run_delta(workspace):
    _bind(workspace)
    return _resolves("full-d", FULL_SEEDS[3], ALL_FLAGS)


@criterion(description="a fifth run carrying every mode bit resolves exactly")
def full_mode_run_epsilon(workspace):
    _bind(workspace)
    return _resolves("full-e", FULL_SEEDS[4], ALL_FLAGS)


@criterion(description="a sixth run carrying every mode bit resolves exactly")
def full_mode_run_zeta(workspace):
    _bind(workspace)
    return _resolves("full-f", FULL_SEEDS[5], ALL_FLAGS)


@criterion(description="a seventh run carrying every mode bit resolves exactly")
def full_mode_run_eta(workspace):
    _bind(workspace)
    return _resolves("full-g", FULL_SEEDS[6], ALL_FLAGS)


@criterion(description="an eighth run carrying every mode bit resolves exactly")
def full_mode_run_theta(workspace):
    _bind(workspace)
    return _resolves("full-h", FULL_SEEDS[7], ALL_FLAGS)


@criterion(description="a full mode run whose operator table is larger than that of any other graded run resolves exactly")
def full_mode_run_with_a_grown_operator_table(workspace):
    _bind(workspace)
    try:
        data, out, _scratch, code, err = _run("alias", ALIAS_SEED, ALL_FLAGS, grow=ALIAS_GROWTH)
        if code != 0:
            return False
        corpus = load_corpus(data)
        if not len(corpus["operators"]) > 8:
            return False
        expected = _expected(data)
        for name in REPORTS:
            if _artifact(out, name) != expected[name]:
                return False
        return True
    except Exception:
        return False


@criterion(description="the delivered program carries the shipped run's plate identifiers as literal answers")
def negative_hardcoded_sample_answers(workspace):
    _bind(workspace)
    # True marks the forbidden behaviour: the program carries the shipped run's plate identifiers as literals.
    try:
        source = _delivered_source()
        shipped = sorted({row[0] for row in build_case(SAMPLE_SEED, False).plates})
        literals = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.append(node.value)
        blob = "\n".join(literals)
        return sum(1 for name in shipped if name in blob) >= 5
    except Exception:
        return False


@criterion(description="the delivered program pulls in a module outside the standard library")
def negative_third_party_dependency(workspace):
    _bind(workspace)
    # True marks the forbidden behaviour: the program imports a module outside the Python standard library.
    try:
        tree = ast.parse(_delivered_source())
        wanted = set()
        for node in ast.walk(tree):
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
    except Exception:
        return False


@criterion(description="repeated runs of the delivered program over one input write differing bytes")
def negative_nondeterministic_output(workspace):
    _bind(workspace)
    # True marks the forbidden behaviour: two runs over one input wrote differing bytes.
    try:
        _data, out, scratch, code, err = _run("repeat", REPEAT_SEED, ALL_FLAGS)
        if code != 0:
            return False
        data = os.path.join(os.path.dirname(out), "data")
        first = {name: _artifact(out, name) for name in REPORTS}
        drifted = False
        for _attempt in range(4):
            again, _err = _launch([sys.executable, SCRIPT, data, out], scratch)
            if again != 0:
                drifted = True
                break
            for name, body in first.items():
                if _artifact(out, name) != body:
                    drifted = True
        return drifted
    except Exception:
        return False


criteria.reusable_program_is_delivered(weight=1)
criteria.untrapped_run_alpha_resolves(weight=1)
criteria.untrapped_run_beta_resolves(weight=1)
criteria.mode_bit_chain_blank(weight=1)
criteria.mode_bit_drift_echo(weight=1)
criteria.mode_bit_role_lookback(weight=1)
criteria.mode_bit_band_tier_shift(weight=1)
criteria.mode_bit_exposure_floor(weight=1)
criteria.mode_bit_panel_parity(weight=1)
criteria.mode_bit_baseline_delta(weight=1)
criteria.mode_bit_exposure_order(weight=1)
criteria.mode_bit_mask_absolves(weight=1)
criteria.mode_bit_count_bias(weight=1)
criteria.mode_bit_matrix_alias(weight=1)
criteria.mode_bit_quarantine_span(weight=1)
criteria.every_bit_except_chain_blank(weight=5)
criteria.every_bit_except_role_lookback(weight=5)
criteria.every_bit_except_exposure_floor(weight=5)
criteria.every_bit_except_baseline_delta(weight=5)
criteria.every_bit_except_mask_absolves(weight=5)
criteria.every_bit_except_matrix_alias(weight=5)
criteria.full_mode_run_alpha(weight=5)
criteria.full_mode_run_beta(weight=5)
criteria.full_mode_run_gamma(weight=5)
criteria.full_mode_run_delta(weight=5)
criteria.full_mode_run_epsilon(weight=5)
criteria.full_mode_run_zeta(weight=5)
criteria.full_mode_run_eta(weight=5)
criteria.full_mode_run_theta(weight=5)
criteria.full_mode_run_with_a_grown_operator_table(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
