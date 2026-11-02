#!/bin/bash
set -euo pipefail
# The program is a deliverable in its own right, so it is installed at the
# declared path first and the settlement is then run from there, exactly as an
# agent leaves it behind. The run itself never reads its own source.
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/settle.py
python3 /app/out/settle.py --data /app/data --out /app/out
