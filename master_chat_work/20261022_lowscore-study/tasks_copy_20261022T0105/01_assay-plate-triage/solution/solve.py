#!/usr/bin/env python3
"""Reference solve for assay-plate-triage.

Written against the contract in data/engine.md and data/reports.md rather than
against tests/test_output.py, so that an oracle run is evidence the task is
solvable instead of a restatement of the verifier. The engine below is emitted
verbatim to /app/out/triage.py and then re-imported here to cross-check the
files it wrote and to fold the closing figures.
"""

import json
import pathlib
import subprocess
import sys

ENGINE = r'''#!/usr/bin/env python3
import csv
import hashlib
import json
import pathlib
import sys

BIT_CHAIN_BLANK = 1 << 0
BIT_DRIFT_ECHO = 1 << 1
BIT_ROLE_LOOKBACK = 1 << 2
BIT_BAND_TIER_SHIFT = 1 << 3
BIT_EXPOSURE_FLOOR = 1 << 4
BIT_PANEL_PARITY = 1 << 5
BIT_BASELINE_DELTA = 1 << 6
BIT_EXPOSURE_ORDER = 1 << 7
BIT_MASK_ABSOLVES = 1 << 8
BIT_COUNT_BIAS = 1 << 9
BIT_MATRIX_ALIAS = 1 << 10
BIT_QUARANTINE_SPAN = 1 << 11

MATRIX_WHEEL = ("buffer", "serum", "plasma", "lysate", "saliva", "urine", "media")

MATRIX_STEP = {
    "serum": lambda n: n - 4,
    "plasma": lambda n: n * 3 // 4,
    "lysate": lambda n: n + 6,
    "saliva": lambda n: n // 2,
    "urine": lambda n: n - (n % 5),
    "media": lambda n: n * 5 // 4,
}

FAMILY_STEP = {
    "pcr": lambda n: n * 9 // 10,
    "turbidity": lambda n: n + 12,
    "fluor": lambda n: n * 7 // 5,
}

GRADE_FLOORS = (("high", 240), ("mid", 120), ("low", 40))

ROLE_ALLOWANCE = {"scientist": 40, "trainee": 12, "service": 0}
DEFAULT_ALLOWANCE = 25

SETUP_ACTIONS = ("blank", "recal")
DRIFT_CAP = 90
HOLD_ABOVE = 30
QUARANTINE_STRIKES = 3
GRADE_KEYS = ("high", "low", "mid", "trace")
STATUS_KEYS = ("masked", "ok", "reject", "review", "setup")
COUNTED = ("ok", "review")


def _table(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return list(csv.DictReader(text.splitlines()))


def _records(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def load_run(data_dir, prefix=""):
    root = pathlib.Path(data_dir)

    def at(stem):
        return root / (prefix + stem)

    manifest = json.loads(at("manifest.json").read_text(encoding="utf-8"))
    rigs = {
        r["instrument"]: {"model": r["model"], "baseline": int(r["baseline"])}
        for r in _table(at("instruments.csv"))
    }
    assays = {
        r["panel"]: {"family": r["family"], "replicates": int(r["replicates"])}
        for r in _table(at("panels.csv"))
    }
    staff = {r["operator"]: {"role": r["role"]} for r in _table(at("operators.csv"))}
    trays = {
        r["plate"]: {
            "instrument": r["instrument"],
            "panel": r["panel"],
            "matrix": r["matrix"],
            "tier": int(r["tier"]),
        }
        for r in _table(at("plates.csv"))
    }
    wells = [
        {
            "seq": int(r["seq"]),
            "plate": r["plate"],
            "well": r["well"],
            "operator": r["operator"],
            "action": r["action"],
            "raw": int(r["raw"]),
            "exposure": int(r["exposure"]),
        }
        for r in _records(at("reads.jsonl"))
    ]
    return {
        "mode": int(manifest["mode"]),
        "instruments": rigs,
        "panels": assays,
        "operators": staff,
        "plates": trays,
        "reads": wells,
    }


def _apply_matrix(n, matrix):
    step = MATRIX_STEP.get(matrix)
    return n if step is None else step(n)


def _apply_family(n, family):
    step = FAMILY_STEP.get(family)
    return n if step is None else step(n)


def _band_of(n, lift):
    for name, floor in GRADE_FLOORS:
        if n >= floor + lift:
            return name
    return "trace"


def _allowance(role):
    return ROLE_ALLOWANCE.get(role, DEFAULT_ALLOWANCE)


def _verdict(action, band, drift_in, role):
    if action in SETUP_ACTIONS:
        return "setup"
    if action == "mask":
        return "masked"
    if band == "trace":
        return "reject"
    return "review" if drift_in > _allowance(role) else "ok"


def _tick(exposure, tier):
    step = exposure // 50
    return step * 2 if tier == 3 else step


def _starting_baselines(rigs, trays, mode):
    levels = {name: row["baseline"] for name, row in rigs.items()}
    in_use = sorted({row["instrument"] for row in trays.values()})
    if mode & BIT_BASELINE_DELTA and len(levels) > 1 and in_use:
        odd = in_use[-1]
        rest = [v for k, v in levels.items() if k != odd]
        if rest:
            levels[odd] = levels[odd] + min(rest)
    return levels


def _matrix_name(tray, staff_count, mode):
    written = tray["matrix"]
    if not mode & BIT_MATRIX_ALIAS or written not in MATRIX_WHEEL:
        return written
    spun = MATRIX_WHEEL.index(written) + tray["tier"] + staff_count
    return MATRIX_WHEEL[spun % len(MATRIX_WHEEL)]


def _family_name(assay, mode):
    odd_replicates = assay["replicates"] % 2 == 1
    return "elisa" if mode & BIT_PANEL_PARITY and odd_replicates else assay["family"]


def _walk_order(wells, tray_count, mode):
    walk = sorted(wells, key=lambda r: r["seq"])
    if mode & BIT_COUNT_BIAS:
        walk = walk[: -(1 + tray_count % 4)]
    if mode & BIT_EXPOSURE_ORDER:
        walk = sorted(walk, key=lambda r: (r["exposure"], r["seq"]))
    return walk


def _floor_map(walk):
    floors = {}
    for read in walk:
        seen = floors.get(read["plate"])
        if seen is None or read["exposure"] < seen:
            floors[read["plate"]] = read["exposure"]
    return floors


def resolve_run(run):
    mode = run["mode"]
    rigs, assays = run["instruments"], run["panels"]
    staff, trays = run["operators"], run["plates"]
    staff_count = len(staff)
    levels = _starting_baselines(rigs, trays, mode)
    walk = _walk_order(run["reads"], len(trays), mode)
    floors = _floor_map(walk) if mode & BIT_EXPOSURE_FLOOR else {}

    carried = {}
    newest = {}
    resolved = []

    for read in walk:
        tray_id = read["plate"]
        tray = trays[tray_id]
        rig = tray["instrument"]
        if tray_id not in carried:
            opening = levels[rig]
            earlier = newest.get(rig)
            if mode & BIT_CHAIN_BLANK and earlier is not None:
                opening = carried[earlier]["blank"]
            carried[tray_id] = {
                "blank": opening,
                "drift": 0,
                "pending": 0,
                "strikes": 0,
                "operator": None,
                "previous": newest.get(rig),
            }
            newest[rig] = tray_id
        held = carried[tray_id]

        matrix = _matrix_name(tray, staff_count, mode)
        family = _family_name(assays[tray["panel"]], mode)
        role = staff[read["operator"]]["role"]
        if mode & BIT_ROLE_LOOKBACK and held["operator"] is not None:
            role = staff[held["operator"]]["role"]
        window = floors[tray_id] if mode & BIT_EXPOSURE_FLOOR else read["exposure"]
        lift = tray["tier"] * 15 if mode & BIT_BAND_TIER_SHIFT else 0

        signal = max(0, (read["raw"] - held["blank"]) * 1000 // window)
        signal = max(0, _apply_matrix(signal, matrix))
        signal = max(0, _apply_family(signal, family))
        drift_in = held["drift"]
        amount = max(0, signal - drift_in)
        band = _band_of(amount, lift)
        verdict = _verdict(read["action"], band, drift_in, role)

        resolved.append({
            "action": read["action"],
            "drift_before": drift_in,
            "grade": band,
            "operator": read["operator"],
            "plate": tray_id,
            "seq": read["seq"],
            "status": verdict,
            "value": amount,
            "well": read["well"],
        })

        if verdict == "reject":
            held["strikes"] += 1
        if read["action"] == "mask" and mode & BIT_MASK_ABSOLVES and held["strikes"] > 0:
            held["strikes"] -= 1
        held["operator"] = read["operator"]

        tick = _tick(read["exposure"], tray["tier"]) if read["action"] == "measure" else 0
        if mode & BIT_DRIFT_ECHO:
            moved, held["pending"] = held["pending"], tick
        else:
            moved = tick
        if read["action"] == "blank":
            held["blank"] = read["raw"]
        elif read["action"] == "recal":
            held["drift"] = 0
            held["pending"] = 0
            moved = 0
        held["drift"] = min(DRIFT_CAP, held["drift"] + moved)

    tray_rows = []
    for tray_id in sorted(trays):
        mine = [row for row in resolved if row["plate"] == tray_id]
        held = carried.get(tray_id)
        kept = [row for row in mine if row["status"] in COUNTED]
        total = sum(row["value"] for row in kept)
        crest = max((row["value"] for row in kept), default=0)
        leader = None
        for row in kept:
            if leader is None or (row["value"], row["seq"]) > (leader["value"], leader["seq"]):
                leader = row
        strikes = held["strikes"] if held else 0
        drift_out = held["drift"] if held else 0
        weighed = strikes
        if mode & BIT_QUARANTINE_SPAN and held is not None and held["previous"] is not None:
            weighed += carried[held["previous"]]["strikes"]
        if weighed >= QUARANTINE_STRIKES:
            outcome = "quarantine"
        elif drift_out > HOLD_ABOVE:
            outcome = "hold"
        else:
            outcome = "release"
        tally = {key: 0 for key in GRADE_KEYS}
        for row in mine:
            tally[row["grade"]] += 1
        tray_rows.append({
            "blank_end": held["blank"] if held else levels[trays[tray_id]["instrument"]],
            "disposition": outcome,
            "drift_end": drift_out,
            "grades": tally,
            "measured": sum(1 for row in mine if row["action"] == "measure"),
            "peak": crest,
            "plate": tray_id,
            "reads": len(mine),
            "rejects": strikes,
            "reviewed": sum(1 for row in mine if row["status"] == "review"),
            "top_well": leader["well"] if leader is not None else None,
            "value_total": total,
        })

    grade_tally = {key: 0 for key in GRADE_KEYS}
    status_tally = {key: 0 for key in STATUS_KEYS}
    for row in resolved:
        grade_tally[row["grade"]] += 1
        status_tally[row["status"]] += 1

    front = None
    for row in tray_rows:
        if front is None or row["value_total"] > front["value_total"]:
            front = row

    summary = {
        "by_grade": grade_tally,
        "by_status": status_tally,
        "plates": len(tray_rows),
        "quarantined": sorted(
            row["plate"] for row in tray_rows if row["disposition"] == "quarantine"
        ),
        "reads": len(resolved),
        "top_plate": front["plate"] if front is not None else None,
        "value_total": sum(row["value_total"] for row in tray_rows),
    }
    return resolved, tray_rows, summary


def derive(data_dir, prefix=""):
    return resolve_run(load_run(data_dir, prefix))


def render_lines(rows):
    packed = [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows]
    return "".join(line + "\n" for line in packed)


def render_block(payload):
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def plate_digest(resolved, tray_rows, tray_id):
    body = render_lines([r for r in resolved if r["plate"] == tray_id])
    for row in tray_rows:
        if row["plate"] == tray_id:
            body += render_block(row)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def run_digest(resolved, tray_rows, summary):
    body = render_lines(resolved) + render_block({"plates": tray_rows}) + render_block(summary)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_reports(out_dir, resolved, tray_rows, summary):
    target = pathlib.Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "readings.jsonl").write_text(render_lines(resolved), encoding="utf-8", newline="")
    (target / "plates.json").write_text(
        render_block({"plates": tray_rows}), encoding="utf-8", newline=""
    )
    (target / "bench.json").write_text(render_block(summary), encoding="utf-8", newline="")


def main(argv):
    resolved, tray_rows, summary = derive(argv[0])
    write_reports(argv[1], resolved, tray_rows, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


FIGURE_NAMES = [
    "trace_rejects",
    "technician_reviews",
    "off_role_reviews",
    "hold_plates",
    "saturated_reads",
    "thin_matrix_total",
    "rich_matrix_total",
    "assay_family_total",
    "high_reads",
    "blank_end_total",
]

THIN = ("saliva", "urine")
RICH = ("serum", "lysate")
ASSAY_FAMILIES = ("pcr", "turbidity")
OFF_ROLES = ("scientist", "trainee", "service")
DRIFT_CEILING = 90


def closing_figures(run, resolved, tray_rows):
    trays, assays, staff = run["plates"], run["panels"], run["operators"]

    def role_of(row):
        return staff[row["operator"]]["role"]

    def matrix_of(row):
        return trays[row["plate"]]["matrix"]

    def family_of(row):
        return assays[trays[row["plate"]]["panel"]]["family"]

    reviews = [r for r in resolved if r["status"] == "review"]
    return {
        "trace_rejects": sum(1 for r in resolved if r["status"] == "reject"),
        "technician_reviews": sum(1 for r in reviews if role_of(r) == "technician"),
        "off_role_reviews": sum(1 for r in reviews if role_of(r) in OFF_ROLES),
        "hold_plates": sum(1 for p in tray_rows if p["disposition"] == "hold"),
        "saturated_reads": sum(1 for r in resolved if r["drift_before"] == DRIFT_CEILING),
        "thin_matrix_total": sum(r["value"] for r in resolved if matrix_of(r) in THIN),
        "rich_matrix_total": sum(r["value"] for r in resolved if matrix_of(r) in RICH),
        "assay_family_total": sum(r["value"] for r in resolved if family_of(r) in ASSAY_FAMILIES),
        "high_reads": sum(1 for r in resolved if r["grade"] == "high"),
        "blank_end_total": sum(p["blank_end"] for p in tray_rows),
    }


DATA_DIR = pathlib.Path("/app/data")
OUT_DIR = pathlib.Path("/app/out")
SCRIPT = OUT_DIR / "triage.py"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SCRIPT.write_text(ENGINE, encoding="utf-8", newline="")

    finished = subprocess.run([sys.executable, str(SCRIPT), str(DATA_DIR), str(OUT_DIR)])
    if finished.returncode != 0:
        raise SystemExit(finished.returncode)

    scope = {"__name__": "triage_oracle"}
    exec(compile(ENGINE, str(SCRIPT), "exec"), scope)
    run = scope["load_run"](str(DATA_DIR))
    resolved, tray_rows, summary = scope["resolve_run"](run)

    expected = {
        "readings.jsonl": scope["render_lines"](resolved),
        "plates.json": scope["render_block"]({"plates": tray_rows}),
        "bench.json": scope["render_block"](summary),
    }
    for name, want in expected.items():
        if (OUT_DIR / name).read_text(encoding="utf-8") != want:
            raise SystemExit("the written %s disagrees with the resolved run" % name)

    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    stated = manifest["plate_digests"]
    agreed = sum(
        1
        for tray_id, digest in sorted(stated.items())
        if scope["plate_digest"](resolved, tray_rows, tray_id) == digest
    )
    whole = scope["run_digest"](resolved, tray_rows, summary) == manifest["run_digest"]

    figures = closing_figures(run, resolved, tray_rows)
    print("triage engine rebuilt at %s and run over %s" % (SCRIPT, DATA_DIR))
    print(
        "mode word 0x%03x, %d reads resolved over %d plates"
        % (run["mode"], len(resolved), len(tray_rows))
    )
    print("plate digests matched: %d of %d" % (agreed, len(stated)))
    print("run digest matched: %s" % ("yes" if whole else "no"))
    print("closing report for the shipped run:")
    for name in FIGURE_NAMES:
        print("%s = %d" % (name, figures[name]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
