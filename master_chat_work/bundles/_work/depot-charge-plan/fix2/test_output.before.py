"""Checks for the depot charging day plan.

Expected documents are derived here from the shipped data folder and from fresh data
folders drawn by a seeded generator that lives only in this file. The delivered program is
run with the command the instruction states, as an unprivileged user, from a working
directory of its own, and every output document is compared whole.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false, reportOptionalMemberAccess=false

from __future__ import annotations

import ast
import base64
import configparser
import csv
import heapq
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
import xml.etree.ElementTree as ET
import zlib
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
DOC_NAMES = ["policy_audit.json", "summary.json", "data_quality.json", "region_North.json",
             "region_South.json", "region_West.json", "region_East.json",
             "segment_commercial.json", "segment_public.json"]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUN_SECONDS = 120
_FRESH = {"h1": (61207, "hidden"), "h2": (72931, "hidden"), "h3": (84419, "hidden"), "h4": (93503, "large")}
_LOCK = threading.Lock()
_MEMO: dict[str, dict] = {}


# ---- seeded generator of fresh input sets (verifier only) ----

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


# ---- reference derivation from the written contract ----

class MCF:
    def __init__(self, n):
        self.n = n
        self.g = [[] for _ in range(n)]
        self.E = []  # [u, v, cap, cost]

    def add(self, u, v, cap, cost):
        i = len(self.E)
        self.E.append([u, v, cap, cost])
        self.E.append([v, u, 0, -cost])
        self.g[u].append(i)
        self.g[v].append(i + 1)
        return i

    def run(self, s, t, need):
        n, E, g = self.n, self.E, self.g
        pi = [0] * n
        flow = 0
        while flow < need:
            dist = [None] * n
            pe = [-1] * n
            dist[s] = 0
            pq = [(0, s)]
            while pq:
                d, u = heapq.heappop(pq)
                if d != dist[u]:
                    continue
                for ei in g[u]:
                    e = E[ei]
                    if e[2] > 0:
                        v = e[1]
                        nd = d + e[3] + pi[u] - pi[v]
                        if dist[v] is None or nd < dist[v]:
                            dist[v] = nd
                            pe[v] = ei
                            heapq.heappush(pq, (nd, v))
            if dist[t] is None:
                raise RuntimeError("infeasible")
            for v in range(n):
                if dist[v] is not None:
                    pi[v] += dist[v]
            f = need - flow
            v = t
            while v != s:
                e = E[pe[v]]
                f = min(f, e[2])
                v = e[0]
            v = t
            while v != s:
                ei = pe[v]
                E[ei][2] -= f
                E[ei ^ 1][2] += f
                v = E[ei][0]
            flow += f
        return flow

    def potentials(self):
        n, E = self.n, self.E
        pi = [0] * n
        inq = [True] * n
        q = deque(range(n))
        while q:
            u = q.popleft()
            inq[u] = False
            for ei in self.g[u]:
                e = E[ei]
                if e[2] > 0 and pi[u] + e[3] < pi[e[1]]:
                    pi[e[1]] = pi[u] + e[3]
                    if not inq[e[1]]:
                        inq[e[1]] = True
                        q.append(e[1])
        return pi


def dp(inst, d):
    return inst["dprice"][d] if "dprice" in inst else inst["price"]


def build(inst, buses, cap, feeder, K1, K2, KM, eps=0):
    S = inst["S"]
    n = len(buses)
    N = 2 + n + 4 * S + S
    m = MCF(N)
    pos = {}
    total = 0
    for i, b in enumerate(buses):
        bn = 2 + i
        m.add(0, bn, b["need"], 0)
        m.add(bn, 1, b["need"], K1 * b["w"])
        total += b["need"]
        di = DEPOTS.index(b["depot"])
        for s in range(b["a"], b["e"]):
            p = min(b["pub"].get(str(s), 0), b["rate"])
            ds = 2 + n + di * S + s
            c = K2 * dp(inst, b["depot"])[s] + eps * s
            e1 = m.add(bn, ds, p, c - KM) if p > 0 else None
            e2 = m.add(bn, ds, b["rate"] - p, c) if b["rate"] - p > 0 else None
            pos[(s, b["id"])] = (e1, e2, bn, ds)
    for di, d in enumerate(DEPOTS):
        for s in range(S):
            m.add(2 + n + di * S + s, 2 + n + 4 * S + s, cap[d][s], 0)
    for s in range(S):
        m.add(2 + n + 4 * S + s, 1, feeder[s], 0)
    return m, pos, total


def extract(m, pos):
    x = {}
    for (s, bid), (e1, e2, _, _) in pos.items():
        k = 0
        for e in (e1, e2):
            if e is not None:
                k += m.E[e ^ 1][2]
        if k:
            x[(bid, s)] = k
    return x


def tie_pass(m, pos):
    E = m.E
    pi = m.potentials()
    rc0 = [E[i][3] + pi[E[i][0]] - pi[E[i][1]] == 0 for i in range(len(E))]
    blocked = bytearray(len(E))
    for key in sorted(pos):
        e1, e2, u, v = pos[key]
        own = [e for e in (e1, e2) if e is not None]
        for e in own:
            blocked[e] = blocked[e ^ 1] = 1
        while True:
            fw = [e for e in own if E[e][2] > 0 and rc0[e]]
            if not fw:
                break
            # BFS v -> u over free unblocked edges
            prev = {v: -1}
            dq = deque([v])
            while dq and u not in prev:
                a = dq.popleft()
                for ei in m.g[a]:
                    if blocked[ei] or E[ei][2] <= 0 or not rc0[ei]:
                        continue
                    b = E[ei][1]
                    if b not in prev:
                        prev[b] = ei
                        dq.append(b)
            if u not in prev:
                break
            path = []
            c = u
            while c != v:
                path.append(prev[c])
                c = E[prev[c]][0]
            f = min([E[fw[0]][2]] + [E[ei][2] for ei in path])
            for ei in path + [fw[0]]:
                E[ei][2] -= f
                E[ei ^ 1][2] += f


def solve_flow(inst, buses=None, cap=None, feeder=None, tie=True, eps=False, km=1):
    buses = inst["buses"] if buses is None else buses
    cap = inst["cap"] if cap is None else cap
    feeder = inst["feeder"] if feeder is None else feeder
    if eps:
        m, pos, total = build(inst, buses, cap, feeder, 10 ** 24, 10 ** 14, 10 ** 8, eps=1)
    else:
        m, pos, total = build(inst, buses, cap, feeder, 10 ** 15, 10 ** 6, km)
    m.run(0, 1, total)
    if tie:
        tie_pass(m, pos)
    return extract(m, pos)


FMT = "%Y-%m-%dT%H:%M"


def load(data):
    g = configparser.ConfigParser()
    g.read(os.path.join(data, "grid.ini"))
    pd = g["plan"]["plan_date"]
    t0 = datetime.strptime(g["plan"]["first_slot"], FMT)
    S = int(g["plan"]["slots"])

    def slot(t):
        d = datetime.strptime(t, FMT) - t0
        return int(d.total_seconds()) // 900

    def ts(s):
        return (t0 + timedelta(minutes=15 * s)).strftime(FMT)

    feeder = [int(g["feeder"]["feeder_kwh_per_slot"])] * S
    base = t0.hour * 4 + t0.minute // 15

    def tod(hhmm):
        h, mi = hhmm.split(":")
        return (int(h) * 4 + int(mi) // 15 - base) % S

    import xml.etree.ElementTree as ET
    versions = []
    for v in ET.parse(os.path.join(data, "tariff.xml")).getroot().iter("version"):
        arr = [None] * S
        for bd in v.iter("band"):
            a, b2 = tod(bd.get("from")), tod(bd.get("to"))
            n = (b2 - a) % S or S
            for i in range(n):
                arr[(a + i) % S] = int(bd.get("cents_per_kwh"))
        versions.append((v.get("valid_from"), v.get("valid_to"), arr))

    def tariff_on(day):
        hit = [arr for v0, v1, arr in versions if v0 <= day <= v1]
        assert len(hit) == 1, day
        return hit[0]

    price = tariff_on(pd)
    sess = {d: [] for d in DEPOTS}
    for r in csv.DictReader(open(os.path.join(data, "settlements.csv"))):
        st = datetime.strptime(r["start"], FMT)
        en = datetime.strptime(r["end"], FMT)
        L = int((en - st).total_seconds()) // 900
        s0 = tod(st.strftime("%H:%M"))
        sess[r["depot"]].append((tariff_on(r["settled_date"]), s0, L, int(r["kwh"]) // L, int(r["cents"])))
    dprice = {}
    for d in DEPOTS:
        ks = [k for k in range(S) if all(c == sum(rr * arr[(s0 + i + k) % S] for i in range(L)) for arr, s0, L, rr, c in sess[d])]
        assert len(ks) == 1, (d, ks)
        dprice[d] = [price[(s + ks[0]) % S] for s in range(S)]
    dj = json.load(open(os.path.join(data, "depots.json")))
    ck = dj["cabinet_kwh_per_slot"]
    cabs = {d["depot"]: [d["cabinets"]] * S for d in dj["depots"]}
    note = open(os.path.join(data, "disruption_notice.md")).read()
    for m in re.finditer(r"^- (\w+): (\d+) cabinets out of service from (\S+) to (\S+)$", note, re.M):
        for s in range(max(0, slot(m.group(3))), min(S, slot(m.group(4)))):
            cabs[m.group(1)][s] = max(0, cabs[m.group(1)][s] - int(m.group(2)))
    for m in re.finditer(r"^- from (\S+) to (\S+): feeder limit (\d+) kWh per slot$", note, re.M):
        for s in range(max(0, slot(m.group(1))), min(S, slot(m.group(2)))):
            feeder[s] = int(m.group(3))
    nd = (datetime.strptime(pd, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    extra = {}
    for m in re.finditer(r"^- (\w+): extra trip on (\S+), (\d+) kWh$", note, re.M):
        if m.group(2) == nd:
            extra[m.group(1)] = extra.get(m.group(1), 0) + int(m.group(3))
    types = json.load(open(os.path.join(data, "bus_types.json")))
    fleet = {r["vehicle_id"]: r for r in csv.DictReader(open(os.path.join(data, "fleet_register.csv")))}
    ccls = {c["contract_id"]: c["class"] for c in json.load(open(os.path.join(data, "contracts.json")))["contracts"]}
    sc = configparser.ConfigParser()
    sc.read(os.path.join(data, "service_classes.ini"))
    weight = {k: int(sc[k]["weight"]) for k in sc.sections()}
    trips = {}
    for line in open(os.path.join(data, "trips.jsonl")):
        t = json.loads(line)
        if t["service_date"] == nd:
            trips[t["bus_id"]] = trips.get(t["bus_id"], 0) + t["kwh"]
    rej, buses, seen = [], [], set()
    with open(os.path.join(data, "roster.csv")) as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            if r["plan_date"] != pd:
                continue
            bid = r["bus_id"]
            why = None
            if bid not in fleet:
                why = "unknown_vehicle"
            elif fleet[bid]["status"] != "active":
                why = "retired_vehicle"
            elif bid in seen:
                why = "duplicate_roster_row"
            elif not (0 <= slot(r["arrive"]) < slot(r["depart"]) <= S):
                why = "bad_window"
            if why:
                rej.append({"file": "roster.csv", "line": ln, "reason": why})
                continue
            seen.add(bid)
            ty = types[fleet[bid]["type"]]
            need = max(0, trips.get(bid, 0) + extra.get(bid, 0) + ty["reserve_kwh"] - int(r["soc_arrival_kwh"]))
            cls = ccls.get(r["contract_id"], "commercial")
            buses.append({"id": bid, "depot": r["depot"], "a": slot(r["arrive"]), "e": slot(r["depart"]),
                          "need": need, "rate": ty["max_kwh_per_slot"], "w": weight[cls], "cls": cls, "pub": {}})
    byid = {b["id"]: b for b in buses}
    with open(os.path.join(data, "published_plan.csv")) as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            if r["plan_date"] != pd:
                continue
            b = byid[r["bus_id"]]
            s = slot(r["slot_start"])
            if not (b["a"] <= s < b["e"]):
                rej.append({"file": "published_plan.csv", "line": ln, "reason": "published_row_outside_window"})
                continue
            b["pub"][str(s)] = b["pub"].get(str(s), 0) + int(r["kwh"])
    cap = {d: [c * ck for c in cabs[d]] for d in DEPOTS}
    inst = {"S": S, "price": price, "dprice": dprice, "feeder": feeder, "cap": cap, "buses": sorted(buses, key=lambda b: b["id"])}
    return inst, rej, pd, ts


def write(inst, x, rej, pd, ts, out):
    S = inst["S"]
    os.makedirs(out, exist_ok=True)
    load = [0] * S
    for (bid, s), k in x.items():
        load[s] += k
    rows = []
    for b in inst["buses"]:
        ch = sorted((s, k) for (bid, s), k in x.items() if bid == b["id"])
        got = sum(k for _, k in ch)
        un = b["need"] - got
        reason = None
        if un > 0:
            reason = "window" if b["need"] > b["rate"] * (b["e"] - b["a"]) else "supply"
        pubd = {int(s): k for s, k in b["pub"].items()}
        rows.append({"bus_id": b["id"], "depot": b["depot"], "class": b["cls"], "need_kwh": b["need"],
                     "delivered_kwh": got, "unmet_kwh": un, "unmet_reason": reason,
                     "changed": dict(ch) != pubd,
                     "charges": [{"slot": ts(s), "kwh": k} for s, k in ch],
                     "_cost": sum(k * dp(inst, b["depot"])[s] for s, k in ch),
                     "_moved": sum(max(0, p - dict(ch).get(s, 0)) for s, p in pubd.items()),
                     "_w": b["w"], "_ch": ch})
    fs = [{"slot": ts(s), "kwh": load[s]} for s in range(S)]

    def dump(name, obj):
        with open(os.path.join(out, name), "w") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")

    def strip(r):
        return {k: v for k, v in r.items() if not k.startswith("_")}

    def group(sel):
        sl = [0] * S
        for r in sel:
            for s, k in r["_ch"]:
                sl[s] += k
        return {"buses": len(sel), "energy_kwh": sum(r["delivered_kwh"] for r in sel),
                "cost_cents": sum(r["_cost"] for r in sel), "unmet_kwh": sum(r["unmet_kwh"] for r in sel),
                "slots": [{"slot": ts(s), "kwh": sl[s], "feeder_kwh": load[s]} for s in range(S)]}

    dump("policy_audit.json", {"plan_date": pd, "buses": [strip(r) for r in rows]})
    for d in DEPOTS:
        dump("region_%s.json" % d, dict({"depot": d}, **group([r for r in rows if r["depot"] == d])))
    for c in ("commercial", "public"):
        sel = [r for r in rows if r["class"] == c]
        dump("segment_%s.json" % c, dict({"class": c}, **group(sel)))
    dump("summary.json", {"plan_date": pd,
                          "weighted_unmet_kwh": sum(r["_w"] * r["unmet_kwh"] for r in rows),
                          "energy_cost_cents": sum(r["_cost"] for r in rows),
                          "moved_kwh": sum(r["_moved"] for r in rows),
                          "feeder_peak_kwh": max(load),
                          "feeder_kwh_by_slot": fs,
                          "buses_planned": len(rows),
                          "buses_short": sum(1 for r in rows if r["unmet_kwh"] > 0),
                          "buses_changed": sum(1 for r in rows if r["changed"]),
                          "records_rejected": len(rej)})
    dump("data_quality.json", {"plan_date": pd, "rejected": sorted(rej, key=lambda r: (r["file"], r["line"]))})


_SHIPPED_DATA: dict[str, str] = {
    'bus_types.json': (
        'eNqr5lJQUHI1NFKyUqgGMoGc3MSK+OzyjPiC1KL44pz8EqCMsYEORK4otTi1qCwVJA8UNjIAitbqQEwwxWuCiSlWE4yRTbDA'
        'a4IZdjeYgE3gquUCABQTNcQ='
    ),
    'contracts.json': (
        'eNq91LEKgzAUBdDdrwiZLajRJHZ1cSktdSxFbGpB0EaincR/rwoFB3mV+uiSIRdyyOMmnUUIVfrZmky1Dd2Ty7BBSDetsygt'
        '7kNIkyjeOS61P7Guc5O12qQmf4z5ORCzVJVZM55J69etLBSd9nv7u+BBghciCAwQuM8QBB8SHIkgBIAQCo4gcEBgfKMQJye4'
        'S8x3EASoS2JrWycB6pLkG9saHQ/wlHi4JChdVblRRVauV6BJScaRFHBagiEp0OvzF3v1ixL8RYFeYeAKJEVAdxESSZHQnxW6'
        'a5RhvVq99QaMGa2R'
    ),
    'depots.json': (
        'eNqr5lJQUEpOTMrMSy2Jzy7PiC9ILYovzskvUbJSMDTVAcmmpBbklxQD+dFAnoJCNZiEiQOFlfzyi0oylHRg4lDTQDqMDcCC'
        'tTo4dAbnl5KpMzy1uASrRiML/BpdE3FoNDaFaASSsVy1XAD5PkN0'
    ),
    'disruption_notice.md': (
        'eNqVkMtqwzAQRff+igve1jAaxzXRsq9lNw1k7aZyIpp4jDQJ/fzIMqRNC4EutLlz5+gwJZ58DMdRvQwYRP3GoZcAJr6vqK7M'
        'oijKEo/dux+cQo7abV0sigqvEnRnwdjMszgNIT2iC6eMCXL4wVmxsaaBylXGtqYEe0u7/4A1K2JLdAVLWZ0+yLovzn24gPQ6'
        '9cN20v1jQ78B2YbIop+39/7gFaYlfK53GFMS96KZ//yloYMGP+ZTPBhqjIW7pEjH/Ba7Q91MjNw07fJWk+nS5CXfarYz8wzk'
        'mXtY'
    ),
    'docs/charging_rules.md': (
        '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'
    ),
    'fleet_register.csv': (
        'eNp1nbuONNlynX0+yzHifnEJyJUjQyZBkAPwABJIkEMCenslp/99JivzK7fR6K7K3JeIFevyX7/9y1//6f/89g9//ee//P7/'
        '/u23v/zLv/7f3/7hn3/7t3/9/S//8fs//v6f//F3f986+Zf/ofaX//mv//77v/zl33/7/a///ts//93fT5hdP89fP//Hf/r9'
        'r//12/Xjcf3jx//rX//z49et648/8z/+8T9+/9tvV9fPT39++28/zorbHzk/zk17/42cXz99/Y3//vE8Pl+p/Hyd//3b/W9s'
        'yO1L/u3LyB+f4/k3rk8nf/z48fGqfn78x8f785uL/3yQj/9YGg7/sSIUHlOZwrPusYRvPiLzx29//MPxLHimNbN//PjjH072'
        'wlPy//69159ok3r/iZQc+Cau8DDSzOEvxPT7e/R604fwFvrxxMCPJ6PgDfZ0vD9HWzk9/XL4gmlZsGRGF9+gDq27dJf3n1YV'
        'h+cRv97r40+ELDzo8oUV0/HHi53HIvDBR5rp77XRPgMfo0b1/Zd7Mt8fbiIVvp8LngUVsG6r02iRq+P2rqV31SF9e0h/28j1'
        'sw5eJ2FLKp00UYIbIODp6dA5mN20eit3aPWaFzxVoYNX5deafm4A+XKi1PstXjscD14z+N4TBefutfBgD12nD/07wxWWLbdL'
        '4W8vJX3wC0rVe43lSMD66E3YcBOx8PSrf51Lzx2e+Ao1k7aL6NIfWeHDbQqvuKDFNE0Hco86HXm/junPN9C/Vunn81CBFT0e'
        'CQ/adeCgMTyVsnAx5s/581796/AwVH4dbY/fVsMNF0sHRWnDTaSWcLaV7tCukG44DfaPo+axZVV/VSOfFUNk0zdpHbwP1eEN'
        'VhlctNctCWtg12D1K996tAYy6OiZcLoS0uf9JLomacVZ0CP+OWKeX84Ct5TQM25xesa5ScXatW7h2iyRpR0fgXX0tdWEjjUL'
        'Khimf92Gj9/eTig9VR0rFzfBgiYavk5q4Hcfh9OkfekKt4CLyRoqlPaEVZdGF9C1p2jLp8rtHvzzRtgV+hvR+LZm6VY5h/zn'
        'zvzpQF47M4rqggm9NyZ/LoSypVJJaa2nbsDmLOU2RouuNzfD8ufXgvz8jub00wn6iq1KZdhc1SC8cfWgPWdzv2ZvFzt3N0bd'
        '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'
    ),
    'grid.ini': (
        'eNqLLshJzIvlApHxKYklqQq2CkYGRma6Bsa6hiZcaZlFxSXxxTn5JSjiIYZGVgYGXCDx+NzMvNKS1GKgvKEpWATEtDTj4opO'
        'S01NSS2K5YLQ8dnlGfEFQBpqmqEx0AQAZbQmMQ=='
    ),
    'published_plan.csv': (
        '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'
        '7nzJKFrtQok1H0w429B50R2746NZxMe6qHdN6tmrP5efJYKxlQOsTep6x90PC9YF7vhDJiGZ6mHx65kJ6GSOOFNEs9dArKhQ'
        'S2MuxejDYfx7MMe7e2JDwQDdjXgCZIBgvg9p76VsgCXd963evZQNEPH3JWL2Ph2F+n2ANXR38NP3orzWjrvDZwNUqfcZ3p0w'
        'BuDM4R5Xyrt7srzVIXBHNTPH3S8SA6xkjXiH0ADldcTNrgOk1IiskoWgz3qAxZ2/GyCl3jeNg9EAX6fuBrcEdOZ+XB8gW8a7'
        'ktXLlsTdzpB9XWtUo0DnRUrNfX18gCr1tkQXGG8e47AlacPKlszpzAF4fMSFswzjLcC3o+7cdtABxMOIBwQGYN/3bfq1SsIQ'
        'mRFPZ0vcjYPjYFhkjNAdGmDPTzDvnmGhMuL+YHOSUjpVSxSYuzck+bqnUPeyO6EwLIKMdKySVR49biFOIJh91F+33UL/S0uN'
        'RhnxRzvUnMkc4tRgMJeU3ckQKjHObkds8nVqM6YUyDun6UYiHk6mA467tZ6kvKq7bTaD7zAtg2mkF4LG/ZSSZfDkC2IVj0wY'
        'THUzxaSU2QgZjFpinhfioftCfS53vXTYZ0ms2nTUNdj93pJRNDUu01yULpiOVysp2v8SmNQWdr9OJtLIL+NknClr1RKSSMsC'
        'pEH1wDSXeZQyEHE5Io4SgWtWkRY03YK6wMvac6Y44nb1TGHMNusaPANhQPgKcc2+3LnOlrYuhuWECjBiXmWchIeWMyB/n32S'
        'Uv4uk6QisKldzO+C/Ie1ZbRYXhHTtVkaaQ/lFU8kRq0OeQRZi4bFrxpleAriAWPcrYwmquchOqtVz/LiAVdO92BBiqdAPQIj'
        'vi6075y14zaorgjGXiCf7Pu+RLwvd3UAlfcJ5X1u3sFC7Psk9y6NOpjf9XdvbXMtHWTf4/1PHQzw+5D2vjzRQZze94N37duB'
        '6nlfs+WL7ty92h1A5X3ZesavOyOu7s2GDrjgezmWQsRBMEm1DIGwuBCcxPo98T7qsXN7HjKoDO8ThoqbcGUtuXuNOsD4+xhz'
        'kzLifvdpB7rgDWaXEILTJ6HRg08g4j0Mi4FgcvN5d+qnN++mlvA18sl5ypA3OZeVeadrStkSD67jpG6nQgc68807qgnD34me'
        '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'
        'PQok/l8AMS5jLNjof8KcnZQ='
    ),
    'roster.csv': (
        'eNqkvV3PNEluJXbv39ICSEYwgqFLCQZ0Y3sBNeBLYSwJ2MUudhajWfvvuzIy6+2Hh2Rm1excNKYfNApVmfFBHp6P//Hf/vTf'
        '/+Xf/vTXf//t//mf//Ev/+Xffvu3f/8ff/7rb3/6y1/+y//778e//Okvf/3tP/78r/+y//Kn//Yv//X/+8+//euf//tf//Kn'
        'f/3r67//34Rk/B3J33H/7R8Gj/7b//nnv/z1P//2x59/F/n7rn/8QX+nfvxB6bd//L/+j7+jdn1E+ztav/2DWuu//e9/+o+/'
        '/vbHX38X/nvWX39g+p3a8Yf3J+ivL0Hy2z/MSe4Tjr/+zvPviX7+Qdrxh/cn2K/vwPz6Drr6b//85//562ccf8YvIfAlxq8v'
        'IfP1Ef31958fcfz5d6E/PuL1B/udJP8IGq+HScPgYdL4ndfPj6D5O/HPj/jxQ9rrI7pN9xHHn3/n8cf72H84X9D7I/ofr5R+'
        '+wcT7fBDXs8fXinDK/3jI+T4FmMO+CHSjjfS6OcfXm+kUfJOWY5nYf23//vff7zT1/Nn+/kJr99B9PMTfnyJ19KcJIJfApem'
        '4NKcfzxNOj5itp9fYq/Enwtr/8EvrO4W93j9z3/Ca3Gz/nwd52rv2eI+foba6zu4xX38ivZzcR+/Qn9+hx+fMI7tMSY+iHGs'
        'iZ9vYxxP5sez/GNl7v0xZ1gTe3/8fB17f/z4iB/b/PUtrA+BbT7wSQx4EuOPT3gtCW2D4RPk2B3tj7dB7dgdP76DuGc5Fh4U'
        'x7P0W1Rhi/74Fa8HMV4PE94nHyvixznx+oO4cwL2xmwr2RvLvdB+/IwfL3T+cU68PmI2w5X9+uE/T6vXHzqcVuyPmjFactTM'
        'n5vjeB0tP7ePo2by7LA52vX+fv1hf4lke117vM10j/88aPYez8+qY1FNUVyXeyX/eJg8jz1OlK2q15oweq0tf/TTXhQ/F+Ze'
        'FPnvOHaHKGzRc3P8/B0CT+KP17GP7dfRj7+j4XHX4bgzt79UB5xVv7bTrz9M+BLq1vZcq4W1/fO83BvOn5c/LrDjQSxluIj5'
        'eJT+IiYp3oa+HoTgift69j9Pu/2z/Gnn7+HXkrDkHnZv47iH05X9vjlGcnP4guLXIYxLgv+uHeeEjeW+xfFndw/vP/h7WN2a'
        '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'
    ),
    'service_classes.ini': (
        'eNqLLihNyslMjuUqT81MzyhRsFUw4eKKTs7PzU0tSs5MzEGSMOQCAGN0Dq0='
    ),
    'settlements.csv': (
        'eNqlvc3OtauuJdava1klYX4MVDNSuumkpDRLJzlbqihRnVKdXcrtZ/48GGwPYO5vS+vrPGsyXjC2MWZg/v1vf//7//u3f/0v'
        '//ovf//bX//6t//+b3//6//8n//+X/7vf/3r3//+L//j73/97b/961//z//3X//6v/723/7+7/8hhsj/McT/GNtf/9u//Y+/'
        '/9e//hdOtf01P/9niv8pBPUh/acU/qIW/qohhhXhf/+3//lGqKnVM0J+f8gvBOIYAuhE48YGItlOvCAovmC4QYRcs0HIBQwj'
        'lb9K5LIi/B9/+/e/v0bBHfxFPYoXQOLwVw96EP/rv7wBSmvtDFBEDK1qST5dKM12mYpBeHWh5BdC6A0gMN0RXmLhrywZCbJk'
        'M5vJTsVnNvt3MkEXeuRz+/LuU3r9K1yRFFrPPwBEek1GbUghKbouGF3IbwQwhAeAY05ngI8Y42sicoJCSDHfAF6Dyi99rgVP'
        'w6trXurrB/582HahRkpngI8Q+K1L0KIoheZ/r3vw+vDW58YZibFwSj8gvE2KM1Ln+lJyb0Hrh/qxyddHZgYAjUI9A3yk+HZu'
        'rxkDRl0L1VsP3pqcP64F+zbKHaivgnhjAn0eCDXTP4dQegw3hLc+hpdVELSp1uKlD5+5fHvoSAwk2dptEB+bejvhGpAucAAW'
        'pIfwav8eAgWKBUihJjeZGUjhLccSsEaTWWUcAr8RgGcZE8GBgBXbqURiHL4plXxDeBvV1iZq5ksXPmM4zGSl/ssY2tZBl8TZ'
        '6876oQ11pNjRIEq5I4Svg6XIAYYtLydtIDKAeAuSQkbOoaXYfkCI8aWWNYKYg1uJfuo0QP46SMpGIx85xFS9Eawf+hbhCVuy'
        '64NGiOE9iJOH48oNDFtBvKezvCBqKdhBpXyEeI3jWe56glpdKd/6EMJJlDXDybNK+QKIKUMxUOn+964LL/f2UqiSsCRrvUG8'
        'e4kghpus7YbwXrXfhsGpAYVgNsFP8wrxqFSvEa94ZhTdTyaW5LNqZ2Pc3c/l4+KIKorFa6xkELRhRRIHE3oqcDZT833WEDuF'
        'Gkodez5DhN3W6rFuKuUMEMVFWUHIcpGz9wd6GLRxEMNRBhOKAoh3FPZZ/mMrcN0MdIb4DOQzH6V2tD17CfPWiZ0ovjpBgfmH'
        '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'
        'zWtdGYjd2qOPnIXorIVIAcpgbEX/f4zi+AI='
    ),
    'tariff.xml': (
        'eNqNlNtOg0AQhu95is3cI3sS2oalV/oAxl4T5KAb28VsadW3ly6rqEwKCRdk9/+YyTcT0u3HYU/OtT3q1ihgNxRIbcq20uZZ'
        'we7xPlzBNgvSrrC6aUh5sra//lRwt3sAcjK6U1DWpjvmb7XNX99fIAsISf0HybnY6ypvbHtQwCmPQypCmoA/79rxlAlH9uxT'
        'YSoyIIxvaN/QJceke/1TS4FIIEIw+YNxsRFTjHMM89kLRiWKSQzzWdckx5pkqwFLI69lVhGTU0W384piVBFDFcWjIrRpjprl'
        'YzWKVmO4orEaruh7IEsV8f7BtojGM4rQdRBrVNG4Diy5Ntd/WPLb7OJqPuvMMnT50Dn6rMPWy+fos1d2lk4GkkbDTyALvgCM'
        'Hi7d'
    ),
    'trips.jsonl': (
        'eNqsvcvObDmPJTb3UzRq7AJESSQlD/0MnjdsdwNueGL0xR40/O4OSZGoPMm1ScaWp6z8o+LEt7dELq7Lf/+X//qf/9P/9e//'
        '03/4l//p3/3L/6Jc6V9Lo/Yv/+O/+5f/7b/9l2/9f171Vfov//E//9//6X//j//+P/yv//U/rv9DLVU+//2/Ul//1//z//k/'
        'PkVq5f/9H/77Hx/LMif62FXPfqyaTxVS/fxXpf7jU1fd+9TSvE/Vof1fSy39nz/Bp/78qfVfC//tJxDzsaP2gb7sqme/LBX7'
        'yzZZ37b+82NX3fu21f/YIVXXx45/fttP3f229G8fO+2X7W3/weifX/ZTdz+1/tundvRdJ/xlP/WLX5bo88v+8zNX0X1g//YQ'
        'sH20qOx//z9/1VV3v+n8t0+1TxbzoPXA6j9/1U/dfWCH97cSlYaegFXPPgHDftc5FD6un3r6cbU/rMz1w9byz/Nl1d2f4O/H'
        'Fj38Bu282b/8BuIfBXxOmH9+7Kq73/bvH9vB29XXx9I0b1f3j4LifqzWth4v+ue3XXXvY0ncl7Y1fBx+6umXlsHH0ljPVzcf'
        'S8P9Ddj/DRoxvBPa+VlSd4I9YrTsw808CKt+8yDIhL/tqqd/W/ux0mZZv+0/z5lVd3/bv50zVMF9K3V9rPkRPnX3Y8V/d6Xv'
        'b/vPu2bV3Y+t7reVMgmeNJ96+qRp4GPPc2tamRI8t/7r8LkB9gNmLtxB/gNW/bes1H03lH++ZaW6H1vd7mBQ7atJNJ9K1b9z'
        'yb1zu6zn4JxGf3+8PnX3+FLv+FLmfTPYPpn9m6G7N/nY15g5alc9e9TC1lPW6WV/2E/d/Vjy3zBqHX3sqmc/FvQdc3T0y656'
        '9pcFL9hoU/DFMCV9MQh4bwU3Hp96+jgA762MBhvlTz3bKKMfoawfwX7sqqc/lkADzgO9Yqv+/hUb0jqaGVc9PYqCA1zOyzDN'
        'veC/DEGXxJP3gyCmsWX/QVBvFh3Mu/cyf7BP3f1lq/uptJvwMs1B6zfhVNzHgPl0M3YOCbqZ4Z2JQyeeRD/17BwCzu85cVM7'
        'Z7qpRS1Sr/AAX/Xsx4LpRpjRxbjq2YsRXQu9FNQcrHq6OQAvWF9Yj21qVz3b1CoYblaX2EwHvuruY+Cf30yDUU+76tmeFky5'
        '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'
    ),
}


# ==== CHECKS ====
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


def _shipped_files() -> dict[str, bytes]:
    return {name: zlib.decompress(base64.b64decode(blob)) for name, blob in _SHIPPED_DATA.items()}


def _write_tree(files: dict[str, bytes], root: Path | None = None) -> Path:
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="inputs-"))
    root.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(raw)
    _seal(root)
    return root


def _assert_contract_bounds(root: Path) -> None:
    """Every drawn value stays inside what the shipped rules describe."""
    grid = configparser.ConfigParser()
    grid.read(root / "grid.ini")
    assert grid["plan"]["slot_minutes"] == "15" and grid["plan"]["slots"] == "96"
    assert int(grid["feeder"]["feeder_kwh_per_slot"]) > 0
    first = datetime.strptime(grid["plan"]["first_slot"], "%Y-%m-%dT%H:%M")
    assert first.minute % 15 == 0
    with open(root / "roster.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            for key in ("arrive", "depart"):
                assert datetime.strptime(row[key], "%Y-%m-%dT%H:%M").minute % 15 == 0
            assert int(row["soc_arrival_kwh"]) >= 0
    with open(root / "published_plan.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            assert int(row["kwh"]) > 0
            assert datetime.strptime(row["slot_start"], "%Y-%m-%dT%H:%M").minute % 15 == 0
    with open(root / "settlements.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            assert int(row["kwh"]) > 0 and int(row["cents"]) > 0
    with open(root / "trips.jsonl") as handle:
        for line in handle:
            assert int(json.loads(line)["kwh"]) > 0
    for band in ET.parse(root / "tariff.xml").getroot().iter("band"):
        assert int(band.get("cents_per_kwh")) > 0
    for depot in json.loads((root / "depots.json").read_text())["depots"]:
        assert depot["depot"] in DEPOTS and int(depot["cabinets"]) > 0


def _fresh_tree(seed: int, kind: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="inputs-"))
    render(seed, kind, str(root))
    docs = {name: raw for name, raw in _shipped_files().items() if name.startswith("docs/")}
    _write_tree(docs, root)
    _assert_contract_bounds(root)
    _seal(root)
    return root


def _expected(data: Path) -> dict[str, object]:
    inst, rej, pd, ts = load(str(data))
    plan = solve_flow(inst)
    scratch = tempfile.mkdtemp(prefix="expected-")
    try:
        write(inst, plan, rej, pd, ts, scratch)
        return {name: json.loads(Path(scratch, name).read_text()) for name in DOC_NAMES}
    finally:
        shutil.rmtree(scratch)


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
    out = Path(tempfile.mkdtemp(prefix="plan-out-"))
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


def _shipped() -> dict:
    def build() -> dict:
        data = _write_tree(_shipped_files())
        return {"data": data, "expected": _expected(data)}
    return _memo("shipped", build)


def _fresh(key: str) -> dict:
    def build() -> dict:
        seed, kind = _FRESH[key]
        data = _fresh_tree(seed, kind)
        return {"expected": _expected(data), "run": _run_program(data)}
    return _memo(key, build)


def _altered() -> dict:
    """Fresh set h2 with every table's body rows in a new order and a new public weight."""
    def build() -> dict:
        seed, kind = _FRESH["h2"]
        data = _fresh_tree(seed, kind)
        rng = random.Random(seed * 31 + 7)
        for name in ("roster.csv", "published_plan.csv", "settlements.csv", "fleet_register.csv", "trips.jsonl"):
            path = data / name
            lines = path.read_text().splitlines(keepends=True)
            skip = 0 if name.endswith(".jsonl") else 1
            body = lines[skip:]
            rng.shuffle(body)
            path.write_text("".join(lines[:skip] + body))
        weights = data / "service_classes.ini"
        weights.write_text(weights.read_text().replace("[public]\nweight = 4", "[public]\nweight = 6"))
        _seal(data)
        return {"expected": _expected(data), "run": _run_program(data)}
    return _memo("altered", build)


def _relocated() -> dict:
    """Fresh set h3 placed under a deeper folder and run from a different working directory."""
    def build() -> dict:
        seed, kind = _FRESH["h3"]
        base = Path(tempfile.mkdtemp(prefix="relocated-"))
        base.chmod(0o755)
        data = base / "archive" / "2026" / "inputs"
        shutil.copytree(_fresh_tree(seed, kind), data)
        for part in (base / "archive", base / "archive" / "2026"):
            part.chmod(0o755)
        _seal(data)
        return {"expected": _expected(data), "run": _run_program(data, base / "cwd")}
    return _memo("relocated", build)


def _without_settlements() -> dict:
    def build() -> dict:
        files = _shipped_files()
        del files["settlements.csv"]
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


def _check_present() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    for name in DOC_NAMES:
        if not (OUT / name).is_file():
            raise AssertionError("%s: not delivered" % (OUT / name))


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
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_fresh(key), name)


def _check_altered() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_altered(), "policy_audit.json")


def _check_relocated() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    _check_run(_relocated(), "summary.json")


def _check_missing_input() -> None:
    if not SCRIPT.is_file():
        raise AssertionError("%s: not delivered" % SCRIPT)
    run = _without_settlements()["run"]
    if run["returncode"] is None:
        raise AssertionError(run["note"])
    if run["returncode"] == 0:
        raise AssertionError("exit status 0 with settlements.csv missing")
    if "settlements.csv" not in run["stderr"]:
        raise AssertionError("the error output does not name settlements.csv")


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
    """Holds when the delivered program's source carries every bus id that the shipped
    answers list as short (three or more). The instruction states: "It reads only the
    data folder it is given". The weight is negative, so it counts only against a program
    that does this."""
    source = SCRIPT.read_text(encoding="utf-8")
    rows = _shipped()["expected"]["policy_audit.json"]["buses"]
    marked = sorted(row["bus_id"] for row in rows if row["unmet_kwh"] > 0)
    hits = [bus for bus in marked if bus in source]
    if len(marked) < 3 or len(hits) < len(marked):
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


@criterion(description='The delivered /app/out/derive_report.py parses as Python and /app/out holds all nine report files.')
def program_and_reports_present(workspace: Path) -> bool:
    return _holds(_check_present)


@criterion(description='The delivered /app/out/policy_audit.json for the shipped data equals the policy audit derived from the written rules, as a whole document.')
def shipped_policy_audit_exact(workspace: Path) -> bool:
    return _holds(_check_delivered, 'policy_audit.json')


@criterion(description='The delivered /app/out/summary.json for the shipped data equals the summary derived from the written rules, as a whole document.')
def shipped_summary_exact(workspace: Path) -> bool:
    return _holds(_check_delivered, 'summary.json')


@criterion(description='The delivered /app/out/data_quality.json for the shipped data equals the data quality report derived from the written rules, as a whole document.')
def shipped_data_quality_exact(workspace: Path) -> bool:
    return _holds(_check_delivered, 'data_quality.json')


@criterion(description='The delivered /app/out/segment_public.json for the shipped data equals the public class report derived from the written rules, as a whole document.')
def shipped_segment_public_exact(workspace: Path) -> bool:
    return _holds(_check_delivered, 'segment_public.json')


@criterion(description='The delivered /app/out/region_East.json for the shipped data equals the East depot report derived from the written rules, as a whole document.')
def shipped_region_east_exact(workspace: Path) -> bool:
    return _holds(_check_delivered, 'region_East.json')


@criterion(description="On the first fresh data folder, the program's policy_audit.json equals the per-bus policy audit derived from the written rules, as a whole document.")
def fresh_h1_policy_audit_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'policy_audit.json')


@criterion(description="On the first fresh data folder, the program's region_North.json equals the North depot report derived from the written rules, as a whole document.")
def fresh_h1_region_north_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'region_North.json')


@criterion(description="On the first fresh data folder, the program's region_South.json equals the South depot report derived from the written rules, as a whole document.")
def fresh_h1_region_south_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'region_South.json')


@criterion(description="On the first fresh data folder, the program's region_West.json equals the West depot report derived from the written rules, as a whole document.")
def fresh_h1_region_west_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'region_West.json')


@criterion(description="On the first fresh data folder, the program's region_East.json equals the East depot report derived from the written rules, as a whole document.")
def fresh_h1_region_east_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'region_East.json')


@criterion(description="On the first fresh data folder, the program's segment_commercial.json equals the commercial class report derived from the written rules, as a whole document.")
def fresh_h1_segment_commercial_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'segment_commercial.json')


@criterion(description="On the first fresh data folder, the program's segment_public.json equals the public class report derived from the written rules, as a whole document.")
def fresh_h1_segment_public_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'segment_public.json')


@criterion(description="On the first fresh data folder, the program's summary.json equals the summary derived from the written rules, as a whole document.")
def fresh_h1_summary_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'summary.json')


@criterion(description="On the first fresh data folder, the program's data_quality.json equals the data quality report derived from the written rules, as a whole document.")
def fresh_h1_data_quality_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h1', 'data_quality.json')


@criterion(description="On the second fresh data folder, the program's policy_audit.json equals the per-bus policy audit derived from the written rules, as a whole document.")
def fresh_h2_policy_audit_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'policy_audit.json')


@criterion(description="On the second fresh data folder, the program's region_North.json equals the North depot report derived from the written rules, as a whole document.")
def fresh_h2_region_north_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'region_North.json')


@criterion(description="On the second fresh data folder, the program's region_South.json equals the South depot report derived from the written rules, as a whole document.")
def fresh_h2_region_south_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'region_South.json')


@criterion(description="On the second fresh data folder, the program's region_West.json equals the West depot report derived from the written rules, as a whole document.")
def fresh_h2_region_west_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'region_West.json')


@criterion(description="On the second fresh data folder, the program's region_East.json equals the East depot report derived from the written rules, as a whole document.")
def fresh_h2_region_east_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'region_East.json')


@criterion(description="On the second fresh data folder, the program's segment_commercial.json equals the commercial class report derived from the written rules, as a whole document.")
def fresh_h2_segment_commercial_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'segment_commercial.json')


@criterion(description="On the second fresh data folder, the program's segment_public.json equals the public class report derived from the written rules, as a whole document.")
def fresh_h2_segment_public_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'segment_public.json')


@criterion(description="On the second fresh data folder, the program's summary.json equals the summary derived from the written rules, as a whole document.")
def fresh_h2_summary_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h2', 'summary.json')


@criterion(description="On the third fresh data folder, the program's policy_audit.json equals the per-bus policy audit derived from the written rules, as a whole document.")
def fresh_h3_policy_audit_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'policy_audit.json')


@criterion(description="On the third fresh data folder, the program's region_North.json equals the North depot report derived from the written rules, as a whole document.")
def fresh_h3_region_north_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'region_North.json')


@criterion(description="On the third fresh data folder, the program's region_South.json equals the South depot report derived from the written rules, as a whole document.")
def fresh_h3_region_south_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'region_South.json')


@criterion(description="On the third fresh data folder, the program's region_West.json equals the West depot report derived from the written rules, as a whole document.")
def fresh_h3_region_west_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'region_West.json')


@criterion(description="On the third fresh data folder, the program's region_East.json equals the East depot report derived from the written rules, as a whole document.")
def fresh_h3_region_east_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'region_East.json')


@criterion(description="On the third fresh data folder, the program's segment_commercial.json equals the commercial class report derived from the written rules, as a whole document.")
def fresh_h3_segment_commercial_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'segment_commercial.json')


@criterion(description="On the third fresh data folder, the program's segment_public.json equals the public class report derived from the written rules, as a whole document.")
def fresh_h3_segment_public_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'segment_public.json')


@criterion(description="On the third fresh data folder, the program's summary.json equals the summary derived from the written rules, as a whole document.")
def fresh_h3_summary_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'summary.json')


@criterion(description="On the third fresh data folder, the program's data_quality.json equals the data quality report derived from the written rules, as a whole document.")
def fresh_h3_data_quality_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h3', 'data_quality.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's policy_audit.json equals the per-bus policy audit derived from the written rules, as a whole document.")
def fresh_h4_policy_audit_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'policy_audit.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's region_North.json equals the North depot report derived from the written rules, as a whole document.")
def fresh_h4_region_north_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'region_North.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's region_South.json equals the South depot report derived from the written rules, as a whole document.")
def fresh_h4_region_south_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'region_South.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's region_West.json equals the West depot report derived from the written rules, as a whole document.")
def fresh_h4_region_west_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'region_West.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's region_East.json equals the East depot report derived from the written rules, as a whole document.")
def fresh_h4_region_east_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'region_East.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's segment_commercial.json equals the commercial class report derived from the written rules, as a whole document.")
def fresh_h4_segment_commercial_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'segment_commercial.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's segment_public.json equals the public class report derived from the written rules, as a whole document.")
def fresh_h4_segment_public_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'segment_public.json')


@criterion(description="On the fourth (largest) fresh data folder, the program's summary.json equals the summary derived from the written rules, as a whole document.")
def fresh_h4_summary_exact(workspace: Path) -> bool:
    return _holds(_check_fresh, 'h4', 'summary.json')


@criterion(description="On a copy of the second fresh data folder with its file rows reordered and the public class weight changed, the program's policy_audit.json equals the one derived from the written rules.")
def reordered_copy_policy_audit_exact(workspace: Path) -> bool:
    return _holds(_check_altered)


@criterion(description="Run from an unrelated working directory on a copy of the third fresh data folder placed under another path, the program's summary.json equals the one derived from the written rules.")
def relocated_copy_summary_exact(workspace: Path) -> bool:
    return _holds(_check_relocated)


@criterion(description='On the shipped data without settlements.csv, the program exits non-zero and its error output names settlements.csv.')
def missing_settlements_stops_naming_file(workspace: Path) -> bool:
    return _holds(_check_missing_input)


@criterion(description='The delivered program imports a module outside the Python 3 standard library or a network module.')
def negative_outside_library_or_network_import(workspace: Path) -> bool:
    return _holds(_check_outside_library_import)


@criterion(description="The delivered program's source carries every bus id that the shipped answers list as short.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_hardcoded_sample_answers)


criteria.program_and_reports_present(weight=1)
criteria.shipped_policy_audit_exact(weight=3)
criteria.shipped_summary_exact(weight=3)
criteria.shipped_data_quality_exact(weight=3)
criteria.shipped_segment_public_exact(weight=3)
criteria.shipped_region_east_exact(weight=3)
criteria.fresh_h1_policy_audit_exact(weight=5)
criteria.fresh_h1_region_north_exact(weight=5)
criteria.fresh_h1_region_south_exact(weight=5)
criteria.fresh_h1_region_west_exact(weight=5)
criteria.fresh_h1_region_east_exact(weight=5)
criteria.fresh_h1_segment_commercial_exact(weight=5)
criteria.fresh_h1_segment_public_exact(weight=5)
criteria.fresh_h1_summary_exact(weight=5)
criteria.fresh_h1_data_quality_exact(weight=3)
criteria.fresh_h2_policy_audit_exact(weight=5)
criteria.fresh_h2_region_north_exact(weight=5)
criteria.fresh_h2_region_south_exact(weight=5)
criteria.fresh_h2_region_west_exact(weight=5)
criteria.fresh_h2_region_east_exact(weight=5)
criteria.fresh_h2_segment_commercial_exact(weight=5)
criteria.fresh_h2_segment_public_exact(weight=5)
criteria.fresh_h2_summary_exact(weight=5)
criteria.fresh_h3_policy_audit_exact(weight=5)
criteria.fresh_h3_region_north_exact(weight=5)
criteria.fresh_h3_region_south_exact(weight=5)
criteria.fresh_h3_region_west_exact(weight=5)
criteria.fresh_h3_region_east_exact(weight=5)
criteria.fresh_h3_segment_commercial_exact(weight=5)
criteria.fresh_h3_segment_public_exact(weight=5)
criteria.fresh_h3_summary_exact(weight=5)
criteria.fresh_h3_data_quality_exact(weight=3)
criteria.fresh_h4_policy_audit_exact(weight=5)
criteria.fresh_h4_region_north_exact(weight=5)
criteria.fresh_h4_region_south_exact(weight=5)
criteria.fresh_h4_region_west_exact(weight=5)
criteria.fresh_h4_region_east_exact(weight=5)
criteria.fresh_h4_segment_commercial_exact(weight=5)
criteria.fresh_h4_segment_public_exact(weight=5)
criteria.fresh_h4_summary_exact(weight=5)
criteria.reordered_copy_policy_audit_exact(weight=3)
criteria.relocated_copy_summary_exact(weight=3)
criteria.missing_settlements_stops_naming_file(weight=3)
criteria.negative_outside_library_or_network_import(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)

