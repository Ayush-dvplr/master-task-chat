#!/bin/sh
# /w = WORK, /b = bundle (ro). Oracle and unrepaired-forgery tests-only timings with the budget instrumented.
set -u
export PYTHONDONTWRITEBYTECODE=1
python3 -B /w/p12v13/timing/inst.py /b/tests/test_output.py /tmp/test_inst.py
mkdir -p /tmp/o && cp -a /b/environment/repo /b/environment/ci /tmp/o/
T=$(date +%s); APP_ROOT=/tmp/o python3 -B /b/solution/solve.py > /tmp/o_solve.log 2>&1; echo "oracle solve rc $? secs $(( $(date +%s) - T ))"
T=$(date +%s); TEST_OUTPUT_FILE=/tmp/test_inst.py python3 -B /w/run_checks.py /tmp/o /w/p12v13/timing/oracle.json > /w/p12v13/timing/oracle.txt 2>&1; echo "oracle tests rc $? secs $(( $(date +%s) - T ))"
tail -2 /w/p12v13/timing/oracle.txt
rm -rf /app && mkdir -p /app && cp -a /b/environment/repo /b/environment/ci /app/
python3 -B /w/p12v13/timing/forge.py > /tmp/forge.log 2>&1; echo "forge rc $?"
T=$(date +%s); TEST_OUTPUT_FILE=/tmp/test_inst.py python3 -B /w/run_checks.py /app /w/p12v13/timing/forge.json > /w/p12v13/timing/forge.txt 2>&1; echo "forge tests rc $? secs $(( $(date +%s) - T ))"
tail -2 /w/p12v13/timing/forge.txt
echo ALL_DONE
