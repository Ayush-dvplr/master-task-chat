#!/bin/bash
# Oracle dispatcher for 1d61e794-1d97-598a-a052-5633e067ca06.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/run_levelnet.py
python3 /app/out/run_levelnet.py /app/data /app/out
