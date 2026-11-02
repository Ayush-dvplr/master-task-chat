#!/bin/bash
# Oracle dispatcher for 3f39299a-20c7-5792-a6e6-b2a616a3ec30.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
