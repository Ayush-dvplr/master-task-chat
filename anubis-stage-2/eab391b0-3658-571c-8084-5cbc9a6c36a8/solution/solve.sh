#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/lockres.py
python3 /app/out/lockres.py /app/data /app/out
