#!/bin/sh
set -eu
mkdir -p /app/out
cp /solution/solve.py /app/out/calculate_pension.py
chmod 755 /app/out/calculate_pension.py
python3 /app/out/calculate_pension.py /app/data /app/out
for report in manifest data_quality service_ledger accrual_ledger cola_ledger member_benefits plan_rollups exception_register audit_trace; do
  test -s "/app/out/${report}.json"
done
