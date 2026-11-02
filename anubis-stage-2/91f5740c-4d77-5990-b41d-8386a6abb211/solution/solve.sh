#!/bin/bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/app/data}"
OUT_DIR="${OUT_DIR:-/app/out}"

mkdir -p "$OUT_DIR"

cp /solution/solve.py "$OUT_DIR/derive_report.py"

python3 "$OUT_DIR/derive_report.py" "$DATA_DIR" "$OUT_DIR"

for name in derive_report.py summary.json policy_audit.json data_quality.json \
            region_North.json region_South.json region_West.json region_East.json \
            segment_commercial.json segment_public.json; do
    if [ ! -s "$OUT_DIR/$name" ]; then
        echo "missing or empty deliverable: $name" >&2
        exit 1
    fi
done

python3 - "$OUT_DIR" <<'CHECK'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])


def load(name):
    with open(out / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


summary = load("summary.json")
audit = load("policy_audit.json")
quality = load("data_quality.json")

regions = [load("region_%s.json" % name) for name in ("East", "North", "South", "West")]
segments = [load("segment_%s.json" % name) for name in ("commercial", "public")]

if quality["conservation_residual_micros"] != 0:
    raise SystemExit("region conservation residual is non zero")
if quality["segment_residual_micros"] != 0:
    raise SystemExit("segment conservation residual is non zero")
for flag, value in sorted(quality["invariants"].items()):
    if value is not True:
        raise SystemExit("invariant %s is not held" % flag)

if sum(report["order_count"] for report in regions) != summary["orders_placed"]:
    raise SystemExit("region order counts disagree with the summary")
if sum(report["order_count"] for report in segments) != summary["orders_placed"]:
    raise SystemExit("segment order counts disagree with the summary")
if sum(report["totals"]["net_micros"] for report in regions) != summary["net_micros_total"]:
    raise SystemExit("region net totals disagree with the summary")
if sum(report["totals"]["net_micros"] for report in segments) != summary["net_micros_total"]:
    raise SystemExit("segment net totals disagree with the summary")

for entry in audit["candidate_space"]:
    if entry["resolved"] is None:
        raise SystemExit("constant %s stayed unresolved" % entry["parameter"])
    if len(entry["verdicts"]) != entry["domain_size"]:
        raise SystemExit("constant %s records no verdict per candidate" % entry["parameter"])
for row in audit["calibration_comparison"]:
    if row["reproduced"] != row["published"]:
        raise SystemExit("control %s was not reproduced" % row["control"])

print("settlement verified")
CHECK
