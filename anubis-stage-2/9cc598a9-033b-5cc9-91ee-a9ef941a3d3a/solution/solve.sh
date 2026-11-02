#!/bin/bash
# Oracle: repair the shipped project, keep its test suite passing, package it, and let the repaired package
# itself write the five restore deliverables from /app/data into /app/out.
set -euo pipefail

rm -rf /app/project
mkdir -p /app/out
python3 /solution/solve.py /app/project
cd /app/project
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -t .
python3 /solution/solve.py --zip /app/project /app/out/package.zip
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m restorekit restore --feed /app/data --out /app/out
echo "[oracle] package.zip and the five deliverables written under /app/out"
