#!/bin/bash
# Oracle dispatcher for {{BUNDLE_NAME}}.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/optimize.py
python3 /app/out/optimize.py /app/data/events.csv /app/data/rules.json > /tmp/{{FORMAT_TAG}}_sample.json
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path('/tmp/{{FORMAT_TAG}}_sample.json').read_text())
if not data.get('event_count') or not data.get('account_totals'):
    raise SystemExit('oracle sample aggregation failed')
PY
python3 /app/out/optimize.py /app/data /app/out
