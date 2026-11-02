"""Render a gen_proto instance into the shipped file layout.
Usage: render.py <seed> <kind:shipped|hidden|large> <data_dir>"""
import json, os, random, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_proto import gen, DEPOTS, S  # noqa: E402

TYPES = {"A": ("E12", 30, 20), "B": ("E15", 45, 30), "C": ("E18", 60, 40)}
RATE2T = {30: "A", 45: "B", 60: "C"}
CAB_KWH = 15


def render(seed, kind, out):
    inst = gen(seed, kind)
    rng = random.Random(seed * 104729 + 17)
    shipped = kind == "shipped"
    pd = datetime(2026, 3, 14) if shipped else datetime(2026, 3, 14) + timedelta(days=rng.randint(1, 200))
    t0 = pd + timedelta(hours=12)

    def ts(s):
        return (t0 + timedelta(minutes=15 * s)).strftime("%Y-%m-%dT%H:%M")

    os.makedirs(out, exist_ok=True)
    buses = inst["buses"]
    pub_contracts = ["SCH-%02d" % i for i in range(1, 7)] + ["HSP-%02d" % i for i in range(1, 4)]
    com_contracts = ["COM-%02d" % i for i in range(1, 9)]
    contracts = [{"contract_id": c, "operator_ref": "R%03d" % rng.randint(100, 999),
                  "class": "public" if c[:3] in ("SCH", "HSP") else "commercial"}
                 for c in pub_contracts + com_contracts]
    # demand on the published plan, for non-binding shipped limits
    load = [0] * S
    dload = {d: [0] * S for d in DEPOTS}
    for b in buses:
        for s, k in b["pub"].items():
            load[int(s)] += k
            dload[b["depot"]][int(s)] += k
    if shipped:
        feeder_base = (max(load) * 13 // 10 // 100 + 1) * 100
        cab = {d: max(dload[d]) * 13 // 10 // CAB_KWH + 2 for d in DEPOTS}
        outages = []
        for d in DEPOTS[:2]:
            s0 = rng.randint(30, 60)
            s1 = s0 + rng.randint(2, 6)
            room = min((cab[d] * CAB_KWH - max(dload[d][s0:s1])) // CAB_KWH - 1, 2)
            if room >= 1:
                outages.append((d, room, s0, s1))
        s0 = rng.randint(20, 40)
        s1 = s0 + 8
        derates = [(s0, s1, (max(load[s0:s1]) * 11 // 10 // 10 + 1) * 10)]
    else:
        vals = inst["feeder"]
        feeder_base = max(set(vals), key=vals.count)
        derates = []
        s = 0
        while s < S:
            if vals[s] != feeder_base:
                s1 = s
                while s1 < S and vals[s1] == vals[s]:
                    s1 += 1
                derates.append((s, s1, vals[s]))
                s = s1
            else:
                s += 1
        cab, outages = {}, []
        for d in DEPOTS:
            c = inst["cap"][d]
            cab[d] = max(c) // CAB_KWH
            low = [s for s in range(S) if c[s] < max(c)]
            if low:
                outages.append((d, cab[d] // 2, low[0], low[-1] + 1))
    # fleet register
    fleet = []
    for b in buses:
        fleet.append((b["id"], TYPES[RATE2T[b["rate"]]][0], b["depot"], "active"))
    used = {b["id"] for b in buses}
    i = 0
    while len(fleet) < 2400:
        vid = "B%04d" % (5000 + i)
        i += 1
        if vid in used:
            continue
        fleet.append((vid, TYPES[rng.choice("ABC")][0], rng.choice(DEPOTS),
                      "retired" if rng.random() < 0.08 else "active"))
    retired = [f[0] for f in fleet if f[3] == "retired"]
    spare = [f for f in fleet if f[3] == "active" and f[0] not in used]
    rng.shuffle(fleet)
    with open(os.path.join(out, "fleet_register.csv"), "w") as f:
        f.write("vehicle_id,type,home_depot,status\n")
        for r in fleet:
            f.write(",".join(r) + "\n")
    # roster, trips, published plan
    roster, trips, plan = [], [], []
    extra = []
    nd = pd + timedelta(days=1)
    for b in buses:
        tname, rate, res = TYPES[RATE2T[b["rate"]]]
        x = rng.randrange(0, 45, 5)
        con = rng.choice(pub_contracts) if b["w"] == 4 else rng.choice(com_contracts + [""])
        roster.append([pd.date().isoformat(), b["id"], b["depot"], ts(b["a"]), ts(b["e"]), res + x, con])
        tot = b["need"] + x
        k = rng.randint(2, 4)
        cuts = sorted(rng.sample(range(5, tot, 5), k - 1)) if tot // 5 > k else []
        parts = [q - p for p, q in zip([0] + cuts, cuts + [tot])]
        for j, kwh in enumerate(parts):
            if rng.random() < 0.03 and not extra or rng.random() < 0.01:
                extra.append((b["id"], kwh))
            else:
                trips.append({"trip_id": "T%s-%d" % (b["id"][1:], j), "bus_id": b["id"],
                              "service_date": nd.date().isoformat(), "kwh": kwh})
        for s, k2 in sorted(b["pub"].items(), key=lambda z: int(z[0])):
            plan.append([pd.date().isoformat(), b["id"], ts(int(s)), k2])
    # fully charged buses (need 0)
    for f2 in spare[:3]:
        a = rng.randint(14, 40)
        res = {t[0]: t[2] for t in TYPES.values()}[f2[1]]
        roster.append([pd.date().isoformat(), f2[0], f2[2], ts(a), ts(a + 20), res + 200, ""])
        trips.append({"trip_id": "T%s-0" % f2[0][1:], "bus_id": f2[0], "service_date": nd.date().isoformat(), "kwh": 60})
    # rejected roster rows
    rej_bus = buses[rng.randrange(len(buses))]
    roster.append([pd.date().isoformat(), "B9990", "North", ts(20), ts(40), 50, ""])  # unknown vehicle
    roster.append([pd.date().isoformat(), retired[0], "South", ts(22), ts(50), 40, ""])  # retired
    bw = spare[3]
    roster.append([pd.date().isoformat(), bw[0], bw[2], ts(40), ts(30), 40, ""])  # bad window
    dup = [pd.date().isoformat(), rej_bus["id"], rej_bus["depot"], ts(10), ts(80), 20, ""]  # duplicate
    pb = buses[rng.randrange(len(buses))]
    plan.append([pd.date().isoformat(), pb["id"], ts(max(0, pb["a"] - 2)), 15])  # outside window
    # other dates: padding of the same kind
    for dd in range(1, 18):
        day = pd - timedelta(days=dd)
        dt0 = day + timedelta(hours=12)
        for f2 in rng.sample(spare, 115):
            a = rng.randint(14, 44)
            roster.append([day.date().isoformat(), f2[0], f2[2], (dt0 + timedelta(minutes=15 * a)).strftime("%Y-%m-%dT%H:%M"),
                           (dt0 + timedelta(minutes=15 * (a + 24))).strftime("%Y-%m-%dT%H:%M"), 50, rng.choice(com_contracts)])
            trips.append({"trip_id": "T%s-%s" % (f2[0][1:], day.strftime("%m%d")), "bus_id": f2[0],
                          "service_date": (day + timedelta(days=1)).date().isoformat(), "kwh": 10 * rng.randint(4, 16)})
            plan.append([day.date().isoformat(), f2[0], (dt0 + timedelta(minutes=15 * (a + 2))).strftime("%Y-%m-%dT%H:%M"), 30])
    rng.shuffle(roster)
    first = next(i for i, r in enumerate(roster) if r[0] == pd.date().isoformat() and r[1] == rej_bus["id"])
    roster.insert(rng.randint(first + 1, len(roster)), dup)
    with open(os.path.join(out, "roster.csv"), "w") as f:
        f.write("plan_date,bus_id,depot,arrive,depart,soc_arrival_kwh,contract_id\n")
        for r in roster:
            f.write(",".join(str(v) for v in r) + "\n")
    rng.shuffle(trips)
    with open(os.path.join(out, "trips.jsonl"), "w") as f:
        for t in trips:
            f.write(json.dumps(t) + "\n")
    with open(os.path.join(out, "published_plan.csv"), "w") as f:
        f.write("plan_date,bus_id,slot_start,kwh\n")
        for r in plan:
            f.write(",".join(str(v) for v in r) + "\n")
    json.dump({t[0]: {"max_kwh_per_slot": t[1], "reserve_kwh": t[2]} for t in TYPES.values()},
              open(os.path.join(out, "bus_types.json"), "w"), indent=2)
    json.dump({"cabinet_kwh_per_slot": CAB_KWH,
               "depots": [{"depot": d, "cabinets": cab[d]} for d in DEPOTS]},
              open(os.path.join(out, "depots.json"), "w"), indent=2)
    with open(os.path.join(out, "grid.ini"), "w") as f:
        f.write("[plan]\nplan_date = %s\nfirst_slot = %s\nslot_minutes = 15\nslots = 96\n\n"
                "[feeder]\nfeeder_kwh_per_slot = %d\n" % (pd.date().isoformat(), ts(0), feeder_base))
    with open(os.path.join(out, "service_classes.ini"), "w") as f:
        f.write("[public]\nweight = 4\n\n[commercial]\nweight = 1\n")
    json.dump({"contracts": contracts}, open(os.path.join(out, "contracts.json"), "w"), indent=2)
    price = inst["price"]
    with open(os.path.join(out, "tariff.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<tariff currency="EUR" unit="cents_per_kwh">\n')
        s = 0
        while s < S:
            s1 = s
            while s1 < S and price[s1] == price[s]:
                s1 += 1
            f.write('  <band from="%s" to="%s" cents_per_kwh="%d"/>\n' % (ts(s), ts(s1), price[s]))
            s = s1
        f.write("</tariff>\n")
    with open(os.path.join(out, "disruption_notice.md"), "w") as f:
        f.write("# Disruption notice for %s\n\n## Cabinet outages\n\n" % pd.date().isoformat())
        for d, n_out, s0, s1 in outages:
            f.write("- %s: %d cabinets out of service from %s to %s\n" % (d, n_out, ts(s0), ts(s1)))
        f.write("\n## Feeder derating\n\n")
        for s0, s1, lim in derates:
            f.write("- from %s to %s: feeder limit %d kWh per slot\n" % (ts(s0), ts(s1), lim))
        f.write("\n## Extra trips\n\n")
        for bid, kwh in extra:
            f.write("- %s: extra trip on %s, %d kWh\n" % (bid, nd.date().isoformat(), kwh))


if __name__ == "__main__":
    render(int(sys.argv[1]), sys.argv[2], sys.argv[3])
