#!/bin/bash
set -euo pipefail
SOLUTION_ROOT="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp "${SOLUTION_ROOT}/solve.py" /app/out/derive_report.py
chmod +x /app/out/derive_report.py
python3 -B /app/out/derive_report.py /app/data /app/out
# Run the whole derivation again into an empty directory; the reports must
# come out byte for byte the same.
SECOND_RUN="$(mktemp -d)"
python3 -B /app/out/derive_report.py /app/data "${SECOND_RUN}"
for report in "${SECOND_RUN}"/*.json; do
  cmp -s "${report}" "/app/out/$(basename "${report}")" || exit 1
done
rm -rf "${SECOND_RUN}"
# Recompute the delivered figures by a second route, then rerun the program
# on an altered copy of the data and confirm the dependent figures move.
python3 -B - "${SOLUTION_ROOT}" /app/data /app/out <<'SELFCHECK'
#!/usr/bin/env python3
"""Recompute the delivered figures by a second route and compare them.

Run by solve.sh with <SOLUTION_ROOT> <DATA_DIR> <OUT_DIR>.

The wire decoder is shared with the program; joining, tallying, blame
settlement and partitioning are done here from the raw tables.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

CELLS = ("East", "North", "South", "West")
SEGMENTS = ("commercial", "public")
CONTROL_KEYS = ("CTRL-A", "CTRL-B", "CTRL-C", "CTRL-D", "CTRL-E", "CTRL-F",
                "CTRL-G", "CTRL-H")


def load_solver(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("stall_solver", root / "solve.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_rows(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def settled_constants(solver, quality: dict):
    by_label = {label: name for name, label in solver.PARAM_LABEL.items()}
    chosen = {by_label[entry["name"]]: entry["selected"]
              for entry in quality["candidate_search"]["parameters"]}
    return solver.Constants.from_map(chosen)


def walk(registry: dict, tag: str, epoch: int, owner: bool):
    """Return (tag, status) for a worker walk, or (tag, None) when it fails."""
    seen = set()
    current = tag
    for _ in range(6):
        if current in seen:
            break
        seen.add(current)
        live = [row for row in registry.get(current, [])
                if int(row["effective_from_epoch"]) <= epoch <= int(row["effective_to_epoch"])]
        if not live:
            break
        row = min(live, key=lambda item: int(item["revision"]))
        if row["canonical_tag"] == current:
            return current, row
        current = row["canonical_tag"]
    return (tag, None) if owner else (None, None)


def recount(solver, data: pathlib.Path, constants) -> dict:
    """Join, tally and settle the window from the raw tables."""
    registry = defaultdict(list)
    for row in read_rows(data / "thread_registry.csv"):
        registry[row["worker_tag"]].append(row)
    windows = {row["pool_key"]: (int(row["open_tick"]), int(row["close_tick"]))
               for row in read_rows(data / "pool_windows.csv")}
    cell_of = {row["host_id"]: row["cell"] for row in read_rows(data / "host_cells.csv")}
    segment_of = {row["tenant_class"]: row["tenant_segment"]
                  for row in read_rows(data / "tenant_classes.csv")}
    ladder = defaultdict(dict)
    for row in read_rows(data / "lock_ladder.csv"):
        ladder[row["lock_class"]][int(row["rung_index"])] = int(row["budget_ns"])
    probes = {(row["worker_tag"], int(row["slot"])) for row in read_rows(data / "thread_probe.csv")}
    parks = {}
    for line in (data / "park_reports.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            parks[(item["worker_tag"], int(item["slot"]))] = item

    tally = defaultdict(int)
    counted = []
    journal = (data / "stall_journal.psv").read_text(encoding="utf-8")
    for segment in solver.parse_wire_journal(journal, constants):
        for event in segment.events:
            epoch = event.tick // constants.epoch_span
            worker, row = walk(registry, segment.worker_field, epoch, owner=False)
            if row is None:
                tally["unresolved_worker"] += 1
                continue
            if row["status"] != "active":
                tally["retired_worker"] += 1
                continue
            lo, hi = windows[row["pool_key"]]
            key = (worker, event.slot)
            misses = [reason for reason, missed in (
                ("outside_window", not lo <= event.tick < hi),
                ("unprobed_slot", key not in probes),
                ("unreported_park", key not in parks)) if missed]
            for reason in misses:
                tally[reason] += 1
            if misses:
                continue
            park = parks[key]
            counted.append({
                "cell": cell_of[park["host_id"]],
                "segment": segment_of[park["tenant_class"]],
                "logged": int(park["bytes_logged"]),
                "wait": event.wait_ns,
                "depth": event.depth,
                "lock": event.blocked_class,
                "owner": walk(registry, event.owner_tag, epoch, owner=True)[0],
            })

    rung = {cls: max(steps) for cls, steps in ladder.items()}
    while True:
        hot = {}
        for cls in rung:
            waits = [item["wait"] for item in counted if item["lock"] == cls]
            over = sum(1 for wait in waits if wait > ladder[cls][rung[cls]])
            hot[cls] = over > len(waits) - over
        blamed = set()
        for owner in {item["owner"] for item in counted}:
            held = [item["lock"] for item in counted if item["owner"] == owner]
            heated = sum(1 for cls in held if hot[cls])
            if heated > len(held) - heated:
                blamed.add(owner)
        moved = False
        for cls in rung:
            if rung[cls] > 0 and any(item["owner"] in blamed for item in counted
                                     if item["lock"] == cls):
                rung[cls] -= 1
                moved = True
        if not moved:
            break
    quarantined = sorted(cls for cls in rung if rung[cls] == 0 and hot[cls])
    return {"counted": counted, "tally": dict(tally), "rung": rung,
            "quarantined": quarantined}


def expect(label: str, condition: bool) -> None:
    if not condition:
        raise SystemExit(f"self-check {label} failed")
    print(f"check {label} ok")


def main(argv: list[str]) -> int:
    root, data, out = (pathlib.Path(arg) for arg in argv[1:4])
    solver = load_solver(root)
    quality = read_json(out / "data_quality.json")
    constants = settled_constants(solver, quality)
    window = recount(solver, data, constants)
    counted = window["counted"]

    summary = read_json(out / "summary.json")
    logged_by_cell = defaultdict(int)
    for item in counted:
        logged_by_cell[item["cell"]] += item["logged"]
    expect("R1", summary["by_cell"] == dict(logged_by_cell))

    audit = read_json(out / "policy_audit.json")
    expect("R2", {row["lock_class"]: row["settled_rung"] for row in audit["lock_classes"]}
           == window["rung"])

    regions_ok = True
    for cell in CELLS:
        report = read_json(out / f"region_{cell}.json")
        mine = [item for item in counted if item["cell"] == cell]
        regions_ok &= report["accepted_count"] == len(mine)
        regions_ok &= report["total_wait_ns"] == sum(item["wait"] for item in mine)
    expect("R3", regions_ok)

    segments_ok = True
    for name in SEGMENTS:
        report = read_json(out / f"segment_{name}.json")
        segments_ok &= report["total_depth"] == sum(
            item["depth"] for item in counted if item["segment"] == name)
    expect("R4", segments_ok)

    expect("R5", {reason: count for reason, count in quality["rejections"].items() if count}
           == window["tally"])

    published = read_json(data / "control-slice-figures.json")
    calibration = (data / "calibration_stall_journal.psv").read_text(encoding="utf-8")
    figures = solver.measure_controls(calibration, constants)
    reproduced = {row["control"]: row["reproduced"] for row in quality["calibration_comparison"]}
    expect("R6", all(figures[key] == published[key] == reproduced[key] for key in CONTROL_KEYS))

    print("quarantined lock classes: " + ", ".join(window["quarantined"]))

    with tempfile.TemporaryDirectory() as scratch:
        altered = pathlib.Path(scratch) / "data"
        shutil.copytree(data, altered)
        parks = altered / "park_reports.jsonl"
        rows = [json.loads(line) for line in parks.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            row["bytes_logged"] = int(row["bytes_logged"]) + 1000
        parks.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        moved_out = pathlib.Path(scratch) / "out"
        subprocess.run([sys.executable, str(out / "derive_report.py"), str(altered), str(moved_out)],
                       check=True)
        before = summary["total_bytes_logged"]
        after = read_json(moved_out / "summary.json")["total_bytes_logged"]
        residual = read_json(moved_out / "data_quality.json")["reconciliation"]["residual_bytes"]
        expect("R7", after == before + 1000 * summary["accepted_count"]
               and residual == quality["reconciliation"]["residual_bytes"] - 1000 * summary["accepted_count"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
SELFCHECK
