#!/usr/bin/env python3
"""The plate triage engine.

Reads a bench run out of an input directory and writes the three reports
(readings.jsonl, plates.json, bench.json) into an output directory.

Usage: triage.py INPUT_DIR OUTPUT_DIR

The run's mode word is read from manifest.json in the input directory and
honoured.  Mode zero is the plain chain; every mode bit switches on a single
alteration somewhere in that chain.
"""
import csv
import hashlib
import json
import os
import sys

# ---------------------------------------------------------------- firmware

GAIN = 1000

MATRIX_ORDER = ("buffer", "serum", "plasma", "lysate", "saliva", "urine", "media")
FAMILY_ORDER = ("elisa", "pcr", "turbidity", "fluor")
ROLE_ORDER = ("technician", "scientist", "trainee", "service")
GRADES = ("high", "low", "mid", "trace")
STATUSES = ("masked", "ok", "reject", "review", "setup")

# matrix adjustments; buffer is the matrix that leaves the figure alone
MATRIX_ADJ = {
    "buffer": ("none", 0),
    "serum": ("add", -4),
    "plasma": ("scale", (3, 4)),
    "lysate": ("add", 6),
    "saliva": ("scale", (1, 2)),
    "urine": ("snap", 5),
    "media": ("scale", (5, 4)),
}

# panel adjustments; elisa is the family that leaves the figure alone
PANEL_ADJ = {
    "elisa": ("none", 0),
    "pcr": ("scale", (9, 10)),
    "turbidity": ("add", 12),
    "fluor": ("scale", (7, 5)),
}

BAND_HIGH = 240
BAND_MID = 120
BAND_LOW = 40

ROLE_TOLERANCE = {"technician": 25, "scientist": 40, "trainee": 12, "service": 0}

DRIFT_CHARGE_DIVISOR = 50
DRIFT_TIER = "3"            # the tier whose measure reads charge double
DRIFT_TIER_FACTOR = 2
DRIFT_CEILING = 90

COUNTED_STATUSES = ("ok", "review")
QUARANTINE_STRIKES = 3
HOLD_DRIFT = 30

# ------------------------------------------------------------------- mode
# Twelve bits, taken in the order of the chain they alter.  Only the bits
# listed here carry an alteration this build knows how to honour; the rest are
# accepted and left inert.
BIT_WALK_SHORT = 0x001      # the walk stops one read short of the run's end


def bit(mode, flag):
    return bool(mode & flag)


# ------------------------------------------------------------------ inputs

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_run(indir):
    def path(name):
        return os.path.join(indir, name)

    with open(path("manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    instruments = {r["instrument"]: r for r in read_csv(path("instruments.csv"))}
    panels = {r["panel"]: r for r in read_csv(path("panels.csv"))}
    operators = {r["operator"]: r for r in read_csv(path("operators.csv"))}
    plates = {r["plate"]: r for r in read_csv(path("plates.csv"))}
    reads = []
    with open(path("reads.jsonl"), encoding="utf-8") as fh:
        for raw_line in fh:
            if raw_line.strip():
                reads.append(json.loads(raw_line))
    return manifest, instruments, panels, operators, plates, reads


# ------------------------------------------------------------------- chain

def clamp(figure):
    return figure if figure > 0 else 0


def adjust(spec, figure):
    kind, arg = spec
    if kind == "none":
        return figure
    if kind == "add":
        return figure + arg
    if kind == "scale":
        return figure * arg[0] // arg[1]
    if kind == "snap":
        return figure // arg * arg
    raise ValueError(kind)


def grade_of(value):
    if value >= BAND_HIGH:
        return "high"
    if value >= BAND_MID:
        return "mid"
    if value >= BAND_LOW:
        return "low"
    return "trace"


def drift_charge(exposure, tier):
    charge = exposure // DRIFT_CHARGE_DIVISOR
    if tier == DRIFT_TIER:
        charge *= DRIFT_TIER_FACTOR
    return charge


def walk_order(reads, mode):
    order = sorted(reads, key=lambda r: r["seq"])
    if bit(mode, BIT_WALK_SHORT) and order:
        order = order[:-1]
    return order


def resolve(instruments, panels, operators, plates, reads, mode):
    state = {}
    for name, plate in plates.items():
        state[name] = {
            "blank": int(instruments[plate["instrument"]]["baseline"]),
            "drift": 0,
            "strikes": 0,
        }
    readings = []
    for read in walk_order(reads, mode):
        plate = plates[read["plate"]]
        carried = state[read["plate"]]
        matrix = plate["matrix"]
        family = panels[plate["panel"]]["family"]
        tier = plate["tier"]
        role = operators[read["operator"]]["role"]

        figure = clamp(read["raw"] - carried["blank"])
        figure = clamp(figure * GAIN // read["exposure"])
        figure = clamp(adjust(MATRIX_ADJ[matrix], figure))
        figure = clamp(adjust(PANEL_ADJ[family], figure))

        drift_before = carried["drift"]
        value = clamp(figure - drift_before)
        grade = grade_of(value)

        action = read["action"]
        if action in ("blank", "recal"):
            status = "setup"
        elif action == "mask":
            status = "masked"
        elif grade == "trace":
            status = "reject"
        elif drift_before > ROLE_TOLERANCE[role]:
            status = "review"
        else:
            status = "ok"

        readings.append({
            "action": action,
            "drift_before": drift_before,
            "grade": grade,
            "operator": read["operator"],
            "plate": read["plate"],
            "seq": read["seq"],
            "status": status,
            "value": value,
            "well": read["well"],
        })

        if action == "blank":
            carried["blank"] = read["raw"]
        elif action == "recal":
            carried["drift"] = 0
        elif action == "measure":
            drift = carried["drift"] + drift_charge(read["exposure"], tier)
            carried["drift"] = min(drift, DRIFT_CEILING)
        if status == "reject":
            carried["strikes"] += 1
    return readings, state


# ----------------------------------------------------------------- rollups

def plate_rows(plates, readings, state, mode):
    mine = {name: [] for name in plates}
    for record in readings:
        mine[record["plate"]].append(record)
    rows = []
    for name in sorted(plates):
        records = mine[name]
        carried = state[name]
        counted = [r for r in records if r["status"] in COUNTED_STATUSES]
        peak = 0
        top_well = None
        for record in counted:
            if top_well is None or record["value"] >= peak:
                peak = record["value"]
                top_well = record["well"]
        grades = {g: 0 for g in GRADES}
        for record in records:
            grades[record["grade"]] += 1
        strikes = carried["strikes"]
        drift_end = carried["drift"]
        if strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif drift_end > HOLD_DRIFT:
            disposition = "hold"
        else:
            disposition = "release"
        rows.append({
            "blank_end": carried["blank"],
            "disposition": disposition,
            "drift_end": drift_end,
            "grades": grades,
            "measured": sum(1 for r in records if r["action"] == "measure"),
            "peak": peak,
            "plate": name,
            "reads": len(records),
            "rejects": strikes,
            "reviewed": sum(1 for r in records if r["status"] == "review"),
            "top_well": top_well,
            "value_total": sum(r["value"] for r in counted),
        })
    return rows


def bench_row(rows, readings, mode):
    by_grade = {g: 0 for g in GRADES}
    by_status = {s: 0 for s in STATUSES}
    for record in readings:
        by_grade[record["grade"]] += 1
        by_status[record["status"]] += 1
    top_plate = None
    best = -1
    for row in rows:
        if row["value_total"] > best:
            best = row["value_total"]
            top_plate = row["plate"]
    return {
        "by_grade": by_grade,
        "by_status": by_status,
        "plates": len(rows),
        "quarantined": sorted(r["plate"] for r in rows if r["disposition"] == "quarantine"),
        "reads": len(readings),
        "top_plate": top_plate,
        "value_total": sum(r["value_total"] for r in rows),
    }


# ------------------------------------------------------------------ output

def readings_text(readings):
    return "".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in readings)


def document_text(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def plate_digests(readings, rows):
    digests = {}
    for row in rows:
        text = readings_text([r for r in readings if r["plate"] == row["plate"]])
        text += document_text(row)
        digests[row["plate"]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digests


def run_digest(readings, plates_doc, bench):
    text = readings_text(readings) + document_text(plates_doc) + document_text(bench)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def triage(indir):
    manifest, instruments, panels, operators, plates, reads = load_run(indir)
    mode = int(manifest["mode"])
    readings, state = resolve(instruments, panels, operators, plates, reads, mode)
    rows = plate_rows(plates, readings, state, mode)
    plates_doc = {"plates": rows}
    bench = bench_row(rows, readings, mode)
    return readings, plates_doc, bench


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: triage.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    indir, outdir = argv[1], argv[2]
    readings, plates_doc, bench = triage(indir)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "readings.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(readings_text(readings))
    with open(os.path.join(outdir, "plates.json"), "w", encoding="utf-8") as fh:
        fh.write(document_text(plates_doc))
    with open(os.path.join(outdir, "bench.json"), "w", encoding="utf-8") as fh:
        fh.write(document_text(bench))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
