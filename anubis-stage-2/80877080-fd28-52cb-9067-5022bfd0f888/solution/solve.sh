#!/bin/bash
# Oracle dispatcher for 80877080-fd28-52cb-9067-5022bfd0f888.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/plan_cache.py
python3 /app/out/plan_cache.py /app/data /app/out
