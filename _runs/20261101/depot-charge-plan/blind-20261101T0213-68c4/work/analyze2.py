import json, csv, os, collections
from datetime import datetime, timedelta
D = "/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind-20261101T0213-68c4/environment/data"
plan_date = "2026-03-14"
t0 = datetime.fromisoformat("2026-03-14T12:00")
nslots = 96
slots = [(t0 + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(nslots)]
sidx = {s: i for i, s in enumerate(slots)}

reg = {}
with open(os.path.join(D, "fleet_register.csv")) as f:
    for r in csv.DictReader(f):
        reg[r["vehicle_id"]] = r
win = {}
dep = {}
with open(os.path.join(D, "roster.csv")) as f:
    seen = set()
    for i, r in enumerate(csv.DictReader(f), start=2):
        if r["plan_date"] != plan_date:
            continue
        b = r["bus_id"]
        if b not in reg or reg[b]["status"] != "active" or b in seen:
            continue
        a = datetime.fromisoformat(r["arrive"]); d = datetime.fromisoformat(r["depart"])
        if not (a < d) or a < t0 or d > t0 + timedelta(minutes=15 * nslots):
            continue
        seen.add(b)
        win[b] = set(j for j in range(nslots) if a <= t0 + timedelta(minutes=15 * j) < d)
        dep[b] = r["depot"]

nrows = 0
nonplan = 0
outside = 0
badslot = 0
ok = 0
pubbus = set()
pubk = collections.Counter()
with open(os.path.join(D, "published_plan.csv")) as f:
    for i, r in enumerate(csv.DictReader(f), start=2):
        if r["plan_date"] != plan_date:
            continue
        nrows += 1
        pubbus.add(r["bus_id"])
        if r["bus_id"] not in win:
            nonplan += 1
            continue
        if r["slot_start"] not in sidx:
            badslot += 1
            continue
        if sidx[r["slot_start"]] not in win[r["bus_id"]]:
            outside += 1
            continue
        ok += 1
        pubk[(r["bus_id"], sidx[r["slot_start"]])] += int(r["kwh"])
print("pub rows planday", nrows, "nonplan bus", nonplan, "badslot", badslot, "outside", outside, "ok", ok)
print("pub buses", len(pubbus), "plan buses", len(win))
print("max pub per cell", max(pubk.values()), "cells", len(pubk))
print("sum ok pub", sum(pubk.values()))
print("window len sum", sum(len(w) for w in win.values()))
# distinct dates in roster/published
print("pub dates", collections.Counter(r for r in []))
