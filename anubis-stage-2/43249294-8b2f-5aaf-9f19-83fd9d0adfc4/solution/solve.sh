#!/bin/bash
# Oracle dispatcher for 43249294-8b2f-5aaf-9f19-83fd9d0adfc4.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
