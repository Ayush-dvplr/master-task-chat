#!/bin/bash
# Oracle dispatcher for ae640566-6067-508e-b982-0158d72da2d4.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
