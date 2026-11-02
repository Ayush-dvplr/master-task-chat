#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/reserving.py
python3 /app/out/reserving.py --data /app/data --out /app/out
