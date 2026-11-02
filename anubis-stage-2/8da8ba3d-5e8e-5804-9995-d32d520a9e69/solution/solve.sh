#!/bin/bash
# Oracle dispatcher for 8da8ba3d-5e8e-5804-9995-d32d520a9e69.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/solve.py"

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_dev.json, profile_prod.json, validation_report.json, summary.json, and tool.zip"
