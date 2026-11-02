#!/bin/bash
# Reference run: install the program and settle the shipped extract.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/optimize.py
python3 -B /app/out/optimize.py /app/data /app/out
