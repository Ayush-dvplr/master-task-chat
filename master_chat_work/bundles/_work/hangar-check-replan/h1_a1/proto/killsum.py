"""Summarise kill.py JSON lines: per program x variant, verdict string per view and seconds."""
import json
import sys
from collections import defaultdict

VIEWS = ["plan_rows", "plan_groups", "settle_checks", "settle_groups", "settle_summary"]
recs = []
for line in open(sys.argv[1]):
    if line.startswith("ALL_DONE"):
        continue
    recs.append(json.loads(line))
cell = defaultdict(list)
secs = defaultdict(list)
fire = defaultdict(set)
ref = defaultdict(list)
for r in recs:
    v = r.get("verdict") or {}
    cell[(r["prog"], r["variant"])].append("".join((v.get(k, "?") or "?")[0] for k in VIEWS))
    secs[r["prog"]].append(r.get("s", 0))
    fire[r["variant"]].add(str(r.get("fire"))[:40])
    ref[r["variant"]].append(r.get("ref_s", 0))
variants = sorted({k[1] for k in cell})
progs = sorted({k[0] for k in cell}, key=lambda p: (p not in ("a1", "a1_first_write"), p))
print("prog | " + " | ".join(variants) + " | max_s")
for p in progs:
    print(p + " | " + " | ".join(",".join(cell.get((p, v), [])) for v in variants) + " | %.1f" % max(secs[p]))
for v in variants:
    print("fire", v, sorted(fire[v]), "ref_max %.1f" % max(ref[v]))
