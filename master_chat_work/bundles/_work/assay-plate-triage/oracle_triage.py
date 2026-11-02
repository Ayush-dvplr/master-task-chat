#!/usr/bin/env python3
"""Plate triage engine: resolves one bench run into its three reports."""

import csv
import hashlib
import json
import os
import sys

# Mode bit owned by each alteration, as settled from the shipped digests.
ALTERATION_BITS = {
    'inherit_blank': 0x001,
    'deferred_charge': 0x002,
    'prior_operator_role': 0x004,
    'tier_band_lift': 0x008,
    'min_exposure': 0x010,
    'odd_replicates_elisa': 0x020,
    'island_offset': 0x040,
    'exposure_walk': 0x080,
    'mask_forgives': 0x100,
    'tail_trim': 0x200,
    'matrix_rotation': 0x400,
    'neighbour_strikes': 0x800,
}

MATRICES = ("buffer", "serum", "plasma", "lysate", "saliva", "urine", "media")
GAIN = 1000
MATRIX_RULES = {
    "serum": lambda figure: figure - 4,
    "plasma": lambda figure: figure * 3 // 4,
    "lysate": lambda figure: figure + 6,
    "saliva": lambda figure: figure // 2,
    "urine": lambda figure: figure - figure % 5,
    "media": lambda figure: figure * 5 // 4,
}
FAMILY_RULES = {
    "pcr": lambda figure: figure * 9 // 10,
    "turbidity": lambda figure: figure + 12,
    "fluor": lambda figure: figure * 7 // 5,
}
BANDS = (("high", 240), ("mid", 120), ("low", 40))
ROLE_TOLERANCE = {"technician": 25, "scientist": 40, "trainee": 12, "service": 0}
CHARGE_STEP = 50
DOUBLED_TIER = 3
DRIFT_CEILING = 90
HOLD_DRIFT = 30
QUARANTINE_AT = 3
TIER_LIFT = 15
COUNTED_STATUSES = ("ok", "review")
SETUP_ACTIONS = ("blank", "recal")
GRADE_KEYS = ("high", "low", "mid", "trace")
STATUS_KEYS = ("masked", "ok", "reject", "review", "setup")


class RunInputError(Exception):
    """Raised when an input directory does not hold a readable run."""


def _table(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_run(directory, prefix=""):
    """Load the six files of one run into plain dictionaries."""
    def named(name):
        return os.path.join(directory, prefix + name)

    try:
        with open(named("manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        run = {
            "mode": int(manifest["mode"]),
            "baselines": {
                row["instrument"]: int(row["baseline"])
                for row in _table(named("instruments.csv"))
            },
            "panels": {
                row["panel"]: (row["family"], int(row["replicates"]))
                for row in _table(named("panels.csv"))
            },
            "roles": {row["operator"]: row["role"] for row in _table(named("operators.csv"))},
            "plates": {
                row["plate"]: {
                    "instrument": row["instrument"],
                    "panel": row["panel"],
                    "matrix": row["matrix"],
                    "tier": int(row["tier"]),
                }
                for row in _table(named("plates.csv"))
            },
        }
        reads = []
        with open(named("reads.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    for field in ("seq", "raw", "exposure"):
                        record[field] = int(record[field])
                    reads.append(record)
    except (OSError, KeyError, ValueError) as problem:
        raise RunInputError("cannot read the run in %s: %s" % (directory, problem)) from problem
    run["reads"] = reads
    return run


def active_alterations(mode):
    return frozenset(name for name, bit in ALTERATION_BITS.items() if mode & bit)


class PlateState:
    """What one plate carries from read to read."""

    def __init__(self, blank_level, predecessor):
        self.blank_level = blank_level
        self.drift = 0
        self.strikes = 0
        self.deferred_charge = 0
        self.last_operator = None
        self.predecessor = predecessor


def instrument_baselines(run, active):
    baselines = dict(run["baselines"])
    in_use = sorted({plate["instrument"] for plate in run["plates"].values()})
    if "island_offset" in active and len(baselines) > 1 and in_use:
        island = in_use[-1]
        rest = [level for name, level in baselines.items() if name != island]
        if rest:
            baselines[island] += min(rest)
    return baselines


def walk_order(run, active):
    walk = sorted(run["reads"], key=lambda record: record["seq"])
    if "tail_trim" in active:
        walk = walk[:max(0, len(walk) - (1 + len(run["plates"]) % 4))]
    if "exposure_walk" in active:
        walk.sort(key=lambda record: (record["exposure"], record["seq"]))
    return walk


def effective_matrix(plate, operator_count, active):
    written = plate["matrix"]
    if "matrix_rotation" not in active or written not in MATRICES:
        return written
    step = MATRICES.index(written) + plate["tier"] + operator_count
    return MATRICES[step % len(MATRICES)]


def effective_family(panel, active):
    family, replicates = panel
    if "odd_replicates_elisa" in active and replicates % 2:
        return "elisa"
    return family


def band_of(value, lift):
    for name, edge in BANDS:
        if value >= edge + lift:
            return name
    return "trace"


def status_of(action, grade, drift_before, role):
    if action in SETUP_ACTIONS:
        return "setup"
    if action == "mask":
        return "masked"
    if grade == "trace":
        return "reject"
    if drift_before > ROLE_TOLERANCE.get(role, ROLE_TOLERANCE["technician"]):
        return "review"
    return "ok"


def score_read(record, state, plate, matrix, family, exposure, lift, role):
    """Run one read through stages one to seven and return its reading row."""
    figure = max(0, record["raw"] - state.blank_level) * GAIN // exposure
    figure = max(0, MATRIX_RULES.get(matrix, int)(figure))
    figure = max(0, FAMILY_RULES.get(family, int)(figure))
    drift_before = state.drift
    value = max(0, figure - drift_before)
    grade = band_of(value, lift)
    return {
        "action": record["action"],
        "drift_before": drift_before,
        "grade": grade,
        "operator": record["operator"],
        "plate": record["plate"],
        "seq": record["seq"],
        "status": status_of(record["action"], grade, drift_before, role),
        "value": value,
        "well": record["well"],
    }


def carry_forward(record, reading, state, tier, active):
    """Stage eight: move the plate state on after a reading is emitted."""
    if reading["status"] == "reject":
        state.strikes += 1
    if record["action"] == "mask" and "mask_forgives" in active and state.strikes:
        state.strikes -= 1
    state.last_operator = record["operator"]

    charge = 0
    if record["action"] == "measure":
        charge = record["exposure"] // CHARGE_STEP * (2 if tier == DOUBLED_TIER else 1)
    if "deferred_charge" in active:
        charge, state.deferred_charge = state.deferred_charge, charge
    if record["action"] == "blank":
        state.blank_level = record["raw"]
    elif record["action"] == "recal":
        state.drift = 0
        state.deferred_charge = 0
        charge = 0
    state.drift = min(DRIFT_CEILING, state.drift + charge)


def resolve(run, active):
    """Resolve a run under a set of alteration names; return the three reports."""
    plates = run["plates"]
    roles = run["roles"]
    baselines = instrument_baselines(run, active)
    walk = walk_order(run, active)

    lowest_exposure = {}
    for record in walk:
        known = lowest_exposure.get(record["plate"], record["exposure"])
        lowest_exposure[record["plate"]] = min(known, record["exposure"])

    states = {}
    newest_on = {}
    readings = []
    for record in walk:
        plate_id = record["plate"]
        plate = plates[plate_id]
        reader = plate["instrument"]
        if plate_id not in states:
            predecessor = newest_on.get(reader)
            blank_level = baselines[reader]
            if "inherit_blank" in active and predecessor is not None:
                blank_level = states[predecessor].blank_level
            states[plate_id] = PlateState(blank_level, predecessor)
            newest_on[reader] = plate_id
        state = states[plate_id]

        role = roles[record["operator"]]
        if "prior_operator_role" in active and state.last_operator is not None:
            role = roles[state.last_operator]
        exposure = record["exposure"]
        if "min_exposure" in active:
            exposure = lowest_exposure[plate_id]
        lift = plate["tier"] * TIER_LIFT if "tier_band_lift" in active else 0

        reading = score_read(
            record,
            state,
            plate,
            effective_matrix(plate, len(roles), active),
            effective_family(run["panels"][plate["panel"]], active),
            exposure,
            lift,
            role,
        )
        readings.append(reading)
        carry_forward(record, reading, state, plate["tier"], active)

    plate_rows = [
        summarise_plate(plate_id, readings, states, baselines[plates[plate_id]["instrument"]], active)
        for plate_id in sorted(plates)
    ]
    return readings, plate_rows, summarise_bench(readings, plate_rows)


def summarise_plate(plate_id, readings, states, baseline, active):
    own = [reading for reading in readings if reading["plate"] == plate_id]
    counted = [reading for reading in own if reading["status"] in COUNTED_STATUSES]
    state = states.get(plate_id)
    strikes = state.strikes if state else 0
    drift_end = state.drift if state else 0
    weighed = strikes
    if "neighbour_strikes" in active and state and state.predecessor is not None:
        weighed += states[state.predecessor].strikes
    if weighed >= QUARANTINE_AT:
        disposition = "quarantine"
    elif drift_end > HOLD_DRIFT:
        disposition = "hold"
    else:
        disposition = "release"
    top = max(counted, key=lambda reading: (reading["value"], reading["seq"]), default=None)
    grades = dict.fromkeys(GRADE_KEYS, 0)
    for reading in own:
        grades[reading["grade"]] += 1
    return {
        "blank_end": state.blank_level if state else baseline,
        "disposition": disposition,
        "drift_end": drift_end,
        "grades": grades,
        "measured": sum(reading["action"] == "measure" for reading in own),
        "peak": max([0] + [reading["value"] for reading in counted]),
        "plate": plate_id,
        "reads": len(own),
        "rejects": strikes,
        "reviewed": sum(reading["status"] == "review" for reading in own),
        "top_well": top["well"] if top else None,
        "value_total": sum(reading["value"] for reading in counted),
    }


def summarise_bench(readings, plate_rows):
    by_grade = dict.fromkeys(GRADE_KEYS, 0)
    by_status = dict.fromkeys(STATUS_KEYS, 0)
    for reading in readings:
        by_grade[reading["grade"]] += 1
        by_status[reading["status"]] += 1
    leader = None
    for row in plate_rows:
        if leader is None or row["value_total"] > leader["value_total"]:
            leader = row
    return {
        "by_grade": by_grade,
        "by_status": by_status,
        "plates": len(plate_rows),
        "quarantined": sorted(row["plate"] for row in plate_rows if row["disposition"] == "quarantine"),
        "reads": len(readings),
        "top_plate": leader["plate"] if leader else None,
        "value_total": sum(row["value_total"] for row in plate_rows),
    }


def lines_text(readings):
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in readings)


def document_text(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def report_texts(readings, plate_rows, bench):
    return {
        "readings.jsonl": lines_text(readings),
        "plates.json": document_text({"plates": plate_rows}),
        "bench.json": document_text(bench),
    }


def digests(readings, plate_rows, bench):
    """Per plate digests and the run digest, as reports.md defines them."""
    per_plate = {}
    for row in plate_rows:
        own = [reading for reading in readings if reading["plate"] == row["plate"]]
        body = lines_text(own) + document_text(row)
        per_plate[row["plate"]] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    texts = report_texts(readings, plate_rows, bench)
    whole = texts["readings.jsonl"] + texts["plates.json"] + texts["bench.json"]
    return per_plate, hashlib.sha256(whole.encode("utf-8")).hexdigest()


def main(argv):
    if len(argv) != 2:
        print("usage: triage.py INPUT_DIR OUTPUT_DIR", file=sys.stderr)
        return 2
    source, target = argv
    try:
        run = read_run(source)
    except RunInputError as problem:
        print(problem, file=sys.stderr)
        return 1
    texts = report_texts(*resolve(run, active_alterations(run["mode"])))
    os.makedirs(target, exist_ok=True)
    for name, text in texts.items():
        with open(os.path.join(target, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
