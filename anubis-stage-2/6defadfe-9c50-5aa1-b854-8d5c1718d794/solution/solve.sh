#!/bin/bash
# Oracle for 6defadfe-9c50-5aa1-b854-8d5c1718d794: repair the shipped trainyard project,
# run its own tests, archive it, and write the stage-1 ledger with it.
set -euo pipefail

mkdir -p /app/out /app/project
python3 /solution/solve.py

cd /app/project && PYTHONPATH=/app/project/src python3 -m unittest discover -s tests -q
for f in package.zip build_report.json module_core.json module_metrics.json dependency_resolution.json selftest.json summary.json; do
    test -s "/app/out/$f" || { echo "missing /app/out/$f" >&2; exit 1; }
done
echo "[oracle] repaired trainyard and wrote the stage-1 ledger under /app/out"
