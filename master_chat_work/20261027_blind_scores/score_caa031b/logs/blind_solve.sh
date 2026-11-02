#!/bin/bash
# Blind-score install: place blind 4f7606c's delivered files where the instruction says the agent leaves them.
set -euo pipefail
S="${SOLUTION_ROOT:-/solution}/blind"
rm -rf /app/repo
cp -R "$S/app/repo" /app/repo
cp "$S/app/build_outputs.py" /app/build_outputs.py
mkdir -p /app/out
cp -R "$S/out/." /app/out/
chown -R 1000:1000 /app/repo /app/build_outputs.py /app/out 2>/dev/null || true
echo "=== INSTALLED SHA256 ==="
cd /app && find repo out build_outputs.py -type f | LC_ALL=C sort | xargs sha256sum
