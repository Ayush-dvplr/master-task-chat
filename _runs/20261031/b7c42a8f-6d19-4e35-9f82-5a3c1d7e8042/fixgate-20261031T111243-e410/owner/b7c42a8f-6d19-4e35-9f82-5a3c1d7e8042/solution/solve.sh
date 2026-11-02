#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/reserving.py
python3 /app/out/reserving.py --data /app/data --out /app/out

# Owner-only variant (QC Step 10): leave every file this run wrote readable by its
# owner alone, the mode an agent editor leaves behind, keeping the owner execute bit.
find /app -xdev -type f -user 1000 -perm -u+x -print0 2>/dev/null | xargs -0 -r chmod 700 || true
find /app -xdev -type f -user 1000 ! -perm -u+x -print0 2>/dev/null | xargs -0 -r chmod 600 || true
