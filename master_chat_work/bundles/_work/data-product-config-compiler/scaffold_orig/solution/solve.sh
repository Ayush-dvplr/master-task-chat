#!/bin/bash
# Oracle dispatcher for data-product-config-compiler.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_dev.json, profile_prod.json, validation_report.json, summary.json, and tool.zip"
