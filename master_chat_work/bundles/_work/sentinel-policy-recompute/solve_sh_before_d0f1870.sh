#!/bin/bash
# Oracle dispatcher for sentinel-policy-recompute.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] ran the shipped sentinel-ctl, repaired it, and resolved the authoritative policy from /app/data"
echo "[oracle] wrote /app/out/config.json, /app/out/report.json, /app/out/tool.zip, /app/out/profile_dev.json"
echo "[oracle] wrote /app/out/profile_prod.json, /app/out/validation_report.json, /app/out/summary.json"
