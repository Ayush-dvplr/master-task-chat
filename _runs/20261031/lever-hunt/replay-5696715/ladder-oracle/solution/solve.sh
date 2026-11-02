#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/settle.py
chmod 755 /app/out/settle.py
python3 /app/out/settle.py /app/data /app/out
