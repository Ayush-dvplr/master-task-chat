#!/bin/bash
# Oracle dispatcher for cleanroom-window-schedule.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
