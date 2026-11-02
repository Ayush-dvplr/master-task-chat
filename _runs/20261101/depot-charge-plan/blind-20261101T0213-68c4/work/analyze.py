import json, csv, os, configparser, collections, re
D = "/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind-20261101T0213-68c4/environment/data"

cp = configparser.ConfigParser()
cp.read(os.path.join(D, "grid.ini"))
plan_date = cp["plan"]["plan_date"].strip()
first_slot = cp["plan"]["first_slot"].strip()
slot_min = int(cp["plan"]["slot_minutes"])
nslots = int(cp["plan"]["slots"])
feeder = int(cp["feeder"]["feeder_kwh_per_slot"])
print("plan", plan_date, first_slot, slot_min, nslots, feeder)

reg = {}
with open(os.path.join(D, "fleet_register.csv")) as f:
    for r in csv.DictReader(f):
        reg[r["vehicle_id"]] = r
bt = json.load(open(os.path.join(D, "bus_types.json")))

rows = []
with open(os.path.join(D, "roster.csv")) as f:
    rd = csv.DictReader(f)
    for i, r in enumerate(rd, start=2):
        if r["plan_date"] == plan_date:
            rows.append((i, r))
print("roster rows plan day", len(rows))
seen = set()
rej = collections.Counter()
acc = []
for ln, r in rows:
    if r["bus_id"] not in reg:
        rej["unknown"] += 1
        continue
    if reg[r["bus_id"]]["status"] != "active":
        rej["retired"] += 1
        continue
    if r["bus_id"] in seen:
        rej["dup"] += 1
        continue
    seen.add(r["bus_id"])
    acc.append((ln, r))
print("accepted", len(acc), dict(rej))

# windows
from datetime import datetime, timedelta
t0 = datetime.fromisoformat(first_slot)
slots = [t0 + timedelta(minutes=slot_min * i) for i in range(nslots)]
end = t0 + timedelta(minutes=slot_min * nslots)
idx = {s.strftime("%Y-%m-%dT%H:%M"): i for i, s in enumerate(slots)}

trips = collections.Counter()
nextday = (datetime.fromisoformat(plan_date) + timedelta(days=1)).date().isoformat()
with open(os.path.join(D, "trips.jsonl")) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if o["service_date"] == nextday:
            trips[o["bus_id"]] += o["kwh"]
extra = {"B1012": 20, "B1218": 55, "B1291": 45, "B1330": 15}
for k, v in extra.items():
    trips[k] += v

tot_need = 0
winfail = 0
depneed = collections.Counter()
wins = []
for ln, r in acc:
    a = datetime.fromisoformat(r["arrive"]); d = datetime.fromisoformat(r["depart"])
    bad = not (a < d) or a < t0 or d > end
    if bad:
        winfail += 1
        continue
    ty = reg[r["bus_id"]]["type"]
    need = trips[r["bus_id"]] + bt[ty]["reserve_kwh"] - int(r["soc_arrival_kwh"])
    need = max(0, need)
    ws = [i for i, s in enumerate(slots) if s >= a and s < d]
    wins.append((r["bus_id"], r["depot"], ty, need, len(ws), ws[0] if ws else None, ws[-1] if ws else None))
    tot_need += need
    depneed[r["depot"]] += need
print("bad_window", winfail, "buses", len(wins), "total need", tot_need, dict(depneed))
cap_short = [w for w in wins if w[3] > bt[w[2]]["max_kwh_per_slot"] * w[4]]
print("window-short buses", len(cap_short), cap_short[:5])
print("need stats", min(w[3] for w in wins), max(w[3] for w in wins), tot_need/len(wins))
print("winlen stats", min(w[4] for w in wins), max(w[4] for w in wins))
# arrive/depart distribution
print(sorted(collections.Counter((w[5], w[6]) for w in wins).items())[:10])

pub = collections.Counter()
pubtot = 0
nbadpub = 0
with open(os.path.join(D, "published_plan.csv")) as f:
    for i, r in enumerate(csv.DictReader(f), start=2):
        if r["plan_date"] != plan_date:
            continue
        pub[(r["bus_id"], r["slot_start"])] += int(r["kwh"])
        pubtot += int(r["kwh"])
print("published rows", sum(1 for _ in []), "pub total", pubtot)
