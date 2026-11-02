#!/bin/bash
# Oracle for 725e575c-62c9-5e28-a103-27072945bca6: repair the shipped runledger project, archive it, rebuild the stage-1 ledger.
# Pass --tolerant to skip feed files that are listed in the index but absent.
set -euo pipefail

python3 /solution/solve.py "$@"

cd /app/project && PYTHONPATH=/app/project/src python3 -m unittest discover -s tests -q

for f in package.zip shard_ledger.csv step_ledger.csv mixture_report.json checkpoint_report.json reconciliation.json resume_state.json; do
    test -s "/app/out/$f" || { echo "missing /app/out/$f" >&2; exit 1; }
done
echo "[oracle] repaired runledger and wrote seven deliverables under /app/out"
