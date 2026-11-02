#!/bin/bash
set -euo pipefail

install -m 0755 /solution/solve.py /app/schedule_repair.py
mkdir -p /app/out
python3 /app/schedule_repair.py /app/data /app/out

check_dir="$(mktemp -d)"
python3 /app/schedule_repair.py /app/data "$check_dir"
for report in /app/out/*; do
    cmp -s "$report" "$check_dir/$(basename "$report")" || { echo "nondeterministic report: $report"; false; }
done
rm -rf "$check_dir"

python3 - <<'PYEOF'
import csv
import json

with open("/app/out/occurrences.csv", newline="") as fh:
    count = sum(1 for _row in csv.DictReader(fh))
summary = json.load(open("/app/out/settle_summary.json"))
manifest = json.load(open("/app/out/manifest.json"))
print("occurrences %d, settling rounds %d, stop reason %s, chain head %s"
      % (count, summary["rounds"], summary["stop_reason"], manifest["chain_head"]))
PYEOF
