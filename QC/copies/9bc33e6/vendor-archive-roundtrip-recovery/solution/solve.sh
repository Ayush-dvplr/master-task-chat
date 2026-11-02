#!/bin/bash
set -euo pipefail

# Build self-contained decode.py and encode.py with the field schema baked in
# (the programs may not read /app/data at grade time), then emit the reports.
python3 /solution/solve.py --build /app/data /app/decode.py /app/encode.py
mkdir -p /app/out
python3 /solution/solve.py --emit-reports /app/data /app/out
