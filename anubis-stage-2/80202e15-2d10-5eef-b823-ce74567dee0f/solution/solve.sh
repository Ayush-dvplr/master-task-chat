#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/transform.py
python3 /app/out/transform.py /app/data /app/out
