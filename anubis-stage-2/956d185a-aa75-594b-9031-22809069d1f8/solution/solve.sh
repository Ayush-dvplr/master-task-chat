#!/bin/bash
# Oracle dispatcher for 956d185a-aa75-594b-9031-22809069d1f8.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_core.json, profile_edge.json, profile_dmz.json, profile_mgmt.json, validation_report.json, summary.json, and tool.zip"
