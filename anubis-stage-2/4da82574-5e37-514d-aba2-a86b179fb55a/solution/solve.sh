#!/bin/bash
# Oracle dispatcher for 4da82574-5e37-514d-aba2-a86b179fb55a.
set -euo pipefail

SOLUTION_DIR="${SOLUTION_ROOT:-/solution}"
if [ -f /solution/solve.py ]; then
  SOLUTION_DIR=/solution
fi

python3 "$SOLUTION_DIR/solve.py"

test -s /app/out/package.zip
test -s /app/out/summary.json
test -s /app/out/run_manifest.txt

cd /app/project && PYTHONPATH=/app/project/src python3 -m unittest discover -s tests -t tests -q

python3 - <<'PY'
import json
from pathlib import Path

out = Path("/app/out")
required = [
    "package.zip", "selftest.json", "repair_report.json",
    "unit_normalisation.json", "alias_resolution.jsonl",
    "canonical_order.csv", "checkpoint_selection.json", "replay_window.json",
    "dependency_closure.json", "quarantine_ledger.csv",
    "transition_log.jsonl", "compensation_register.csv",
    "derived_counters.csv", "eligibility_passes.json", "final_state.json",
    "derived_index.jsonl", "checkpoint_reconciliation.json",
    "equivalence_report.json", "state_at_event.json", "bounded_replay.json",
    "defect_register.md", "verification_notes.md", "run_manifest.txt",
    "summary.json",
]
missing = [n for n in required if not (out / n).is_file()]
if missing:
    raise SystemExit("missing oracle artifacts: {}".format(missing))

equivalence = json.loads((out / "equivalence_report.json").read_text(encoding="utf-8"))
if not equivalence["identical"]:
    raise SystemExit("oracle replay from checkpoint left the from scratch replay")

passes = json.loads((out / "eligibility_passes.json").read_text(encoding="utf-8"))
if passes["round_count"] <= 0:
    raise SystemExit("oracle ran no re offer round")

register = (out / "compensation_register.csv").read_text(encoding="utf-8").splitlines()[1:]
applied = [r for r in register if r.split(",")[3] == "applied"]
if not applied:
    raise SystemExit("oracle applied no compensation")

summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
totals = summary["control_totals"]
if totals["quarantined_events"] <= 0 or totals["replayed_positions"] <= 0:
    raise SystemExit("oracle screened nothing")
if totals["spilled_cu"] <= 0:
    raise SystemExit("oracle settled no carry")

manifest = (out / "run_manifest.txt").read_text(encoding="utf-8").splitlines()
if not manifest[-1].startswith("publication "):
    raise SystemExit("oracle manifest has no publication digest")
PY

echo "[oracle] repaired bcrep and published 24 deliverables under /app/out"
