#!/bin/bash
# Oracle dispatcher for 98ed74c1-19ac-5ec8-adaf-392a172d4600.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
