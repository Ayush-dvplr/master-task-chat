#!/bin/bash
# Oracle dispatcher for b5ab455b-75fd-5b57-8ace-7c8ba50e866e.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_dev.json, profile_prod.json, validation_report.json, summary.json, and tool.zip"
