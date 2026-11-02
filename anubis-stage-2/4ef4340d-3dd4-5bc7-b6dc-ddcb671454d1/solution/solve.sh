#!/bin/bash
# Oracle for 4ef4340d-3dd4-5bc7-b6dc-ddcb671454d1.
#
# solve.py is the reference decoder and encoder; it is installed as both
# /app/decode.py and /app/encode.py. The four report artifacts are generated
# from the codec's own illustrative examples and the shipped capture log. Two
# self-checks follow: every capture in the log that decodes to a document is
# rebuilt byte for byte, and the installed programs round-trip each
# illustrative example through their command lines.
set -euo pipefail

install -m 0644 /solution/solve.py /app/decode.py
install -m 0644 /solution/solve.py /app/encode.py

mkdir -p /app/out
python3 /app/decode.py --reports-json /app/data/POLYP-capture-log.jsonl > /tmp/POLYP-reports.json
python3 - <<'PY'
import json
from pathlib import Path

reports = json.loads(Path("/tmp/POLYP-reports.json").read_text())
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
echo "[oracle] report artifacts written under /app/out"

# Self-check 1: every capture in the log that decodes to a document is rebuilt byte for byte.
python3 - <<'PY'
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("polyp_codec", "/app/decode.py")
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)

checked = 0
for line in Path("/app/data/POLYP-capture-log.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    blob = bytes.fromhex(row["hex"])
    doc = codec.decode(blob)
    if "error" in doc:
        continue
    if codec.encode(doc) != blob:
        sys.exit(f"encoder round trip diverged on {row['capture_id']}")
    checked += 1
print(f"[oracle] {checked} decodable captures rebuilt byte for byte")
PY

# Self-check 2: the installed programs round-trip each illustrative example through their command lines.
python3 - <<'PY'
import json
import subprocess
import sys
import tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp(prefix="polyp-oracle-"))
lines = Path("/app/out/decoded_examples.jsonl").read_text(encoding="utf-8").splitlines()
for number, line in enumerate(lines):
    row = json.loads(line)
    original = bytes.fromhex(row["hex"])
    capture = work / f"example_{number}.vcm"
    capture.write_bytes(original)
    printed = subprocess.run(
        ["python3", "/app/decode.py", str(capture)],
        capture_output=True, text=True, check=True,
    ).stdout
    decoded = json.loads(printed)
    if decoded != row["decoded"]:
        sys.exit(f"decoder output differs from decoded_examples.jsonl for {row['name']}")
    document = work / f"example_{number}.json"
    document.write_text(json.dumps(decoded), encoding="utf-8")
    rebuilt = work / f"example_{number}.rebuilt.vcm"
    subprocess.run(["python3", "/app/encode.py", str(document), str(rebuilt)], check=True)
    if rebuilt.read_bytes() != original:
        sys.exit(f"encoder round trip diverged on {row['name']}")
print(f"[oracle] {len(lines)} illustrative examples round-trip through /app/decode.py and /app/encode.py")
PY
