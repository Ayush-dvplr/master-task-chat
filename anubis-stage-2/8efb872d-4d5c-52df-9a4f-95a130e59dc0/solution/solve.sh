#!/bin/bash
# Reference run for 8efb872d-4d5c-52df-9a4f-95a130e59dc0: install the optimizer, run the three stages, confirm repeatability.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/build.py
chmod 0755 /app/out/build.py

python3 /app/out/build.py phase1 /app/data /app/out/p1
python3 /app/out/build.py phase2 /app/out/p1 /app/out/p2
python3 /app/out/build.py phase3 /app/out/p1 /app/out/p2 /app/out/p3

for f in p1/nodes.csv p1/properties.csv p1/policies.csv p1/footprints.csv p1/pending.json p1/pops.json \
         p2/pop_rollup.csv p2/class_rollup.csv p2/shield_alloc.csv p2/pin_plan.csv p2/risk_rank.csv p2/manifest.json \
         p3/projection.csv p3/pop_outlook.csv p3/spill_alloc.csv p3/tickets.csv p3/class_drift.csv p3/manifest.json; do
    if [ ! -s "/app/out/$f" ]; then
        echo "solve.sh: /app/out/$f was not produced" >&2
        exit 1
    fi
done

check_dir="$(mktemp -d)"
python3 /app/out/build.py phase2 /app/out/p1 "$check_dir/p2"
python3 /app/out/build.py phase3 /app/out/p1 "$check_dir/p2" "$check_dir/p3"
if ! diff -r /app/out/p2 "$check_dir/p2" > /dev/null || ! diff -r /app/out/p3 "$check_dir/p3" > /dev/null; then
    echo "solve.sh: a second phase 2 or phase 3 run disagrees with /app/out" >&2
    exit 1
fi
rm -rf "$check_dir"
echo "solve.sh: wrote /app/out/build.py and the eighteen phase files"
