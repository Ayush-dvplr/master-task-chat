#!/bin/bash
# Oracle dispatcher for 6285fcad-50f6-5494-97c4-e1b982c7e713.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/run_flowrecord.py
python3 /app/out/run_flowrecord.py /app/data /app/out
