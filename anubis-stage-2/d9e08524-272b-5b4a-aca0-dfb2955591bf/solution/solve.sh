#!/bin/bash
# Oracle dispatcher for d9e08524-272b-5b4a-aca0-dfb2955591bf.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/optimize.py
python3 /app/out/optimize.py /app/data /app/out
rm -f /app/out/*.json
python3 /app/out/optimize.py /app/data /app/out
rm -rf /tmp/registry-replay
mkdir -p /tmp/registry-replay/mirror /tmp/registry-replay/out
cp -a /app/data/. /tmp/registry-replay/mirror/
python3 /app/out/optimize.py /tmp/registry-replay/mirror /tmp/registry-replay/out
for produced in /app/out/*.json; do cmp "$produced" "/tmp/registry-replay/out/$(basename "$produced")"; done
