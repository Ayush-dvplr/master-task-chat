#!/bin/bash
# Oracle dispatcher for slipway-overhaul-replan-repair.
set -euo pipefail

SOLUTION_DIR="${SOLUTION_ROOT:-/solution}"
if [ -f /solution/solve.py ]; then
  SOLUTION_DIR=/solution
fi

python3 "$SOLUTION_DIR/solve.py"

test -s /app/out/patched_engine.zip
test -s /app/out/25_summary.json
test -s /app/out/24_run_manifest.txt

cd /app/project && PYTHONPATH=/app/project/src python3 -m unittest discover -s tests -t tests -q

python3 - <<'PY'
import json
from pathlib import Path

out = Path("/app/out")
required = ["patched_engine.zip"] + [
    "01_identifier_canon.json", "02_precedence_edges.tsv",
    "03_reverse_index.json", "04_normalised_jobs.csv",
    "05_normalised_rules.csv", "06_feasibility_map.csv",
    "07_closure_map.jsonl", "08_demand_vectors.csv",
    "09_conflict_groups.json", "10_charge_contributions.csv",
    "11_baseline_selection.json", "12_baseline_trace.jsonl",
    "13_amendment_classification.csv", "14_invalidation_sets.jsonl",
    "15_reuse_ledger.csv", "16_work_counters.csv", "17_cache_summary.json",
    "18_final_selection.json", "19_rejected_register.csv",
    "20_resource_usage.tsv", "21_amendment_optima.csv",
    "22_defect_register.md", "23_verification_notes.md",
    "24_run_manifest.txt", "25_summary.json"]
missing = [n for n in required if not (out / n).is_file()]
if missing:
    raise SystemExit("missing oracle artifacts: {}".format(missing))

summary = json.loads((out / "25_summary.json").read_text(encoding="utf-8"))
totals = summary["control_totals"]
if totals["jobs_in_force"] <= 0 or totals["edges_accepted"] <= 0:
    raise SystemExit("oracle derived an empty round")
if totals["amendments_applied"] <= 0:
    raise SystemExit("oracle folded in no amendment")
if totals["cells_recomputed_after_build"] >= totals["cells_in_model"]:
    raise SystemExit("oracle rebuilt the whole model after the build")

classes = (out / "13_amendment_classification.csv").read_text(encoding="utf-8").splitlines()[1:]
if not any(row.split(",")[4] == "inert" for row in classes):
    raise SystemExit("oracle classified no amendment as inert")

counters = (out / "16_work_counters.csv").read_text(encoding="utf-8").splitlines()[1:]
if not any(int(row.split(",")[3]) == 0 for row in counters):
    raise SystemExit("oracle reached a cell for every amendment")
if not any(int(row.split(",")[9]) == 0 and int(row.split(",")[8]) > 0
           for row in counters):
    raise SystemExit("oracle never read a value back out of the store")

manifest = (out / "24_run_manifest.txt").read_text(encoding="utf-8").splitlines()
if not manifest[-1].startswith("publication "):
    raise SystemExit("oracle manifest has no closing digest")
PY

echo "[oracle] repaired slwopt and published 25 documents under /app/out"
