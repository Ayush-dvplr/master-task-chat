#!/bin/bash
# Oracle dispatcher for 00372225-134c-56e6-80ea-8bd47c66c816.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py

# Run twice into separate trees and diff: the determinism check the rubric rewards.
verify_dir="$(mktemp -d)"
python3 /app/out/derive_report.py /app/data "$verify_dir"
python3 /app/out/derive_report.py /app/data /app/out
for artifact in "$verify_dir"/*; do
    diff -q "$artifact" "/app/out/$(basename "$artifact")"
done
rm -rf "$verify_dir"

echo "objective_value $(python3 -c "import json,sys; print(json.load(open('/app/out/data_quality.json'))['objective_value'])")"
echo "core_sha256 $(python3 -c "import json,sys; print(json.load(open('/app/out/data_quality.json'))['core_sha256'])")"
echo "artifacts written to /app/out"
