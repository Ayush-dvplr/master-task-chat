#!/bin/bash
# Oracle dispatcher for d49244f2-a14b-56f9-bc43-bc9986dd2b6f.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
