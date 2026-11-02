#!/bin/bash
# Oracle dispatcher for 9f9d7ac2-9e52-58fa-b8e9-7e95c068b549.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_core.json, profile_edge.json, profile_dmz.json, profile_mgmt.json, validation_report.json, summary.json, and tool.zip"
