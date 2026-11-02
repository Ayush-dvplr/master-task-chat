#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
who=$1
mkdir -p "/tmp/$who/out"
cp -a /candidate/. "/tmp/$who/out/"
started=$(date +%s)
TEST_OUTPUT_FILE=/b/tests/test_output.py python3 -B /w/run_checks.py "/tmp/$who" "/w/proto/g37_cost_$who.json" > "/w/proto/g37_cost_$who.txt" 2>&1
seconds=$(( $(date +%s) - started ))
python3 -B - "$who" "$seconds" <<'PY'
import json
import sys
from pathlib import Path

who, seconds = sys.argv[1], int(sys.argv[2])
path = Path(f"/w/proto/g37_cost_{who}.json")
result = json.loads(path.read_text())
result["wall_seconds"] = seconds
path.write_text(json.dumps(result, indent=1) + "\n")
print("ALL_DONE", who, seconds, result["earned"], result["positive"], flush=True)
PY
