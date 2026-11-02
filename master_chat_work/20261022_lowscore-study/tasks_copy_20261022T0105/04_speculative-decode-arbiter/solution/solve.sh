#!/bin/bash
set -euo pipefail

# Oracle entry point. Runs the replay, drives the control plane service over
# both of its channels and prints the closing summary.
python3 "$(dirname "$0")/solve.py" --oracle --data /app/data --out /app/out
