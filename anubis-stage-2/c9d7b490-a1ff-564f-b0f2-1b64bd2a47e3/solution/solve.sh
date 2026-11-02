#!/bin/bash
set -euo pipefail

mkdir -p /app/out
python3 /solution/solve.py /app/data /app/out
cp /solution/solve.py /app/out/derive_report.py
