#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/out

python3 /solution/solve.py /app/data /app/out

REQUIRED=(
    schedule_matrix.json
    fleet_utilization.json
    tenant_fairness_report.json
    migration_ledger.json
    preemption_events.json
    sla_violation_report.json
    objective_breakdown.json
    fixed_point_trace.json
    integrity_manifest.json
    final_state.json
    reusable_scheduler.py
)
for name in "${REQUIRED[@]}"; do
    if [[ ! -s "/app/out/${name}" ]]; then
        echo "reference solver failed to emit /app/out/${name}" >&2
        exit 1
    fi
done

echo "reference solver produced ${#REQUIRED[@]} artifacts"
