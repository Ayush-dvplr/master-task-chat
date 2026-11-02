#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /app/out
install -m 0755 "$HERE/solve.py" /app/out/derive_report.py
python3 /app/out/derive_report.py --data /app/data --out /app/out
