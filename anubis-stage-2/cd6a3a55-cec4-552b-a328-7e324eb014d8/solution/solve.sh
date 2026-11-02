#!/bin/bash
# Oracle: repair the close program, install it as /app/out/build.py, then run the one-pass close.
set -euo pipefail

python3 /solution/solve.py
python3 /app/out/build.py /app/data /app/out

test "$(find /app/out -maxdepth 1 -type f | wc -l)" -eq 25 || {
  echo "[oracle] expected build.py and 24 close artifacts" >&2
  exit 4
}
echo "[oracle] repaired the close program and wrote 24 artifacts under /app/out"
