#!/bin/bash
# Oracle dispatcher for 9e96e588-55bc-5e39-8eb7-134bec04dd22.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_core.json, profile_edge.json, profile_dmz.json, profile_mgmt.json, validation_report.json, summary.json, and tool.zip"
