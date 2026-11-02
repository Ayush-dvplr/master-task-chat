#!/bin/bash
# Oracle for 56fe3bdd-00c6-5b13-a5c8-90a94ccc475e: install the reference engine and run it on the shipped estate.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/evalctl.py
python3 /app/out/evalctl.py /app/data /app/out
