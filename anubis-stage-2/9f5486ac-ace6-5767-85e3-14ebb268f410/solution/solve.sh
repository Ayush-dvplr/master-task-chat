#!/bin/bash
# Oracle: install the reference builder and build release TR-2026.09 from /app/data.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/transform.py
python3 /app/out/transform.py /app/data /app/out

echo "[oracle] built TR-2026.09 into /app/out"
