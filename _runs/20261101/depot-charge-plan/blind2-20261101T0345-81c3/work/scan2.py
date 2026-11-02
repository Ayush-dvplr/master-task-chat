import csv, json, os, datetime, collections
D = "/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind2-20261101T0345-81c3/environment/data"
PD = "2026-03-14"
def T(s): return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M")
first = T("2026-03-14T12:00"); endd = first + datetime.timedelta(minutes=15*96)
fleet = {r["vehicle_id"]: r for r in csv.DictReader(open(os.path.join(D, "fleet_register.csv")))}
types = json.load(open(os.path.join(D, "bus_types.json")))
rows = list(csv.DictReader(open(os.path.join(D, "roster.csv"))))
acc = {}; rej = []
for i, r in enumerate(rows, start=2):
    if r["plan_date"] != PD: continue
    b = r["bus_id"]
    if b not in fleet: rej.append((i, b, "unknown_vehicle")); continue
    if fleet[b]["status"] != "active": rej.append((i, b, "retired_vehicle")); continue
    if b in acc: rej.append((i, b, "duplicate_roster_row")); continue
    a, dp = T(r["arrive"]), T(r["depart"])
    if not (a < dp) or a < first or dp > endd: rej.append((i, b, "bad_window")); continue
    acc[b] = r
print("accepted", len(acc), "rejected", rej)
trips = collections.Counter()
for l in open(os.path.join(D, "trips.jsonl")):
    t = json.loads(l)
    if t["service_date"] == "2026-03-15": trips[t["bus_id"]] += int(t["kwh"])
extra = {"B1051": 35, "B1179": 20, "B1292": 75}
need = {}
for b, r in acc.items():
    ty = types[fleet[b]["type"]]
    n = trips.get(b, 0) + extra.get(b, 0) + ty["reserve_kwh"] - int(r["soc_arrival_kwh"])
    need[b] = max(0, n)
print("total need", sum(need.values()), "zero-need buses", sum(1 for v in need.values() if v == 0))
print("extra bus on plan?", {k: (k in acc) for k in extra})
wlen = {}
for b, r in acc.items():
    a, dp = T(r["arrive"]), T(r["depart"])
    wlen[b] = sum(1 for i in range(96) if a <= first+datetime.timedelta(minutes=15*i) < dp)
short = [(b, need[b], wlen[b]*types[fleet[b]["type"]]["max_kwh_per_slot"]) for b in acc if need[b] > wlen[b]*types[fleet[b]["type"]]["max_kwh_per_slot"]]
print("window-short buses", len(short), short[:5])
print("sum cap", sum(wlen[b]*types[fleet[b]["type"]]["max_kwh_per_slot"] for b in acc))
print("vars", sum(wlen.values()))
pp = list(csv.DictReader(open(os.path.join(D, "published_plan.csv"))))
pdr = [(i, r) for i, r in enumerate(pp, start=2) if r["plan_date"] == PD]
print("pub rows", len(pdr))
out = 0; notplan = 0; tot = 0
for i, r in pdr:
    b = r["bus_id"]
    if b not in acc: notplan += 1; out += 1; continue
    a, dp = T(acc[b]["arrive"]), T(acc[b]["depart"])
    ss = T(r["slot_start"])
    if not (a <= ss < dp): out += 1
    else: tot += int(r["kwh"])
print("pub outside window", out, "of which bus not on plan", notplan, "accepted pub kwh", tot)
# contracts
ct = {c["contract_id"]: c["class"] for c in json.load(open(os.path.join(D, "contracts.json")))["contracts"]}
cls = collections.Counter(ct.get(acc[b]["contract_id"].strip(), "commercial") for b in acc)
print("classes", cls)
print("sample pub kwh > maxslot?", sum(1 for i,r in pdr if r["bus_id"] in acc and int(r["kwh"]) > types[fleet[r["bus_id"]]["type"]]["max_kwh_per_slot"]))
