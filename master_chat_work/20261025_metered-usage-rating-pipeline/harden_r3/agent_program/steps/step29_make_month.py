"""Build a fresh extract for another month (2027-01) at another size from the real one."""
import json
import os
import random
import re
import shutil
from datetime import datetime, timedelta, timezone

SRC, DST = "/app/data", "/tmp/jan/in"
SHIFT = timedelta(days=122)  # 2026-09-01 -> 2027-01-01
random.seed(3)
shutil.rmtree("/tmp/jan", ignore_errors=True)
os.makedirs(DST)
for name in ["accounts.csv", "products.ini", "rate_card.json"]:
    shutil.copy(f"{SRC}/{name}", DST)

keep = {"central": 0.55, "east": 0.40, "north": 0.75, "south": 0.30, "west": 0.60}
counts = {}

lines = open(f"{SRC}/collector_central.csv").read().splitlines()
out = [lines[0]]
for l in lines[1:]:
    if random.random() > keep["central"]:
        continue
    f = l.split(",")
    t = datetime.strptime(f[1].strip(), "%Y-%m-%d %H:%M:%S") + SHIFT
    f[1] = t.strftime("%Y-%m-%d %H:%M:%S")
    out.append(",".join(f))
counts["central"] = len(out) - 1
open(f"{DST}/collector_central.csv", "w").write("\n".join(out) + "\n")

lines = open(f"{SRC}/collector_east.tsv").read().splitlines()
out = [lines[0]]
for l in lines[1:]:
    if random.random() > keep["east"]:
        continue
    f = l.split("\t")
    f[1] = str(int(f[1].strip()) + int(SHIFT.total_seconds()))
    out.append("\t".join(f))
counts["east"] = len(out) - 1
open(f"{DST}/collector_east.tsv", "w").write("\n".join(out) + "\n")

out = []
for l in open(f"{SRC}/collector_north.jsonl"):
    if not l.strip() or random.random() > keep["north"]:
        continue
    o = json.loads(l)
    o["at"] = (datetime.strptime(o["at"], "%Y-%m-%dT%H:%M:%SZ") + SHIFT).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.append(json.dumps(o))
counts["north"] = len(out)
open(f"{DST}/collector_north.jsonl", "w").write("\n".join(out) + "\n")

out = []
for l in open(f"{SRC}/collector_south.txt", encoding="latin-1"):
    l = l.rstrip("\n")
    if not l.strip() or random.random() > keep["south"]:
        continue
    t = (datetime.strptime(l[10:24], "%Y%m%d%H%M%S") + SHIFT).strftime("%Y%m%d%H%M%S")
    out.append(l[:10] + t + l[24:])
counts["south"] = len(out)
open(f"{DST}/collector_south.txt", "w", encoding="latin-1").write("\n".join(out) + "\n")

out = []
for l in open(f"{SRC}/collector_west.log"):
    l = l.strip()
    if not l or random.random() > keep["west"]:
        continue
    head, rest = l.split(" ", 1)
    t = datetime.fromisoformat(head) + SHIFT
    out.append(t.isoformat() + " " + rest)
counts["west"] = len(out)
open(f"{DST}/collector_west.log", "w").write("\n".join(out) + "\n")

out = []
for l in open(f"{SRC}/plan_changes.log"):
    l = l.strip()
    if not l:
        continue
    head, rest = l.split(" ", 1)
    t = datetime.strptime(head, "%Y-%m-%dT%H:%M:%SZ") + SHIFT
    out.append(t.strftime("%Y-%m-%dT%H:%M:%SZ") + " " + rest)
open(f"{DST}/plan_changes.log", "w").write("\n".join(out) + "\n")

open(f"{DST}/collector_controls.json", "w").write(json.dumps({
    "month": "2027-01",
    "collectors": {r: {"file": f, "records": counts[r]} for r, f in [
        ("central", "collector_central.csv"), ("east", "collector_east.tsv"),
        ("north", "collector_north.jsonl"), ("south", "collector_south.txt"),
        ("west", "collector_west.log")]}}, indent=2))

pools = {"central": ("12000.00", "80000.00"), "east": ("9000.00", "5000.00"),
         "north": ("50000.00", "60000.00"), "south": ("1000.00", "1000.00"),
         "west": ("0.01", "99999.99")}
body = "".join(f'  <pool region="{r}" amount="{a}" minimum="{m}"/>\n' for r, (a, m) in pools.items())
open(f"{DST}/commitments.xml", "w").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<commitments month="2027-01" currency="USD">\n'
    + body + "</commitments>\n")
print("counts", counts)
