#!/bin/bash
# Oracle dispatcher for 5048c412-d327-5667-8375-624261697644.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
