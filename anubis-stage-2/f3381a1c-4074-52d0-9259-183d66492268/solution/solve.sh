#!/bin/bash
# Oracle entrypoint for f3381a1c-4074-52d0-9259-183d66492268.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/relplan.py
chmod 0755 /app/out/relplan.py

python3 /app/out/relplan.py /app/data /app/out

cat > /app/out/diagnosis.md <<'DOC'
# Defects of the retired planner corrected in this build

1. Cost scaling collapsed the four ordered steps into one multiplication over
   floats with a single final rounding, against addendum A section A1 and A2.
   Each step now rounds up to a whole tick before the next step reads it.
2. The cost rules were taken from the capacity workbook without resolving
   revision_seq, so the superseded surcharge fractions were used, against
   handbook section 2 rule 6.
3. The per component cost was read from the legacy_cost_ticks column, which the
   handbook preamble excludes from planning.
4. Pool budgets were read as plain numbers, so a budget whose scale_unit reads
   milli_tick was overstated by three orders of magnitude, against addendum A
   section A3.
5. Maintenance window reservations were left out of the net budget, against
   addendum A section A3.
6. Admission ranked dirty units one at a time by priority class, against the
   closure priced objective of addendum A section A4.
7. The priority class override table of addendum A section A8 was never read, so
   every unit kept its register priority.
8. Cycles were broken at the first edge of the group, against the
   minimum break_cost tuple of addendum A section A6, and the applicability
   table was ignored, so a cycle out of scope for a target lost an edge rather
   than blocking that target.
9. Versions were chosen per component by local preference alone, against the
   cluster rule of addendum B, so locally preferred pairs that reject each other
   were shipped.
10. Every declared optional dependency was treated as live, against handbook
    section 2 rule 8.
11. The contract digest covered optional consumption as well as required
    consumption, against handbook section 4.
12. A previous artifact whose index row carries retained false was treated as
    reusable, against handbook section 5.
13. Rows whose status reads superseded were applied as live rows throughout,
    against handbook section 2 rule 5.
14. Units beyond the eligibility table of the target register were planned,
    against handbook section 3.
DOC

python3 - <<'PY'
import json
import sys
from pathlib import Path

out = Path("/app/out")
required = ["relplan.py", "diagnosis.md"] + ["normalized_inventory.jsonl", "revision_delta.jsonl", "toolchain_resolution.jsonl", "contract_delta.jsonl", "invalidation_reasons.jsonl", "invalidation_closure.jsonl", "generated_output_plan.jsonl", "build_unit_ledger.jsonl", "build_cost_breakdown.jsonl", "capacity_allocation.jsonl", "deferred_units.jsonl", "dependency_schedule.jsonl", "cycle_resolution.jsonl", "worker_pool_summary.json", "compatibility_matrix.jsonl", "rejected_combinations.jsonl", "version_selection.jsonl", "release_membership.jsonl", "deployment_manifest.json", "generated_sdk_manifest.jsonl", "migration_order.jsonl", "artifact_provenance.jsonl", "cache_reuse_manifest.jsonl", "release_delta.json", "audit_exceptions.jsonl", "release_decision.json", "cost_amortization.jsonl", "conformance_summary.csv"]
missing = [name for name in required if not (out / name).is_file()]
if missing:
    sys.exit("oracle did not produce: " + ", ".join(missing))

decision = json.loads((out / "release_decision.json").read_text())
pools = json.loads((out / "worker_pool_summary.json").read_text())["pools"]
schedule = [json.loads(line) for line in
            (out / "dependency_schedule.jsonl").read_text().splitlines() if line]

if decision["units_total"] <= 0:
    sys.exit("oracle planned no units")
if decision["scheduled_units"] != len(schedule):
    sys.exit("oracle schedule disagrees with the decision")
for pool, row in pools.items():
    if row["consumed_ticks"] > row["net_budget_ticks"]:
        sys.exit("oracle overran pool " + pool)
    if row["net_budget_ticks"] != max(
            0, row["gross_budget_ticks"] - row["reserved_ticks"]):
        sys.exit("oracle net budget does not reconcile for " + pool)

print("oracle: %d units, %d scheduled, decision %s" % (
    decision["units_total"], decision["scheduled_units"], decision["decision"]))
PY
