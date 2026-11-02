#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/reconcile.py
python3 /app/out/reconcile.py /app/data /app/out
