#!/bin/bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

mkdir -p /app/out

# The candidate space of every withheld quantity is enumerated into the record
# before a single line of the reusable program is put in place.
python3 - <<'PY'
import glob
import json
import os

slice_text = ""
for name in sorted(glob.glob(os.path.join("/app/data", "*.md"))):
    with open(name, encoding="utf-8") as handle:
        body = handle.read()
    if "| control | published figure |" in body:
        slice_text = body
        break

quantities = []
table = []
for line in slice_text.splitlines():
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) == 4 and cells[0].startswith("`") and " through " in cells[1]:
        low, _, high = cells[1].partition(" through ")
        quantities.append({"name": cells[0].strip("`"), "value": 0,
                           "control": cells[2],
                           "rejected": [{"candidate": step, "falsifier": ""}
                                        for step in range(int(low), int(high) + 1)]})
    if len(cells) == 2 and cells[0].startswith("CTRL-"):
        table.append({"control": cells[0], "published": cells[1].strip("`"),
                      "produced": ""})

with open("/app/out/bottleneck_analysis.json", "w", encoding="utf-8") as handle:
    handle.write(json.dumps({"quantities": quantities, "settling_passes": 0,
                             "calibration_table": table},
                            indent=2, sort_keys=False) + "\n")
PY

cp /solution/solve.py /app/out/optimize.py
chmod 0644 /app/out/optimize.py

python3 /app/out/optimize.py /app/data /app/out

# Every settlement report and the record are cleared once the last withheld
# quantity has settled, then rebuilt in one clean run; the program stays put.
rm -f /app/out/scenario_visible.json
rm -f /app/out/scenario_peak.json
rm -f /app/out/scenario_steady.json
rm -f /app/out/scenario_burst.json
rm -f /app/out/scenario_latency.json
rm -f /app/out/perf_report.json
rm -f /app/out/recommendations.json
rm -f /app/out/data_quality.json
rm -f /app/out/bottleneck_analysis.json

python3 /app/out/optimize.py /app/data /app/out
