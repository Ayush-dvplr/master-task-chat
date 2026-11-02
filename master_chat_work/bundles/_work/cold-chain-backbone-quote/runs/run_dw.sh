#!/bin/bash
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
echo "=== dw $(date +%T)"
python3 -B variants.py /tmp/ccapp dw /tmp/ccvar/dw || echo "BUILD FAIL dw"
python3 -B run_local_tests.py /tmp/ccvar/dw 2> runs/variant_dw.err | tail -30
echo ALL_DONE
