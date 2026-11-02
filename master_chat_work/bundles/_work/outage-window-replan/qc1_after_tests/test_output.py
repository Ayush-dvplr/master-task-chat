"""Checks for the season replan task.

Expected documents are derived here, from the shipped input files and from fresh input
sets drawn by a seeded generator that lives only in this file. The delivered program is
run with the command the instruction states, as an unprivileged user, from a working
directory of its own, and every output document is compared whole.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import ast
import base64
import csv
import json
import os
import pwd
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import zlib
from pathlib import Path

from rewardkit import criteria, criterion


# ---- seeded generator for fresh input sets ----

H = 91


REGIONS = ["North", "South", "West", "East"]


TYPES = ["line", "substation", "protection"]


CL_N = (7, 9)


NCL = (3,)


N_RANGE = (26, 32)


CL_W = (6, 9)


BRIDGE = (1, 2)


def release_literals(seed):
    r = random.Random(seed * 31 + 5)
    pub_minute = r.randint(2 * 1440, 4 * 1440)
    if pub_minute == 3 * 1440 + 360:
        pub_minute += 1
    lit = dict(pub_minute=pub_minute, public=r.choice([3, 4]), defer=r.choice([5, 6]),
               band2=r.choice([380, 420, 450]), band3=r.choice([680, 720, 750]))
    assert 2 * 1440 <= lit["pub_minute"] <= 4 * 1440 and lit["band2"] < lit["band3"] < 950
    lit["band"] = {1: (150, lit["band2"] - 1), 2: (lit["band2"], lit["band3"] - 1), 3: (lit["band3"], 950)}
    return lit


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


def lane_requests(lrng, trng, krng, srng, tier, valleys, b):
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
        if srng.random() < 0.6:
            for _ in range(50):
                t = srng.randint(4, H - 20)
                if not overlaps(t - 1, t + 3, busy):
                    for x in range(t, t + 3):
                        loss[x] = b
                    reqs.append(dict(dur=2, e=t, l=t + 2, crews=1, w=srng.randint(1, 12), new=False, role="stuck"))
                    protected.append((t, t + 2))
                    busy.append((t, t + 2))
                    break
        n = max(n, len(reqs) + 4)
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
    tries = 0
    while len(reqs) < n and tries < 5000:
        tries += 1
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


def build_inputs(seed, tier="hidden", quiet_check=None, max_tries=400):
    lit = release_literals(seed)
    rng = random.Random(seed)
    trng_root = random.Random(seed * 104729 + 17)
    krng_root = random.Random(seed * 15485863 + 3)
    srng_root = random.Random(seed * 2654435761 + 7)
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
            sseed = srng_root.randint(0, 10 ** 9)
            for attempt in range(max_tries):
                lrng = random.Random("%d:%s:%s:%d" % (seed, R, T, attempt))
                trng = random.Random("%d:%d" % (tseed, attempt))
                krng = random.Random("%d:%d" % (kseed, attempt))
                srng = random.Random("%d:%d" % (sseed, attempt))
                b = lrng.choice([1, 2, 2])
                reqs, loss, protected, busy, extra = lane_requests(lrng, trng, krng, srng, tier, region_valleys[R], b)
                pre_cap = [b] * (H + 2)
                leave_days = []
                if b == 2:
                    for d in range(1, H + 1):
                        if lrng.random() < 0.04 and not overlaps(d, d, busy):
                            pre_cap[d] = 1
                            leave_days.append(d)
                # incompatible twin: a new request on the same window as a crews-1 filler, on a lane with room for both
                irng = random.Random("%d:%s:%s:inc:%d" % (seed, R, T, attempt))
                twin = None
                cands = [i for i in range(len(reqs)) if reqs[i]["role"] == "filler" and reqs[i]["crews"] == 1]
                if b == 2 and cands and irng.random() < 0.7:
                    src = irng.choice(cands)
                    reqs.append(dict(dur=reqs[src]["dur"], e=reqs[src]["e"], l=reqs[src]["l"], crews=1,
                                     w=irng.randint(1, 12), new=True, role="incpair"))
                    twin = (src, len(reqs) - 1)
                # precedence follower: a new request whose window opens with a crews-1 filler's window
                prng = random.Random("%d:%s:%s:prec:%d" % (seed, R, T, attempt))
                follow = None
                cands = [i for i in cands if twin is None or i != twin[0]]
                if b == 2 and cands and prng.random() < 0.8:
                    src = prng.choice(cands)
                    fd = prng.randint(1, 3)
                    fl = min(H, reqs[src]["l"] + fd + prng.randint(0, 3))
                    reqs.append(dict(dur=fd, e=reqs[src]["e"], l=fl, crews=1,
                                     w=prng.randint(4, 12), new=True, role="precpair"))
                    follow = (src, len(reqs) - 1)
                m = len(reqs)
                plain = [i for i in range(m) if reqs[i]["role"] in ("filler", "cluster")]
                inc, prec = [], []
                if twin is not None:
                    inc.append(twin)
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
                if follow is not None and follow[0] not in [c for _, c in prec]:
                    prec.append(follow)
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
                raise RuntimeError("no lane for %s %s" % (R, T))
            for r in reqs:
                assert 1 <= r["e"] and r["l"] <= H and r["dur"] >= 1 and r["l"] - r["e"] + 1 >= r["dur"], r
                assert r["crews"] in (1, 2) and 1 <= r["w"] <= 12, r
            lanes[(R, T)] = lane
    return render(seed, lit, rng, lanes, region_f, region_black, used_ids, used_crews, new_id)


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


def peak_rows(rng, R, d, v, band):
    lo, hi = band[v]
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


def render(seed, lit, rng, lanes, region_f, region_black, used_ids, used_crews, new_id):
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
    # records that fail two checks at once, from their own stream
    orng = random.Random(seed * 7 + 3)
    aid = sp[k][0]; k += 1
    bad.append(("ins", {"asset_id": aid, "duration_days": 6, "earliest_start": 0, "latest_finish": orng.randint(2, 4), "crews": 1}))
    orig = orng.choice(pub_records)
    bad.append(("dup", dict(orig, duration_days=orig["latest_finish"] - orig["earliest_start"] + 2)))
    for kind, rec in bad:
        if kind == "ins":
            records.insert(rng.randint(0, len(records)), rec)
        else:
            p = next(j for j, x in enumerate(records) if x["asset_id"] == rec["asset_id"])
            records.insert(rng.randint(p + 1, len(records)), rec)
    while True:
        gid = "A%05d" % orng.randint(10000, 99999)
        if gid not in used_ids:
            used_ids.add(gid)
            break
    records.insert(orng.randint(0, len(records)), {"asset_id": gid, "duration_days": 2, "earliest_start": 0,
                                                   "latest_finish": orng.randint(5, 12), "crews": 1})
    # a rejected record followed later by a valid record of the same asset: the later one is accepted
    files["requests.json"] = json.dumps({"season": {"first_day": 1, "last_day": H}, "requests": records}, indent=1) + "\n"
    plan.sort(key=lambda x: x["asset_id"])
    files["published_plan.json"] = json.dumps({"published_at": ts_at(lit["pub_minute"]), "plan": plan}, indent=1) + "\n"
    # ---------------- customers ----------------
    rows = []
    for aid, R, T, w in req_assets:
        npub = rng.randint(0, w // lit["public"])
        ncom = w - lit["public"] * npub
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
            lines += peak_rows(rng, R, d, region_f[R][d], lit["band"])
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
    PUB_MINUTE = lit["pub_minute"]
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
    # one notice stamped exactly at the publication time
    brng = random.Random(seed * 11 + 5)
    (bR, bT), blane = brng.choice(sorted(lanes.items(), key=lambda kv: kv[0]))
    bs = brng.randint(10, H - 20)
    out.append("%s WARN CREW_LOSS region=%s crew_type=%s from=%d to=%d count=2" % (ts_at(PUB_MINUTE), bR, bT, bs, bs + 9))
    pp = dict(zip(post_pos, post))
    for j, mnt in enumerate(post_minutes):
        if j in pp:
            out.append("%s %s" % (ts_at(mnt), pp[j]))
        else:
            seq += 1
            out.append("%s INFO HEARTBEAT seq=%d" % (ts_at(mnt), seq))
    files["control_room.log"] = "\n".join(out) + "\n"
    files["risk_policy.toml"] = (
        "[class_weight]\ncommercial = 1\npublic = %d\n\n"
        "[load_band]\n# daily peak load_mw at or above min_mw takes the band factor\n"
        "bands = [\n  { min_mw = 0, factor = 1 },\n  { min_mw = %d, factor = 2 },\n  { min_mw = %d, factor = 3 },\n]\n\n"
        "[deferral]\ndefer_factor = %d\n" % (lit["public"], lit["band2"], lit["band3"], lit["defer"]))
    return files


# ---- reference reading of the contract ----

DEF = H + 1


REASONS = ("unknown_asset", "out_of_season", "window_too_short", "duplicate_request")


class InputError(Exception):
    pass


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise InputError("%s: %s" % (os.path.basename(path), exc)) from exc


def load_lines(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().splitlines()
    except OSError as exc:
        raise InputError("%s: %s" % (os.path.basename(path), exc)) from exc


def read_inputs(data):
    p = lambda name: os.path.join(data, name)
    inp = {}
    assets = {}
    for n, line in enumerate(load_lines(p("assets.jsonl")), 1):
        if not line.strip():
            continue
        try:
            a = json.loads(line)
            assets[a["asset_id"]] = (a["region"], a["crew_type"])
        except (ValueError, KeyError) as exc:
            raise InputError("assets.jsonl line %d: %s" % (n, exc)) from exc
    inp["assets"] = assets
    inp["requests"] = load_json(p("requests.json"))["requests"]
    inp["plan"] = load_json(p("published_plan.json"))
    inp["network"] = load_json(p("network_constraints.json"))
    inp["calendar"] = load_json(p("region_calendar.json"))
    try:
        with open(p("risk_policy.toml"), "rb") as fh:
            inp["policy"] = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InputError("risk_policy.toml: %s" % exc) from exc
    try:
        with open(p("customers.csv"), encoding="utf-8", newline="") as fh:
            inp["customers"] = list(csv.DictReader(fh))
    except OSError as exc:
        raise InputError("customers.csv: %s" % exc) from exc
    peak = {}
    for n, line in enumerate(load_lines(p("load_forecast.tsv"))[1:], 2):
        parts = line.split("\t")
        if len(parts) != 4:
            raise InputError("load_forecast.tsv line %d: expected 4 fields" % n)
        key = (parts[0], int(parts[1]))
        peak[key] = max(peak.get(key, 0), int(parts[3]))
    inp["peak"] = peak
    duty = {}
    for n, line in enumerate(load_lines(p("crew_roster.jsonl")), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if r["status"] == "on_duty":
            k = (r["region"], r["crew_type"], r["day"])
            duty[k] = duty.get(k, 0) + 1
    inp["duty"] = duty
    inp["log"] = load_lines(p("control_room.log"))
    return inp


EVENT_KEYS = {
    "CREW_LOSS": ("region", "crew_type", "from", "to", "count"),
    "NEW_REQUEST": ("asset_id", "duration_days", "earliest_start", "latest_finish", "crews"),
    "WITHDRAW": ("asset_id",),
}


INT_KEYS = {"from", "to", "count", "duration_days", "earliest_start", "latest_finish", "crews"}


TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def parse_event(line):
    """Return (ts, event, fields) for a well-formed event line, ('HB',) for a heartbeat, None otherwise."""
    parts = line.split()
    if len(parts) < 3 or not TS_RE.match(parts[0]):
        return None
    if parts[2] == "HEARTBEAT":
        return ("HB",)
    keys = EVENT_KEYS.get(parts[2])
    if keys is None:
        return None
    fields = {}
    for tok in parts[3:]:
        k, sep, v = tok.partition("=")
        if not sep or k in fields:
            return None
        fields[k] = v
    if set(fields) != set(keys):
        return None
    for k in keys:
        if k in INT_KEYS:
            if not re.fullmatch(r"-?\d+", fields[k]):
                return None
            fields[k] = int(fields[k])
    if parts[2] == "CREW_LOSS":
        if fields["region"] not in REGIONS or fields["crew_type"] not in TYPES:
            return None
        if fields["from"] > fields["to"] or fields["count"] < 1:
            return None
    return (parts[0], parts[2], fields)


def check_record(rec, assets, accepted):
    if rec["asset_id"] not in assets:
        return "unknown_asset"
    if rec["earliest_start"] < 1 or rec["latest_finish"] > H:
        return "out_of_season"
    if rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]:
        return "window_too_short"
    if rec["asset_id"] in accepted:
        return "duplicate_request"
    return None


def build_season(inp):
    assets = inp["assets"]
    rejected = []
    accepted = {}  # asset_id -> record (origin kept)
    for pos, rec in enumerate(inp["requests"]):
        why = check_record(rec, assets, accepted)
        if why:
            rejected.append({"source": "requests.json", "position": pos, "asset_id": rec["asset_id"], "reason": why})
        else:
            accepted[rec["asset_id"]] = dict(rec, origin="published")
    pub_at = inp["plan"]["published_at"]
    loss = {}
    withdrawn = []
    active = set(accepted)
    ignored = 0
    for n, line in enumerate(inp["log"], 1):
        ev = parse_event(line)
        if ev is None:
            ignored += 1
            continue
        if ev[0] == "HB" or ev[0] <= pub_at:
            continue
        _, kind, f = ev
        if kind == "CREW_LOSS":
            for d in range(max(1, f["from"]), min(H, f["to"]) + 1):
                k = (f["region"], f["crew_type"], d)
                loss[k] = loss.get(k, 0) + f["count"]
        elif kind == "NEW_REQUEST":
            why = check_record(f, assets, accepted)
            if why:
                rejected.append({"source": "control_room.log", "position": n, "asset_id": f["asset_id"], "reason": why})
            else:
                accepted[f["asset_id"]] = dict(f, origin="control_room")
                active.add(f["asset_id"])
        else:
            if f["asset_id"] in active:
                active.discard(f["asset_id"])
                withdrawn.append(f["asset_id"])
            else:
                ignored += 1
    pol = inp["policy"]
    cw = pol["class_weight"]
    bands = sorted(pol["load_band"]["bands"], key=lambda b: b["min_mw"])
    defer_factor = pol["deferral"]["defer_factor"]
    counts = {}
    for row in inp["customers"]:
        k = (row["asset_id"], row["class"])
        counts[k] = counts.get(k, 0) + 1
    factor = {}
    for (R, d), pk in inp["peak"].items():
        fv = None
        for b in bands:
            if pk >= b["min_mw"]:
                fv = b["factor"]
        factor[(R, d)] = fv
    plan = {}
    for x in inp["plan"]["plan"]:
        plan[x["asset_id"]] = x["start"] if x["status"] == "scheduled" else DEF
    reqs = []
    for aid in sorted(active):
        rec = accepted[aid]
        R, T = assets[aid]
        wc = counts.get((aid, "commercial"), 0) * cw["commercial"]
        wp = counts.get((aid, "public"), 0) * cw["public"]
        pub = plan.get(aid) if rec["origin"] == "published" else None
        reqs.append(dict(id=aid, region=R, type=T, origin=rec["origin"], crews=rec["crews"], dur=rec["duration_days"],
                         e=rec["earliest_start"], l=rec["latest_finish"], wc=wc, wp=wp, w=wc + wp, pub=pub))
    ids = {r["id"] for r in reqs}
    inc = [(a, b) for a, b in inp["network"]["incompatible"] if a in ids and b in ids]
    prec = [(x["before"], x["after"]) for x in inp["network"]["precedence"] if x["before"] in ids and x["after"] in ids]
    cap = {}
    for R in REGIONS:
        for T in TYPES:
            cap[(R, T)] = [0] + [max(0, inp["duty"].get((R, T, d), 0) - loss.get((R, T, d), 0)) for d in range(1, H + 1)] + [0]
    fac = {R: [0] + [factor[(R, d)] for d in range(1, H + 1)] + [0] for R in REGIONS}
    black = {R: set(inp["calendar"][R]["blackout_days"]) for R in REGIONS}
    return dict(reqs=reqs, inc=inc, prec=prec, cap=cap, fac=fac, black=black, defer=defer_factor,
                rejected=rejected, withdrawn=sorted(withdrawn), ignored=ignored)


def derive(inp):
    S = build_season(inp)
    reqs = S["reqs"]
    lanes = {}
    for r in reqs:
        lanes.setdefault((r["region"], r["type"]), []).append(r)
    start = {}
    for (R, T), rs in lanes.items():
        ids = {r["id"] for r in rs}
        inc = [x for x in S["inc"] if x[0] in ids and x[1] in ids]
        prec = [x for x in S["prec"] if x[0] in ids and x[1] in ids]
        vec = solve_lane(rs, inc, prec, S["cap"][(R, T)], S["fac"][R], S["black"][R], S["defer"])
        for r, s in zip(rs, vec):
            start[r["id"]] = s
    preds = {}
    for a, b in S["prec"]:
        preds.setdefault(b, []).append(a)
    audit = []
    for r in reqs:
        s = start[r["id"]]
        fs = S["fac"][r["region"]]
        capl = S["cap"][(r["region"], r["type"])]
        blk = S["black"][r["region"]]
        has_start = any(x not in blk and all(capl[y] >= r["crews"] for y in range(x, x + r["dur"]))
                        for x in range(r["e"], r["l"] - r["dur"] + 2))
        if s == DEF:
            days = r["dur"] * S["defer"]
            if not has_start:
                why = "no_feasible_start"
            elif any(start.get(p) == DEF for p in preds.get(r["id"], [])):
                why = "predecessor_deferred"
            else:
                why = "displaced"
        else:
            days = sum(fs[s:s + r["dur"]])
            why = None
        pub = r["pub"]
        audit.append(dict(
            asset_id=r["id"], region=r["region"], crew_type=r["type"], origin=r["origin"],
            status="deferred" if s == DEF else "scheduled",
            start=None if s == DEF else s, end=None if s == DEF else s + r["dur"] - 1,
            published_start=pub if pub is not None and pub != DEF else None,
            moved=pub is not None and pub != s, risk_days=r["w"] * days, reason=why,
            _wc=r["wc"] * days, _wp=r["wp"] * days, _crew_days=0 if s == DEF else r["crews"] * r["dur"]))
    return S, audit


def write_outputs(S, audit, out):
    os.makedirs(out, exist_ok=True)

    def dump(name, obj):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.write("\n")

    dump("policy_audit.json", {"requests": [{k: v for k, v in a.items() if not k.startswith("_")} for a in audit]})
    for R in REGIONS:
        rows = [a for a in audit if a["region"] == R]
        dump("region_%s.json" % R, {
            "region": R,
            "schedule": [{"asset_id": a["asset_id"], "crew_type": a["crew_type"], "start": a["start"], "end": a["end"]}
                         for a in sorted(rows, key=lambda a: (a["start"] or 0, a["asset_id"])) if a["status"] == "scheduled"],
            "crew_days": {T: sum(a["_crew_days"] for a in rows if a["crew_type"] == T) for T in TYPES},
            "risk_days": sum(a["risk_days"] for a in rows),
            "deferred": [a["asset_id"] for a in rows if a["status"] == "deferred"],
            "moved": sum(1 for a in rows if a["moved"]),
        })
    for seg, key in (("commercial", "_wc"), ("public", "_wp")):
        dump("segment_%s.json" % seg, {
            "segment": seg,
            "risk_days": sum(a[key] for a in audit),
            "by_region": {R: sum(a[key] for a in audit if a["region"] == R) for R in REGIONS},
            "deferred_risk_days": sum(a[key] for a in audit if a["status"] == "deferred"),
        })
    risk = sum(a["risk_days"] for a in audit)
    moved = sum(1 for a in audit if a["moved"])
    dump("summary.json", {
        "requests": len(audit),
        "scheduled": sum(1 for a in audit if a["status"] == "scheduled"),
        "deferred": sum(1 for a in audit if a["status"] == "deferred"),
        "moved": moved, "risk_days": risk,
        "crew_days": sum(a["_crew_days"] for a in audit),
        "objective": [risk, moved],
    })
    rej = sorted(S["rejected"], key=lambda x: (x["source"], x["position"]))
    dump("data_quality.json", {
        "rejected": rej,
        "counts": {k: sum(1 for x in rej if x["reason"] == k) for k in REASONS},
        "withdrawn": S["withdrawn"],
        "ignored_lines": S["ignored"],
    })


# ---- exact lane optimiser (forward and backward day sweep, then a fixing pass) ----

SCALE = 100000  # value = cost * SCALE + moved


class Lane:
    def __init__(self, d):
        self.H = d["H"]
        self.DEF = self.H + 1
        self.cap = d["cap"]
        self.factor = d["factor"]
        self.blackout = set(d["blackout"])
        self.reqs = d["reqs"]
        self.defer = d["defer"]
        self.n = len(self.reqs)
        self.incompat = [tuple(x) for x in d["incompat"]]
        self.prec = [tuple(x) for x in d["prec"]]
        n = self.n
        self.inc_of = [set() for _ in range(n)]
        for i, j in self.incompat:
            self.inc_of[i].add(j)
            self.inc_of[j].add(i)
        self.pred_of = [[] for _ in range(n)]
        self.succ_of = [[] for _ in range(n)]
        for i, j in self.prec:
            self.pred_of[j].append(i)
            self.succ_of[i].append(j)
        self.is_pred = frozenset(i for i, _ in self.prec)
        self.ls = [r["l"] - r["dur"] + 1 for r in self.reqs]
        self.opts = []
        self.cost = []
        for k, r in enumerate(self.reqs):
            o = []
            c = {}
            for s in range(r["e"], self.ls[k] + 1):
                if s in self.blackout:
                    continue
                if all(self.cap[x] >= r["crews"] for x in range(s, s + r["dur"])):
                    o.append(s)
                    c[s] = r["w"] * sum(self.factor[x] for x in range(s, s + r["dur"]))
            o.append(self.DEF)
            c[self.DEF] = r["w"] * r["dur"] * self.defer
            self.opts.append(o)
            self.cost.append(c)

    def moved(self, i, s):
        p = self.reqs[i]["pub"]
        return 0 if p is None or p == s else 1

    def val(self, i, s):
        return self.cost[i][s] * SCALE + self.moved(i, s)

    def objective(self, plan):
        v = sum(self.val(i, plan[i]) for i in range(self.n))
        return (v // SCALE, v % SCALE, tuple(plan))

    def feasible(self, plan):
        use = [0] * (self.H + 2)
        for i, s in enumerate(plan):
            if s == self.DEF:
                continue
            if s not in self.cost[i]:
                return False
            r = self.reqs[i]
            for x in range(s, s + r["dur"]):
                use[x] += r["crews"]
                if use[x] > self.cap[x]:
                    return False
        for i, j in self.incompat:
            a, b = plan[i], plan[j]
            if a != self.DEF and b != self.DEF and a < b + self.reqs[j]["dur"] and b < a + self.reqs[i]["dur"]:
                return False
        for i, j in self.prec:
            a, b = plan[i], plan[j]
            if a == self.DEF and b != self.DEF:
                return False
            if a != self.DEF and b != self.DEF and b < a + self.reqs[i]["dur"]:
                return False
        return True


def sweep(L, fixed, store_edges=True, deadline=None, order_big_first=False):
    """Forward day sweep. fixed: dict i -> start or DEF. Returns (opt value, edges per day, fwd per day)."""
    H = L.H
    reqs = L.reqs
    arrive = [[] for _ in range(H + 2)]
    for i, r in enumerate(reqs):
        arrive[r["e"]].append(i)
    expire = [[] for _ in range(H + 2)]
    for i in range(L.n):
        ls = min(L.ls[i], H)
        if ls < reqs[i]["e"]:
            ls = reqs[i]["e"]
        expire[ls].append(i)
    start_state = (frozenset(), (), frozenset())
    fwd = {start_state: 0}
    days = []
    for d in range(1, H + 1):
        if deadline is not None and time.time() > deadline:
            raise TimeoutError()
        nxt = {}
        edges = [] if store_edges else None
        for st, fv in fwd.items():
            pend, run, dset = st
            if arrive[d]:
                pend = pend | frozenset(arrive[d])
            run_now = [(e, i) for (e, i) in run if e >= d]
            # eligible to start today
            elig = []
            if d not in L.blackout:
                for i in sorted(pend):
                    f = fixed.get(i)
                    if f is not None and f != d:
                        continue
                    if d not in L.cost[i]:
                        continue
                    okp = True
                    for p in L.pred_of[i]:
                        if p in pend or p in dset or reqs[p]["e"] >= d or any(q == p for _, q in run_now):
                            okp = False
                            break
                    if not okp:
                        continue
                    if any(q in L.inc_of[i] for _, q in run_now):
                        continue
                    elig.append(i)
            occ = {}
            for e, i in run_now:
                c = reqs[i]["crews"]
                for x in range(d, e + 1):
                    occ[x] = occ.get(x, 0) + c
            subsets = []

            def rec(k, chosen, occ_local):
                if k == len(elig):
                    subsets.append(tuple(chosen))
                    return
                rec(k + 1, chosen, occ_local)
                i = elig[k]
                r = reqs[i]
                if any(q in L.inc_of[i] for q in chosen):
                    return
                for x in range(d, d + r["dur"]):
                    if occ_local.get(x, 0) + r["crews"] > L.cap[x]:
                        return
                o2 = dict(occ_local)
                for x in range(d, d + r["dur"]):
                    o2[x] = o2.get(x, 0) + r["crews"]
                chosen.append(i)
                rec(k + 1, chosen, o2)
                chosen.pop()

            rec(0, [], occ)
            if order_big_first:
                subsets.sort(key=lambda s: -len(s))
            for S in subsets:
                add = 0
                for i in S:
                    add += L.val(i, d)
                p2 = pend.difference(S)
                dfr = []
                for i in expire[d]:
                    if i in p2:
                        f = fixed.get(i)
                        dfr.append(i)
                bad = False
                for i in dfr:
                    f = fixed.get(i)
                    if f is not None and f != L.DEF:
                        bad = True
                        break
                    add += L.val(i, L.DEF)
                if bad:
                    continue
                if dfr:
                    p2 = p2.difference(dfr)
                d2 = dset
                for i in dfr:
                    if i in L.is_pred:
                        d2 = d2 | {i}
                r2 = [(e, i) for (e, i) in run_now if e >= d + 1]
                for i in S:
                    e = d + reqs[i]["dur"] - 1
                    if e >= d + 1:
                        r2.append((e, i))
                k2 = (p2, tuple(sorted(r2)), d2)
                v2 = fv + add
                if store_edges:
                    edges.append((st, k2, add, S, tuple(dfr)))
                if k2 not in nxt or v2 < nxt[k2]:
                    nxt[k2] = v2
        days.append((fwd, edges))
        fwd = nxt
    # all requests must be resolved at end (pending empty, nothing running beyond H handled by cap index)
    final = {k: v for k, v in fwd.items() if not k[0]}
    if not final:
        return None, days, final
    return min(final.values()), days, final


def optimal_options(L, fixed):
    opt, days, final = sweep(L, fixed)
    if opt is None:
        return None, None
    # backward values
    bwd = {k: 0 for k, v in final.items()}
    sets = [set() for _ in range(L.n)]
    per_day_bwd = [None] * len(days)
    for idx in range(len(days) - 1, -1, -1):
        fwd, edges = days[idx]
        b = {}
        for st, k2, add, S, dfr in edges:
            if k2 in bwd:
                v = add + bwd[k2]
                if st not in b or v < b[st]:
                    b[st] = v
        per_day_bwd[idx] = (bwd, b)
        bwd = b
    for idx, (fwd, edges) in enumerate(days):
        bnext, _ = per_day_bwd[idx]
        d = idx + 1
        for st, k2, add, S, dfr in edges:
            if k2 in bnext and fwd[st] + add + bnext[k2] == opt:
                for i in S:
                    sets[i].add(d)
                for i in dfr:
                    sets[i].add(L.DEF)
    return opt, sets


def reference(L, counter=None):
    fixed = {}
    opt0 = None
    i = 0
    opt, sets = optimal_options(L, fixed)
    opt0 = opt
    runs = 1
    while i < L.n:
        s = sets[i]
        if len(s) == 1:
            fixed[i] = next(iter(s))
            i += 1
            continue
        fixed[i] = min(s)
        i += 1
        opt, sets = optimal_options(L, fixed)
        runs += 1
        assert opt == opt0
    if counter is not None:
        counter[0] += runs
    return [fixed[i] for i in range(L.n)]


_SHIPPED_DATA: dict[str, str] = {
    "assets.jsonl": "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",
    "requests.json": "eNq9Wk2LI0cMvftXGJ/3UFLpo5RbfkdYBpPxEsMwS9xeQlj2v295hwmEzBv64d5cZbefVZKenlT9dbc/LKfj8vn58Mv+626/P3w6X5brw+Px72mQDzfL0/EfQ8lu/20aD5fTn19Oy3WZtt/md25P7g/HZTldH86P03j4VX1UO3z48cHjl8vxev78fPuV2yP6Yj4dL0/n+SsPy/V4uU6728sHT8frzfzp/Hxe/rjZ48X+++X01+35+S9+/I23cD27B8A1gJsAd+i/cfUdXJMKBbgd4La3YUXXu2sRgmAFHTPADVnvroikkOEV4G4notubKQmrwN3e1uPOU5YkcSPfxn3NtjW4OsyKDK8NUEW1PryVo7H+CsBVX4/rUiZkFWmA+MZ63BEykmQNeM5EPmdpDvKcE+RVEfks1bqTeaUAtxPxzS7B+tv727hG1NFoWixduYL4DoKepSlLz93u9ze1FXvOWiC+RfCVN3OyjiBPEnXUJRvrb4D6TSH60RDpLD+DNsh035FG0xVog06kVaTD8kW4DsIbvh53smQrlibvF1eTJCPJ6CZgjSSqaGQT1l1DrEFo55oiZ2ylctr6dO69dWPDC7rCIKo3vYw9Z+8bdIWuGqy6AuyshL99RPb/f0YZzQbbFF5F43+akWzDVvIT2cpSqlgRC4ajV9G1SrSL0WUExRXhbza++SqgSSW6UZ8syY76AvJZCbEhUvCcUV4FGFJSmfK1Rg9HQOT0vj6vIro11l+Qz5GEmGwJ6crYYZ/ZqbhZZ9sRavvM6ipisENKv5+eNTTptLJ1O5V3Z/3ywZavgWO2QWzqCovnn7lDurVBNp0N0IYz4rnN6XerWdAY0V7F0obL/TsV7Q7jy7ZfZrchIi7s5hmpWGa3MccUdigTtIsl6ErVneWNLVS7S7pvNIRys74pnc/oRiOZG41Utn4NyGdLZhrUzspnNHQTNFnmtIqF0wKj2qNaY9WG3k+TkzaUvSiDK2/mnFUHW74CzlkZ2igZbSsVO5h0zmLzyoG/QbSj6C1YfyXvn1LKWjiJG4Cugrg6ysLLnE6qWKJ8NTVjm03sYFYMSi9i0WjE7LtdW2dXDJbretG792Rz5M6tkpkaBflkdkCSYcwoiN8mgFmFNoTMTFZYa0B/a53GeVfDRhi78RZQRsr427xojaP3b7ytJ1ypwHvQ+zWOjqA3kx1pHKKMpJmxGkdAOmtjFu0CX9tw8r7KmB4YOgbbi4pIq93+4+7b7js93ByW",
    "published_plan.json": "eNqtmE2KG0EMhfc+ReP1DKhU+inNLnfIKiEMTmzIwBBC2l4Nc/eUs8kqLxIU2Au7y59bKunpVb8dtuPP29fXl/375fx8uh6ftiMT2yP1R2ofyZ6I5uvT8eG+8PX0Yy74fNi2t/nejqd9v1yfX873X31oJEL3dfPCfj1db/v96/3bBN9eL+e/V37d/6X5/Pj+8A9Ua5xHcWCUtjTKFaM8j2qQFF3SJDOEMhPP35Qg1PACSmCAQV3zG4hqgYksj1KDKA3OB8gQ5d7zARJCsVYqFO0gdy3sYId3pST5tBvcQR2R72aFARoXWpAHQjm75YsBkYZI5EnwpobZyG8gUiuONmhRqkIKcqxIjju1yGe9oQrtzSmfK0MB9k4FPYZDog+hfIV2JKLSiPNy1VHapTMX0o5RXggQaaho10IHdogS6Ws0VMxaPutKEBVEi2rBW+Q1hhFKm2tB2QWiQtoan6ZMvSCiaN7o1NBCCyKSVyoUlpW6F5pZkMToaK0vmVw6SsIOUaHD1ngr62SLDhKzl5uvcTFmvXC8gW1jzgWbZgFRWjAMhtLuVJmnDFFMUbAxaDR7bxVHhNLuGgWfpkgYPCqGAZPY8/ENpAtjeitfM+QHTfuYTxVDlIyCWtl/ULrG0g6bp901nn1MPxRrlH2ek3q+GBqa8pNkvsbSBs1yWGNjYsrxWKPH0biQK0ySQjOLQJRHHqUw68wFFwO7eUoM5St0QFJUjvKwFKTyXAfO05gnCVlUoMZjrHkGFj6oIMd/0n7YvhzeD78BLliFgg==",
    "customers.csv": "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",
    "load_forecast.tsv": "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",
    "crew_roster.jsonl": "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",
    "network_constraints.json": "eNqVVDFuwzAM3P0Kw3MGUiJFslvfUXRIUgcI0CZFkC3I36vYtWyEtYAOBmzhjjzxjr41bXc87c9f39vrcffZdy/tW9MOT9u9ckqK3Wb8oCiAXX5/38wIYSObEGJB1CEkQkEYitEzQiFY6SIRk6vBEjlNCEYjp8OII81d0OtgYy01LAR1NTShyoQIkIU/I4iixVIjBXVdKESYESpqVR0IRFC9rREkruuAmMQhEEIodzFUqPqCuYjrwijM88TMwDtHWnREQEtVRIoJxok1A6j7vvT7/qM/7afc3Qbgrj+cL4+jKTAjf3u49pfhNKXs8KPQffMXSXNQzZFGe1dJ45CeSawUoELSvCGORBCU10kkaF5eVBrXa4U0bJ+7EzBVSAIC+l/SMqAzKcBvDlc65QB5nyTouEQr02M1P/KyNSvmLhK1kBeYa4NALau9MHf6k9xzHpt78wMgXvxd",
    "region_calendar.json": "eNqr5lJQ8ssvKslQslKo5lJQUErKSUzOzi8tiU9JrCwGCkYDBRUsdUCkoRmYMoFQpsZgyhwiZ2EAJGO5FGqBPKVgoH78BhoaQYyCUqbIBpuZQw1GMjE8tbgEr4FGBmBNxlAK4jYLEwgFMdfCHMlA10QCBppD3GQO0WsOdZMFip+NoAZy1XIBABrVROo=",
    "control_room.log": "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",
    "risk_policy.toml": "eNpljssOgjAQRffzFTdxywKRxBVfQhoytEUaWkpKlRjjv0uJGom7k3vuPGppeZ6bRZtLHwVJ75wO0rBFhSNN19YauWJBVFvPqml5VIIOUGzsHZPmAVvuFnCED+DW3zScGVMUedAzYq+R5tCxjD5Q4nldWhPw+FQr5Nm7kE7jme1tmf/64s+fd/6UvFifVrrTIbAVtFHzbZT0Am1gTuc=",
}


_SHIPPED_DOCS: dict[str, str] = {
    "docs/RULES.md": "eNqNlNuO0zAQhu/7FCPtDUhteAZYwQoJBFqQuEwn9jTxxvEE22kVqQ/P2E72wKH0Ik1qz3z/eA6+gfvJEnhqTYjk4cAeYkfAU8SWIBAGdrI9WnSbzXtUHUQejYKGLJ/ABGj5SN6RhmYGdgSa1TSQixX86MgTxBM/rgXQJmDrSQQcYEFts+BqIn8E+hiPw4HCEhXGRbtIhmqzOcP3vHKGu7xmXPtEOm/Ou90uP2L4NgSKIYsZnwVSCE6D8nSCOI8klL04hzfGReypGvQeXmmMCMbBHrN/9SD5sPvXCQ7fSnYanpwOmeXp50Qhyluxl7WLxMW4MBfkfXYE1ZHqV+QDqWhyFZLcX6HJ9evUWBM6qUQq1mXpcbWtk+3zAG7ZRc9255kHoGMuWgrDtI69sK1x9J9zqYKoE6Ky3K7kKUQepKYnMm0XnyClu+rshir+TlvcQqXCcb+VtJnQ1yNbo+ZKdtZifGLUcBB/9teirbjU0lukMMQqXsTfpi5ROKIycb42dPGRLKRGftE37yyqXiYMNM7XxloatlZoyWn0z0v20SkeRoymkUke0fhSsVHORZqcoislHMms+j5tB9mX2r5ozQ/SflmiXApbSJna5SMkuXxrNLlXj/LltVT6km5Cfpah1ctdUyiaDuQ92j+a/V+IL1McUybXG2YLPc3ye0Q7UR7rAs4BpethBXJ2rIOM2oAL7hfO99Ww",
    "docs/intake.md": "eNqNV0tv4zYQvvtXENhLgjoC0vbkRQ/pxkC2aLJt7CJoLxYt0RZjmVRJKq7/fb8ZUtZjH20OgS3Ne775ZvxOfDRBHpSwOyG9V8HPhVN/t8oHL6QpRWFNcLa+cdYehXpTJvjZ7N07ccfCs1ketbJXb02di8rWpRfWKPHL6tOTsNtXVQTRKCdqjYcnHSoRVTa6zOcid2qvraFPB23KnH3mhVOnTTg3Ks/EXRePoDi9CJUSUSnGB1FBopSBpqDJuNg5hBsq7cVO1yoTz6yBt06J/Mm6UJHLlW3jhxfYT76XEh/f93aTDoVPkr7d+iADxRzlG2cDcqQHGVdmpaRPwXWRO1VYV1K1utpyvbpy5Z5VcnGV77TzYVPKc7Jey/T1vcD/GMsJWkqY9rhVzqNBrQmqjBnfXrMa1ajWcHzxh0IuZVGlSEQhndNIbdSKsnWcGPnz9EBJV0MqbJCxC/SkloG+77TRvho0y1Pu66qLDa2YZopOOCXLudAmhoYwlJuLrdpZ5EQRj6BW2/04ZBgoKlUckKrcS20IEJXyUGWswiy3O5ntqsD1ZBGAQ+ykrj1ZIqA49Rr7RoEhxsVsdpuJvDUHY09mw5XJFyzal4mUjQ3kboz8bPY9lIGnjd1tUj+T8qSMZCJlPWy3dVF6UmIIy13A/PRQyGY/wNUJ42IxJdZufAVAw9tYV9yIsWfxnbhlg7XyNEfSTHuezX7M6FlT6wKmNqmHMA3ZaMwJWRSqIcSlxhh5TGPp8WlQK5o6xn2vwiCdQoN6leb1cxCIrQVlMMhjV2Xn1wdd1/FNV6PY1jhzyJPYpnTyZADOu04NeXdAMDYho48w8g0Bo08w8g6Edy14A24aKiYDjqioqaWJk/9buwW0K2jSM0x70z3YsNBo5vt3Epi4kiJo1DHIY3OdiAUqmDniUrCuOzOLppC+WdCFUJrjzImpWp/jA0anbGsFADMFM9ISHNH5OaGvly7VTjkH4ZjWh0lLZjOeSyZ0mvTUsg29z/A+grbPh4R4Fq1DrH/i7+bx8eb+fv3wsHh8XKxWfyFNCVS+qVqckN6c4Ua7hsE1J21g9aDOP73JulW5CPagDFaVBAK8Qj8kFWN7Bv9otLSRhULsN2hmXDuVJaK4BFRJn3BAIVG1o0Tvk1LIH5Z3z+ufl3frnDWAALXb0T4jjUQEiX4zctYFzT4JfwrhkQtFDpAClf0rUcz55SSAD8/Ll82vn1Yr4t4nfH5e/v7HcrVmtshfPq4f7p/vXvKoG2vC1H4W6h9ZhPrMdUfdPHMu4QWK7DN62qranuYYbfTTmkLFEcM7mICaOErHhEu3ABAf1B6wigCWoz0kTk6HQCkaUapCH2UtSr2nuBhwULcNEQ2e19gD2uzFUZvWC6/3hqZukOwXCwiSPfdV7O6G6b3ACzIyUsq4NVgI6VxBFWlgLiyemDXYfJ4MUTcjfgPFCXK4zWYCVDoIbzG8WnrXF+NXqVDXczY9+p4cXB4l48PeLr61lUfGpotl+G6yRkYx8ML+LIYLnIYBEK6XDAfuCUOHipcYRo6GhEWMpcfUuZvUucFQJLYmqPEKRe+xB8sNvaST4wT7hL7xpPBwfc3kdLZj7xBEt2PHRPt/BnnNvH7EkUEw7X15XgWdLh8yRIF0cSymICED9o1OrNRyrnrkyx6tVIMOydakwUOjE69HPAWbIMqrUJuibkvaVPd0EOLi8LqMB5RPlyeybo3kKEluRWYxd8hSF4iIOIC2CvmRJSak+QIKI4ePD9iuXN0dtj0nXm9dusLkFjm/5+411mu+rtK5FcERySLtTuyK+eR+zYhFpxcG7w+YoV8IMa7RldAFSdF17eWFmdw0o7U8RfulUSRKzNGf7cw2DPn4o6KKPDgIL/0w6aYCMDpD7nJ39HdoNPBqcbfy94sI01QmPtE4nbRX6Xb/z1lJ9zZYXr+pwU+2dEtPSpgWDZOjHQSYdcMtiQgdLgThGyUPDNSpbWLgbPYvyskLKQ==",
    "docs/output_schema.md": "eNqVVk2PGzcMvftXENhDdoFZN71uTwWSS1skQHPooQhm5BnaVlYjTfSxW//7kJRGnrGdID3trEQ9PpKPpO/gY4pTijC4Po1oY9hs3r+gP4Fbn4MO4CzCH58+fgC3+4J93MKfSHZ+QA/KDvB61BHDpHoE5RH2HnELf+kQ6eUeVAhIKEOQS23poEc7aHuATu5aPXQFLVmDgQxh0Ps9enafL4jEQb+g3cI7dQKbxh360EDvEjEXEl6H58dBnWY3EQ9ksoW/8aCdzaeGOOFAXhjyd/YdmFBHsYZf6Il6xu04dNvN5u4OJmd0f2pVGnTcfgnObjadx68JKa7uSXKS0wET56GPxA+KQfPjOBt41fH4tNk8Lq4aIHjmyl+9x9c2nibsfmMj5/VBW/LaTWlHURyRoPaO3M4eiUCPE0e3926EylSYC6Kz0TvTeufG/JYjWL+KR8qRO4jLEFVMHGgXenKXDAp7ShZSZTz9N5v5yPgUKhlryuhee+ZDNTGKPqgmrKkGdi4eobPJmI4kgxZmJAGqgbUZMmPJNyeTqVUTmIyyzQpLRziqAFbK4m+YZ29U7yjuRveCTLiLPmEObK9MoE9CIVNt6V3VhkeGaCWHVGkWiaCw6FoWXaFbRZhvUXHy81UOVhnIp2v2NcVZelkH7Qfn41EK2MxHnyiTF0f/UJnXJ+9VmBX7WEX1JDnJ/4BVI+byFcfXgq6UqsKolxcQrOC1es+abS500WTZE9buNF+JQCIHz2cVR1gJUkkrVa6wEo/PSB3eGSqPeEk71inHJ3jd5F0k29xFqPqjUA5pZPaCGzqIekQCGZKXp9kTkCCybq4iDzl0FYEBgEOcJZmTcaUFuaoDiYegMRcjIqzz2dRu4ELwWOpNGkpv1JbLyOeJuoJ4E84Ys5OV1tk0j05+KKffYZNlGPDAG4BkP47oe61M0dl8IR3Wn6VWzrmtzm9yc2XT7mamyrM3YZkzrsaNrAnA7tRWVV/og1VMGhEJF6UenZEp/D1XUkoq7qKWcx7bn6Z6lXliYk4lj2kclT8tW7KskWY5XZtFoZtz1cqOYxHdSMWKoIs8X1YzaNlK/68VOPnXrZDXkSScuBRQ3qvQ/Vu5NFlcn8smHVRU7dekjI6rJDCIhHgxeuYb+uhpcJRRE1zyPc3n+4vdJvJabrctrbDugTI4uaDzbLhnlprW/n9z455rkNlLluc9+LaZdwhBAQ+buW9WZr+yk/NqlwFUZv7FxCvUVz8KQvT8J/++uQ/uRhDkjsuzQ1rXeLnTH9YTtAabyy6iuW4PjmlPbEqOuT0y48B7j4frYmyeZ8VFRcIMJl3Dz+H+bR1ZD8KALQavXu2toVUv17rSB+u46zjj4WpgzbUItQpEuTy5/TPuGw6s6Sg=",
    "docs/replan_contract.md": "eNqlV0uP2zYQvutXEMihLeJ1u+lt99RuU6BAgABJgRxNSqJtZinSJakV/O/7zZCU5UeSPm42OZzHN9889Ep80AernOi8S0F1qWnevuhwFIextSbudS+2ZjcGLUyEzHAYEx0FP4i018I7LQIrcDiOWkXvcKFSvm0/6y6ZF/wKvQ64t/gf103z6pX4pM1un2LT/AINf406pu/YwqBDZ5QVE9+TWVLlxqGFBr8Vshtj8pCK6y6+SBH8FOm8sypG3M4apNj6IEyKAhcaHplBZ2ULK/lVteWEDCY+bw7emu64hhkrH1kFw9FdOBXVoNlIsZ2F5Fr8keKl6DiQk/QzTT4j8M4rQAnMfQAM0uLvBtp0p2JaJ4ptr2KOj4xozkvQOwOMlevLQQG9V8e1+BPqe2Us0qfVMxlU9QG9IaHqkFVhB8xFNjtMUqjBux3f3XJldoOzu/BiNmxP4eRQr+SqbZmlZEWkpfub4IvJpP25v4Nx7C7rh0Lnk1CtB8nSWfQZ46egJ9Gpg+pMOjYN+Vn/ncFDHnQkm44HfQXWkn0Q2gQfkw7rzwDe3oZmtdBWo5/2PiL4mFQaoyTd0rtNP6ajXAmrYyEn3iHrekBIvajlRO/bo5BPH95+2rx7//GjpPS7FEu1qWct9HaL8hLfy9538Ufj6HA99PKHFbvgiC+i1dZP4qeMzu/gjmmtLiSiWix02qFqY2GYyjVcqlRopITAQOkjlJB94+j5ALGJXm91CLpfi7m4RezQTEaLmJIvDzNtgQiD4cd6EvkIYjKK16Ifg0qGkKKbO3EvSW3xE++2NYhpr10titlYNT9oTZ3A2kK6qB+a5g61nX0hHgmtgjWa8+i46mU+iWnDQpJxpAvUe4l7LCTEUTp7Sv/xcGsc2qh8ZFtxgVilrmit6p5JD+vbslhhJdcE/9x0ymrXq0w6NKWLd6Bfa3oEOENrjznt8AdCaqczU6ilKBu06o9ZlPp2ImRJVdoHP+728IEchgdadfvqVF+kVrmImahcw4TqFeLxIpbzCmNfFMZKtloYrvpejAfKPAAd0H8ynvWeBkQp3owng8i0LuRR3NsLr7h3qJkBrEU6jf4bnjeYdxEDD1USM6QC447aNj2C5tHRxJLG0dAD/0AwTiJ3YgJFHtAeda9dp1GLGJ7HbMEpGjPQAKCl2oIUMgNW/SCBnm9bTT2WyX+Cj3C6LZ6VVb7yv9IaF2QsLfWLxlD4v3rChWYi5yhXzFeAycFR46D54MvQn5NKf+fEojRdeUDd8stKF1ghw3lCM/bI/EXDIcpSdXJ7y43rAwbFHfGRW9ZVsfMyY1rsKpEpWGbxaQNYjOPF2LqkrCdmLZlPjaf2tn9mjFvBWQeT5Uayok0dhbxSXQ/AtXg6LSuEdllEQgWAi2hezOatZKr8v9h3KrvO9pmM6fvzba1p7hEu7wRU33OXvVz3YmZ33u10pgNljA8HPOXa8wnGZ6dX1Kvht1rkrjSpf5u6O14eLvJX85Ub4H9IWc3Ywi4rKYbWzZuKTQFBQDMixAuLerLi/gYqNNGzrq2eyI0ccnxc9Gi0gjz4eZhRFzlgmSHfjTsljvdyXtvrQFpkJU8Yg2oBIEyreYHldyyA2bA4Wg6IVoMu+jTDZ5dWl710UkupL7tH1TstMv1/FeZxtfSPBmlVyRmvajFQINEeSxkg697eBQ9MrN+dpge/XTc/fz2pUdyz+jffZHzIIBPXeaysBA1cCknFDmPcwIbknrcxvcz1BtfzV9PWBPI8d0QuE/TQ2aWc2MfbrB4df+0sd5GrjwSu9d/4LZVkVktt9FqfCsFUxrJTdXWqz8oYPxxoSXrgjiGd39ReUbamB+revKRUMl7tVZgq10sTdr3z3e81dj9KmlqsUWefAec7EeXKanVaZOuM5MY4fwbgPaQQHXuQt5pVBtPwB5GJJz5hBmqufhr/PRaAGH3YVOgQqvranOdPTHVrdTCLpZl4KHsTQfiOdXpauCcTYflv9FijuQ==",
}


# ---- harness ----

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
DOC_NAMES = ["policy_audit.json", "summary.json", "data_quality.json", "segment_commercial.json",
             "segment_public.json", "region_North.json", "region_South.json", "region_West.json",
             "region_East.json"]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUN_SECONDS = 60
_FRESH_SEEDS = {"h2": 70413, "h3": 88261}
_LOCK = threading.Lock()
_MEMO: dict[str, dict] = {}


def _root_only_tests_present() -> bool:
    try:
        st = Path("/tests").stat()
    except OSError:
        return False
    return st.st_uid == 0 and (st.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it, so a
    program the agent wrote can land at mode 0600 (owner-only). The checks run that
    program as an unprivileged user, which then cannot open it, and a correct submission
    would score zero for a reason that has nothing to do with the task. The verifier runs
    as root, so widening the mode is always allowed here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    try:
        if path.exists():
            path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            if parent == Path("/"):
                break
            parent.chmod(parent.stat().st_mode | 0o555)
            if parent == Path("/app"):
                break
    except OSError as exc:
        print("could not widen the mode of %s: %s" % (argument, exc), file=sys.stderr)


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" or not hasattr(os, "geteuid"):
        if _root_only_tests_present():
            raise RuntimeError("cannot drop privileges on this platform")
        return command
    if os.geteuid() != 0:
        if _root_only_tests_present():
            raise RuntimeError("checks must run as root to drop privileges")
        return command
    for argument in command:
        _grant_read(argument)
    return [*_SETPRIV, *command]


def _seal(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        path.chmod(0o755 if path.is_dir() else 0o644)
    root.chmod(0o755)


def _write_tree(files: dict[str, bytes], root: Path | None = None) -> Path:
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="inputs-"))
    root.mkdir(parents=True, exist_ok=True)
    # every input set carries the shipped contract documents, as /app/data does
    for name, raw in {**_contract_docs(), **files}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(raw)
    _seal(root)
    return root


def _contract_docs() -> dict[str, bytes]:
    return {name: zlib.decompress(base64.b64decode(blob)) for name, blob in _SHIPPED_DOCS.items()}


def _shipped_files() -> dict[str, bytes]:
    return {name: zlib.decompress(base64.b64decode(blob)) for name, blob in _SHIPPED_DATA.items()}


def _expected(data: Path) -> dict[str, object]:
    season, audit = derive(read_inputs(str(data)))
    scratch = tempfile.mkdtemp(prefix="expected-")
    try:
        write_outputs(season, audit, scratch)
        return {name: json.loads(Path(scratch, name).read_text()) for name in DOC_NAMES}
    finally:
        shutil.rmtree(scratch)


def solve_lane(rs, inc, prec, cap, fac, black, defer):
    pos = {r["id"]: k for k, r in enumerate(rs)}
    lane = Lane(dict(
        H=H, cap=cap, factor=fac, blackout=sorted(black), defer=defer,
        reqs=[dict(id=r["id"], crews=r["crews"], dur=r["dur"], e=r["e"], l=r["l"], w=r["w"], pub=r["pub"])
              for r in rs],
        incompat=[(min(pos[a], pos[b]), max(pos[a], pos[b])) for a, b in inc],
        prec=[(pos[a], pos[b]) for a, b in prec]))
    plan = reference(lane)
    if not lane.feasible(plan):
        raise RuntimeError("reference plan infeasible")
    return tuple(plan)


def _kill_leftovers(proc: subprocess.Popen, command: list[str]) -> None:
    """Stop every process the run left behind before its check returns."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if command[:1] != _SETPRIV[:1]:
        return
    # runs are serialised under _LOCK, so every process of the unprivileged user is this run's,
    # including a child that left the process group with setsid()
    nobody = pwd.getpwnam("nobody").pw_uid
    for status in Path("/proc").glob("[0-9]*/status"):
        try:
            uids = [line.split()[1] for line in status.read_text().splitlines() if line.startswith("Uid:")]
        except OSError:
            continue
        if uids and int(uids[0]) == nobody:
            try:
                os.kill(int(status.parent.name), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _run_program(data: Path, workdir: Path | None = None) -> dict:
    """Run the delivered program with the stated command; collect its documents."""
    out = Path(tempfile.mkdtemp(prefix="replan-out-"))
    out.chmod(0o777)
    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="elsewhere-"))
    workdir.mkdir(parents=True, exist_ok=True)
    workdir.chmod(0o777)
    command = _untrusted_command(["python3", str(SCRIPT), "--data", str(data), "--out", str(out)])
    result = {"returncode": None, "stderr": "", "docs": {}, "note": ""}
    proc = subprocess.Popen(command, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        _, stderr = proc.communicate(timeout=_RUN_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_leftovers(proc, command)
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()
        result["note"] = "the program did not finish within %d seconds" % _RUN_SECONDS
        return result
    _kill_leftovers(proc, command)
    result["returncode"] = proc.returncode
    result["stderr"] = stderr
    for name in DOC_NAMES:
        path = out / name
        if path.is_file():
            try:
                result["docs"][name] = json.loads(path.read_text())
            except ValueError as exc:
                result["docs"][name] = ("not valid JSON", str(exc))
    shutil.rmtree(out, ignore_errors=True)
    return result


def _memo(key: str, build) -> dict:
    with _LOCK:
        if key not in _MEMO:
            _MEMO[key] = build()
        return _MEMO[key]


def _fresh(key: str) -> dict:
    def build() -> dict:
        files = {name: text.encode() for name, text in build_inputs(_FRESH_SEEDS[key]).items()}
        data = _write_tree(files)
        return {"expected": _expected(data), "run": _run_program(data)}
    return _memo(key, build)


def _shipped() -> dict:
    def build() -> dict:
        data = _write_tree(_shipped_files())
        return {"data": data, "expected": _expected(data)}
    return _memo("shipped", build)


def _altered() -> dict:
    def build() -> dict:
        files = _shipped_files()
        rng = random.Random(4421)
        for name in ("customers.csv", "load_forecast.tsv"):
            lines = files[name].decode().splitlines(keepends=True)
            body = lines[1:]
            rng.shuffle(body)
            files[name] = "".join(lines[:1] + body).encode()
        for name in ("crew_roster.jsonl", "assets.jsonl"):
            lines = files[name].decode().splitlines(keepends=True)
            rng.shuffle(lines)
            files[name] = "".join(lines).encode()
        policy = files["risk_policy.toml"].decode()
        if "public = 2\n" not in policy:
            raise RuntimeError("risk_policy.toml has no public = 2 line to alter")
        files["risk_policy.toml"] = policy.replace("public = 2\n", "public = 3\n").encode()
        data = _write_tree(files)
        return {"expected": _expected(data), "run": _run_program(data)}
    return _memo("altered", build)


def _relocated() -> dict:
    def build() -> dict:
        base = Path(tempfile.mkdtemp(prefix="moved-"))
        base.chmod(0o755)
        data = _write_tree(_shipped_files(), base / "archive" / "2026" / "inputs")
        for parent in (base / "archive", base / "archive" / "2026"):
            parent.chmod(0o755)
        return {"run": _run_program(data, base / "cwd")}
    return _memo("relocated", build)


def _without_customers() -> dict:
    def build() -> dict:
        files = _shipped_files()
        del files["customers.csv"]
        return {"run": _run_program(_write_tree(files))}
    return _memo("missing", build)


def _first_difference(expected, got, path: str = "$") -> str | None:
    if type(expected) is not type(got):
        return path
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(got)):
            if key not in expected or key not in got:
                return "%s.%s" % (path, key)
            found = _first_difference(expected[key], got[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(expected, list):
        for index, (left, right) in enumerate(zip(expected, got)):
            found = _first_difference(left, right, "%s[%d]" % (path, index))
            if found:
                return found
        if len(expected) != len(got):
            return "%s[%d]" % (path, min(len(expected), len(got)))
        return None
    return None if expected == got else path


def _same_document(name: str, expected: dict, got) -> None:
    if not expected:
        raise AssertionError("%s: nothing to compare" % name)
    if got is None:
        raise AssertionError("%s: document not written" % name)
    where = _first_difference(expected, got)
    if where is not None:
        raise AssertionError("%s: first difference at %s" % (name, where))


def _check_delivered(name: str) -> None:
    path = OUT / name
    if not path.is_file():
        raise AssertionError("%s: not delivered" % path)
    _same_document(name, _shipped()["expected"][name], json.loads(path.read_text()))


def _check_run(case: dict, name: str) -> None:
    run = case["run"]
    if run["returncode"] is None:
        raise AssertionError(run["note"])
    if run["returncode"] != 0:
        raise AssertionError("exit status %d: %s" % (run["returncode"], run["stderr"][-400:]))
    _same_document(name, case["expected"][name], run["docs"].get(name))


def _check_fresh(key: str, name: str) -> None:
    _check_run(_fresh(key), name)


def _check_altered() -> None:
    _check_run(_altered(), "policy_audit.json")


def _check_relocated() -> None:
    case = {"run": _relocated()["run"], "expected": _shipped()["expected"]}
    _check_run(case, "summary.json")


def _check_missing_input() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    run = _without_customers()["run"]
    if run["returncode"] is None:
        raise AssertionError(run["note"])
    if run["returncode"] == 0:
        raise AssertionError("exit status 0 with customers.csv missing")
    if "customers.csv" not in run["stderr"]:
        raise AssertionError("the error output does not name customers.csv")


_NETWORK_MODULES = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib",
                    "imaplib", "telnetlib", "xmlrpc", "asyncio", "socketserver"}


def _check_outside_library_import() -> None:
    """Holds when the delivered program imports a module from outside the Python 3
    standard library or a network module. The instruction states: "Use the Python 3
    standard library only, with no network access." The weight is negative, so it
    counts only against a program that does this."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            root = name.split(".")[0]
            if root not in sys.stdlib_module_names or root in _NETWORK_MODULES:
                found.append(name)
    if not found:
        raise AssertionError("no outside or network import")
    print("outside or network imports: %s" % ", ".join(sorted(set(found))), file=sys.stderr)


def _check_hardcoded_sample_answers() -> None:
    """Holds when the delivered program's source carries three or more asset ids that the
    shipped answers single out (deferred, moved or rejected records of /app/data). The
    instruction states: "It reads only the data directory it is given". The weight is
    negative, so it counts only against a program that does this."""
    source = SCRIPT.read_text(encoding="utf-8")
    docs = _shipped()["expected"]
    marked = {row["asset_id"] for row in docs["policy_audit.json"]["requests"]
              if row["status"] == "deferred" or row["moved"]}
    marked |= {row["asset_id"] for row in docs["data_quality.json"]["rejected"]}
    hits = sorted(a for a in marked if a in source)
    if len(hits) < 3:
        raise AssertionError("no shipped answer ids in the program source")
    print("shipped answer ids in source: %s" % ", ".join(hits), file=sys.stderr)


def _holds(check, *args) -> bool:
    try:
        check(*args)
    except Exception as exc:
        print("%s%s: %s" % (check.__name__, args, exc), file=sys.stderr)
        return False
    return True


# ---- criteria ----

@criterion(description="The delivered policy_audit.json for /app/data matches the contract exactly.")
def shipped_policy_audit(workspace: Path) -> bool:
    return _holds(_check_delivered, "policy_audit.json")


@criterion(description="The delivered summary.json for /app/data matches the contract exactly.")
def shipped_summary(workspace: Path) -> bool:
    return _holds(_check_delivered, "summary.json")


@criterion(description="The delivered data_quality.json for /app/data matches the contract exactly.")
def shipped_data_quality(workspace: Path) -> bool:
    return _holds(_check_delivered, "data_quality.json")


@criterion(description="Fresh input set h2: region_North.json matches the contract exactly.")
def h2_region_north(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "region_North.json")


@criterion(description="Fresh input set h2: region_South.json matches the contract exactly.")
def h2_region_south(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "region_South.json")


@criterion(description="Fresh input set h2: region_West.json matches the contract exactly.")
def h2_region_west(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "region_West.json")


@criterion(description="Fresh input set h2: region_East.json matches the contract exactly.")
def h2_region_east(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "region_East.json")


@criterion(description="Fresh input set h2: policy_audit.json matches the contract exactly.")
def h2_policy_audit(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "policy_audit.json")


@criterion(description="Fresh input set h2: segment_commercial.json matches the contract exactly.")
def h2_segment_commercial(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "segment_commercial.json")


@criterion(description="Fresh input set h2: segment_public.json matches the contract exactly.")
def h2_segment_public(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "segment_public.json")


@criterion(description="Fresh input set h2: summary.json matches the contract exactly.")
def h2_summary(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "summary.json")


@criterion(description="Fresh input set h2: data_quality.json matches the contract exactly.")
def h2_data_quality(workspace: Path) -> bool:
    return _holds(_check_fresh, "h2", "data_quality.json")


@criterion(description="Fresh input set h3: region_North.json matches the contract exactly.")
def h3_region_north(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "region_North.json")


@criterion(description="Fresh input set h3: region_South.json matches the contract exactly.")
def h3_region_south(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "region_South.json")


@criterion(description="Fresh input set h3: region_West.json matches the contract exactly.")
def h3_region_west(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "region_West.json")


@criterion(description="Fresh input set h3: region_East.json matches the contract exactly.")
def h3_region_east(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "region_East.json")


@criterion(description="Fresh input set h3: policy_audit.json matches the contract exactly.")
def h3_policy_audit(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "policy_audit.json")


@criterion(description="Fresh input set h3: segment_commercial.json matches the contract exactly.")
def h3_segment_commercial(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "segment_commercial.json")


@criterion(description="Fresh input set h3: segment_public.json matches the contract exactly.")
def h3_segment_public(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "segment_public.json")


@criterion(description="Fresh input set h3: summary.json matches the contract exactly.")
def h3_summary(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "summary.json")


@criterion(description="Fresh input set h3: data_quality.json matches the contract exactly.")
def h3_data_quality(workspace: Path) -> bool:
    return _holds(_check_fresh, "h3", "data_quality.json")


@criterion(description="A copy of /app/data with rows reordered and the public class weight changed gives the exact policy_audit.json.")
def altered_copy_policy_audit(workspace: Path) -> bool:
    return _holds(_check_altered)


@criterion(description="A copy of /app/data in another directory, run from a third directory, gives the exact summary.json.")
def relocated_copy_summary(workspace: Path) -> bool:
    return _holds(_check_relocated)


@criterion(description="With customers.csv missing the program exits non-zero and its error output names customers.csv.")
def missing_customers_named(workspace: Path) -> bool:
    return _holds(_check_missing_input)


@criterion(description="Penalises a delivered program that imports a module from outside the Python 3 standard library or a network module.")
def negative_outside_library_import(workspace: Path) -> bool:
    return _holds(_check_outside_library_import)


@criterion(description="Penalises a delivered program whose source carries three or more asset ids of the deferred, moved or rejected records of the shipped data.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_hardcoded_sample_answers)


criteria.shipped_policy_audit(weight=3)
criteria.shipped_summary(weight=3)
criteria.shipped_data_quality(weight=3)
criteria.h2_region_north(weight=5)
criteria.h2_region_south(weight=5)
criteria.h2_region_west(weight=5)
criteria.h2_region_east(weight=5)
criteria.h2_policy_audit(weight=5)
criteria.h2_segment_commercial(weight=3)
criteria.h2_segment_public(weight=3)
criteria.h2_summary(weight=3)
criteria.h2_data_quality(weight=3)
criteria.h3_region_north(weight=5)
criteria.h3_region_south(weight=5)
criteria.h3_region_west(weight=5)
criteria.h3_region_east(weight=5)
criteria.h3_policy_audit(weight=5)
criteria.h3_segment_commercial(weight=3)
criteria.h3_segment_public(weight=3)
criteria.h3_summary(weight=3)
criteria.h3_data_quality(weight=3)
criteria.altered_copy_policy_audit(weight=3)
criteria.relocated_copy_summary(weight=3)
criteria.missing_customers_named(weight=3)
criteria.negative_outside_library_import(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)
