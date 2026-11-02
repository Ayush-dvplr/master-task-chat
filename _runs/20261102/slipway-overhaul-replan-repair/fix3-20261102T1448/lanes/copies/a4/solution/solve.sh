#!/bin/bash
# Re-score lane: the a4 trajectory's delivered /app/out, unchanged.
set -euo pipefail
S="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp "$S"/a4out/* /app/out/
ls -l /app/out | head -40
