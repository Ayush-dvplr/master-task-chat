#!/bin/bash
# Oracle dispatcher for sentinel-policy-recompute.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] ran the shipped sentinel-ctl, repaired it, and resolved the authoritative policy from /app/data"
echo "[oracle] wrote config.json, report.json, tool.zip, profile_dev.json, profile_prod.json"
echo "[oracle] wrote validation_report.json, summary.json"
