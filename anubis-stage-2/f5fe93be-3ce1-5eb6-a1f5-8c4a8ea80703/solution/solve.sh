#!/bin/bash
# Oracle: install the reconciler as the delivered program, then write every artifact from what it prints.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/optimize.py
for workload in visible peak steady burst latency; do
    python3 /app/out/optimize.py /app/data "$workload" > "/app/out/scenario_${workload}.json"
done
for rollup in perf_report bottleneck_analysis recommendations data_quality; do
    python3 /app/out/optimize.py --rollup /app/data "$rollup" > "/app/out/${rollup}.json"
done
