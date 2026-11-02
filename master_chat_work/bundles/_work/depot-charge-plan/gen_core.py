"""Seeded corpus generator for depot-charge-plan (stdlib only).

Usage: gen_core.py <seed> <kind:shipped|hidden|large> <data_dir>
Same RNG call order as WORK/proto2 (gen_proto + conv + render), so the kill-test results carry over.
Extra for hidden kinds only: rare fixtures drawn from their own RNG stream.
"""
import json
import os
import random
import sys
from datetime import datetime, timedelta

DEPOTS = ["North", "South", "West", "East"]
S = 96
TYPES = {"A": ("E12", 30, 20), "B": ("E15", 45, 30), "C": ("E18", 60, 40)}
RATE2T = {30: "A", 45: "B", 60: "C"}
CAB_KWH = 15
FLEET_ROWS = 4000
PAD_DAYS = 42


def price_of(s, bands):
    for lo, hi, p in bands:
        if lo <= s < hi:
            return p
    raise ValueError(s)


def gen(seed, kind):
    big = kind == "large"
    kind = "hidden" if big else kind
    rng = random.Random(seed * 7919 + (1 if kind == "hidden" else 0))
    bands = [(0, 16, 31), (16, 40, 27), (40, 72, 14), (72, 96, 22)]
    if kind == "hidden":
        e1 = rng.choice([14, 16, 20]); e2 = rng.choice([36, 40, 44]); e3 = rng.choice([68, 72, 76])
        bands = [(0, e1, rng.choice([29, 31, 33])), (e1, e2, rng.choice([25, 27])),
                 (e2, e3, rng.choice([12, 14, 15])), (e3, 96, rng.choice([20, 22]))]
    price = [price_of(s, bands) for s in range(S)]
    rates = {"A": 30, "B": 45, "C": 60}
    n = 120 if kind == "shipped" else (rng.randint(350, 450) if big else rng.randint(70, 120))
    d0 = rng.randint(20, 40)
    dl = rng.randint(10, 24)
    buses = []
    for i in range(n):
        d = DEPOTS[i % 4] if kind == "shipped" else rng.choice(DEPOTS)
        t = rng.choice("ABC")
        a = rng.randint(14, 44)
        e = min(S, a + rng.randint(12, 52))
        rate = rates[t]
        need = rng.randint(3, 10) * 20
        need = min(need, rate * (e - a)) if rng.random() > 0.08 else need
        if kind == "hidden" and rng.random() < 0.18:
            a = rng.randint(d0, d0 + dl - 4)
            e = min(S, a + rng.randint(3, 6))
            need = rate * (e - a) // 10 * 10
        if i % 37 == 5:
            e = a + max(2, need // rate - 1)
        w = rng.choice([1, 1, 1, 4])
        pub = {}
        rem = need
        cands = sorted(range(a, e), key=lambda s: (price[s], s))
        if kind == "shipped":
            cands = sorted(range(a, e), key=lambda s: (price[s], rng.random()))
        for s in cands:
            if rem <= 0:
                break
            k = min(rate, rem)
            if kind != "shipped" and rng.random() < 0.25:
                k = min(k, 10 * rng.randint(1, 3))
            pub[s] = k
            rem -= k
        buses.append({"id": "B%04d" % (1000 + i * 3 + rng.randint(0, 2)), "depot": d, "a": a, "e": e,
                      "need": need, "rate": rate, "w": w, "pub": {str(k): v for k, v in pub.items()}})
    seen = set()
    for b in buses:
        while b["id"] in seen:
            b["id"] = "B%04d" % (int(b["id"][1:]) + 1)
        seen.add(b["id"])
    if kind == "shipped":
        cap = {d: [100000] * S for d in DEPOTS}
        feeder = [10 ** 6] * S
    else:
        dem = [0] * S
        ddem = {d: [0] * S for d in DEPOTS}
        for b in buses:
            for s, k in b["pub"].items():
                dem[int(s)] += k
                ddem[b["depot"]][int(s)] += k
        peak = max(dem)
        feeder = [max(60, int(peak * rng.uniform(0.45, 0.65)) // 10 * 10)] * S
        for s in range(S):
            if rng.random() < 0.1:
                feeder[s] = feeder[s] // 2 // 10 * 10
        for s in range(d0, min(S, d0 + dl)):
            feeder[s] = max(30, feeder[s] * 3 // 10 // 10 * 10)
        cap = {}
        for d in DEPOTS:
            pk = max(ddem[d]) or 60
            c = max(60, int(pk * rng.uniform(0.5, 0.9)) // 15 * 15)
            cap[d] = [c] * S
            o0 = rng.randint(30, 70)
            for s in range(o0, o0 + rng.randint(2, 8)):
                cap[d][s] = c // 2
    return {"S": S, "price": price, "feeder": feeder, "cap": cap, "buses": buses}


def bands_rng(rng):
    n = rng.randint(4, 6)
    edges = [0] + sorted(rng.sample(range(4, 92, 2), n - 1)) + [S]
    prices = [rng.randint(10, 40) for _ in range(n)]
    arr = []
    for i in range(n):
        arr += [prices[i]] * (edges[i + 1] - edges[i])
    return arr


def cents(tar, s0, L, r, k):
    return sum(r * tar[(s + k) % S] for s in range(s0, s0 + L))


def fits(tar_of_day, sess, k):
    return all(c == cents(tar_of_day[day], s0, L, r, k) for (day, s0, L, r, c) in sess)


def conv(seed, kind):
    inst = gen(seed, kind)
    rng = random.Random(seed * 104729 + {"shipped": 0, "hidden": 1, "large": 2}[kind])
    if kind == "shipped":
        ks = {"North": 0, "South": 0, "West": 0, "East": 28}
    else:
        pool = list(range(4, 92))
        rng.shuffle(pool)
        ks = {d: pool[i] for i, d in enumerate(DEPOTS)}
    while True:
        old = [bands_rng(rng), bands_rng(rng)]
        tar_of_day = {day: old[0 if day < 7 else 1] for day in range(14)}
        hist = {d: [] for d in DEPOTS}
        for d in DEPOTS:
            for day in range(14):
                for _ in range(rng.randint(36, 44)):
                    L = rng.randint(1, 10)
                    s0 = rng.randint(0, S - L)
                    r = rng.choice([30, 45, 60])
                    hist[d].append((day, s0, L, r, cents(tar_of_day[day], s0, L, r, ks[d])))
        if all([k for k in range(S) if fits(tar_of_day, hist[d], k)] == [ks[d]] for d in DEPOTS):
            break
    inst["k"] = ks
    inst["old"] = old
    inst["hist"] = hist
    return inst


def _w(path, text):
    with open(path, "w", newline="\n") as f:
        f.write(text)


def render(seed, kind, out):
    inst = conv(seed, kind)
    rng = random.Random(seed * 104729 + 17)
    rare = random.Random(seed * 15485863 + 3)
    shipped = kind == "shipped"
    pd = datetime(2026, 3, 14) if shipped else datetime(2026, 3, 14) + timedelta(days=rng.randint(1, 200))
    t0 = pd + timedelta(hours=12)
    pds = pd.date().isoformat()

    def ts(s, base=t0):
        return (base + timedelta(minutes=15 * s)).strftime("%Y-%m-%dT%H:%M")

    os.makedirs(out, exist_ok=True)
    buses = inst["buses"]
    pub_contracts = ["SCH-%02d" % i for i in range(1, 7)] + ["HSP-%02d" % i for i in range(1, 4)]
    com_contracts = ["COM-%02d" % i for i in range(1, 9)]
    contracts = [{"contract_id": c, "operator_ref": "R%03d" % rng.randint(100, 999),
                  "class": "public" if c[:3] in ("SCH", "HSP") else "commercial"}
                 for c in pub_contracts + com_contracts]
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
        derates = [(s0, s1, (max(load[s0:s1]) * 6 // 10 // 10) * 10)]
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
    fleet = []
    for b in buses:
        fleet.append((b["id"], TYPES[RATE2T[b["rate"]]][0], b["depot"], "active"))
    used = {b["id"] for b in buses}
    i = 0
    while len(fleet) < FLEET_ROWS:
        vid = "B%04d" % (5000 + i)
        i += 1
        if vid in used:
            continue
        fleet.append((vid, TYPES[rng.choice("ABC")][0], rng.choice(DEPOTS),
                      "retired" if rng.random() < 0.08 else "active"))
    retired = [f[0] for f in fleet if f[3] == "retired"]
    spare = [f for f in fleet if f[3] == "active" and f[0] not in used]
    rng.shuffle(fleet)
    _w(os.path.join(out, "fleet_register.csv"),
       "vehicle_id,type,home_depot,status\n" + "".join(",".join(r) + "\n" for r in fleet))
    roster, trips, plan, extra = [], [], [], []
    nd = pd + timedelta(days=1)
    for b in buses:
        tname, rate, res = TYPES[RATE2T[b["rate"]]]
        x = rng.randrange(0, 45, 5)
        con = rng.choice(pub_contracts) if b["w"] == 4 else rng.choice(com_contracts + [""])
        roster.append([pds, b["id"], b["depot"], ts(b["a"]), ts(b["e"]), res + x, con])
        tot = b["need"] + x
        k = rng.randint(2, 4)
        cuts = sorted(rng.sample(range(5, tot, 5), k - 1)) if tot // 5 > k else []
        parts = [q - p for p, q in zip([0] + cuts, cuts + [tot])]
        for j, kwh in enumerate(parts):
            if rng.random() < 0.03 and not extra or rng.random() < 0.01:
                extra.append((b["id"], kwh, nd))
            else:
                trips.append({"trip_id": "T%s-%d" % (b["id"][1:], j), "bus_id": b["id"],
                              "service_date": nd.date().isoformat(), "kwh": kwh})
        for s, k2 in sorted(b["pub"].items(), key=lambda z: int(z[0])):
            plan.append([pds, b["id"], ts(int(s)), k2])
    if not shipped:
        # rare fixture: a commercial bus with a contract id that contracts.json does not list
        cands = [r for r in roster if r[6] in com_contracts + [""]]
        rare.choice(cands)[6] = "SCH-%02d" % rare.randint(10, 40)
        # rare fixture: an extra trip in the notice dated on the plan date itself
        extra.append((rare.choice(buses)["id"], 5 * rare.randint(3, 9), pd))
    for f2 in spare[:3]:
        a = rng.randint(14, 40)
        res = {t[0]: t[2] for t in TYPES.values()}[f2[1]]
        roster.append([pds, f2[0], f2[2], ts(a), ts(a + 20), res + 200, ""])
        trips.append({"trip_id": "T%s-0" % f2[0][1:], "bus_id": f2[0], "service_date": nd.date().isoformat(), "kwh": 60})
    rej_bus = buses[rng.randrange(len(buses))]
    roster.append([pds, "B9990", "North", ts(20), ts(40), 50, ""])
    roster.append([pds, retired[0], "South", ts(22), ts(50), 40, ""])
    bw = spare[3]
    roster.append([pds, bw[0], bw[2], ts(40), ts(30), 40, ""])
    dup = [pds, rej_bus["id"], rej_bus["depot"], ts(10), ts(80), 20, ""]
    pb = buses[rng.randrange(len(buses))]
    plan.append([pds, pb["id"], ts(max(0, pb["a"] - 2)), 15])
    if not shipped:
        # rare fixtures: windows that start before the first slot, end after the last, or are empty
        roster.append([pds, spare[4][0], spare[4][2], ts(-rare.randint(1, 4)), ts(rare.randint(10, 30)), 30, ""])
        roster.append([pds, spare[5][0], spare[5][2], ts(rare.randint(40, 80)), ts(S + rare.randint(1, 4)), 30, ""])
        s_eq = rare.randint(20, 60)
        roster.append([pds, spare[6][0], spare[6][2], ts(s_eq), ts(s_eq), 30, ""])
    for dd in range(1, PAD_DAYS + 1):
        day = pd - timedelta(days=dd)
        dt0 = day + timedelta(hours=12)
        for f2 in rng.sample(spare, 115):
            a = rng.randint(14, 44)
            roster.append([day.date().isoformat(), f2[0], f2[2], ts(a, dt0), ts(a + 24, dt0), 50, rng.choice(com_contracts)])
            trips.append({"trip_id": "T%s-%s" % (f2[0][1:], day.strftime("%m%d")), "bus_id": f2[0],
                          "service_date": (day + timedelta(days=1)).date().isoformat(), "kwh": 10 * rng.randint(4, 16)})
            plan.append([day.date().isoformat(), f2[0], ts(a + 2, dt0), 30])
    rng.shuffle(roster)
    first = next(i for i, r in enumerate(roster) if r[0] == pds and r[1] == rej_bus["id"])
    roster.insert(rng.randint(first + 1, len(roster)), dup)
    if not shipped:
        # rare fixture: a rejected (bad window) row for a plan bus placed before its accepted row
        tb = rare.choice([b for b in buses if b["id"] != rej_bus["id"]])
        at = next(i for i, r in enumerate(roster) if r[0] == pds and r[1] == tb["id"])
        s_b = rare.randint(30, 60)
        roster.insert(rare.randint(0, at), [pds, tb["id"], tb["depot"], ts(s_b), ts(s_b - rare.randint(1, 8)), 40, ""])
    # rows that meet two rejection conditions at once (the earlier rule in rule 4 names the reason)
    taken = {rej_bus["id"]} if shipped else {rej_bus["id"], tb["id"]}
    assert "B9991" not in used and all(f2[0] != "B9991" for f2 in fleet) and len(retired) >= 2
    s_u = rare.randint(20, 60)
    roster.insert(rare.randint(0, len(roster)), [pds, "B9991", rare.choice(DEPOTS), ts(s_u), ts(s_u - rare.randint(1, 8)), 40, ""])
    s_r = rare.randint(20, 60)
    roster.insert(rare.randint(0, len(roster)), [pds, retired[-1], rare.choice(DEPOTS), ts(s_r), ts(s_r - rare.randint(1, 8)), 40, ""])
    db = rare.choice([b for b in buses if b["id"] not in taken])
    at = next(i for i, r in enumerate(roster) if r[0] == pds and r[1] == db["id"])
    s_d = rare.randint(20, 60)
    roster.insert(rare.randint(at + 1, len(roster)), [pds, db["id"], db["depot"], ts(s_d), ts(s_d - rare.randint(1, 8)), 40, ""])
    if not shipped:
        # rare fixture: a published row for a bus that is not on the plan
        plan.append([pds, retired[0], ts(rare.randint(22, 49)), 15])
    _w(os.path.join(out, "roster.csv"), "plan_date,bus_id,depot,arrive,depart,soc_arrival_kwh,contract_id\n"
       + "".join(",".join(str(v) for v in r) + "\n" for r in roster))
    rng.shuffle(trips)
    _w(os.path.join(out, "trips.jsonl"), "".join(json.dumps(t) + "\n" for t in trips))
    _w(os.path.join(out, "published_plan.csv"), "plan_date,bus_id,slot_start,kwh\n"
       + "".join(",".join(str(v) for v in r) + "\n" for r in plan))
    _w(os.path.join(out, "bus_types.json"), json.dumps(
        {t[0]: {"max_kwh_per_slot": t[1], "reserve_kwh": t[2]} for t in TYPES.values()}, indent=2) + "\n")
    _w(os.path.join(out, "depots.json"), json.dumps(
        {"cabinet_kwh_per_slot": CAB_KWH, "depots": [{"depot": d, "cabinets": cab[d]} for d in DEPOTS]}, indent=2) + "\n")
    _w(os.path.join(out, "grid.ini"), "[plan]\nplan_date = %s\nfirst_slot = %s\nslot_minutes = 15\nslots = 96\n\n"
       "[feeder]\nfeeder_kwh_per_slot = %d\n" % (pds, ts(0), feeder_base))
    _w(os.path.join(out, "service_classes.ini"), "[public]\nweight = 4\n\n[commercial]\nweight = 1\n")
    _w(os.path.join(out, "contracts.json"), json.dumps({"contracts": contracts}, indent=2) + "\n")

    def bands(arr):
        s, outb = 0, []
        while s < S:
            s1 = s
            while s1 < S and arr[s1] == arr[s]:
                s1 += 1
            outb.append((ts(s)[11:], ts(s1)[11:], arr[s]))
            s = s1
        return outb

    h0 = pd - timedelta(days=14)
    versions = [(pd - timedelta(days=40), h0 + timedelta(days=6), inst["old"][0]),
                (h0 + timedelta(days=7), pd - timedelta(days=1), inst["old"][1]),
                (pd, pd + timedelta(days=60), inst["price"])]
    rng.shuffle(versions)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tariff currency="EUR" unit="cents_per_kwh">']
    for v0, v1, arr in versions:
        xml.append('  <version valid_from="%s" valid_to="%s">' % (v0.date().isoformat(), v1.date().isoformat()))
        for a, b2, c in bands(arr):
            xml.append('    <band from="%s" to="%s" cents_per_kwh="%d"/>' % (a, b2, c))
        xml.append("  </version>")
    xml.append("</tariff>")
    _w(os.path.join(out, "tariff.xml"), "\n".join(xml) + "\n")
    rate_of = {t2[0]: t2[1] for t2 in TYPES.values()}
    act = {r: [f2[0] for f2 in fleet if f2[3] == "active" and rate_of[f2[1]] == r] for r in (30, 45, 60)}
    srows = []
    for d in DEPOTS:
        for (day, s0, L, r, c) in inst["hist"][d]:
            dd = h0 + timedelta(days=day)
            b0 = dd + timedelta(hours=12)
            srows.append(((dd, s0), [dd.date().isoformat(), d, rng.choice(act[r]), ts(s0, b0), ts(s0 + L, b0), r * L, c]))
    srows.sort(key=lambda z: z[0])
    _w(os.path.join(out, "settlements.csv"), "settled_date,depot,bus_id,start,end,kwh,cents\n"
       + "".join(",".join(str(v) for v in r) + "\n" for _, r in srows))
    md = ["# Disruption notice for %s" % pds, "", "## Cabinet outages", ""]
    md += ["- %s: %d cabinets out of service from %s to %s" % (d, n_out, ts(s0), ts(s1)) for d, n_out, s0, s1 in outages]
    md += ["", "## Feeder derating", ""]
    md += ["- from %s to %s: feeder limit %d kWh per slot" % (ts(s0), ts(s1), lim) for s0, s1, lim in derates]
    md += ["", "## Extra trips", ""]
    md += ["- %s: extra trip on %s, %d kWh" % (bid, day.date().isoformat(), kwh) for bid, kwh, day in extra]
    _w(os.path.join(out, "disruption_notice.md"), "\n".join(md) + "\n")
    return inst


def uplift(seed, out):
    """The hidden folder of seed h (seed, or the first later seed whose cabinets leave room above the
    feeder limit), with one feeder derating line whose limit is above feeder_kwh_per_slot and a
    cluster of buses that can take that limit.  Every hidden row is kept; rows are only inserted.
    Returns (h, added) where added maps a file name to the lines inserted into it."""
    h = seed
    while True:
        inst = render(h, "hidden", out)
        urng = random.Random(h * 7919 + 3)
        feeder = inst["feeder"]
        base = max(set(feeder), key=feeder.count)

        def read(name):
            with open(os.path.join(out, name)) as f:
                return f.read()

        grid = dict(x.split(" = ") for x in read("grid.ini").splitlines() if " = " in x)
        t0 = datetime.strptime(grid["first_slot"], "%Y-%m-%dT%H:%M")
        pds = grid["plan_date"]
        assert int(grid["feeder_kwh_per_slot"]) == base

        def ts(s):
            return (t0 + timedelta(minutes=15 * s)).strftime("%Y-%m-%dT%H:%M")

        def slot(text):
            return int((datetime.strptime(text, "%Y-%m-%dT%H:%M") - t0).total_seconds()) // 900

        dep = json.loads(read("depots.json"))
        limit = {d["depot"]: [d["cabinets"] * dep["cabinet_kwh_per_slot"]] * S for d in dep["depots"]}
        notice = read("disruption_notice.md").splitlines()
        for line in notice:
            if line.startswith("- ") and " cabinets out of service from " in line:
                p = line[2:].split()
                for s in range(max(0, slot(p[7])), min(S, slot(p[9]))):
                    limit[p[0][:-1]][s] -= int(p[1]) * dep["cabinet_kwh_per_slot"]
        L = urng.randint(4, 8)
        starts = [u for u in range(4, S - L - 4) if all(feeder[s] == base for s in range(u, u + L))]

        def mcap(u, d):
            return max(0, min(limit[d][u:u + L]))

        u0 = max(starts, key=lambda u: (sum(mcap(u, d) for d in DEPOTS), -u))
        room = sum(mcap(u0, d) for d in DEPOTS)
        lim = min(int(base * urng.uniform(1.4, 1.9)), room) // 10 * 10
        if lim >= base + base // 5:
            break
        h += 1
    assert base < lim <= room and all(feeder[s] == base for s in range(u0, u0 + L)), (seed, h)
    pub_contracts = ["SCH-%02d" % i for i in range(1, 7)] + ["HSP-%02d" % i for i in range(1, 4)]
    com_contracts = ["COM-%02d" % i for i in range(1, 9)]
    seen = {r.split(",")[0] for r in read("fleet_register.csv").splitlines()[1:]}
    nd = (datetime.strptime(pds, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    added = {"fleet_register.csv": [], "roster.csv": [], "trips.jsonl": [], "published_plan.csv": [],
             "disruption_notice.md": ["- from %s to %s: feeder limit %d kWh per slot" % (ts(u0), ts(u0 + L), lim)]}
    load = {d: 0 for d in DEPOTS}
    i = len(inst["buses"])
    while sum(min(load[d], mcap(u0, d)) for d in DEPOTS) < lim:
        d = urng.choice([d for d in DEPOTS if load[d] < mcap(u0, d)])
        tname, rate, res = TYPES[urng.choice("ABC")]
        load[d] += rate
        need = rate * L // 10 * 10
        bid = "B%04d" % (1000 + i * 3 + urng.randint(0, 2))
        while bid in seen:
            bid = "B%04d" % (int(bid[1:]) + 1)
        seen.add(bid)
        i += 1
        x = urng.randrange(0, 45, 5)
        con = urng.choice(pub_contracts) if urng.random() < 0.25 else urng.choice(com_contracts + [""])
        added["fleet_register.csv"].append("%s,%s,%s,active" % (bid, tname, d))
        added["roster.csv"].append("%s,%s,%s,%s,%s,%d,%s" % (pds, bid, d, ts(u0), ts(u0 + L), res + x, con))
        cut = urng.randrange(5, need + x, 5)
        for j, kwh in enumerate((cut, need + x - cut)):
            added["trips.jsonl"].append(json.dumps({"trip_id": "T%s-%d" % (bid[1:], j), "bus_id": bid,
                                                    "service_date": nd, "kwh": kwh}))
        added["published_plan.csv"].extend("%s,%s,%s,%d" % (pds, bid, ts(s), rate) for s in range(u0, u0 + L))
    for name, rows in added.items():
        lines = read(name).splitlines()
        if name == "disruption_notice.md":
            at = lines.index("## Extra trips") - 1
            while lines[at - 1].startswith("- from ") and lines[at - 1][7:23] > rows[0][7:23]:
                at -= 1
            lines[at:at] = rows
        else:
            head = 0 if name.endswith(".jsonl") else 1
            for row in rows:
                lines.insert(urng.randint(head, len(lines)), row)
        _w(os.path.join(out, name), "\n".join(lines) + "\n")
    return h, added


if __name__ == "__main__":
    if sys.argv[2] == "uplift":
        uplift(int(sys.argv[1]), sys.argv[3])
    else:
        render(int(sys.argv[1]), sys.argv[2], sys.argv[3])
