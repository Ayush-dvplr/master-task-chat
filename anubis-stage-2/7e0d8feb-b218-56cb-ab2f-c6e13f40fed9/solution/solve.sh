#!/bin/bash
set -euo pipefail
SOLUTION_DIR="${SOLUTION_ROOT:-/solution}"
if [ -f /solution/solve.py ]; then
  SOLUTION_DIR=/solution
fi
mkdir -p /app/out
python3 "$SOLUTION_DIR/solve.py"
cp "$SOLUTION_DIR/solve.py" /app/out/conform.py
