#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/arena.py
python3 /app/out/arena.py /app/data /app/out
