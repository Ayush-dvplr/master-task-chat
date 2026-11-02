#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/apportion_berth.py
python3 /app/out/apportion_berth.py --data /app/data --out /app/out
