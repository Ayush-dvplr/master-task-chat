#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/clear_spectrum.py
chmod 755 /app/out/clear_spectrum.py
python3 /app/out/clear_spectrum.py /app/data /app/out
for f in manifest data_quality grant_ledger spectrum_slice_ledger preemption_ledger party_settlements auction_adjustments exception_register audit_trace; do
  test -s "/app/out/${f}.json"
done
