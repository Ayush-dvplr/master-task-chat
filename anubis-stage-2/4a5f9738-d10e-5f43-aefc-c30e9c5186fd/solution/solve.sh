#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
