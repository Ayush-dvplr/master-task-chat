#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/prune.py
python3 /app/out/prune.py /app/data /app/out
