"""Seeded stdlib generator for the outage-window-replan data set.

usage: python3 datagen.py <out_data_dir> [--seed N] [--tier shipped|hidden]

tier shipped: quiet lanes (every plausible solver in proto/lanekill agrees with the reference),
tier hidden: contended lanes with planted clusters, tie pairs and keep pairs.
The hidden half is copied into tests/ later; only the shipped quiet check imports proto/.
"""
import json
import os
import random
import sys

H = 91
REGIONS = ["North", "South", "West", "East"]
TYPES = ["line", "substation", "protection"]
PUB_TS = "2026-03-01T06:00:00Z"
BAND = {1: (150, 399), 2: (400, 699), 3: (700, 950)}
CLASS_W = {"commercial": 1, "public": 2}
DEFER = 4
# hidden-tier scale knobs (members per cluster, clusters per lane, lane size)
CL_N = (7, 9)
NCL = (3,)
N_RANGE = (26, 32)
CL_W = (6, 9)
BRIDGE = (1, 2)


def factor_calendar(rng):
    f = [0] * (H + 2)
    d = 1
    while d <= H:
        n = rng.randint(3, 8)
        v = rng.choice([1, 2, 2, 3])
        for x in range(d, min(H, d + n - 1) + 1):
            f[x] = v
        d += n
    return f


def place_valleys(rng, f):
    """Five factor-1 valleys, each flanked by three factor-3 days."""
    out = []
    pos = rng.randint(2, 5)
    for _ in range(5):
        lv = rng.randint(6, 8)
        a = pos + 3
        for x in range(pos, a):
            f[x] = 3
        for x in range(a, a + lv):
            f[x] = 1
        for x in range(a + lv, a + lv + 3):
            f[x] = 3
        out.append((a, lv))
        pos = a + lv + 3 + rng.randint(0, 2)
    assert pos - 1 <= H
    return out


def overlaps(e, l, wins):
    return any(not (l < a or e > b) for a, b in wins)


def lane_requests(lrng, trng, krng, tier, valleys, b):
    """Returns (reqs, loss runs, protected windows). Each req: dur, e, l, crews, w, new, role, pubset."""
    reqs = []
    loss = [0] * (H + 2)
    protected = []
    busy = []
    if tier == "hidden":
        order = list(range(5))
        lrng.shuffle(order)
        ncl = lrng.choice(NCL)
        for c in range(ncl):
            a, lv = valleys[order[c]]
            busy.append((a - 3, a + lv + 2))
            for x in range(a - 3, a + lv + 3):
                loss[x] = max(loss[x], b - 1)
            for _ in range(lrng.randint(*CL_N)):
                reqs.append(dict(dur=lrng.randint(2, 4), e=a - lrng.randint(0, 3), l=a + lv - 1 + lrng.randint(0, 3),
                                 crews=1, w=lrng.randint(*CL_W), new=lrng.random() < 0.4, role="cluster"))
        cl_valleys = sorted(valleys[order[c]] for c in range(ncl))
        for (a1, lv1), (a2, lv2) in zip(cl_valleys, cl_valleys[1:]):
            for _ in range(lrng.randint(*BRIDGE)):
                reqs.append(dict(dur=lrng.randint(2, 3), e=a1 + lrng.randint(0, 2), l=a2 + lv2 - 1 - lrng.randint(0, 2),
                                 crews=1, w=lrng.randint(*CL_W), new=lrng.random() < 0.4, role="cluster"))
        a, lv = valleys[order[ncl]]
        d1, d2 = trng.randint(1, 3), trng.randint(1, 3)
        t = a + trng.randint(0, lv - d1 - d2)
        for x in range(t, t + d1 + d2):
            loss[x] = max(loss[x], b - 1)
        wl = trng.randint(2, 5)
        wh = wl + trng.randint(2, 6)
        reqs.append(dict(dur=d1, e=t, l=t + d1 + d2 - 1, crews=1, w=wl, new=True, role="tieL"))
        reqs.append(dict(dur=d2, e=t, l=t + d1 + d2 - 1, crews=1, w=wh, new=True, role="tieH"))
        protected.append((t, t + d1 + d2 - 1))
        busy.append((t, t + d1 + d2 - 1))
        a, lv = valleys[order[ncl + 1]]
        t = a + krng.randint(0, lv - 5)
        for x in range(t, t + 5):
            loss[x] = max(loss[x], b - 1)
        wx = krng.randint(2, 5)
        wy = wx + krng.randint(1, 6)
        reqs.append(dict(dur=2, e=t, l=t + 4, crews=1, w=wx, new=False, role="keepX", pubset=t + 1))
        reqs.append(dict(dur=2, e=t, l=t + 4, crews=1, w=wy, new=True, role="keepY"))
        protected.append((t, t + 4))
        busy.append((t, t + 4))
        n = lrng.randint(*N_RANGE)
        pnew = 0.3
    else:
        n = lrng.randint(6, 10)
        pnew = 0.25
        if lrng.random() < 0.35:
            t = lrng.randint(10, H - 30)
            for x in range(t, t + 3):
                loss[x] = b
            reqs.append(dict(dur=2, e=t, l=t + 2, crews=1, w=lrng.randint(1, 12), new=False, role="stuck"))
            protected.append((t, t + 2))
            busy.append((t, t + 2))
    while len(reqs) < n:
        dur = lrng.randint(1, 4)
        e = lrng.randint(1, H - 14)
        l = min(H, e + lrng.randint(dur + 2, dur + 12) - 1)
        if overlaps(e, l, protected):
            continue
        reqs.append(dict(dur=dur, e=e, l=l, crews=lrng.choice([1, 1, b]), w=lrng.randint(1, 12),
                         new=lrng.random() < pnew, role="filler"))
    # extra crew loss written as two overlapping notices (cumulative, floored at zero)
    extra = []
    if lrng.random() < 0.4:
        for _ in range(20):
            ln = lrng.randint(3, 6)
            u = lrng.randint(1, H - ln)
            if not overlaps(u, u + ln - 1, busy):
                m = u + lrng.randint(1, ln - 2)
                extra = [(u, m, 1), (m, u + ln - 1, 1)]
                break
    return reqs, loss, protected, busy, extra


def runs_of(loss):
    out = []
    d = 1
    while d <= H:
        if loss[d] > 0:
            v = loss[d]
            s = d
            while d + 1 <= H and loss[d + 1] == v:
                d += 1
            out.append((s, d, v))
        d += 1
    return out


def published_plan(rng, reqs, pre_cap, blackout, inc, prec):
    """Pre-disruption plan over the published-origin requests: random feasible start or deferred."""
    use = [0] * (H + 2)
    start = {}
    idx = [i for i, r in enumerate(reqs) if not r["new"]]
    first = [i for i in idx if "pubset" in reqs[i]]
    rest = [i for i in idx if "pubset" not in reqs[i]]
    rng.shuffle(rest)
    for i in first + rest:
        r = reqs[i]
        cands = []
        for s in range(r["e"], r["l"] - r["dur"] + 2):
            if "pubset" in r and s != r["pubset"]:
                continue
            if s in blackout:
                continue
            if any(use[x] + r["crews"] > pre_cap[x] for x in range(s, s + r["dur"])):
                continue
            ok = True
            for a, c in inc:
                j = c if a == i else a if c == i else None
                if j is not None and start.get(j) is not None:
                    sj = start[j]
                    if s < sj + reqs[j]["dur"] and sj < s + r["dur"]:
                        ok = False
            for a, c in prec:
                if c == i and a in start and (start[a] is None or s < start[a] + reqs[a]["dur"]):
                    ok = False
                if a == i and c in start and start[c] is not None and start[c] < s + r["dur"]:
                    ok = False
                if c == i and a not in start and not reqs[a]["new"]:
                    ok = False
            if ok:
                cands.append(s)
        if "pubset" in r:
            assert cands == [r["pubset"]], (r, cands)
        s = rng.choice(cands) if cands else None
        start[i] = s
        if s is not None:
            for x in range(s, s + r["dur"]):
                use[x] += r["crews"]
    return start


def optimal_published(reqs, pre_cap, f, black, inc, prec):
    """Shipped tier: the published plan is the optimum of the pre-disruption season."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "proto"))
    from lane import Lane, reference
    keep = [i for i, r in enumerate(reqs) if not r["new"]]
    pos = {i: k for k, i in enumerate(keep)}
    d = dict(H=H, cap=pre_cap, factor=f, blackout=black,
             reqs=[dict(id=str(i), crews=reqs[i]["crews"], dur=reqs[i]["dur"], e=reqs[i]["e"], l=reqs[i]["l"],
                        w=reqs[i]["w"], pub=None) for i in keep],
             incompat=[(pos[a], pos[b]) for a, b in inc if a in pos and b in pos],
             prec=[(pos[a], pos[b]) for a, b in prec if a in pos and b in pos])
    plan = reference(Lane(d))
    return {i: (None if plan[pos[i]] == H + 1 else plan[pos[i]]) for i in keep}


def build(seed, tier, quiet_check=None, max_tries=400):
    rng = random.Random(seed)
    trng_root = random.Random(seed * 104729 + 17)
    krng_root = random.Random(seed * 15485863 + 3)
    used_ids = set()
    used_crews = set()

    def new_id(r):
        while True:
            x = "A%05d" % r.randint(10000, 99999)
            if x not in used_ids:
                used_ids.add(x)
                return x

    region_f = {}
    region_valleys = {}
    region_black = {}
    for R in REGIONS:
        f = factor_calendar(rng)
        valleys = place_valleys(rng, f) if tier == "hidden" else []
        black = set()
        cheap = [d for d in range(1, H + 1) if f[d] == 1]
        while len(black) < 6:
            # shipped seasons put the blackout days on cheap days, where they change the best start
            x = rng.choice(cheap) if tier == "shipped" and len(cheap) > 8 else rng.randint(1, H)
            if tier == "hidden" and any(a - 3 <= x <= a + lv + 2 for a, lv in valleys):
                continue
            black.add(x)
        region_f[R], region_valleys[R], region_black[R] = f, valleys, sorted(black)

    lanes = {}
    for R in REGIONS:
        for T in TYPES:
            tseed = trng_root.randint(0, 10 ** 9)
            kseed = krng_root.randint(0, 10 ** 9)
            for attempt in range(max_tries):
                lrng = random.Random("%d:%s:%s:%d" % (seed, R, T, attempt))
                trng = random.Random("%d:%d" % (tseed, attempt))
                krng = random.Random("%d:%d" % (kseed, attempt))
                b = lrng.choice([1, 2, 2])
                reqs, loss, protected, busy, extra = lane_requests(lrng, trng, krng, tier, region_valleys[R], b)
                pre_cap = [b] * (H + 2)
                leave_days = []
                if b == 2:
                    for d in range(1, H + 1):
                        if lrng.random() < 0.04 and not overlaps(d, d, busy):
                            pre_cap[d] = 1
                            leave_days.append(d)
                m = len(reqs)
                plain = [i for i in range(m) if reqs[i]["role"] in ("filler", "cluster")]
                inc, prec = [], []
                for _ in range(lrng.randint(0, 2)):
                    i, j = lrng.sample(plain, 2)
                    if (min(i, j), max(i, j)) not in inc:
                        inc.append((min(i, j), max(i, j)))
                fill = [i for i in range(m) if reqs[i]["role"] == "filler"]
                if lrng.random() < 0.6 and len(fill) >= 2:
                    i, j = lrng.sample(fill, 2)
                    if reqs[i]["e"] > reqs[j]["e"]:
                        i, j = j, i
                    if (min(i, j), max(i, j)) not in inc:
                        prec.append((i, j))
                stuck = [i for i in range(m) if reqs[i]["role"] == "stuck"]
                later = [j for j in fill if stuck and reqs[j]["e"] > reqs[stuck[0]]["l"]]
                if stuck and later and lrng.random() < 0.6:
                    prec.append((stuck[0], lrng.choice(later)))
                if tier == "shipped":
                    start = optimal_published(reqs, pre_cap, region_f[R], region_black[R], inc, prec)
                else:
                    start = published_plan(lrng, reqs, pre_cap, set(region_black[R]), inc, prec)
                withdraw = set()
                for i in fill:
                    if not reqs[i]["new"] and lrng.random() < 0.06:
                        withdraw.add(i)
                # ids: random, with the planted pair order enforced (lighter / published member first)
                ids = [new_id(lrng) for _ in range(m)]
                for lo, hi in (("tieL", "tieH"), ("keepX", "keepY")):
                    pi = [k for k in range(m) if reqs[k]["role"] == lo]
                    qi = [k for k in range(m) if reqs[k]["role"] == hi]
                    if pi and qi and ids[pi[0]] > ids[qi[0]]:
                        ids[pi[0]], ids[qi[0]] = ids[qi[0]], ids[pi[0]]
                for k in range(m):
                    reqs[k]["asset_id"] = ids[k]
                post_cap = list(pre_cap)
                for s_, e_, v in runs_of(loss):
                    for x in range(s_, e_ + 1):
                        post_cap[x] = max(0, post_cap[x] - v)
                for s_, e_, v in extra:
                    for x in range(s_, e_ + 1):
                        post_cap[x] = max(0, post_cap[x] - v)
                lane = dict(R=R, T=T, b=b, reqs=reqs, loss=loss, extra=extra, pre_cap=pre_cap, post_cap=post_cap,
                            inc=inc, prec=prec, start=start, withdraw=withdraw, leave_days=leave_days)
                if quiet_check is None or quiet_check(lane_dict(lane, region_f[R], region_black[R])):
                    break
                used_ids.difference_update(ids)
            else:
                raise RuntimeError("no quiet lane for %s %s %s" % (R, T, QUIET_FAILS))
            lanes[(R, T)] = lane
    return render(seed, tier, rng, lanes, region_f, region_black, used_ids, used_crews, new_id)


def lane_dict(lane, f, black):
    """Lane in the proto/lane.py format (post-disruption, withdrawn removed, sorted by asset id)."""
    keep = [i for i in range(len(lane["reqs"])) if i not in lane["withdraw"]]
    keep.sort(key=lambda i: lane["reqs"][i]["asset_id"])
    pos = {i: k for k, i in enumerate(keep)}
    out = []
    for i in keep:
        r = lane["reqs"][i]
        if r["new"]:
            pub = None
        else:
            pub = lane["start"][i] if lane["start"][i] is not None else H + 1
        out.append(dict(id=r["asset_id"], crews=r["crews"], dur=r["dur"], e=r["e"], l=r["l"], w=r["w"], pub=pub,
                        role=r["role"]))
    inc = [(min(pos[a], pos[b]), max(pos[a], pos[b])) for a, b in lane["inc"] if a in pos and b in pos]
    prec = [(pos[a], pos[b]) for a, b in lane["prec"] if a in pos and b in pos]
    return dict(H=H, cap=lane["post_cap"], factor=f, blackout=black, reqs=out, incompat=inc, prec=prec)


def peak_rows(rng, R, d, v):
    lo, hi = BAND[v]
    roll = rng.random()
    if roll < 0.08 and v > 1:
        peak = lo
    elif roll < 0.16 and v < 3:
        peak = hi
    else:
        peak = rng.randint(lo, hi)
    k = rng.randint(1, 6)
    rows = []
    for p in range(1, 7):
        val = peak if p == k else rng.randint(100, peak)
        rows.append("%s\t%d\t%d\t%d" % (R, d, p, val))
    return rows


def ts_at(minute):
    day = 26 + minute // 1440
    month = 2
    if day > 28:
        day -= 28
        month = 3
    hh, mm = divmod(minute % 1440, 60)
    return "2026-%02d-%02dT%02d:%02d:00Z" % (month, day, hh, mm)


PUB_MINUTE = (3 * 1440) + 6 * 60  # 2026-03-01T06:00 counted from 2026-02-26T00:00


def render(seed, tier, rng, lanes, region_f, region_black, used_ids, used_crews, new_id):
    files = {}
    # ---------------- requests and plan ----------------
    pub_records = []   # (asset_id, dict) accepted requests.json records
    log_new = []       # NEW_REQUEST events after publication
    withdraws = []
    plan = []
    inc_pairs, prec_pairs = [], []
    req_assets = []
    for (R, T), lane in lanes.items():
        reqs = lane["reqs"]
        for i, r in enumerate(reqs):
            rec = {"asset_id": r["asset_id"], "duration_days": r["dur"], "earliest_start": r["e"],
                   "latest_finish": r["l"], "crews": r["crews"]}
            req_assets.append((r["asset_id"], R, T, r["w"]))
            if r["new"]:
                log_new.append(rec)
            else:
                pub_records.append(rec)
                s = lane["start"][i]
                plan.append({"asset_id": r["asset_id"], "status": "scheduled", "start": s} if s is not None
                            else {"asset_id": r["asset_id"], "status": "deferred"})
                if i in lane["withdraw"]:
                    withdraws.append(r["asset_id"])
        for a, c in lane["inc"]:
            inc_pairs.append([reqs[a]["asset_id"], reqs[c]["asset_id"]])
        for a, c in lane["prec"]:
            prec_pairs.append({"before": reqs[a]["asset_id"], "after": reqs[c]["asset_id"]})
    rng.shuffle(pub_records)
    rng.shuffle(log_new)
    # ---------------- assets ----------------
    assets = []
    for aid, R, T, _ in req_assets:
        assets.append({"asset_id": aid, "region": R, "kind": "line" if T == "line" else "transformer", "crew_type": T})
    spare = []
    while len(assets) < 2500:
        aid = new_id(rng)
        R = rng.choice(REGIONS)
        T = rng.choice(TYPES)
        assets.append({"asset_id": aid, "region": R, "kind": "line" if T == "line" else "transformer", "crew_type": T})
        spare.append((aid, R, T))
    rng.shuffle(assets)
    files["assets.jsonl"] = "".join(json.dumps(a) + "\n" for a in assets)
    # ---------------- bad records in requests.json ----------------
    def ghost():
        while True:
            x = "A%05d" % rng.randint(10000, 99999)
            if x not in used_ids:
                used_ids.add(x)
                return x
    records = list(pub_records)
    bad = []
    for _ in range(rng.randint(1, 2)):
        bad.append(("ins", {"asset_id": ghost(), "duration_days": 2, "earliest_start": 20, "latest_finish": 30, "crews": 1}))
    sp = list(spare)
    rng.shuffle(sp)
    k = 0
    for _ in range(rng.randint(1, 2)):
        aid = sp[k][0]; k += 1
        if rng.random() < 0.5:
            bad.append(("ins", {"asset_id": aid, "duration_days": 3, "earliest_start": 0, "latest_finish": 12, "crews": 1}))
        else:
            bad.append(("ins", {"asset_id": aid, "duration_days": 3, "earliest_start": 85, "latest_finish": 92, "crews": 1}))
    for _ in range(rng.randint(1, 2)):
        aid = sp[k][0]; k += 1
        bad.append(("ins", {"asset_id": aid, "duration_days": 5, "earliest_start": 40, "latest_finish": 43, "crews": 1}))
    for _ in range(rng.randint(1, 3)):
        orig = rng.choice(pub_records)
        bad.append(("dup", dict(orig, duration_days=orig["duration_days"] % 4 + 1)))
    for kind, rec in bad:
        if kind == "ins":
            records.insert(rng.randint(0, len(records)), rec)
        else:
            p = next(j for j, x in enumerate(records) if x["asset_id"] == rec["asset_id"])
            records.insert(rng.randint(p + 1, len(records)), rec)
    # a rejected record followed later by a valid record of the same asset: the later one is accepted
    files["requests.json"] = json.dumps({"season": {"first_day": 1, "last_day": H}, "requests": records}, indent=1) + "\n"
    plan.sort(key=lambda x: x["asset_id"])
    files["published_plan.json"] = json.dumps({"published_at": PUB_TS, "plan": plan}, indent=1) + "\n"
    # ---------------- customers ----------------
    rows = []
    for aid, R, T, w in req_assets:
        npub = rng.randint(0, w // 2)
        ncom = w - 2 * npub
        rows += [(aid, "public")] * npub + [(aid, "commercial")] * ncom
    while len(rows) < 9000:
        rows.append((rng.choice(sp)[0], rng.choice(["commercial", "commercial", "public"])))
    rng.shuffle(rows)
    cids = rng.sample(range(100000, 999999), len(rows))
    files["customers.csv"] = "customer_id,asset_id,class\n" + "".join(
        "C%06d,%s,%s\n" % (c, a, k) for c, (a, k) in zip(cids, rows))
    # ---------------- load forecast ----------------
    lines = ["region\tday\tperiod\tload_mw"]
    for R in REGIONS:
        for d in range(1, H + 1):
            lines += peak_rows(rng, R, d, region_f[R][d])
    files["load_forecast.tsv"] = "\n".join(lines) + "\n"
    # ---------------- crew roster ----------------
    roster = []
    for (R, T), lane in lanes.items():
        b = lane["b"]
        crews = []
        while len(crews) < b + 1:
            c = "K%04d" % rng.randint(1000, 9999)
            if c not in used_crews:
                used_crews.add(c)
                crews.append(c)
        for d in range(1, H + 1):
            on = lane["pre_cap"][d]
            order = crews[d % len(crews):] + crews[:d % len(crews)]
            for j, c in enumerate(order):
                st = "on_duty" if j < on else rng.choice(["leave", "training"])
                roster.append({"crew_id": c, "region": R, "crew_type": T, "day": d, "status": st})
    rng.shuffle(roster)
    files["crew_roster.jsonl"] = "".join(json.dumps(x) + "\n" for x in roster)
    # ---------------- network constraints ----------------
    ghosts = [ghost() for _ in range(2)]
    inc_all = inc_pairs + [[ghosts[0], rng.choice(req_assets)[0]]]
    prec_all = prec_pairs + [{"before": ghosts[1], "after": rng.choice(req_assets)[0]}]
    rng.shuffle(inc_all)
    files["network_constraints.json"] = json.dumps({"incompatible": inc_all, "precedence": prec_all}, indent=1) + "\n"
    files["region_calendar.json"] = json.dumps({R: {"blackout_days": region_black[R]} for R in REGIONS}, indent=1) + "\n"
    # ---------------- control-room log ----------------
    post = []
    for (R, T), lane in lanes.items():
        for s_, e_, v in runs_of(lane["loss"]):
            post.append("WARN CREW_LOSS region=%s crew_type=%s from=%d to=%d count=%d" % (R, T, s_, e_, v))
        for s_, e_, v in lane["extra"]:
            post.append("WARN CREW_LOSS region=%s crew_type=%s from=%d to=%d count=%d" % (R, T, s_, e_, v))
    for rec in log_new:
        post.append("INFO NEW_REQUEST asset_id=%s duration_days=%d earliest_start=%d latest_finish=%d crews=%d" % (
            rec["asset_id"], rec["duration_days"], rec["earliest_start"], rec["latest_finish"], rec["crews"]))
    for aid in withdraws:
        post.append("INFO WITHDRAW asset_id=%s" % aid)
    rng.shuffle(post)
    # log-side rejections and ignored lines (after publication)
    if withdraws:
        aid = withdraws[0]
        rec = next(x for x in pub_records if x["asset_id"] == aid)
        p = post.index("INFO WITHDRAW asset_id=%s" % aid)
        post.insert(rng.randint(p + 1, len(post)), "INFO NEW_REQUEST asset_id=%s duration_days=%d earliest_start=%d latest_finish=%d crews=1" % (
            aid, rec["duration_days"], rec["earliest_start"], rec["latest_finish"]))
    post.insert(rng.randint(0, len(post)), "INFO NEW_REQUEST asset_id=%s duration_days=2 earliest_start=30 latest_finish=40 crews=1" % ghost())
    post.insert(rng.randint(0, len(post)), "INFO NEW_REQUEST asset_id=%s duration_days=4 earliest_start=50 latest_finish=52 crews=1" % sp[k][0]); k += 1
    post.insert(rng.randint(0, len(post)), "INFO WITHDRAW asset_id=%s" % sp[k][0]); k += 1
    post.insert(rng.randint(0, len(post)), "WARN CREW_RESTORE region=%s crew_type=line from=10 to=20 count=1" % rng.choice(REGIONS))
    post.insert(rng.randint(0, len(post)), "WARN CREW_LOSS region=%s crew_type=line from=30 to=24 count=1" % rng.choice(REGIONS))
    post.insert(rng.randint(0, len(post)), "INFO NEW_REQUEST asset_id=%s duration_days=two earliest_start=5 latest_finish=20 crews=1" % sp[k][0]); k += 1
    pre = []
    for _ in range(rng.randint(2, 3)):
        pre.append("WARN CREW_LOSS region=%s crew_type=%s from=%d to=%d count=1" % (
            rng.choice(REGIONS), rng.choice(TYPES), *sorted(rng.sample(range(1, H + 1), 2))))
    for _ in range(rng.randint(1, 2)):
        rec = rng.choice(pub_records)
        pre.append("INFO NEW_REQUEST asset_id=%s duration_days=%d earliest_start=%d latest_finish=%d crews=%d" % (
            rec["asset_id"], rec["duration_days"], rec["earliest_start"], rec["latest_finish"], rec["crews"]))
    pre.append("INFO NEW_REQUEST asset_id=%s duration_days=2 earliest_start=60 latest_finish=70 crews=1" % sp[k][0]); k += 1
    pre.append("WARN CREW_LOSS region=North crew_type=protection from=12 count=1")
    rng.shuffle(pre)
    total = 2600
    n_pre_slots = total * PUB_MINUTE // (PUB_MINUTE + 18 * 60)
    pre_minutes = sorted(rng.sample(range(0, PUB_MINUTE + 1), n_pre_slots))
    post_minutes = sorted(rng.sample(range(PUB_MINUTE + 1, PUB_MINUTE + 18 * 60), total - n_pre_slots))
    pre_pos = set(rng.sample(range(len(pre_minutes)), len(pre)))
    post_pos = sorted(rng.sample(range(len(post_minutes)), len(post)))
    out = []
    seq = 0
    it = iter(pre)
    for j, mnt in enumerate(pre_minutes):
        if j in pre_pos:
            out.append("%s %s" % (ts_at(mnt), next(it)))
        else:
            seq += 1
            out.append("%s INFO HEARTBEAT seq=%d" % (ts_at(mnt), seq))
    pp = dict(zip(post_pos, post))
    for j, mnt in enumerate(post_minutes):
        if j in pp:
            out.append("%s %s" % (ts_at(mnt), pp[j]))
        else:
            seq += 1
            out.append("%s INFO HEARTBEAT seq=%d" % (ts_at(mnt), seq))
    files["control_room.log"] = "\n".join(out) + "\n"
    files["risk_policy.toml"] = (
        "[class_weight]\ncommercial = 1\npublic = 2\n\n"
        "[load_band]\n# daily peak load_mw at or above min_mw takes the band factor\n"
        "bands = [\n  { min_mw = 0, factor = 1 },\n  { min_mw = 400, factor = 2 },\n  { min_mw = 700, factor = 3 },\n]\n\n"
        "[deferral]\ndefer_factor = %d\n" % DEFER)
    return files


def quiet(d):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "proto"))
    import time
    from lane import Lane, reference
    import lanekill as K
    L = Lane(d)
    ref = reference(L)
    plans = [K.g_weight(L), K.g_edf(L), K.g_id(L), K.repair(L), K.g_swap(L, time.time() + 2), K.nomove(L, d),
             K.dp_tuple_nofix(L)]
    for order in (list(range(L.n)), sorted(range(L.n), key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i))):
        plans.append(K.bb(L, order, time.time() + 2, seed_plan=K.g_weight(L))[0])
        plans.append(K.bb(L, order, time.time() + 2, lex=False, seed_plan=K.g_weight(L))[0])
    names = ["g_weight", "g_edf", "g_id", "repair", "g_swap", "nomove", "dp_nofix", "bb_id", "bb_id_nolex",
             "bb_heur", "bb_heur_nolex"]
    bad = [nm for nm, p in zip(names, plans) if p is None or K.label(L, p, ref) != "EXACT"]
    for nm in bad:
        QUIET_FAILS[nm] = QUIET_FAILS.get(nm, 0) + 1
    return not bad


QUIET_FAILS = {}


def main():
    out = sys.argv[1]
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 594183
    tier = sys.argv[sys.argv.index("--tier") + 1] if "--tier" in sys.argv else "shipped"
    global CL_N, NCL, N_RANGE, CL_W, BRIDGE
    if "--bridge" in sys.argv:
        BRIDGE = tuple(int(x) for x in sys.argv[sys.argv.index("--bridge") + 1].split(","))
    if "--clw" in sys.argv:
        CL_W = tuple(int(x) for x in sys.argv[sys.argv.index("--clw") + 1].split(","))
    if "--cl" in sys.argv:
        CL_N = tuple(int(x) for x in sys.argv[sys.argv.index("--cl") + 1].split(","))
    if "--ncl" in sys.argv:
        NCL = tuple(int(x) for x in sys.argv[sys.argv.index("--ncl") + 1].split(","))
    if "--n" in sys.argv:
        N_RANGE = tuple(int(x) for x in sys.argv[sys.argv.index("--n") + 1].split(","))
    files = build(seed, tier, quiet_check=quiet if tier == "shipped" else None)
    os.makedirs(out, exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(out, name), "w", newline="\n") as fh:
            fh.write(text)
    print("wrote", len(files), "files to", out)


if __name__ == "__main__":
    main()
