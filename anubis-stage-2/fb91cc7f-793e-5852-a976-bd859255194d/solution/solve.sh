#!/bin/bash
# Oracle dispatcher for the fb91cc7f-793e-5852-a976-bd859255194d.
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/cadence_settle.py
python3 /app/out/cadence_settle.py /app/data /app/out
