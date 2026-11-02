#!/bin/bash
set -euo pipefail
mkdir -p /app/out
python3 -B "${SOLUTION_ROOT:-/solution}/solve.py"
