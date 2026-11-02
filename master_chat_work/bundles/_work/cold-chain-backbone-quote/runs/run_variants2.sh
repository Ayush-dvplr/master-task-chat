#!/bin/bash
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
for v in nop copier kmb greedy perlink report_only; do
  echo "=== $v $(date +%T)"
  python3 -B variants.py /tmp/ccapp $v /tmp/ccvar/$v || { echo "BUILD FAIL $v"; continue; }
  python3 -B run_local_tests.py /tmp/ccvar/$v 2> runs/variant_$v.err | grep -E "SCORE|RESULTS"
done
echo ALL_DONE
