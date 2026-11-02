#!/bin/bash
# Oracle dispatcher for 337a1262-8071-57af-95e7-403f0516ae31.
set -euo pipefail

python3 /solution/solve.py
# self-check stage: re-runs the delivered tool on scratch corpora and recomputes delivered values; /app/out is left as written
python3 /solution/solve.py --self-check

echo "[oracle] ran the shipped sentinel-ctl, repaired it, and resolved the authoritative policy from /app/data"
echo "[oracle] wrote /app/out/config.json, /app/out/report.json, /app/out/tool.zip, /app/out/profile_dev.json"
echo "[oracle] wrote /app/out/profile_prod.json, /app/out/validation_report.json, /app/out/summary.json"
