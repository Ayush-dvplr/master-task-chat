#!/bin/bash
# Oracle dispatcher for 11750b7a-a240-5905-a4f7-adbdadbb7c9a.
#
# solve.py is the reference decoder+encoder: it is installed as both
# /app/decode.py and /app/encode.py, then run once over the shipped capture
# log to write the four /app/out report artifacts.
set -euo pipefail

install -m 0644 /solution/solve.py /app/decode.py
install -m 0644 /solution/solve.py /app/encode.py

mkdir -p /app/out
python3 /app/decode.py --reports-json /app/data/SEALB-capture-log.jsonl > /tmp/SEALB-reports.json
python3 - <<'PY'
import json
from pathlib import Path

reports = json.loads(Path("/tmp/SEALB-reports.json").read_text())
if not reports["roundtrip_report"]["all_roundtrips_equal"]:
    raise SystemExit("own examples do not round-trip byte for byte")
out = Path("/app/out")
with (out / "decoded_examples.jsonl").open("w", encoding="utf-8") as handle:
    for item in reports["decoded_examples"]:
        handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
for name in ("format_report", "roundtrip_report", "error_analysis"):
    (out / f"{name}.json").write_text(
        json.dumps(reports[name], sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
PY
echo "[oracle] decode.py, encode.py and the four report artifacts are in place"
