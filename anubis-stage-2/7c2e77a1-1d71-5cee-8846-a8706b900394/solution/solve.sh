#!/bin/bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0

mkdir -p /app/out
python3 /solution/solve.py /app/data /app/out
