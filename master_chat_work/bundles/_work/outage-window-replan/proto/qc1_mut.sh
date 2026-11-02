#!/bin/bash
# P12 qc1: run every mutant through the mounted tests; logs to /d/$1
LD="$1"; mkdir -p /app && cp -r /srcdata /app/data
cd /d; mkdir -p "$LD"
for m in mut/*.py; do
  id=$(basename "$m" .py); rm -rf /app/out && mkdir -p /app/out; cp "$m" /app/out/derive_report.py
  python3 -B /app/out/derive_report.py --data /app/data --out /app/out > /dev/null 2>&1
  python3 -B proto/drive_tests.py /tests/test_output.py > "$LD/$id.log" 2>/dev/null
  echo "MUT $id | $(grep '^SCORE' $LD/$id.log) | $(grep '^CHECK' $LD/$id.log | awk '/ FAIL /{print $2}' | tr '\n' ',')"
done
echo ALL_DONE
