#!/bin/bash
# Oracle dispatcher for 0b27b9dc-7985-54f1-a120-46e6810315a3.
set -euo pipefail

mkdir -p /app/out
# lgactl delivers itself as /app/out/lgactl.py beside the plan it writes.
python3 /solution/solve.py /app/data /app/out

echo "[oracle] wrote the LGA admission plan into /app/out"
