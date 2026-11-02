#!/bin/bash
# Repair pagerecover, build /app/out/package.zip and recover the book with it.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
python3 -B /solution/solve.py
