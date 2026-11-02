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

# Own-input probes on copies of the shipped extract (judge R12-R16).
PYTHONDONTWRITEBYTECODE=1 python3 - /app/data /app/out <<'PY'
import ast
import csv
import io
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, sys.argv[2])
import derive_report as d

data, out = Path(sys.argv[1]), Path(sys.argv[2])
program = out / "derive_report.py"
work = Path(tempfile.mkdtemp(prefix="probe_"))
CSV_SHARD = "obs_source_district_north.csv"


def split_shard(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    head = [ln for ln in lines if ln.startswith("#")]
    rows = list(csv.reader(ln for ln in lines if not ln.startswith("#")))
    return head, rows[0], rows[1:]


def write_shard(path, head, header, rows, quoting=csv.QUOTE_MINIMAL):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n", quoting=quoting).writerows([header] + rows)
    path.write_text("\n".join(head) + "\n" + buf.getvalue(), encoding="utf-8")


def run(src, name):
    dest = work / name
    dest.mkdir()
    start = time.monotonic()
    subprocess.run([sys.executable, str(program), str(src), str(dest)], check=True)
    return dest, time.monotonic() - start


def copy_extract(name):
    dest = work / name
    shutil.copytree(data, dest)
    return dest


def tree(root):
    return {p.relative_to(root): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


head, header, rows = split_shard(data / CSV_SHARD)

# R12: every field of the CSV shard written as a quoted field, same values
quoted = copy_extract("quoted")
write_shard(quoted / CSV_SHARD, head, header, rows, quoting=csv.QUOTE_ALL)
q_out, _ = run(quoted, "quoted_out")
plain = {k: v for k, v in tree(out).items() if k.suffix != ".py" and "__pycache__" not in k.parts}
assert tree(q_out) == plain, "R12 quoted copy changed an output"
print(f"check R12 ok: quoted CSV shard copy gives byte-identical outputs ({len(plain)} files)")

# R13: csv module rows of the CSV shard against the rows derive_report.py reads
program_rows = [rec for rec, _, shard in d.shard_records(data) if shard == CSV_SHARD]
assert len(program_rows) == len(rows), "R13 row count differs"
for rec, row in zip(program_rows, rows):
    assert [rec[k] for k in header] == row, f"R13 row {row[0]} differs"
print(f"check R13 ok: {len(rows)} CSV shard rows match the csv module")

# R14: drop the last five observation rows of the CSV shard and inspect
cut = copy_extract("cut")
write_shard(cut / CSV_SHARD, head, header, rows[:-5])
c_out, _ = run(cut, "cut_out")
before = (out / "status.txt").read_text().split()
after = (c_out / "status.txt").read_text().split()
assert before != after, "R14 removing rows changed nothing"
print(f"check R14 ok: five rows removed; status {' '.join(after)}")

# R15: a larger extract, sixty extra observation rows with fresh ids
big = copy_extract("big")
extra = [["OB9" + r[0][3:]] + r[1:] for r in rows[:60]]
write_shard(big / CSV_SHARD, head, header, rows + extra)
b_out, seconds = run(big, "big_out")
assert seconds < 120, "R15 too slow"
print(f"check R15 ok: {len(rows) + len(extra)}-row CSV shard extract ran in {seconds:.1f} s")

# R16: modules derive_report.py imports, all from the standard library
names = set()
for node in ast.walk(ast.parse(program.read_text(encoding="utf-8"))):
    if isinstance(node, ast.Import):
        names.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.level == 0:
        names.add(node.module.split(".")[0])
assert names <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)
print(f"check R16 ok: imports {', '.join(sorted(names))} are all standard library")
shutil.rmtree(work)
PY

# Owner-only variant (QC Step 10): leave every file this run wrote readable by its
# owner alone, the mode an agent editor leaves behind, keeping the owner execute bit.
find /app -xdev -type f -user 1000 -perm -u+x -print0 2>/dev/null | xargs -0 -r chmod 700 || true
find /app -xdev -type f -user 1000 ! -perm -u+x -print0 2>/dev/null | xargs -0 -r chmod 600 || true
