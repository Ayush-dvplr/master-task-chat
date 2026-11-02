#!/bin/bash
# Oracle dispatcher for cohort-retention-reconciliation.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
