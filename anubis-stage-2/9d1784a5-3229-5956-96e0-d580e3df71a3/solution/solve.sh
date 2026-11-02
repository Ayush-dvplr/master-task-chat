#!/bin/bash
# Oracle dispatcher for 9d1784a5-3229-5956-96e0-d580e3df71a3.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/run_budget.py
python3 /app/out/run_budget.py /app/data /app/out
