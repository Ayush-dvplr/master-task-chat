#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /tmp/g37-oracle
cp -a /b/environment/repo /b/environment/ci /tmp/g37-oracle/
APP_ROOT=/tmp/g37-oracle python3 -B /b/solution/solve.py
mkdir -p /w/proto/g37_oracle_out
cp -a /tmp/g37-oracle/out/. /w/proto/g37_oracle_out/
TEST_OUTPUT_FILE=/b/tests/test_output.py python3 -B /w/run_checks.py /tmp/g37-oracle /w/proto/g37_cost_oracle.json
echo ALL_DONE
