#!/bin/bash
set -euo pipefail
mkdir -p /app/out
install -m 0755 "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/transform.py
python3 /app/out/transform.py /app/data /app/out
