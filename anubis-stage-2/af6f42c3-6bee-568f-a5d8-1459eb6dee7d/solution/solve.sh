#!/bin/bash
# Oracle dispatcher for af6f42c3-6bee-568f-a5d8-1459eb6dee7d.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] repaired CLI and wrote /app/out/config.json + /app/out/report.json"
echo "[oracle] wrote profile_core.json, profile_edge.json, profile_dmz.json, profile_mgmt.json, validation_report.json, summary.json, and tool.zip"
echo "[oracle] re-ran compile into /tmp/sealb-verify and confirmed every artifact is byte-identical across the two runs"
