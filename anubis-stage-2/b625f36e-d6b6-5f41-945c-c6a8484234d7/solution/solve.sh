#!/bin/bash
set -euo pipefail
DATA="${MG_DATA:-/app/data}"
OUT="${MG_OUT:-/app/out}"
mkdir -p "$OUT"
# The reusable program is the deliverable, so place it at its declared path and
# run that copy. It then reads nothing outside the directory --data names.
cp "$(dirname "$0")/solve.py" "$OUT/materialize.py"
python3 "$OUT/materialize.py" --data "$DATA" --out "$OUT"
