import csv, json, collections, os
D = "/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind2-20261101T0345-81c3/environment/data"
PD = "2026-03-14"
fleet = {}
with open(os.path.join(D, "fleet_register.csv")) as f:
    for r in csv.DictReader(f):
        fleet[r["vehicle_id"]] = r
print("fleet", len(fleet), collections.Counter(r["status"] for r in fleet.values()))
rows = list(csv.DictReader(open(os.path.join(D, "roster.csv"))))
print("roster rows", len(rows))
pdrows = [r for r in rows if r["plan_date"] == PD]
print("plan-date rows", len(pdrows))
print("depots", collections.Counter(r["depot"] for r in pdrows))
ids = [r["bus_id"] for r in pdrows]
print("distinct bus ids", len(set(ids)))
print("dup count", len(ids) - len(set(ids)))
unk = [r for r in pdrows if r["bus_id"] not in fleet]
print("unknown", len(unk))
ret = [r for r in pdrows if r["bus_id"] in fleet and fleet[r["bus_id"]]["status"] != "active"]
print("retired", len(ret))
import datetime
def T(s): return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M")
first = T("2026-03-14T12:00")
end = first + datetime.timedelta(minutes=15*96)
bad = [r for r in pdrows if not (T(r["arrive"]) < T(r["depart"]) and T(r["arrive"]) >= first and T(r["depart"]) <= end)]
print("bad_window-ish", len(bad), bad[:3])
wl = collections.Counter(int((T(r["depart"])-T(r["arrive"])).total_seconds()//900) for r in pdrows)
print("window lens", sorted(wl.items()))
trips = [json.loads(l) for l in open(os.path.join(D, "trips.jsonl")) if l.strip()]
print("trips", len(trips), collections.Counter(t["service_date"] for t in trips).most_common(5))
pp = list(csv.DictReader(open(os.path.join(D, "published_plan.csv"))))
print("published rows", len(pp), "for plan date", sum(1 for r in pp if r["plan_date"] == PD))
st = list(csv.DictReader(open(os.path.join(D, "settlements.csv"))))
print("settlements", len(st), collections.Counter(r["depot"] for r in st))
print("settled dates", sorted(set(r["settled_date"] for r in st)))
ct = json.load(open(os.path.join(D, "contracts.json")))["contracts"]
print("contracts", len(ct), collections.Counter(c["class"] for c in ct))
print("roster contract blank", sum(1 for r in pdrows if not r["contract_id"].strip()))
print("roster contract unknown", sum(1 for r in pdrows if r["contract_id"].strip() and r["contract_id"] not in set(c["contract_id"] for c in ct)))
