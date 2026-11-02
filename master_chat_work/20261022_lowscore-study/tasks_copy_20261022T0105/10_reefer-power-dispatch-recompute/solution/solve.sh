#!/bin/bash
set -euo pipefail
SOLUTION_DIR="${SOLUTION_ROOT:-/solution}"
if [ -f /solution/solve.py ]; then
  SOLUTION_DIR=/solution
fi
mkdir -p /app/out
python3 "$SOLUTION_DIR/solve.py" --data /app/data --out /app/out
cp "$SOLUTION_DIR/solve.py" /app/out/reeferdispatch.py
