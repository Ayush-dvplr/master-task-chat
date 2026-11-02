#!/bin/bash
# Oracle dispatcher for b42c61b9-698f-5667-a335-85a1da8d5b76.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/run_readout.py
python3 /app/out/run_readout.py /app/data /app/out
