#!/bin/bash
# Oracle dispatcher for 8956ff8b-d38c-557d-b0c6-cff12c5c2da3.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/settle_laytime.py
chmod 755 /app/out/settle_laytime.py
python3 /app/out/settle_laytime.py /app/data /app/out
for report in manifest data_quality event_ledger interval_ledger call_settlements voyage_rollups charterer_statements exception_register audit_trace; do
    test -s "/app/out/${report}.json"
done
