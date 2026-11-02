#!/bin/bash
# Oracle dispatcher for a710b00e-a841-592d-bcbc-5a51d2b0439c.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py --verify-and-answer /app/data /app/out
