#!/usr/bin/env python3
"""The plate triage engine.

Usage: triage.py <input-dir> <output-dir>

Resolves a bench run of well reads into graded readings, rolls them up per
plate and for the bench, and writes readings.jsonl, plates.json and bench.json.
The run's mode word is read from manifest.json in the input directory.

The chain at mode zero is recovered in full: this reproduces both shipped mode
zero runs byte for byte, readings, plates, bench and both kinds of manifest
digest. The twelve mode bits are not recovered; see _unidentified below. Runs
at a non-zero mode word are therefore resolved by the mode zero chain.
"""

import csv
import hashlib
import json
import os
import sys

MATRICES = ("buffer", "serum", "plasma", "lysate", "saliva", "urine", "media")
FAMILIES = ("elisa", "pcr", "turbidity", "fluor")
ROLES = ("technician", "scientist", "trainee", "service")
GRADES = ("high", "mid", "low", "trace")
STATUSES = ("masked", "ok", "reject", "review", "setup")
SETUP_ACTIONS = ("blank", "recal")


def base_config():
    """The firmware constants of the chain at mode zero."""
    return {
        "gain": 1000,
        "matrix": {
            "buffer": None,
            "serum": ("add", -4),
            "plasma": ("mul", 3, 4),
            "lysate": ("add", 6),
            "saliva": ("mul", 1, 2),
            "urine": ("floor", 5),
            "media": ("mul", 5, 4),
        },
        "panel": {
            "elisa": None,
            "pcr": ("mul", 9, 10),
            "turbidity": ("add", 12),
            "fluor": ("mul", 7, 5),
        },
        "band_high": 240,
        "band_mid": 120,
        "band_low": 40,
        "tol": {"technician": 25, "scientist": 40, "trainee": 12, "service": 0},
        "charge_div": 50,
        "charge_tier": 3,
        "charge_mult": 2,
        "drift_cap": 90,
        "quarantine_strikes": 3,
        "hold_drift": 30,
        "counted": ("ok", "review"),
        "blank_init": "baseline",
        "top_well_tie": "last",
        "top_plate_tie": "first",
    }


def config_for_mode(mode):
    """Apply the alteration each set bit of the mode word switches on."""
    cfg = base_config()
    for bit in range(12):
        if mode & (1 << bit):
            ALTERATIONS[bit](cfg)
    return cfg


def _unidentified(cfg):
    """A mode bit whose alteration could not be recovered; left as a no-op.

    No run ships at an intermediate mode word: digests exist only at 0x000, via
    the two worked runs, and at 0xfff, via manifest.json and trial_manifest.json.
    A plate digest at 0xfff therefore tests all twelve alterations at once and
    cannot isolate one bit, and a wrong reading of a single bit fails it exactly
    as a wrong reading of all twelve does. Treating an unrecovered bit as a
    no-op keeps the chain at its verified mode zero behaviour rather than
    guessing an alteration.
    """
    return cfg


ALTERATIONS = [_unidentified] * 12


def clamp(x):
    return x if x > 0 else 0


def apply_adjust(fig, adj):
    if adj is None:
        return fig
    kind = adj[0]
    if kind == "mul":
        return fig * adj[1] // adj[2]
    if kind == "add":
        return fig + adj[1]
    if kind == "floor":
        return fig - fig % adj[1]
    raise ValueError("unknown adjustment %r" % (adj,))


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_run(indir):
    run = {}
    with open(os.path.join(indir, "manifest.json"), encoding="utf-8") as fh:
        run["manifest"] = json.load(fh)
    run["instruments"] = {
        r["instrument"]: r for r in read_csv(os.path.join(indir, "instruments.csv"))
    }
    run["panels"] = {r["panel"]: r for r in read_csv(os.path.join(indir, "panels.csv"))}
    run["operators"] = {
        r["operator"]: r["role"] for r in read_csv(os.path.join(indir, "operators.csv"))
    }
    run["plates"] = {r["plate"]: r for r in read_csv(os.path.join(indir, "plates.csv"))}
    reads = []
    with open(os.path.join(indir, "reads.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                reads.append(json.loads(line))
    run["reads"] = reads
    return run


def resolve(run, cfg):
    plates_meta = run["plates"]
    state = {}
    for name, meta in plates_meta.items():
        inst = run["instruments"][meta["instrument"]]
        blank = int(inst["baseline"]) if cfg["blank_init"] == "baseline" else 0
        state[name] = {"blank": blank, "drift": 0, "strikes": 0}

    readings = []
    for r in sorted(run["reads"], key=lambda r: r["seq"]):
        plate = r["plate"]
        meta = plates_meta[plate]
        st = state[plate]
        fam = run["panels"][meta["panel"]]["family"]
        role = run["operators"][r["operator"]]

        fig = clamp(int(r["raw"]) - st["blank"])
        fig = clamp(fig * cfg["gain"] // int(r["exposure"]))
        fig = clamp(apply_adjust(fig, cfg["matrix"][meta["matrix"]]))
        fig = clamp(apply_adjust(fig, cfg["panel"][fam]))
        drift_before = st["drift"]
        value = clamp(fig - drift_before)

        if value >= cfg["band_high"]:
            grade = "high"
        elif value >= cfg["band_mid"]:
            grade = "mid"
        elif value >= cfg["band_low"]:
            grade = "low"
        else:
            grade = "trace"

        action = r["action"]
        if action in SETUP_ACTIONS:
            status = "setup"
        elif action == "mask":
            status = "masked"
        elif grade == "trace":
            status = "reject"
        elif drift_before > cfg["tol"][role]:
            status = "review"
        else:
            status = "ok"

        readings.append(
            {
                "action": action,
                "drift_before": drift_before,
                "grade": grade,
                "operator": r["operator"],
                "plate": plate,
                "seq": r["seq"],
                "status": status,
                "value": value,
                "well": r["well"],
            }
        )

        if action == "blank":
            st["blank"] = int(r["raw"])
        elif action == "recal":
            st["drift"] = 0
        elif action == "measure":
            charge = int(r["exposure"]) // cfg["charge_div"]
            if int(meta["tier"]) == cfg["charge_tier"]:
                charge *= cfg["charge_mult"]
            st["drift"] = min(st["drift"] + charge, cfg["drift_cap"])
        if status == "reject":
            st["strikes"] += 1

    return readings, state


def roll_up(run, cfg, readings, state):
    counted = set(cfg["counted"])
    rows = []
    for plate in sorted(run["plates"]):
        own = [o for o in readings if o["plate"] == plate]
        st = state[plate]
        grades = {g: 0 for g in GRADES}
        for o in own:
            grades[o["grade"]] += 1
        peak = 0
        top_well = None
        total = 0
        for o in own:
            if o["status"] not in counted:
                continue
            total += o["value"]
            if top_well is None or o["value"] > peak:
                peak, top_well = o["value"], o["well"]
            elif o["value"] == peak:
                if cfg["top_well_tie"] == "last":
                    top_well = o["well"]
                elif cfg["top_well_tie"] == "greatest":
                    top_well = max(top_well, o["well"])
                elif cfg["top_well_tie"] == "least":
                    top_well = min(top_well, o["well"])
        if st["strikes"] >= cfg["quarantine_strikes"]:
            disposition = "quarantine"
        elif st["drift"] > cfg["hold_drift"]:
            disposition = "hold"
        else:
            disposition = "release"
        rows.append(
            {
                "blank_end": st["blank"],
                "disposition": disposition,
                "drift_end": st["drift"],
                "grades": grades,
                "measured": sum(1 for o in own if o["action"] == "measure"),
                "peak": peak,
                "plate": plate,
                "reads": len(own),
                "rejects": st["strikes"],
                "reviewed": sum(1 for o in own if o["status"] == "review"),
                "top_well": top_well,
                "value_total": total,
            }
        )

    by_grade = {g: 0 for g in GRADES}
    by_status = {s: 0 for s in STATUSES}
    for o in readings:
        by_grade[o["grade"]] += 1
        by_status[o["status"]] += 1

    top_plate = None
    best = None
    for row in rows:
        if best is None or row["value_total"] > best:
            best, top_plate = row["value_total"], row["plate"]
        elif row["value_total"] == best and cfg["top_plate_tie"] == "last":
            top_plate = row["plate"]

    bench = {
        "by_grade": by_grade,
        "by_status": by_status,
        "plates": len(rows),
        "quarantined": sorted(
            r["plate"] for r in rows if r["disposition"] == "quarantine"
        ),
        "reads": len(readings),
        "top_plate": top_plate,
        "value_total": sum(r["value_total"] for r in rows),
    }
    return rows, bench


def readings_text(readings):
    return "".join(
        json.dumps(o, sort_keys=True, separators=(",", ":")) + "\n" for o in readings
    )


def plates_text(rows):
    return json.dumps({"plates": rows}, sort_keys=True, indent=2) + "\n"


def bench_text(bench):
    return json.dumps(bench, sort_keys=True, indent=2) + "\n"


def digests(readings, rows, bench):
    rtext = readings_text(readings)
    ptext = plates_text(rows)
    btext = bench_text(bench)
    plate_digests = {}
    for row in rows:
        plate = row["plate"]
        own = readings_text([o for o in readings if o["plate"] == plate])
        own += json.dumps(row, sort_keys=True, indent=2) + "\n"
        plate_digests[plate] = hashlib.sha256(own.encode("utf-8")).hexdigest()
    run_digest = hashlib.sha256((rtext + ptext + btext).encode("utf-8")).hexdigest()
    return plate_digests, run_digest


def run_engine(indir):
    run = load_run(indir)
    cfg = config_for_mode(int(run["manifest"]["mode"]))
    readings, state = resolve(run, cfg)
    rows, bench = roll_up(run, cfg, readings, state)
    return run, readings, rows, bench


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: triage.py <input-dir> <output-dir>\n")
        return 2
    indir, outdir = argv[1], argv[2]
    _, readings, rows, bench = run_engine(indir)
    os.makedirs(outdir, exist_ok=True)
    for name, text in (
        ("readings.jsonl", readings_text(readings)),
        ("plates.json", plates_text(rows)),
        ("bench.json", bench_text(bench)),
    ):
        with open(os.path.join(outdir, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
