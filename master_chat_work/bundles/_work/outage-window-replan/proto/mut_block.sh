#!/bin/bash
# Docker: mounts /srcdata (bundle data), /tests (bundle tests), /d (WORK). Runs every mutant through the real tests.
mkdir -p /app && cp -r /srcdata /app/data
cd /d
for m in mut/*.py; do
  id=$(basename "$m" .py)
  rm -rf /app/out && mkdir -p /app/out
  cp "$m" /app/out/derive_report.py
  python3 -B /app/out/derive_report.py --data /app/data --out /app/out > /dev/null 2>&1
  python3 -B proto/drive_tests.py /tests/test_output.py > "mutlogs/$id.log" 2>/dev/null
  score=$(grep '^SCORE' "mutlogs/$id.log")
  fails=$(grep '^CHECK' "mutlogs/$id.log" | awk '/ FAIL /{print $2}' | tr '\n' ',')
  echo "MUT $id | $score | $fails"
done
echo ALL_DONE
