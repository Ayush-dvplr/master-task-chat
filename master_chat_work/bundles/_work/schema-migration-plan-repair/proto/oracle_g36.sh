#!/bin/sh
# Scratch: oracle solve + full tests in the verifier image (gate v3.6). Mounts /w WORK, /b bundle (ro).
set -u
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /tmp/o && cp -a /b/environment/repo /b/environment/ci /tmp/o/
s=$(date +%s); APP_ROOT=/tmp/o python3 -B /b/solution/solve.py > /w/proto/g36_oracle_solve.log 2>&1; echo "oracle solve rc $? secs $(( $(date +%s) - s ))"
grep "probe" /w/proto/g36_oracle_solve.log
s=$(date +%s); TEST_OUTPUT_FILE=/b/tests/test_output.py python3 -B /w/run_checks.py /tmp/o /w/proto/g36_cost_o.json > /w/proto/g36_cost_o.txt 2>&1
echo "RUN o rc $? secs $(( $(date +%s) - s )) $(tail -1 /w/proto/g36_cost_o.txt)"
echo ALL_DONE
