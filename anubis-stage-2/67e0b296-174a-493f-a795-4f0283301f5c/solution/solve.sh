#!/bin/bash
# Oracle: install the reference compiler, build the three stages, and run the release checks.
set -euo pipefail

verify_root=/tmp/sentinel-release-verify
manifest_before=/tmp/sentinel-inputs-before.sha256
manifest_after=/tmp/sentinel-inputs-after.sha256

find /app/data /app/contract -type f -print0 | sort -z | xargs -0 sha256sum > "$manifest_before"

mkdir -p /app/out
cp /solution/solve.py /app/out/build.py
python3 /app/out/build.py phase1 /app/data /app/out/p1
python3 /app/out/build.py phase2 /app/out/p1 /app/out/p2
python3 /app/out/build.py phase3 /app/out/p1 /app/out/p2 /app/out/p3

find /app/data /app/contract -type f -print0 | sort -z | xargs -0 sha256sum > "$manifest_after"
cmp "$manifest_before" "$manifest_after"

# One clean build simultaneously proves path independence and read-only upstream handling.
mkdir -p "$verify_root/data"
cp -a /app/data/. "$verify_root/data/"
find "$verify_root/data" -type f -exec chmod 0444 {} +
find "$verify_root/data" -type d -exec chmod 0555 {} +
cd /tmp
python3 /app/out/build.py phase1 "$verify_root/data" "$verify_root/p1"
find "$verify_root/p1" -type f -exec chmod 0444 {} +
chmod 0555 "$verify_root/p1"
python3 /app/out/build.py phase2 "$verify_root/p1" "$verify_root/p2"
find "$verify_root/p2" -type f -exec chmod 0444 {} +
chmod 0555 "$verify_root/p2"
python3 /app/out/build.py phase3 "$verify_root/p1" "$verify_root/p2" "$verify_root/p3"

for phase in p1 p2 p3; do
    for delivered in "/app/out/$phase"/*; do
        cmp "$delivered" "$verify_root/$phase/$(basename "$delivered")"
    done
done

# A short record must produce the controlled input-error form, never a traceback.
mkdir -p "$verify_root/malformed"
for source in /app/data/*; do
    ln -s "$source" "$verify_root/malformed/$(basename "$source")"
done
cp --remove-destination /app/data/pdu_hall_a.csv "$verify_root/malformed/pdu_hall_a.csv"
printf 'broken,row\n' >> "$verify_root/malformed/pdu_hall_a.csv"
malformed_code=0
if python3 /app/out/build.py phase1 "$verify_root/malformed" "$verify_root/malformed-out" \
        > "$verify_root/malformed.stdout" 2> "$verify_root/malformed.stderr"; then
    malformed_code=0
else
    malformed_code=$?
fi
test "$malformed_code" -eq 3
test "$(wc -l < "$verify_root/malformed.stderr")" -eq 1
if grep -q Traceback "$verify_root/malformed.stderr"; then
    exit 1
fi

# Recompute every byte-level lineage value with a separate reader.
python3 - /app/out <<'PY'
import configparser
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])

def facts(path):
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "lines": raw.count(b"\n")}

p2 = json.loads((root / "p2/fleet_summary.json").read_text())["inputs"]
assert p2 == {f"p1/{p.name}": facts(p) for p in sorted((root / "p1").iterdir()) if p.is_file()}

expected = {}
for phase in ("p1", "p2"):
    expected.update({f"{phase}/{p.name}": facts(p) for p in sorted((root / phase).iterdir()) if p.is_file()})
for name in ("pdu_alarms.json", "chargeback.json", "exceptions.json", "capacity.json", "release.json"):
    assert json.loads((root / "p3" / name).read_text())["lineage"] == expected
ini = configparser.ConfigParser()
ini.read(root / "p3/bmc_caps.ini")
assert dict(ini["lineage"]) == {
    key: f'{value["sha256"]}:{value["bytes"]}:{value["lines"]}' for key, value in expected.items()
}
print("phase-2 lineage: 6 matched; phase-3 lineage: 12 matched in every document")
PY

# Recalculate one rack's N+1 count directly from the phase-1 tables.
python3 - /app/out <<'PY'
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
read = lambda name: list(csv.DictReader((root / "p1" / name).open()))
rack = "den1-r02"
hosts = [row for row in read("hosts.csv") if row["rack_id"] == rack]
demand = {row["host_id"]: row for row in read("demand.csv")}
rated = {row["psu_model"]: int(row["rated_w"]) for row in read("psu.csv")}
calculated = sum(
    1 for host in hosts
    if host["psu_count"] == "2"
    and demand[host["host_id"]]["p95_w"] != ""
    and float(demand[host["host_id"]]["p95_w"]) <= rated[host["psu_model"]]
)
reported = {
    row["rack_id"]: int(row["psu_n1_ok"])
    for row in csv.DictReader((root / "p2/rack_budget.csv").open())
}[rack]
assert calculated == reported
print(f"{rack} psu_n1_ok: {calculated} matched")
PY

for file in p1/hosts.csv p1/circuits.csv p1/demand.csv p1/psu.csv p1/registry.json p1/amendments.csv \
            p2/rack_budget.csv p2/host_alloc.csv p2/site_energy.csv p2/circuit_alarms.csv p2/tenant_pool.csv \
            p2/fleet_summary.json p3/bmc_caps.ini p3/pdu_alarms.json p3/chargeback.json p3/exceptions.json \
            p3/capacity.json p3/release.json; do
    test -s "/app/out/$file"
done

echo "[oracle] source conflicts: none"
echo "[oracle] release-verification mismatches: none"
echo "[oracle] wrote /app/out/build.py and the eighteen stage files"
