#!/bin/bash
set -euo pipefail

mkdir -p /app/out
install -m 0644 /solution/solve.py /app/out/optimize.py
python3 /app/out/optimize.py --data /app/data --out /app/out
