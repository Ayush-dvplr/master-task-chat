"""Prototype instance generator (core only). Usage: gen_proto.py <seed> <kind:shipped|hidden> <out.json>"""
import json, random, sys

DEPOTS = ["North", "South", "West", "East"]
S = 96  # slot 0 = 12:00


def price_of(s, bands):
    for lo, hi, p in bands:
        if lo <= s < hi:
            return p
    raise ValueError(s)


def gen(seed, kind):
    big = kind == "large"
    kind = "hidden" if big else kind
    rng = random.Random(seed * 7919 + (1 if kind == "hidden" else 0))
    bands = [(0, 16, 31), (16, 40, 27), (40, 72, 14), (72, 96, 22)]  # flat bands -> many ties
    if kind == "hidden":
        # shift band edges a little per corpus
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
        need = min(need, rate * (e - a)) if rng.random() > 0.08 else need  # few windows too short
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
            # shipped: the published plan is the unique optimum (cheapest slots at full rate; the top
            # used price level may be split across its slots), so no supply limit or tie ever decides
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
    # unique ids
    seen = set()
    for b in buses:
        while b["id"] in seen:
            b["id"] = "B%04d" % (int(b["id"][1:]) + 1)
        seen.add(b["id"])
    if kind == "shipped":
        cap = {d: [100000] * S for d in DEPOTS}
        feeder = [10 ** 6] * S
    else:
        # demand-driven binding: per-slot demand in cheap band if every bus charged cheapest
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
        # derating block over the arrival peak: weighted unmet energy fires on most hidden corpora
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


if __name__ == "__main__":
    inst = gen(int(sys.argv[1]), sys.argv[2])
    json.dump(inst, open(sys.argv[3], "w"))
