#!/bin/bash
# Oracle dispatcher for 75407a55-6665-505e-95d8-5ff9bdb3384f.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/calculate_royalties.py
chmod 755 /app/out/calculate_royalties.py
python3 /app/out/calculate_royalties.py /app/data /app/out
for report in manifest data_quality statement_ledger waterfall_ledger recoupment_ledger participant_statements project_rollups exception_register audit_trace; do
  test -s "/app/out/${report}.json"
done
