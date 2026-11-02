"""Self-check of the shipped-data run: shapes, caps, totals, cost lower bound."""
import csv, datetime, json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "app"))
import derive_report as dr

DATA = os.path.join(BASE, "environment", "data")
OUT = os.path.join(BASE, "out")
P = lambda n: json.load(open(os.path.join(OUT, n)))

plan = dr.load_grid(DATA)
weights = dr.load_classes(DATA)
types = dr.load_types(DATA)
per_cab, depots, cabinets = dr.load_depots(DATA)
contracts = dr.load_contracts(DATA)
fleet = dr.load_fleet(DATA)
versions = dr.load_tariff(DATA)
nd = (datetime.datetime.strptime(plan.plan_date, "%Y-%m-%d") + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
trips = dr.load_trips(DATA, nd)
outages, derate, extras = dr.load_disruption(DATA, plan)
meters = dr.pick_meters(dr.load_settlements(DATA), versions, plan, depots)
bands = dr.version_for(versions, plan.plan_date)
price = {d: [meters[d][1](bands, t.hour * 60 + t.minute) for t in plan.times] for d in depots}
accepted, order, rej = dr.build_buses(DATA, plan, fleet, types, contracts, weights, trips, extras, depots)
published, prej = dr.load_published(DATA, plan, accepted)

fails = []
def ck(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (" " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)

names = ["policy_audit.json", "summary.json", "data_quality.json"] + \
        ["region_%s.json" % d for d in depots] + \
        ["segment_commercial.json", "segment_public.json"]
ck("all 9 documents exist", all(os.path.exists(os.path.join(OUT, n)) for n in names), len(names))

audit = P("policy_audit.json")
summ = P("summary.json")
dq = P("data_quality.json")
idx = {n: i for i, n in enumerate(plan.names)}

ck("audit keys", set(audit) == {"plan_date", "buses"})
ck("audit sorted by bus_id", [b["bus_id"] for b in audit["buses"]] == sorted(b["bus_id"] for b in audit["buses"]))
ck("audit bus count == accepted roster", len(audit["buses"]) == len(accepted), len(accepted))
ck("audit bus keys", all(list(b) == ["bus_id", "depot", "class", "need_kwh", "delivered_kwh",
    "unmet_kwh", "unmet_reason", "changed", "charges"] for b in audit["buses"]))

plan_kwh = {}
bad = []
for b in audit["buses"]:
    bus = accepted[b["bus_id"]]
    tot = 0
    last = -1
    for c in b["charges"]:
        s = idx[c["slot"]]
        if s <= last: bad.append(("order", b["bus_id"]))
        last = s
        if s not in bus.slots: bad.append(("window", b["bus_id"], c["slot"]))
        if not (0 < c["kwh"] <= bus.max_slot): bad.append(("cap", b["bus_id"], c["kwh"]))
        plan_kwh[(b["bus_id"], s)] = c["kwh"]
        tot += c["kwh"]
    if tot != b["delivered_kwh"] or tot > bus.need: bad.append(("total", b["bus_id"]))
    if b["need_kwh"] != bus.need: bad.append(("need", b["bus_id"]))
    if b["unmet_kwh"] != bus.need - tot: bad.append(("unmet", b["bus_id"]))
    want = None if b["unmet_kwh"] == 0 else ("window" if bus.need > bus.max_slot * len(bus.slots) else "supply")
    if b["unmet_reason"] != want: bad.append(("reason", b["bus_id"]))
    chg = any(plan_kwh.get((b["bus_id"], s), 0) != published.get((b["bus_id"], s), 0) for s in bus.slots)
    if b["changed"] != chg: bad.append(("changed", b["bus_id"]))
    if b["depot"] != bus.depot or b["class"] != bus.cls: bad.append(("meta", b["bus_id"]))
ck("per-bus rules (window, slot cap, need cap, order, unmet, reason, changed)", not bad, bad[:5])

dcap = {d: [max(0, cabinets[d] - outages.get((d, s), 0)) * per_cab for s in range(plan.nslots)] for d in depots}
fcap = [derate.get(s, plan.feeder_base) for s in range(plan.nslots)]
de = {d: [0] * plan.nslots for d in depots}
ce = {c: [0] * plan.nslots for c in weights}
cost = 0
for (bid, s), k in plan_kwh.items():
    bus = accepted[bid]
    de[bus.depot][s] += k
    ce[bus.cls][s] += k
    cost += price[bus.depot][s] * k
feeder = [sum(de[d][s] for d in depots) for s in range(plan.nslots)]
ck("depot cabinet caps respected", all(de[d][s] <= dcap[d][s] for d in depots for s in range(plan.nslots)))
ck("feeder cap respected (incl. derated slots)", all(feeder[s] <= fcap[s] for s in range(plan.nslots)),
   "derated slots=%d max there=%d" % (len(derate), max([feeder[s] for s in derate] or [0])))

wu = sum(accepted[b["bus_id"]].weight * b["unmet_kwh"] for b in audit["buses"])
moved = sum(max(0, k - plan_kwh.get(key, 0)) for key, k in published.items())
ck("summary.weighted_unmet_kwh", summ["weighted_unmet_kwh"] == wu, wu)
ck("summary.energy_cost_cents", summ["energy_cost_cents"] == cost, cost)
ck("summary.moved_kwh", summ["moved_kwh"] == moved, moved)
ck("summary.feeder_peak_kwh", summ["feeder_peak_kwh"] == max(feeder), max(feeder))
ck("summary.feeder_kwh_by_slot", [r["kwh"] for r in summ["feeder_kwh_by_slot"]] == feeder and
   [r["slot"] for r in summ["feeder_kwh_by_slot"]] == plan.names)
ck("summary.buses_planned/short/changed", (summ["buses_planned"], summ["buses_short"], summ["buses_changed"]) ==
   (len(accepted), sum(1 for b in audit["buses"] if b["unmet_kwh"] > 0), sum(1 for b in audit["buses"] if b["changed"])),
   (summ["buses_planned"], summ["buses_short"], summ["buses_changed"]))
ck("summary.records_rejected == data_quality rows", summ["records_rejected"] == len(dq["rejected"]) == len(rej) + len(prej),
   len(dq["rejected"]))
ck("data_quality sorted by file then line",
   dq["rejected"] == sorted(dq["rejected"], key=lambda r: (r["file"], r["line"])))

esum = csum = 0
for d in depots:
    r = P("region_%s.json" % d)
    ok = (list(r) == ["depot", "buses", "energy_kwh", "cost_cents", "unmet_kwh", "slots"]
          and len(r["slots"]) == plan.nslots
          and [x["slot"] for x in r["slots"]] == plan.names
          and [x["kwh"] for x in r["slots"]] == de[d]
          and [x["feeder_kwh"] for x in r["slots"]] == feeder
          and r["energy_kwh"] == sum(de[d])
          and r["cost_cents"] == sum(price[d][s] * de[d][s] for s in range(plan.nslots))
          and r["buses"] == sum(1 for b in audit["buses"] if b["depot"] == d)
          and r["unmet_kwh"] == sum(b["unmet_kwh"] for b in audit["buses"] if b["depot"] == d))
    ck("region_%s.json consistent" % d, ok, "%d kWh %d c" % (r["energy_kwh"], r["cost_cents"]))
    esum += r["energy_kwh"]; csum += r["cost_cents"]
ck("regions sum to summary cost/energy", csum == cost and esum == sum(feeder), "%d kWh %d c" % (esum, csum))

e2 = c2 = 0
for c in ("commercial", "public"):
    r = P("segment_%s.json" % c)
    ok = (list(r) == ["class", "buses", "energy_kwh", "cost_cents", "unmet_kwh", "slots"]
          and [x["kwh"] for x in r["slots"]] == ce[c]
          and [x["feeder_kwh"] for x in r["slots"]] == feeder
          and r["energy_kwh"] == sum(ce[c])
          and r["buses"] == sum(1 for b in audit["buses"] if b["class"] == c)
          and r["unmet_kwh"] == sum(b["unmet_kwh"] for b in audit["buses"] if b["class"] == c)
          and r["cost_cents"] == sum(price[accepted[b["bus_id"]].depot][idx[x["slot"]]] * x["kwh"]
                                     for b in audit["buses"] if b["class"] == c for x in b["charges"]))
    ck("segment_%s.json consistent" % c, ok, "%d kWh %d c" % (r["energy_kwh"], r["cost_cents"]))
    e2 += r["energy_kwh"]; c2 += r["cost_cents"]
ck("segments sum to summary cost/energy", c2 == cost and e2 == sum(feeder), "%d kWh %d c" % (e2, c2))

# independent optimality controls
lb = 0
maxdel = 0
for bus in accepted.values():
    room = min(bus.need, bus.max_slot * len(bus.slots))
    maxdel += room
    left = room
    for s in sorted(bus.slots, key=lambda s: price[bus.depot][s]):
        take = min(left, bus.max_slot)
        lb += take * price[bus.depot][s]
        left -= take
        if not left: break
ck("delivered == per-bus window maximum", sum(feeder) == maxdel, maxdel)
ck("cost == unconstrained per-bus cheapest-slot lower bound (so cost is optimal)", cost == lb, lb)
pubcost = sum(price[accepted[b].depot][s] * k for (b, s), k in published.items())
ck("published plan cost equals plan cost (moved=0 consistent)", pubcost == cost, pubcost)
print("TOTAL need=%d delivered=%d unmet=%d" % (sum(b.need for b in accepted.values()), sum(feeder), sum(b["unmet_kwh"] for b in audit["buses"])))
print("FAILS:", fails if fails else "none")
