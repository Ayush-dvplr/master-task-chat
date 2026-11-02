"""Independent self-check of the shipped reports (no reuse of solver code)."""
import json, os, sys, collections
B = "/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind-20261101T0213-68c4"
O = os.path.join(B, "out")
sys.path.insert(0, os.path.join(B, "app"))
import derive_report as dr

model = dr.build(os.path.join(B, "environment", "data"), os.path.join(B, "environment", "docs"))
nslots = model["nslots"]
price = model["price"]
slot_name = model["slot_name"]
audit = json.load(open(os.path.join(O, "policy_audit.json")))
summary = json.load(open(os.path.join(O, "summary.json")))

x = {}
for e in audit["buses"]:
    row = [0] * nslots
    for c in e["charges"]:
        row[slot_name.index(c["slot"])] = c["kwh"]
    x[e["bus_id"]] = row

prob = []
# 1. per-bus limits
for e in audit["buses"]:
    b = e["bus_id"]
    info = model["buses"][b]
    win = set(info["window"])
    for s in range(nslots):
        if x[b][s] < 0 or x[b][s] > info["max_slot"]:
            prob.append("maxslot %s %d" % (b, s))
        if x[b][s] and s not in win:
            prob.append("outside window %s %d" % (b, s))
    d = sum(x[b])
    if d > info["need"]:
        prob.append("over need %s" % b)
    if d != e["delivered_kwh"] or info["need"] != e["need_kwh"]:
        prob.append("delivered mismatch %s" % b)
    if e["unmet_kwh"] != info["need"] - d:
        prob.append("unmet mismatch %s" % b)
    if info["class"] != e["class"] or info["depot"] != e["depot"]:
        prob.append("attr mismatch %s" % b)

# 2. depot + feeder caps
dep_slot = collections.defaultdict(lambda: [0] * nslots)
tot = [0] * nslots
for b, row in x.items():
    d = model["buses"][b]["depot"]
    for s in range(nslots):
        dep_slot[d][s] += row[s]
        tot[s] += row[s]
for d, caps in model["depot_cap"].items():
    for s in range(nslots):
        if dep_slot[d][s] > caps[s]:
            prob.append("depot cap %s %d %d>%d" % (d, s, dep_slot[d][s], caps[s]))
for s in range(nslots):
    if tot[s] > model["feeder"][s]:
        prob.append("feeder %d %d>%d" % (s, tot[s], model["feeder"][s]))

# 3. objective values
wu = sum(model["buses"][b]["weight"] * (model["buses"][b]["need"] - sum(x[b])) for b in x)
cost = sum(x[b][s] * price[s] for b in x for s in range(nslots))
moved = 0
for (b, s), p in model["published"].items():
    if p > x[b][s]:
        moved += p - x[b][s]
print("weighted_unmet", wu, summary["weighted_unmet_kwh"])
print("cost", cost, summary["energy_cost_cents"])
print("moved", moved, summary["moved_kwh"])
print("feeder_peak", max(tot), summary["feeder_peak_kwh"])
assert wu == summary["weighted_unmet_kwh"] and cost == summary["energy_cost_cents"]
assert moved == summary["moved_kwh"] and max(tot) == summary["feeder_peak_kwh"]

# 4. lower bounds, ignoring the shared caps (relaxation)
lb_unmet = 0
lb_cost = 0
for b, info in model["buses"].items():
    cap_total = info["max_slot"] * len(info["window"])
    short = max(0, info["need"] - cap_total)
    lb_unmet += info["weight"] * short
    rem = min(info["need"], cap_total)
    for s in sorted(info["window"], key=lambda s: (price[s], s)):
        take = min(rem, info["max_slot"])
        lb_cost += take * price[s]
        rem -= take
        if rem == 0:
            break
print("lower bound weighted_unmet", lb_unmet, "cost(at same delivery)", lb_cost)

# 5. region / segment consistency
for d in ["North", "South", "West", "East"]:
    r = json.load(open(os.path.join(O, "region_%s.json" % d)))
    assert r["depot"] == d and len(r["slots"]) == nslots
    assert r["buses"] == sum(1 for b in x if model["buses"][b]["depot"] == d)
    assert r["energy_kwh"] == sum(dep_slot[d]), (d, r["energy_kwh"], sum(dep_slot[d]))
    for s in range(nslots):
        assert r["slots"][s]["slot"] == slot_name[s]
        assert r["slots"][s]["kwh"] == dep_slot[d][s]
        assert r["slots"][s]["feeder_kwh"] == tot[s]
    assert r["cost_cents"] == sum(x[b][s] * price[s] for b in x
                                  if model["buses"][b]["depot"] == d for s in range(nslots))
    print("region", d, r["buses"], r["energy_kwh"], r["cost_cents"], r["unmet_kwh"])
tot_e = 0
for k in ["commercial", "public"]:
    g = json.load(open(os.path.join(O, "segment_%s.json" % k)))
    assert g["class"] == k and len(g["slots"]) == nslots
    assert g["buses"] == sum(1 for b in x if model["buses"][b]["class"] == k)
    assert g["energy_kwh"] == sum(sum(x[b]) for b in x if model["buses"][b]["class"] == k)
    for s in range(nslots):
        assert g["slots"][s]["feeder_kwh"] == tot[s]
    tot_e += g["energy_kwh"]
    print("segment", k, g["buses"], g["energy_kwh"], g["cost_cents"], g["unmet_kwh"])
assert tot_e == sum(sum(r) for r in x.values())
assert sum(json.load(open(os.path.join(O, "region_%s.json" % d)))["energy_kwh"]
           for d in ["North", "South", "West", "East"]) == tot_e

dq = json.load(open(os.path.join(O, "data_quality.json")))
print("rejected", dq["rejected"])
assert len(dq["rejected"]) == summary["records_rejected"]
assert summary["buses_planned"] == len(x) == len(model["buses"])
print("delivered total", sum(sum(r) for r in x.values()), "need total",
      sum(i["need"] for i in model["buses"].values()))
print("PROBLEMS:", prob if prob else "none")
