#!/bin/bash
# Blind-score install: place the blind's delivered files where the instruction says the agent leaves them.
set -euo pipefail
ROOT="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp -Rp "$ROOT/blind/app/." /app/
cp -Rp "$ROOT/blind/out/." /app/out/
echo "install diff (blind app -> /app, blind out -> /app/out):"
diff -r "$ROOT/blind/out" /app/out && echo "diff out: identical"
for f in "$ROOT"/blind/app/*; do cmp "$f" "/app/$(basename "$f")" && echo "cmp $(basename "$f"): identical"; done
sha256sum /app/transform.py /app/out/*
