#!/bin/bash
# Oracle dispatcher for b28ebc90-3080-5d41-9f01-e02549d3efaf.
set -euo pipefail

SOLUTION_DIR="${SOLUTION_ROOT:-/solution}"
if [ -f /solution/solve.py ]; then
  SOLUTION_DIR=/solution
fi

python3 "$SOLUTION_DIR/solve.py"

PYTHONPATH=/app/project/src python3 -m unittest discover -s /app/project/tests -q

python3 - <<'PY'
import json
from pathlib import Path

out = Path("/app/out")
required = [
    "package.zip", "build_report.json", "selftest.json",
    "defect_register.md", "verification_notes.md",
    "unit_normalization.json", "alias_resolution.jsonl",
    "expansion_ledger.csv", "config_resolution.json", "parameter_audit.csv",
    "trigger_eligibility_index.json", "dependency_graph.json",
    "cycle_break_ledger.json", "canonical_action_order.json",
    "resource_demand.csv", "window_capacity_report.csv",
    "initial_allocation.json", "displaced_action_queue.json",
    "fallback_expansion.json", "precedence_reconciliation.json",
    "final_action_order.json", "cooldown_state.csv", "derived_state.json",
    "suppression_ledger.csv", "next_state_snapshot.json",
    "per_context_manifest.json", "per_device_manifest.csv",
    "daily_automation_manifest.json", "resource_utilization_report.csv",
    "terminal_action_report.md", "audit_ledger.jsonl", "run_manifest.txt",
    "summary.json",
]
missing = [n for n in required if not (out / n).is_file()]
if missing:
    raise SystemExit("missing oracle artifacts: {}".format(missing))

summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
totals = summary["control_totals"]
for key in ("instances_expanded", "instances_eligible", "cycles_settled",
            "fallback_proposals", "final_instances"):
    if totals[key] <= 0:
        raise SystemExit("oracle produced no " + key)
if totals["overturned"] <= 0:
    raise SystemExit("oracle overturned nothing in the second round")
if totals["readmitted"] <= 0:
    raise SystemExit("oracle readmitted nothing at the feedback stage")

manifest = (out / "run_manifest.txt").read_text(encoding="utf-8").splitlines()
if not manifest[-1].startswith("publication "):
    raise SystemExit("oracle manifest has no publication digest")
PY

echo "[oracle] repaired daybreak and published 33 deliverables under /app/out"
