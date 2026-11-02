#!/bin/bash
set -euo pipefail

# Inspect representative raw rows before installing the parser.
head -n 2 /app/data/prompt_registry.csv
head -n 1 /app/data/adjudications.jsonl
head -n 3 /app/data/batch_registry.xml

mkdir -p /app/out
cp /solution/solve.py /app/out/build.py
chmod 0755 /app/out/build.py
python3 /app/out/build.py /app/data /app/out

# Check one parsed policy value directly against its raw source line.
python3 - /app/data /app/out <<'PY'
import json
import re
import sys
from pathlib import Path

data_dir, out_dir = map(Path, sys.argv[1:])
policy = (data_dir / "corpus_policy.md").read_text(encoding="utf-8")
raw_line = next(line for line in policy.splitlines() if "| sequence_length |" in line)
raw_value = int(re.fullmatch(r"\| sequence_length \| (\d+) \|", raw_line).group(1))
parsed_value = json.loads((out_dir / "packing_plan.json").read_text())["sequence_length"]
assert parsed_value == raw_value, (parsed_value, raw_line)
print(f"parsed sequence_length={parsed_value}; raw source: {raw_line}")
PY

# Rebuild from an identically populated directory with a different name and
# compare every release artifact byte-for-byte.
verify_root=/app/out/.reference-verification
trap 'rm -rf /app/out/.reference-verification' EXIT
mkdir -p "$verify_root/renamed-corpus" "$verify_root/renamed-release"
cp -a /app/data/. "$verify_root/renamed-corpus/"
python3 /app/out/build.py "$verify_root/renamed-corpus" "$verify_root/renamed-release"
python3 - /app/out "$verify_root/renamed-release" <<'PY'
import sys
from pathlib import Path

left, right = map(Path, sys.argv[1:])
names = (
    "annotator_standing.json", "verdict_admissibility.jsonl",
    "comparison_resolution.jsonl", "agreement.json",
    "prompt_eligibility.jsonl", "dedup_clusters.json",
    "preference_pairs.jsonl", "split_assignment.json", "mixture_plan.json",
    "packing_plan.json", "training_schedule.json", "slice_coverage.json",
    "source_audit.json", "control_reconciliation.json", "release_gates.json",
)
for name in names:
    assert (left / name).read_bytes() == (right / name).read_bytes(), name
print("renamed-directory rebuild matches all fifteen release artifacts")
PY

# Compare the published entity controls with the release reconciliation.
python3 - /app/data /app/out <<'PY'
import json
import re
import sys
from pathlib import Path

data_dir, out_dir = map(Path, sys.argv[1:])
html = (data_dir / "control_totals.html").read_text(encoding="utf-8")
published = {key: int(value) for key, value in re.findall(
    r"<tr><td>(prompts|completions|comparisons|verdicts)</td><td>(\d+)</td></tr>", html
)}
release = json.loads((out_dir / "control_reconciliation.json").read_text())
assert {key: release[key] for key in published} == published
print(f"control totals match: {published}")
PY

rm -rf "$verify_root"
trap - EXIT
echo 'Reusable builder: /app/out/build.py'
echo 'Rebuild command: python3 /app/out/build.py <DATA_DIR> <OUT_DIR>'
