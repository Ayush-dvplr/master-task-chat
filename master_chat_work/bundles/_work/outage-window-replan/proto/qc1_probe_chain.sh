#!/bin/bash
# before tests: R_check_order_first alone, then TS-24 probe; after tests: TS-24 probe
mkdir -p /app && cp -r /srcdata /app/data
rm -rf /app/out && mkdir -p /app/out; cp /d/mut/R_check_order_first.py /app/out/derive_report.py
python3 -B /app/out/derive_report.py --data /app/data --out /app/out > /dev/null 2>&1
python3 -B /d/proto/drive_tests.py /d/qc1_before_tests/test_output.py > /d/mutlogs_qc1_before/R_check_order_first.log 2>/dev/null
echo "MUT R_check_order_first | $(grep '^SCORE' /d/mutlogs_qc1_before/R_check_order_first.log) | $(grep '^CHECK' /d/mutlogs_qc1_before/R_check_order_first.log | awk '/ FAIL /{print $2}' | tr '\n' ',')"
