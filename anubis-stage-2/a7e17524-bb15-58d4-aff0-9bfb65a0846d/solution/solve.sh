#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/out

if [ -f /solution/solve.py ]; then
  python3 /solution/solve.py
else
  python3 "$HERE/solve.py"
fi

echo "[relay-gate] the seven cycle artifacts for RC-2411 now sit under /app/out"
