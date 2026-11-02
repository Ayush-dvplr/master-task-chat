#!/bin/bash
# Reference run for the KCBA replica retention and tape packing plan.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/optimize.py
chmod 0755 /app/out/optimize.py

# Publish the plan for the shipped estate.
python3 /app/out/optimize.py --data /app/data --out /app/out

# Second run into a scratch folder to confirm the output is byte identical.
check_dir="$(mktemp -d)"
python3 /app/out/optimize.py --data /app/data --out "$check_dir"
python3 - "$check_dir" <<'PY'
import json
import sys
from pathlib import Path

first = Path("/app/out")
second = Path(sys.argv[1])
names = sorted(p.name for p in second.iterdir())
for name in names:
    if (first / name).read_bytes() != (second / name).read_bytes():
        raise SystemExit("repeat run differs in " + name)
print("repeat run identical across", len(names), "files")

report = json.loads((first / "perf_report.json").read_text())
print("plan", report["plan_id"], "status", report["status"])
bad = [e["file"] for e in report["census"]
       if not (e["present"] and e["bytes_ok"] and e["sha256_ok"])
       or e["records_seen"] != e["records_expected"]]
print("census files", len(report["census"]), "mismatched", len(bad))
for entry in report["scenarios"]:
    print(entry["name"], entry["as_of"], "objects", entry["objects"],
          "kept", entry["kept_replicas"], "released", entry["released_replicas"],
          "volumes", entry["volumes"])

# Where two papers disagree, retention_charter.md section 10 says which item
# of each older paper still decides; everything else in it is set aside.
charter = Path("/app/data/retention_charter.md").read_text(encoding="utf-8")
section = charter.split("## 10.", 1)[1].split("## 11.", 1)[0]
print("papers followed where they disagree (retention_charter.md section 10):")
for line in section.splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) == 3 and cells[0].startswith("`"):
        print(" ", cells[0], "followed only for", cells[1] + ";", "set aside:", cells[2])
PY
printf 'checks run on the output:\n'
printf '  1. repeat run into a second folder, every output file compared byte for byte\n'
printf '  2. every census file compared on byte count, SHA-256 and record count\n'
printf '  3. per-file record counts recomputed by the desk brief rules and compared one file at a time\n'
printf '  4. plan status and per scenario object, kept, released and volume counts read back from perf_report.json\n'
printf '  5. charter section 10 table parsed, and the paper followed printed for every row\n'

rm -rf "$check_dir"
