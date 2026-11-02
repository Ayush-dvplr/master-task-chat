#!/bin/bash
# Oracle dispatcher for ceadc676-2dc1-5575-80d7-b145aba9b5f1.
set -euo pipefail

mkdir -p /app/out
cp "${SOLUTION_ROOT:-/solution}/solve.py" /app/out/run_irms.py
python3 /app/out/run_irms.py /app/data /app/out
