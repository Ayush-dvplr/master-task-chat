#!/bin/bash
# Oracle dispatcher for sensor-network-lsq-correlated-adjustment.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out

# Own-input recomputes, written apart from derive_report.py (judge R9-R11).
PYTHONDONTWRITEBYTECODE=1 python3 - /app/data /app/out <<'PY'
import json
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, sys.argv[2])
import derive_report as d

data, out = Path(sys.argv[1]), Path(sys.argv[2])

# kept record per obs_id: highest shard revision
kept = {}
for rec, decl, shard in d.shard_records(data):
    ident = rec["obs_id"]
    if d.is_true(decl.get("transpose_ids")) and rec["epoch"].strip() == "2":
        ident = ident[-3:] + ident[:-3]
    rev = int(decl["revision"])
    if ident not in kept or rev > kept[ident][0]:
        kept[ident] = (rev, shard, rec)
district = {name: dist for (name, _), dist in zip(d.SHARDS, d.DISTRICTS)}
factors = d.unit_factors(data)
observations, _ = d.load_observations(data)
used = {o.ident: o for o in observations}

# R9: absorbed closure of the first district and epoch in the register
row = d.table_rows(data / "traverse_closure_register.csv")[0]
closure, floor = int(row["closure_micrometres"]), int(row["floor_micrometres"])
legs = sorted((i, int(abs(Fraction(r["computed_nominal"].strip()) * factors[r["unit"].strip()])))
              for i, (_, s, r) in kept.items()
              if r["kind"] == "length" and district[s] == row["district"]
              and int(r["epoch"]) == int(row["epoch"]))
magnitude = abs(closure)


def lr(total, members):
    weight = sum(b for _, b in members)
    whole = {i: total * b // weight for i, b in members}
    order = sorted(members, key=lambda m: (-((total * m[1]) % weight), m[0]))
    for i, _ in order[:total - sum(whole.values())]:
        whole[i] += 1
    return whole


if magnitude == 0:
    got = {i: 0 for i, _ in legs}
elif sum(b for _, b in legs) <= magnitude:
    got = dict(legs)
else:
    got = lr(magnitude, legs)
    held = [(i, b) for i, b in legs if got[i] >= floor]
    if len(held) < len(legs):
        got = {i: 0 for i, _ in legs}
        if held:
            got.update(lr(magnitude, held))
sign = 1 if closure > 0 else -1
assert all(used[i].absorbed == sign * got[i] for i, _ in legs), "R9 mismatch"
print(f"check R9 ok: {row['district']} epoch {row['epoch']} absorbed "
      f"{sign * sum(got.values())} of {closure} micrometres over {len(legs)} lengths")

# R10: centring variance of every station, walking set_out_from iteratively
marks = {r["mark_id"]: r for r in d.table_rows(data / "control_mark_register.csv")}
program = d.centring_variances(data)
seen = set()
for r in d.table_rows(data / "station_registry.csv"):
    ordinal = int(r["ordinal"])
    if r["mark_status"] != "active" or ordinal in seen:
        continue
    seen.add(ordinal)
    total, node = Fraction(0), r
    while node is not None:
        if node["mount"] == "tripod":
            total += (Fraction(node["centring_mm"]) / 1000) ** 2
        parent = (node.get("set_out_from") or "").strip()
        node = marks[parent] if parent else None
    assert program[ordinal] == total, f"R10 mismatch at {r['station']}"
print(f"check R10 ok: centring variance of {len(seen)} stations recomputed")

# R11: district observation counts from the shards minus removed blunders
removed = set(json.loads((out / "removed_blunders.json").read_text())["obs_ids"])
for dist in d.DISTRICTS:
    count = sum(1 for i, (_, s, _) in kept.items() if district[s] == dist and i not in removed)
    reported = json.loads((out / f"district_{dist}.json").read_text())["observation_count"]
    assert count == reported, f"R11 mismatch in {dist}"
print("check R11 ok: district observation counts match district_*.json")
PY
