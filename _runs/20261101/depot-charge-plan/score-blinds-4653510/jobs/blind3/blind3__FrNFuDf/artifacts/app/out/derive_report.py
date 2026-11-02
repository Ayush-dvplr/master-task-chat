#!/usr/bin/env python3
"""Overnight depot charging planner.

Builds the day plan defined by <data>/docs/charging_rules.md and writes the
planning reports into the output folder.

Usage:
    python3 derive_report.py --data <data folder> --out <output folder>
"""

import argparse
import configparser
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from heapq import heappush, heappop

# --------------------------------------------------------------------------
# lexicographic scalarisation weights: weighted unmet >> energy cost >> moved
W_UNMET = 10 ** 22
W_COST = 10 ** 11


class DataError(Exception):
    def __init__(self, filename, detail):
        super().__init__("%s: %s" % (filename, detail))
        self.filename = filename
        self.detail = detail


def need_path(base, name):
    p = os.path.join(base, name)
    if not os.path.isfile(p):
        raise DataError(name, "file is missing from the data folder")
    return p


def parse_dt(txt, fname, what):
    try:
        return datetime.strptime(txt.strip(), "%Y-%m-%dT%H:%M")
    except Exception:
        try:
            return datetime.fromisoformat(txt.strip())
        except Exception:
            raise DataError(fname, "cannot read %s as a timestamp: %r" % (what, txt))


def parse_int(txt, fname, what):
    try:
        return int(str(txt).strip())
    except Exception:
        raise DataError(fname, "cannot read %s as a whole number: %r" % (what, txt))


def read_csv_rows(base, name):
    path = need_path(base, name)
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            rdr = csv.DictReader(fh)
            if rdr.fieldnames is None:
                raise DataError(name, "file has no header row")
            rows = []
            for i, row in enumerate(rdr):
                rows.append((i + 2, row))  # header is line 1
            return rdr.fieldnames, rows
    except DataError:
        raise
    except Exception as exc:
        raise DataError(name, "cannot be read as CSV (%s)" % exc)


def read_json(base, name):
    path = need_path(base, name)
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        raise DataError(name, "cannot be read as JSON (%s)" % exc)


def read_ini(base, name):
    path = need_path(base, name)
    cp = configparser.ConfigParser()
    try:
        with open(path, encoding="utf-8") as fh:
            cp.read_file(fh)
    except Exception as exc:
        raise DataError(name, "cannot be read as INI (%s)" % exc)
    return cp


# --------------------------------------------------------------------------
# tariff


def tod_minutes(txt, fname):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", txt or "")
    if not m:
        raise DataError(fname, "cannot read %r as a time of day" % txt)
    return int(m.group(1)) * 60 + int(m.group(2))


class TariffVersion(object):
    def __init__(self, valid_from, valid_to, bands):
        self.valid_from = valid_from
        self.valid_to = valid_to
        self.bands = bands  # list of (start_min, end_min, cents)

    def price_at(self, minute):
        minute %= 1440
        for a, b, c in self.bands:
            if a < b:
                if a <= minute < b:
                    return c
            elif a > b:
                if minute >= a or minute < b:
                    return c
            else:
                return c
        return None


def load_tariff(base):
    name = "tariff.xml"
    path = need_path(base, name)
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        raise DataError(name, "cannot be read as XML (%s)" % exc)
    versions = []
    for ve in root.iter("version"):
        vf = (ve.get("valid_from") or "").strip()
        vt = (ve.get("valid_to") or "").strip()
        if not vf or not vt:
            raise DataError(name, "a version has no valid_from/valid_to")
        bands = []
        for be in ve.findall("band"):
            a = tod_minutes(be.get("from"), name)
            b = tod_minutes(be.get("to"), name)
            cents = parse_int(be.get("cents_per_kwh"), name, "cents_per_kwh")
            bands.append((a, b, cents))
        if not bands:
            raise DataError(name, "version %s has no bands" % vf)
        versions.append(TariffVersion(vf, vt, bands))
    if not versions:
        raise DataError(name, "holds no tariff versions")
    return versions


def version_in_force(versions, date_str, fname):
    hit = None
    for v in versions:
        if v.valid_from <= date_str <= v.valid_to:
            hit = v
            break
    if hit is None:
        raise DataError(fname, "no tariff version is in force on %s" % date_str)
    return hit


# meter candidates: how a depot's meter maps a slot to a band price.
def meter_candidates(slot_minutes):
    sm = slot_minutes

    def at(v, m):
        return v.price_at(m)

    return [
        ("start", lambda v, m: at(v, m)),
        ("slot_end", lambda v, m: at(v, m + sm)),
        ("slot_prev", lambda v, m: at(v, m - sm)),
        ("floor_hour", lambda v, m: at(v, (m // 60) * 60)),
        ("ceil_hour", lambda v, m: at(v, -((-m) // 60) * 60)),
        ("floor_half", lambda v, m: at(v, (m // 30) * 30)),
        ("ceil_half", lambda v, m: at(v, -((-m) // 30) * 30)),
        ("max_edges", lambda v, m: max(at(v, m), at(v, m + sm))),
        ("min_edges", lambda v, m: min(at(v, m), at(v, m + sm))),
    ]


def infer_meters(base, versions, depots, slot_minutes):
    """Per depot, the unique way of applying a tariff that bills every
    settlement row of that depot exactly its cents."""
    name = "settlements.csv"
    _, rows = read_csv_rows(base, name)
    sessions = {d: [] for d in depots}
    for line, row in rows:
        depot = (row.get("depot") or "").strip()
        if depot not in sessions:
            continue
        sd = (row.get("settled_date") or "").strip()
        ver = None
        for v in versions:
            if v.valid_from <= sd <= v.valid_to:
                ver = v
                break
        if ver is None:
            continue
        start = parse_dt(row.get("start"), name, "start")
        end = parse_dt(row.get("end"), name, "end")
        total = int((end - start).total_seconds() // 60)
        if total <= 0 or total % slot_minutes:
            continue
        n = total // slot_minutes
        kwh = parse_int(row.get("kwh"), name, "kwh")
        cents = parse_int(row.get("cents"), name, "cents")
        mins = []
        for i in range(n):
            t = start + timedelta(minutes=slot_minutes * i)
            mins.append(t.hour * 60 + t.minute)
        sessions[depot].append((ver, mins, n, kwh, cents))

    cands = meter_candidates(slot_minutes)
    chosen = {}
    for depot in depots:
        fits = []
        for cname, fn in cands:
            ok = True
            for ver, mins, n, kwh, cents in sessions[depot]:
                try:
                    tot = sum(fn(ver, m) for m in mins)
                except Exception:
                    ok = False
                    break
                # kwh split in equal parts over n slots
                if kwh * tot != cents * n:
                    ok = False
                    break
            if ok:
                fits.append((cname, fn))
        if not fits:
            raise DataError(name, "no tariff reading bills depot %s as settled" % depot)
        chosen[depot] = fits[0]
    return chosen


# --------------------------------------------------------------------------
# disruption notice


def load_disruption(base, depots):
    name = "disruption_notice.md"
    path = need_path(base, name)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception as exc:
        raise DataError(name, "cannot be read (%s)" % exc)
    outages = []   # (depot, count, from_dt, to_dt)
    derates = []   # (from_dt, to_dt, limit)
    extras = []    # (bus_id, date_str, kwh)
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            low = line.lstrip("#").strip().lower()
            if "cabinet" in low:
                section = "cab"
            elif "derat" in low or "feeder" in low:
                section = "der"
            elif "extra" in low or "trip" in low:
                section = "extra"
            else:
                section = None
            continue
        if not line.startswith("-") and not line.startswith("*"):
            continue
        body = line[1:].strip()
        if section == "cab":
            m = re.match(
                r"^([A-Za-z][\w ]*?)\s*:\s*(\d+)\s+cabinets?\s+out of service\s+"
                r"from\s+(\S+)\s+to\s+(\S+)\s*$", body)
            if not m:
                raise DataError(name, "cannot read cabinet outage line %r" % body)
            depot = m.group(1).strip()
            if depot not in depots:
                raise DataError(name, "unknown depot %r in a cabinet outage" % depot)
            outages.append((depot, int(m.group(2)),
                            parse_dt(m.group(3), name, "outage start"),
                            parse_dt(m.group(4), name, "outage end")))
        elif section == "der":
            m = re.match(
                r"^from\s+(\S+)\s+to\s+(\S+)\s*:\s*feeder limit\s+(\d+)\s*kWh",
                body, re.I)
            if not m:
                raise DataError(name, "cannot read feeder derating line %r" % body)
            derates.append((parse_dt(m.group(1), name, "derating start"),
                            parse_dt(m.group(2), name, "derating end"),
                            int(m.group(3))))
        elif section == "extra":
            m = re.match(
                r"^(\S+)\s*:\s*extra trip on\s+(\d{4}-\d{2}-\d{2})\s*,\s*(\d+)\s*kWh",
                body, re.I)
            if not m:
                raise DataError(name, "cannot read extra trip line %r" % body)
            extras.append((m.group(1).strip(), m.group(2), int(m.group(3))))
    return outages, derates, extras


# --------------------------------------------------------------------------
# min cost flow (successive shortest paths + negative cycle canceling)


class MCMF(object):
    def __init__(self, n):
        self.n = n
        self.to = []
        self.cap = []
        self.cost = []
        self.g = [[] for _ in range(n)]

    def add(self, u, v, cap, cost):
        e = len(self.to)
        self.to.append(v); self.cap.append(cap); self.cost.append(cost)
        self.g[u].append(e)
        self.to.append(u); self.cap.append(0); self.cost.append(-cost)
        self.g[v].append(e + 1)
        return e

    def _spfa(self, s, t):
        n = self.n
        INF = None
        dist = [None] * n
        inq = [False] * n
        pre = [-1] * n
        dist[s] = 0
        from collections import deque
        q = deque([s])
        inq[s] = True
        to, cap, cost, g = self.to, self.cap, self.cost, self.g
        while q:
            u = q.popleft()
            inq[u] = False
            du = dist[u]
            for e in g[u]:
                if cap[e] <= 0:
                    continue
                v = to[e]
                nd = du + cost[e]
                if dist[v] is None or nd < dist[v]:
                    dist[v] = nd
                    pre[v] = e
                    if not inq[v]:
                        inq[v] = True
                        q.append(v)
        if dist[t] is None:
            return None
        return dist, pre

    def _dijkstra(self, s, t, h):
        n = self.n
        INF = float("inf")
        dist = [INF] * n
        pre = [-1] * n
        dist[s] = 0
        pq = [(0, s)]
        to, cap, cost, g = self.to, self.cap, self.cost, self.g
        while pq:
            d, u = heappop(pq)
            if d > dist[u]:
                continue
            for e in g[u]:
                if cap[e] <= 0:
                    continue
                v = to[e]
                nd = d + cost[e] + h[u] - h[v]
                if nd < dist[v]:
                    dist[v] = nd
                    pre[v] = e
                    heappush(pq, (nd, v))
        if dist[t] == INF:
            return None
        return dist, pre

    def run(self, s, t):
        """Minimum cost flow of the value that minimises cost."""
        res = self._spfa(s, t)
        if res is None:
            return
        dist, pre = res
        h = [0] * self.n
        for v in range(self.n):
            h[v] = dist[v] if dist[v] is not None else 0
        to, cap, cost = self.to, self.cap, self.cost
        while True:
            r = self._dijkstra(s, t, h)
            if r is None:
                break
            dist, pre = r
            dt = dist[t]
            for v in range(self.n):
                dv = dist[v]
                if dv == float("inf"):
                    dv = dt
                h[v] += dv
            if h[t] - h[s] >= 0:
                break
            # bottleneck
            d = None
            v = t
            while v != s:
                e = pre[v]
                d = cap[e] if d is None else min(d, cap[e])
                v = to[e ^ 1]
            v = t
            while v != s:
                e = pre[v]
                cap[e] -= d
                cap[e ^ 1] += d
                v = to[e ^ 1]

    def cancel_negative_cycles(self, limit=100000):
        """Cancel negative residual cycles; returns valid node potentials."""
        n = self.n
        to, cap, cost, g = self.to, self.cap, self.cost, self.g
        for _ in range(limit):
            dist = [0] * n
            pre = [-1] * n
            cyc = -1
            for it in range(n):
                upd = False
                for u in range(n):
                    du = dist[u]
                    for e in g[u]:
                        if cap[e] <= 0:
                            continue
                        v = to[e]
                        nd = du + cost[e]
                        if nd < dist[v]:
                            dist[v] = nd
                            pre[v] = e
                            upd = True
                            if it == n - 1:
                                cyc = v
                if not upd:
                    break
            if cyc < 0:
                return dist
            seen = [False] * n
            v = cyc
            while not seen[v]:
                seen[v] = True
                if pre[v] < 0:
                    return dist
                v = to[pre[v] ^ 1]
            start = v
            arcs = []
            x = start
            while True:
                e = pre[x]
                arcs.append(e)
                x = to[e ^ 1]
                if x == start:
                    break
            d = min(cap[e] for e in arcs)
            for e in arcs:
                cap[e] -= d
                cap[e ^ 1] += d
        raise RuntimeError("could not reach an optimal plan")


# --------------------------------------------------------------------------
# data loading


def load_inputs(data):
    grid = read_ini(data, "grid.ini")
    try:
        plan_date = grid.get("plan", "plan_date").strip()
        first_slot = parse_dt(grid.get("plan", "first_slot"), "grid.ini", "first_slot")
        slot_minutes = int(grid.get("plan", "slot_minutes").strip())
        nslots = int(grid.get("plan", "slots").strip())
        feeder_base = int(grid.get("feeder", "feeder_kwh_per_slot").strip())
    except DataError:
        raise
    except Exception as exc:
        raise DataError("grid.ini", "a required setting is missing (%s)" % exc)

    dep = read_json(data, "depots.json")
    try:
        cab_kwh = int(dep["cabinet_kwh_per_slot"])
        depot_names = [str(d["depot"]) for d in dep["depots"]]
        cabinets = {str(d["depot"]): int(d["cabinets"]) for d in dep["depots"]}
    except Exception as exc:
        raise DataError("depots.json", "unexpected shape (%s)" % exc)

    bt = read_json(data, "bus_types.json")
    types = {}
    try:
        for name, spec in bt.items():
            types[str(name)] = (int(spec["max_kwh_per_slot"]), int(spec["reserve_kwh"]))
    except Exception as exc:
        raise DataError("bus_types.json", "unexpected shape (%s)" % exc)

    sc = read_ini(data, "service_classes.ini")
    weights = {}
    for sec in sc.sections():
        try:
            weights[sec] = int(sc.get(sec, "weight").strip())
        except Exception as exc:
            raise DataError("service_classes.ini",
                            "class %s has no weight (%s)" % (sec, exc))

    con = read_json(data, "contracts.json")
    classes = {}
    try:
        items = con["contracts"] if isinstance(con, dict) else con
        for c in items:
            classes[str(c["contract_id"]).strip()] = str(c["class"]).strip()
    except Exception as exc:
        raise DataError("contracts.json", "unexpected shape (%s)" % exc)

    _, freg = read_csv_rows(data, "fleet_register.csv")
    register = {}
    for _line, row in freg:
        vid = (row.get("vehicle_id") or "").strip()
        if vid and vid not in register:
            register[vid] = ((row.get("type") or "").strip(),
                             (row.get("status") or "").strip())

    trips = {}
    tpath = need_path(data, "trips.jsonl")
    try:
        with open(tpath, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                rec = json.loads(raw)
                key = (str(rec["bus_id"]).strip(), str(rec["service_date"]).strip())
                trips[key] = trips.get(key, 0) + int(rec["kwh"])
    except Exception as exc:
        raise DataError("trips.jsonl", "cannot be read as JSON lines (%s)" % exc)

    versions = load_tariff(data)
    outages, derates, extras = load_disruption(data, set(depot_names))
    meters = infer_meters(data, versions, depot_names, slot_minutes)

    try:
        svc = (datetime.strptime(plan_date, "%Y-%m-%d")
               + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        raise DataError("grid.ini", "cannot read plan_date %r as a date" % plan_date)

    return dict(service_date=svc, plan_date=plan_date, first_slot=first_slot,
                slot_minutes=slot_minutes, nslots=nslots,
                feeder_base=feeder_base, cab_kwh=cab_kwh,
                depot_names=depot_names, cabinets=cabinets, types=types,
                weights=weights, classes=classes, register=register,
                trips=trips, versions=versions, outages=outages,
                derates=derates, extras=extras, meters=meters)


def build_buses(data, env):
    """Accepted roster rows for the plan date, plus rejections."""
    plan_date = env["plan_date"]
    first = env["first_slot"]
    sm = env["slot_minutes"]
    day_end = first + timedelta(minutes=sm * env["nslots"])
    register = env["register"]
    rejected = []
    buses = []
    seen = set()
    _, rows = read_csv_rows(data, "roster.csv")
    for line, row in rows:
        if (row.get("plan_date") or "").strip() != plan_date:
            continue
        bus_id = (row.get("bus_id") or "").strip()
        reason = None
        if bus_id not in register:
            reason = "unknown_vehicle"
        elif register[bus_id][1] != "active":
            reason = "retired_vehicle"
        elif bus_id in seen:
            reason = "duplicate_roster_row"
        else:
            arrive = parse_dt(row.get("arrive"), "roster.csv", "arrive")
            depart = parse_dt(row.get("depart"), "roster.csv", "depart")
            if not (arrive < depart) or arrive < first or depart > day_end:
                reason = "bad_window"
        if reason is not None:
            rejected.append({"file": "roster.csv", "line": line, "reason": reason})
            continue
        seen.add(bus_id)
        btype = register[bus_id][0]
        if btype not in env["types"]:
            raise DataError("bus_types.json", "no entry for type %r" % btype)
        max_slot, reserve = env["types"][btype]
        contract = (row.get("contract_id") or "").strip()
        cls = env["classes"].get(contract, "commercial")
        if cls not in env["weights"]:
            raise DataError("service_classes.ini", "no weight for class %r" % cls)
        svc_date = env["service_date"]
        soc = parse_int(row.get("soc_arrival_kwh"), "roster.csv", "soc_arrival_kwh")
        need = env["trips"].get((bus_id, svc_date), 0)
        for xb, xd, xk in env["extras"]:
            if xb == bus_id and xd == svc_date:
                need += xk
        need = need + reserve - soc
        if need < 0:
            need = 0
        a_off = int((arrive - first).total_seconds() // 60)
        d_off = int((depart - first).total_seconds() // 60)
        s0 = -((-a_off) // sm)          # first slot starting at or after arrive
        s1 = -((-d_off) // sm)          # first slot starting at or after depart
        if s1 > env["nslots"]:
            s1 = env["nslots"]
        if s0 < 0:
            s0 = 0
        buses.append(dict(bus_id=bus_id, depot=(row.get("depot") or "").strip(),
                          cls=cls, weight=env["weights"][cls], need=need,
                          max_slot=max_slot, s0=s0, s1=s1))
    buses.sort(key=lambda b: b["bus_id"])
    return buses, rejected


def load_published(data, env, buses):
    index = {b["bus_id"]: i for i, b in enumerate(buses)}
    pub = [dict() for _ in buses]
    rejected = []
    plan_date = env["plan_date"]
    first = env["first_slot"]
    sm = env["slot_minutes"]
    _, rows = read_csv_rows(data, "published_plan.csv")
    for line, row in rows:
        if (row.get("plan_date") or "").strip() != plan_date:
            continue
        bus_id = (row.get("bus_id") or "").strip()
        slot = parse_dt(row.get("slot_start"), "published_plan.csv", "slot_start")
        kwh = parse_int(row.get("kwh"), "published_plan.csv", "kwh")
        off = int((slot - first).total_seconds() // 60)
        i = index.get(bus_id)
        ok = (i is not None and off >= 0 and off % sm == 0
              and buses[i]["s0"] <= off // sm < buses[i]["s1"])
        if not ok:
            rejected.append({"file": "published_plan.csv", "line": line,
                             "reason": "published_row_outside_window"})
            continue
        s = off // sm
        pub[i][s] = pub[i].get(s, 0) + kwh
    return pub, rejected


# --------------------------------------------------------------------------
# capacities and prices


def slot_times(env):
    first = env["first_slot"]
    sm = env["slot_minutes"]
    return [first + timedelta(minutes=sm * s) for s in range(env["nslots"])]


def depot_slot_caps(env, times):
    caps = {}
    for d in env["depot_names"]:
        row = []
        for t in times:
            out = 0
            for od, cnt, a, b in env["outages"]:
                if od == d and a <= t < b:
                    out += cnt
            n = env["cabinets"][d] - out
            if n < 0:
                n = 0
            row.append(n * env["cab_kwh"])
        caps[d] = row
    return caps


def feeder_caps(env, times):
    out = []
    for t in times:
        lim = env["feeder_base"]
        for a, b, val in env["derates"]:
            if a <= t < b:
                lim = val
        out.append(lim)
    return out


def depot_prices(env, times):
    ver = version_in_force(env["versions"], env["plan_date"], "tariff.xml")
    prices = {}
    for d in env["depot_names"]:
        _name, fn = env["meters"][d]
        prices[d] = [int(fn(ver, t.hour * 60 + t.minute)) for t in times]
    return prices


# --------------------------------------------------------------------------
# the plan


def solve(env, buses, pub, times):
    ns = env["nslots"]
    nb = len(buses)
    dcaps = depot_slot_caps(env, times)
    fcaps = feeder_caps(env, times)
    prices = depot_prices(env, times)
    dindex = {d: i for i, d in enumerate(env["depot_names"])}
    nd = len(env["depot_names"])

    S, T = 0, 1
    bus0 = 2
    ds0 = bus0 + nb
    sl0 = ds0 + nd * ns
    n_nodes = sl0 + ns
    net = MCMF(n_nodes)

    INF = 1 << 50
    for i, b in enumerate(buses):
        net.add(S, bus0 + i, b["need"], -W_UNMET * b["weight"])
    pos = {}
    for i, b in enumerate(buses):
        d = b["depot"]
        if d not in dindex:
            raise DataError("roster.csv", "unknown depot %r" % d)
        pr = prices[d]
        for s in range(b["s0"], b["s1"]):
            node = ds0 + dindex[d] * ns + s
            cap = b["max_slot"]
            p = pub[i].get(s, 0)
            c1 = p if p < cap else cap
            arcs = []
            if c1 > 0:
                arcs.append(net.add(bus0 + i, node, c1, W_COST * pr[s] - 1))
            if cap - c1 > 0:
                arcs.append(net.add(bus0 + i, node, cap - c1, W_COST * pr[s]))
            if arcs:
                pos[(s, i)] = arcs
    for d in env["depot_names"]:
        for s in range(ns):
            net.add(ds0 + dindex[d] * ns + s, sl0 + s, dcaps[d][s], 0)
    sink_arcs = []
    for s in range(ns):
        sink_arcs.append(net.add(sl0 + s, T, fcaps[s], 0))

    net.run(S, T)

    # close the circulation so that potentials cover every residual arc
    total = sum(net.cap[e ^ 1] for e in sink_arcs)
    back = net.add(T, S, INF, 0)
    net.cap[back ^ 1] = total
    potential = net.cancel_negative_cycles()

    to, cap, cost, g = net.to, net.cap, net.cost, net.g
    rc = [cost[e] + potential[to[e ^ 1]] - potential[to[e]]
          for e in range(len(to))]
    blocked = bytearray(len(to))

    from collections import deque

    def push_max(a):
        """Raise the flow on arc a as far as the optimal face allows."""
        src, dst = to[a], to[a ^ 1]
        while cap[a] > 0 and rc[a] == 0:
            pre = [-1] * n_nodes
            pre[src] = a
            q = deque([src])
            found = False
            while q and not found:
                u = q.popleft()
                for e in g[u]:
                    if cap[e] <= 0 or rc[e] != 0 or blocked[e]:
                        continue
                    v = to[e]
                    if pre[v] >= 0:
                        continue
                    pre[v] = e
                    if v == dst:
                        found = True
                        break
                    q.append(v)
            if not found:
                return
            path = []
            v = dst
            while v != src:
                e = pre[v]
                path.append(e)
                v = to[e ^ 1]
            d = cap[a]
            for e in path:
                if cap[e] < d:
                    d = cap[e]
            cap[a] -= d
            cap[a ^ 1] += d
            for e in path:
                cap[e] -= d
                cap[e ^ 1] += d

    # lexicographically greatest plan, slot order then bus_id order
    for s in range(ns):
        for i in range(nb):
            for a in pos.get((s, i), ()):
                if cap[a] > 0 and rc[a] == 0:
                    push_max(a)
                blocked[a] = 1
                blocked[a ^ 1] = 1

    plan = [dict() for _ in buses]
    for (s, i), arcs in pos.items():
        v = 0
        for a in arcs:
            v += cap[a ^ 1]
        if v:
            plan[i][s] = v
    return plan, prices


# --------------------------------------------------------------------------
# reports


def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path


def build_reports(env, buses, pub, plan, prices, rejected, times, out_dir):
    ns = env["nslots"]
    labels = [t.strftime("%Y-%m-%dT%H:%M") for t in times]
    plan_date = env["plan_date"]

    delivered = []
    unmet = []
    bus_cost = []
    changed = []
    for i, b in enumerate(buses):
        got = sum(plan[i].values())
        delivered.append(got)
        unmet.append(b["need"] - got)
        pr = prices[b["depot"]]
        bus_cost.append(sum(k * pr[s] for s, k in plan[i].items()))
        ch = False
        for s in set(plan[i]) | set(pub[i]):
            if plan[i].get(s, 0) != pub[i].get(s, 0):
                ch = True
                break
        changed.append(ch)

    feeder = [0] * ns
    dep_slot = {d: [0] * ns for d in env["depot_names"]}
    cls_slot = {c: [0] * ns for c in ("commercial", "public")}
    for i, b in enumerate(buses):
        row = dep_slot.get(b["depot"])
        crow = cls_slot.setdefault(b["cls"], [0] * ns)
        for s, k in plan[i].items():
            row[s] += k
            crow[s] += k
            feeder[s] += k

    moved = 0
    for i in range(len(buses)):
        for s, k in pub[i].items():
            d = k - plan[i].get(s, 0)
            if d > 0:
                moved += d

    audit = []
    for i, b in enumerate(buses):
        if unmet[i] == 0:
            reason = None
        elif b["need"] > b["max_slot"] * (b["s1"] - b["s0"]):
            reason = "window"
        else:
            reason = "supply"
        charges = [{"slot": labels[s], "kwh": plan[i][s]}
                   for s in sorted(plan[i]) if plan[i][s] > 0]
        audit.append({
            "bus_id": b["bus_id"],
            "depot": b["depot"],
            "class": b["cls"],
            "need_kwh": b["need"],
            "delivered_kwh": delivered[i],
            "unmet_kwh": unmet[i],
            "unmet_reason": reason,
            "changed": changed[i],
            "charges": charges,
        })
    write_json(out_dir, "policy_audit.json",
               {"plan_date": plan_date, "buses": audit})

    for d in env["depot_names"]:
        idx = [i for i, b in enumerate(buses) if b["depot"] == d]
        write_json(out_dir, "region_%s.json" % d, {
            "depot": d,
            "buses": len(idx),
            "energy_kwh": sum(delivered[i] for i in idx),
            "cost_cents": sum(bus_cost[i] for i in idx),
            "unmet_kwh": sum(unmet[i] for i in idx),
            "slots": [{"slot": labels[s], "kwh": dep_slot[d][s],
                       "feeder_kwh": feeder[s]} for s in range(ns)],
        })

    for cls in ("commercial", "public"):
        idx = [i for i, b in enumerate(buses) if b["cls"] == cls]
        row = cls_slot.get(cls, [0] * ns)
        write_json(out_dir, "segment_%s.json" % cls, {
            "class": cls,
            "buses": len(idx),
            "energy_kwh": sum(delivered[i] for i in idx),
            "cost_cents": sum(bus_cost[i] for i in idx),
            "unmet_kwh": sum(unmet[i] for i in idx),
            "slots": [{"slot": labels[s], "kwh": row[s],
                       "feeder_kwh": feeder[s]} for s in range(ns)],
        })

    summary = {
        "plan_date": plan_date,
        "weighted_unmet_kwh": sum(b["weight"] * unmet[i]
                                  for i, b in enumerate(buses)),
        "energy_cost_cents": sum(bus_cost),
        "moved_kwh": moved,
        "feeder_peak_kwh": max(feeder) if feeder else 0,
        "feeder_kwh_by_slot": [{"slot": labels[s], "kwh": feeder[s]}
                               for s in range(ns)],
        "buses_planned": len(buses),
        "buses_short": sum(1 for u in unmet if u > 0),
        "buses_changed": sum(1 for c in changed if c),
        "records_rejected": len(rejected),
    }
    write_json(out_dir, "summary.json", summary)

    rej = sorted(rejected, key=lambda r: (r["file"], r["line"]))
    write_json(out_dir, "data_quality.json",
               {"plan_date": plan_date, "rejected": rej})
    return summary, rej


# --------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(description="derive the overnight charging plan")
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--out", default="/app/out")
    args = ap.parse_args(argv)

    data = args.data
    out_dir = args.out
    if not os.path.isdir(data):
        sys.stderr.write("error: data folder %s is missing\n" % data)
        return 2
    try:
        os.makedirs(out_dir, exist_ok=True)
        env = load_inputs(data)
        buses, rej_roster = build_buses(data, env)
        pub, rej_pub = load_published(data, env, buses)
        times = slot_times(env)
        plan, prices = solve(env, buses, pub, times)
        summary, rej = build_reports(env, buses, pub, plan, prices,
                                     rej_roster + rej_pub, times, out_dir)
    except DataError as exc:
        sys.stderr.write("error: %s: %s\n" % (exc.filename, exc.detail))
        return 1
    print("plan_date %s" % summary["plan_date"])
    for key in ("weighted_unmet_kwh", "energy_cost_cents", "moved_kwh",
                "feeder_peak_kwh", "buses_planned", "buses_short",
                "buses_changed", "records_rejected"):
        print("%s %s" % (key, summary[key]))
    for r in rej:
        print("rejected %s line %d %s" % (r["file"], r["line"], r["reason"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
