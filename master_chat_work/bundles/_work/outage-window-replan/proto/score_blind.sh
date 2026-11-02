#!/bin/bash
# Score one blind program on the final tests/test_output.py.
# Mounts: /srcdata (bundle environment/data, ro), /tests (bundle tests, ro),
# /blind (BLIND_DIR, ro), /d (WORK).
set -u
mkdir -p /app/out
cp -r /srcdata /app/data
if [ -f /blind/app/derive_report.py ]; then
  cp /blind/app/derive_report.py /app/out/derive_report.py
elif [ -f /blind/out/derive_report.py ]; then
  cp /blind/out/derive_report.py /app/out/derive_report.py
else
  echo "NO_PROGRAM in /blind/app or /blind/out"
fi
cp /blind/out/*.json /app/out/ 2>/dev/null || echo "NO_DELIVERED_JSON in /blind/out"
ls -l /app/out
cd /d/proto
python3 -B score_blind.py /tests/test_output.py
echo ALL_DONE
