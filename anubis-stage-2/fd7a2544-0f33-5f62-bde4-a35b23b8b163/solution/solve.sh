#!/bin/bash
# Oracle for fd7a2544-0f33-5f62-bde4-a35b23b8b163: install the levy engine, run it on
# the current export, check it against every archived ledger, on a renamed
# copy of an archive export, and on a timed market export of crossing stalls.
set -euo pipefail

echo "== archive =="
ls /app/data/archive
ls /app/data/current

mkdir -p /app/out
install -m 0644 /solution/solve.py /app/out/derive_report.py
python3 -B /app/out/derive_report.py /app/data/current /app/out

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

python3 -B - "$SCRATCH/ledgers" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

scratch = Path(sys.argv[1])
archive = Path("/app/data/archive")
exports = sorted(path for path in archive.iterdir() if path.is_dir())
for export in exports:
    out = scratch / export.name
    subprocess.run([sys.executable, "-B", "/app/out/derive_report.py", str(export), str(out)], check=True)
    names = sorted(path.name for path in (export / "ledger").iterdir())
    assert len(names) == 9, names
    for name in names:
        expected = json.loads((export / "ledger" / name).read_text(encoding="utf-8"))
        produced = json.loads((out / name).read_text(encoding="utf-8"))
        assert produced == expected, (export.name, name)
    print(f"{export.name}: all nine reports match the ledger")
print(f"engine reproduces the ledgers of {len(exports)} archive exports")
PY

ORIGINAL=/app/data/archive/export-05
mkdir -p "$SCRATCH/renamed"
number=0
for f in "$ORIGINAL"/*; do
  [ -f "$f" ] || continue
  case "$f" in
    *.svy) number=$((number + 1)); cp "$f" "$SCRATCH/renamed/zz-copy-$number.svy" ;;
    *) cp "$f" "$SCRATCH/renamed/" ;;
  esac
done
python3 -B /app/out/derive_report.py "$ORIGINAL" "$SCRATCH/original-out"
PYTHONHASHSEED=7 python3 -B /app/out/derive_report.py "$SCRATCH/renamed" "$SCRATCH/renamed-out"
for f in "$SCRATCH"/original-out/*.json; do
  cmp "$f" "$SCRATCH/renamed-out/$(basename "$f")"
done
echo "a renamed archive copy without its ledger and a different hash seed give identical reports"
python3 -B - "$SCRATCH/market" <<'PY'
import json
import random
import sys
from pathlib import Path

root = Path(sys.argv[1])
root.mkdir(parents=True)
rng = random.Random(20240611)


def dump(name, obj):
    (root / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


dump("datums.json", {"grid": "TVG", "datums": [
    {"code": "TVG", "transform": {"a": "1", "b": "0", "c": "0", "d": "0", "e": "1", "f": "0"},
     "revisions": []},
    {"code": "MKS", "transform": {"a": "0.54", "b": "-0.72", "c": "0", "d": "0.72", "e": "0.54", "f": "0"},
     "revisions": []}]})
dump("land_use.json", {"uses": [
    {"code": "STL", "segment": "commercial", "weight": "3"},
    {"code": "WLK", "segment": "public", "weight": "1"}]})
dump("regions.json", {"origin": {"x": "0", "y": "0"},
                      "order": ["North", "East", "South", "West"],
                      "origin_region": "North"})
dump("policy.json", {"rulesets": [
    {"id": "MK-1", "from_book": 1, "method": "webster", "house_size": 40,
     "minimum_seats": 1, "levy_total_cents": 987654321}]})
dump("quality.json", {"precedence": [
    "UNKNOWN_DATUM", "UNKNOWN_USE", "MALFORMED_NUMBER", "OPEN_RING",
    "TOO_FEW_VERTICES", "SELF_INTERSECTING", "ZERO_AREA"]})
books = {seq: [] for seq in range(3, 3 + 14)}
stalls = []
pitch = 4800 // 800
for row in range(800):
    low = -2400 + row * pitch + rng.randint(0, 2)
    high = low + rng.randint(2, 4)
    start, stop = -2400 + rng.randint(0, 200), 2400 - rng.randint(0, 200)
    stalls.append((start, low, stop, high))
    stalls.append((low, start, high, stop))
for booth in range(40):
    w, h = rng.randint(60, 300), rng.randint(60, 300)
    x0, y0 = rng.randint(-2400, 2400 - w), rng.randint(-2400, 2400 - h)
    stalls.append((x0, y0, x0 + w, y0 + h))
rng.shuffle(stalls)
for number, (x0, y0, x1, y1) in enumerate(stalls, 1):
    w, h = x1 - x0, y1 - y0
    seq = rng.choice(sorted(books))
    use = rng.choice(["STL", "WLK"])
    books[seq].append(
        f"PARCEL MK-{number:05d} REV 1 USE {use}\n"
        f"V {x0} {y0}\nV {x0 + w} {y0}\nV {x0 + w} {y0 + h}\nV {x0} {y0 + h}\nV {x0} {y0}\nEND\n")
for seq, items in books.items():
    head = f"THORNVALE SURVEY BOOK\nBOOK {seq}\nFORMAT 1\nDATUM MKS\n"
    (root / f"stalls-{seq}.svy").write_text(head + "".join(items), encoding="utf-8")
(root.parent / "stalls.json").write_text(json.dumps(stalls), encoding="utf-8")
print(f"market export: {len(stalls)} crossing rows, lanes and booths on a turned datum in {len(books)} books")
PY

python3 -B - "$SCRATCH/market" "$SCRATCH/market-out" "$SCRATCH/stalls.json" <<'PY'
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

data, out, stalls_file = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
start = time.monotonic()
subprocess.run([sys.executable, "-B", "/app/out/derive_report.py", data, str(out)], check=True)
elapsed = time.monotonic() - start
print(f"market export settled in {elapsed:.2f} seconds")
assert elapsed < 60, elapsed

# independent union area by coordinate compression over the surveyed rectangles;
# the turned datum scales every area by its determinant 0.54*0.54 + 0.72*0.72
stalls = json.loads(Path(stalls_file).read_text(encoding="utf-8"))
xs = sorted({x for s in stalls for x in (s[0], s[2])})
union = 0
for left, right in zip(xs, xs[1:]):
    spans = sorted((s[1], s[3]) for s in stalls if s[0] <= left and s[2] >= right)
    covered, top = 0, None
    for low, high in spans:
        if top is None or low > top:
            covered += high - low
            top = high
        elif high > top:
            covered += high - top
            top = high
    union += (right - left) * covered
union = union * Fraction(81, 100)

claimed = Fraction(0)
for name in ("North", "East", "South", "West"):
    report = json.loads((out / f"region_{name}.json").read_text(encoding="utf-8"))
    claimed += sum(Fraction(p["claimed"]) for p in report["parcels"])
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
quality = json.loads((out / "data_quality.json").read_text(encoding="utf-8"))
print(f"union of stalls {union}, sum of claimed areas {claimed}, "
      f"active {summary['active']}, eclipsed {len(quality['eclipsed'])}")
assert claimed == union
assert Fraction(summary["total_area"]) == union
assert summary["active"] + len(quality["eclipsed"]) == len(stalls)
print("claimed areas add up to the union of the market stalls")
PY

for f in /app/out/*.json; do
  echo "== $f =="
  cat "$f"
done

python3 -B - <<'PY'
import json

summary = json.load(open("/app/out/summary.json"))
seats = ", ".join(f"{name} {count}" for name, count in sorted(summary["seats"].items()))
print(f"Built /app/out/derive_report.py, a standard library engine with exact fractions.")
print(f"Ruleset in force for the current export: {summary['ruleset']} ({summary['method']}, "
      f"house {summary['house_size']}). Seats: {seats}.")
PY
