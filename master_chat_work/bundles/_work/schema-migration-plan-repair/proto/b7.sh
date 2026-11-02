#!/bin/sh
# Scratch: wave-1 B7, the whole tests channel on the Opus a4 deliverable (verifier image, root, tests copy at /t).
set -u
export PYTHONDONTWRITEBYTECODE=1
mkdir -p /app
cp -a /src_app/out /app/out
echo "== start $(date +%s)"
TEST_OUTPUT_FILE=/t/test_output.py python3 -B /w/run_checks.py /app /w/proto/b7_opus.json
echo "== end $(date +%s)"
echo ALL_DONE
