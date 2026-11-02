#!/bin/bash
# Oracle dispatcher for vendor-archive-roundtrip-recovery.
#
# solve.py IS the reference decoder+encoder - installing it as /app/decode.py
# AND /app/encode.py IS the "solution". After install, verify that every sample
# decodes structurally and every non-damaged capture round-trips byte-identically.
set -euo pipefail
shopt -s nullglob  # no sample/field captures ship post-reshape; the verifier reseeds its own corpus

install -m 0644 /solution/solve.py /app/decode.py
install -m 0644 /solution/solve.py /app/encode.py

mkdir -p /app/out
python3 /app/decode.py --reports-json /app/data/VARC-capture-log.jsonl > /tmp/VARC-reports.json
python3 - <<'PY'
import json
from pathlib import Path

reports = json.loads(Path("/tmp/VARC-reports.json").read_text())
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
echo "[oracle] Phase 0 OK - report artifacts written under /app/out"

# Phase 1 - every sample decodes to a structurally valid document.
sample_count=0
for capture in /app/data/sample_*.varc; do
    python3 - "$capture" <<'PY'
import json, subprocess, sys
capture = sys.argv[1]
produced = subprocess.run(
    ["python3", "/app/decode.py", capture],
    capture_output=True, text=True, check=True,
).stdout
got = json.loads(produced)
if "records" not in got or got.get("record_count") != len(got["records"]):
    sys.exit(f"decoder produced an invalid document for {capture}")
PY
    sample_count=$((sample_count + 1))
done
echo "[oracle] Phase 1 OK - ${sample_count} samples decoded"

# Phase 2 - encoder rebuilds every non-damaged capture byte-identically.
round_count=0
for capture in /app/data/sample_*.varc /app/data/field_*.varc; do
    python3 - "$capture" <<'PY'
import json, subprocess, sys, tempfile, os
capture = sys.argv[1]
decoded = subprocess.run(
    ["python3", "/app/decode.py", capture],
    capture_output=True, text=True, check=True,
).stdout
doc = json.loads(decoded)
# Damaged captures decode to an error dict; skip round-trip on those.
if isinstance(doc, dict) and "error" in doc:
    sys.exit(0)
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
    json.dump(doc, fh)
    doc_path = fh.name
with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fh:
    out_path = fh.name
try:
    subprocess.run(
        ["python3", "/app/encode.py", doc_path, out_path],
        check=True,
    )
    rebuilt = open(out_path, "rb").read()
    original = open(capture, "rb").read()
    if rebuilt != original:
        sys.exit(f"encoder round-trip diverged on {capture}: "
                 f"{len(original)} → {len(rebuilt)} bytes")
finally:
    os.unlink(doc_path)
    os.unlink(out_path)
PY
    round_count=$((round_count + 1))
done
echo "[oracle] Phase 2 OK - ${round_count} captures round-tripped byte-identically"
