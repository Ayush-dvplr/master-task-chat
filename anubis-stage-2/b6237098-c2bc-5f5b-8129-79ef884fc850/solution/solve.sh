#!/bin/bash
# Oracle dispatcher for b6237098-c2bc-5f5b-8129-79ef884fc850.
#
# solve.py is the reference decoder and encoder. The 4.x field-build
# parameters are recovered first from the 4.x notes' keystream bytes and the
# verified decodings; the 5.x parameters from the raw 5.x captures in the log
# and the 5.x fingerprints. Both sets are written into the codec, which is
# installed as both /app/decode.py and /app/encode.py. The reports are built by
# a temporary copy of that codec from the oracle's own examples and from
# decoding the shipped capture log, so the installed programs never open
# /app/data, and
# every example is round-tripped through the installed programs as a final
# self-check.
set -euo pipefail

python3 -I /solution/solve.py --derive-field-builds /app/data > /tmp/MDUMP-field-builds.json
python3 - <<'PY'
import json
from pathlib import Path

builds = json.loads(Path("/tmp/MDUMP-field-builds.json").read_text())
source = Path("/solution/solve.py").read_text()
assert source.count("\nFIELD_BUILDS = None\n") == 1
source = source.replace("\nFIELD_BUILDS = None\n", f"\nFIELD_BUILDS = {builds!r}\n")
for target in ("/app/decode.py", "/app/encode.py", "/tmp/MDUMP-codec.py"):
    Path(target).write_text(source)
    Path(target).chmod(0o644)
PY
rm -f /tmp/MDUMP-field-builds.json

mkdir -p /app/out
python3 -I /tmp/MDUMP-codec.py --reports-json /app/data/MDUMP-capture-log.jsonl > /tmp/MDUMP-reports.json
rm -f /tmp/MDUMP-codec.py
python3 - <<'PY'
import json
from pathlib import Path

reports = json.loads(Path("/tmp/MDUMP-reports.json").read_text())
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
rm -f /tmp/MDUMP-reports.json
echo "[oracle] reports written under /app/out"

python3 - <<'PY'
import json, os, subprocess, tempfile
from pathlib import Path

rows = [json.loads(line) for line in Path("/app/out/decoded_examples.jsonl").read_text().splitlines()]
with tempfile.TemporaryDirectory() as td:
    for row in rows:
        capture = Path(td) / "example.trc"
        capture.write_bytes(bytes.fromhex(row["hex"]))
        decoded = json.loads(subprocess.run(["python3", "-I", "/app/decode.py", str(capture)],
                                            capture_output=True, text=True, check=True).stdout)
        assert decoded == row["decoded"], row["name"]
        doc = Path(td) / "doc.json"
        doc.write_text(json.dumps(decoded))
        rebuilt = Path(td) / "rebuilt.trc"
        subprocess.run(["python3", "-I", "/app/encode.py", str(doc), str(rebuilt)], check=True)
        assert rebuilt.read_bytes() == capture.read_bytes(), row["name"]
print(f"[oracle] {len(rows)} examples round-tripped through the installed programs")
PY
