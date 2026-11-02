#!/bin/bash
# Oracle dispatcher for 37a0c3d6-c38e-5885-b018-8b8fb2ef88cc.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/run_be.py
python3 /app/out/run_be.py /app/data /app/out
