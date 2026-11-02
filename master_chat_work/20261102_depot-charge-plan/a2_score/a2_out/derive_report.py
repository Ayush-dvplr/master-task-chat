#!/usr/bin/env python3
"""Build the overnight depot charging day plan and write the planning reports.

Usage: derive_report.py [--data DIR] [--out DIR]
"""

import argparse
import configparser
import csv
import heapq
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timedelta


class DataError(Exception):
    pass


SLOT_FMT = "%Y-%m-%dT%H:%M"


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise DataError("%s: cannot be read (%s)" % (path, exc))


def read_rows(path):
    """Return (header, [(line_number, row_list)]) of a csv file."""
    text = read_text(path)
    try:
        rows = list(csv.reader(text.splitlines()))
    except csv.Error as exc:
        raise DataError("%s: cannot be parsed as CSV (%s)" % (path, exc))
    if not rows:
        raise DataError("%s: file is empty" % path)
    header = [c.strip() for c in rows[0]]
    out = []
    for i, row in enumerate(rows[1:], start=2):
        if not row or all(c.strip() == "" for c in row):
            continue
        out.append((i, row))
    return header, out


def row_dict(path, header, line, row):
    if len(row) != len(header):
        raise DataError("%s: line %d has %d fields, expected %d"
                        % (path, line, len(row), len(header)))
    return dict(zip(header, row))


def to_int(path, line, field, value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise DataError("%s: line %d has a bad %s value %r" % (path, line, field, value))


def parse_dt(path, line, field, value):
    try:
        return datetime.strptime(str(value).strip(), SLOT_FMT)
    except (TypeError, ValueError):
        raise DataError("%s: line %d has a bad %s value %r" % (path, line, field, value))


# ----------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------

def load_ini(path):
    cp = configparser.ConfigParser()
    try:
        cp.read_string(read_text(path))
    except configparser.Error as exc:
        raise DataError("%s: cannot be parsed (%s)" % (path, exc))
    return cp


def load_plan(data_dir):
    path = os.path.join(data_dir, "grid.ini")
    cp = load_ini(path)
    try:
        plan_date = cp.get("plan", "plan_date").strip()
        first_slot = cp.get("plan", "first_slot").strip()
        slot_minutes = int(cp.get("plan", "slot_minutes"))
        nslots = int(cp.get("plan", "slots"))
        feeder = int(cp.get("feeder", "feeder_kwh_per_slot"))
    except (configparser.Error, ValueError) as exc:
        raise DataError("%s: missing or bad plan settings (%s)" % (path, exc))
    try:
        datetime.strptime(plan_date, "%Y-%m-%d")
    except ValueError:
        raise DataError("%s: bad plan_date %r" % (path, plan_date))
    try:
        first = datetime.strptime(first_slot, SLOT_FMT)
    except ValueError:
        raise DataError("%s: bad first_slot %r" % (path, first_slot))
    if slot_minutes <= 0 or nslots <= 0 or 1440 % slot_minutes != 0:
        raise DataError("%s: bad slot_minutes or slots" % path)
    return plan_date, first, slot_minutes, nslots, feeder


def load_depots(data_dir):
    path = os.path.join(data_dir, "depots.json")
    try:
        obj = json.loads(read_text(path))
        cab_kwh = int(obj["cabinet_kwh_per_slot"])
        depots = [(str(d["depot"]), int(d["cabinets"])) for d in obj["depots"]]
    except (ValueError, KeyError, TypeError) as exc:
        raise DataError("%s: cannot be read as described (%s)" % (path, exc))
    if not depots:
        raise DataError("%s: no depots" % path)
    return cab_kwh, depots


def load_bus_types(data_dir):
    path = os.path.join(data_dir, "bus_types.json")
    try:
        obj = json.loads(read_text(path))
        types = {}
        for name, spec in obj.items():
            types[str(name)] = (int(spec["max_kwh_per_slot"]), int(spec["reserve_kwh"]))
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise DataError("%s: cannot be read as described (%s)" % (path, exc))
    if not types:
        raise DataError("%s: no bus types" % path)
    return types


def load_classes(data_dir):
    path = os.path.join(data_dir, "service_classes.ini")
    cp = load_ini(path)
    weights = {}
    for sec in cp.sections():
        try:
            weights[sec] = int(cp.get(sec, "weight"))
        except (configparser.Error, ValueError) as exc:
            raise DataError("%s: bad weight for %s (%s)" % (path, sec, exc))
    if not weights:
        raise DataError("%s: no service classes" % path)
    return weights


def load_contracts(data_dir):
    path = os.path.join(data_dir, "contracts.json")
    try:
        obj = json.loads(read_text(path))
        out = {}
        for c in obj["contracts"]:
            out[str(c["contract_id"])] = str(c["class"])
    except (ValueError, KeyError, TypeError) as exc:
        raise DataError("%s: cannot be read as described (%s)" % (path, exc))
    return out


def load_fleet(data_dir):
    path = os.path.join(data_dir, "fleet_register.csv")
    header, rows = read_rows(path)
    for need in ("vehicle_id", "type", "status"):
        if need not in header:
            raise DataError("%s: missing column %s" % (path, need))
    fleet = {}
    for line, row in rows:
        d = row_dict(path, header, line, row)
        fleet[d["vehicle_id"].strip()] = d
    return fleet


def load_trips(data_dir, want_date):
    path = os.path.join(data_dir, "trips.jsonl")
    text = read_text(path)
    need = {}
    for i, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
            bus = str(obj["bus_id"])
            date = str(obj["service_date"])
            kwh = int(obj["kwh"])
        except (ValueError, KeyError, TypeError) as exc:
            raise DataError("%s: line %d cannot be read as described (%s)"
                            % (path, i, exc))
        if date == want_date:
            need[bus] = need.get(bus, 0) + kwh
    return need


def load_tariff(data_dir, slot_minutes):
    path = os.path.join(data_dir, "tariff.xml")
    try:
        root = ET.fromstring(read_text(path))
    except ET.ParseError as exc:
        raise DataError("%s: cannot be parsed as XML (%s)" % (path, exc))
    per_day = 1440 // slot_minutes
    versions = []
    for ver in root.findall(".//version"):
        vf = (ver.get("valid_from") or "").strip()
        vt = (ver.get("valid_to") or "").strip()
        if not vf or not vt:
            raise DataError("%s: a version lacks valid_from or valid_to" % path)
        prices = [None] * per_day
        bands = ver.findall("band")
        if not bands:
            raise DataError("%s: version %s has no bands" % (path, vf))
        for band in bands:
            try:
                f = band.get("from").strip()
                t = band.get("to").strip()
                cents = int(band.get("cents_per_kwh"))
                fm = int(f[:2]) * 60 + int(f[3:5])
                tm = int(t[:2]) * 60 + int(t[3:5])
            except (AttributeError, ValueError, TypeError):
                raise DataError("%s: bad band in version %s" % (path, vf))
            if fm % slot_minutes or tm % slot_minutes:
                raise DataError("%s: band not aligned to slots in version %s" % (path, vf))
            fi = fm // slot_minutes
            ti = tm // slot_minutes
            steps = (ti - fi) % per_day
            if steps == 0:
                steps = per_day
            for j in range(steps):
                prices[(fi + j) % per_day] = cents
        if any(p is None for p in prices):
            raise DataError("%s: version %s does not cover the whole day" % (path, vf))
        versions.append((vf, vt, prices))
    if not versions:
        raise DataError("%s: no tariff versions" % path)
    return versions


def version_for(versions, date, path):
    for vf, vt, prices in versions:
        if vf <= date <= vt:
            return prices
    raise DataError("%s: no tariff version in force on %s" % (path, date))


def load_settlement_offsets(data_dir, versions, slot_minutes, depot_names):
    path = os.path.join(data_dir, "settlements.csv")
    tpath = os.path.join(data_dir, "tariff.xml")
    header, rows = read_rows(path)
    for need in ("settled_date", "depot", "start", "end", "kwh", "cents"):
        if need not in header:
            raise DataError("%s: missing column %s" % (path, need))
    per_day = 1440 // slot_minutes
    cands = dict((d, list(range(per_day))) for d in depot_names)
    for line, row in rows:
        d = row_dict(path, header, line, row)
        depot = d["depot"].strip()
        if depot not in cands:
            continue
        start = parse_dt(path, line, "start", d["start"])
        end = parse_dt(path, line, "end", d["end"])
        kwh = to_int(path, line, "kwh", d["kwh"])
        cents = to_int(path, line, "cents", d["cents"])
        span = int((end - start).total_seconds() // 60)
        if span <= 0 or span % slot_minutes != 0:
            raise DataError("%s: line %d has a bad session span" % (path, line))
        n = span // slot_minutes
        prices = version_for(versions, d["settled_date"].strip(), tpath)
        idxs = []
        for i in range(n):
            t = start + timedelta(minutes=slot_minutes * i)
            idxs.append((t.hour * 60 + t.minute) // slot_minutes)
        keep = []
        for k in cands[depot]:
            s = 0
            for ix in idxs:
                s += prices[(ix + k) % per_day]
            if kwh * s == cents * n:
                keep.append(k)
        cands[depot] = keep
        if not keep:
            raise DataError("%s: line %d fits no meter clock offset for depot %s"
                            % (path, line, depot))
    offsets = {}
    for depot, keep in cands.items():
        if len(keep) != 1:
            raise DataError("%s: depot %s does not fit exactly one meter clock offset"
                            % (path, depot))
        offsets[depot] = keep[0]
    return offsets


def load_disruption(data_dir):
    path = os.path.join(data_dir, "disruption_notice.md")
    text = read_text(path)
    outages = []   # (depot, cabinets, from, to)
    derates = []   # (from, to, limit)
    extras = []    # (bus_id, date, kwh)
    re_out = re.compile(
        r"^[-*]\s*(?P<depot>[A-Za-z][\w ]*?)\s*:\s*(?P<n>\d+)\s*cabinets?\b.*?"
        r"\bfrom\s+(?P<f>\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s+to\s+"
        r"(?P<t>\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", re.I)
    re_der = re.compile(
        r"^[-*]\s*from\s+(?P<f>\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s+to\s+"
        r"(?P<t>\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s*:?\s*.*?feeder\s+limit\s+(?P<v>\d+)",
        re.I)
    re_ext = re.compile(
        r"^[-*]\s*(?P<bus>\S+?)\s*:\s*extra trip.*?\b(?P<date>\d{4}-\d{2}-\d{2})\b"
        r"\D*?(?P<kwh>\d+)\s*kwh", re.I)
    for raw in text.splitlines():
        line = raw.strip()
        if not (line.startswith("-") or line.startswith("*")):
            continue
        m = re_der.match(line)
        if m:
            derates.append((datetime.strptime(m.group("f"), SLOT_FMT),
                            datetime.strptime(m.group("t"), SLOT_FMT),
                            int(m.group("v"))))
            continue
        m = re_out.match(line)
        if m:
            outages.append((m.group("depot").strip(), int(m.group("n")),
                            datetime.strptime(m.group("f"), SLOT_FMT),
                            datetime.strptime(m.group("t"), SLOT_FMT)))
            continue
        m = re_ext.match(line)
        if m:
            extras.append((m.group("bus").strip(), m.group("date"), int(m.group("kwh"))))
    return outages, derates, extras


# ----------------------------------------------------------------------------
# min cost circulation
# ----------------------------------------------------------------------------

class Network:
    def __init__(self, n):
        self.n = n
        self.frm = []
        self.to = []
        self.cap = []
        self.cost = []
        self.adj = [[] for _ in range(n)]

    def add(self, u, v, cap, cost):
        e = len(self.to)
        self.frm.append(u)
        self.to.append(v)
        self.cap.append(cap)
        self.cost.append(cost)
        self.adj[u].append(e)
        self.frm.append(v)
        self.to.append(u)
        self.cap.append(0)
        self.cost.append(-cost)
        self.adj[v].append(e + 1)
        return e

    def flow(self, e):
        return self.cap[e ^ 1]


def dag_potentials(net, order, src):
    pi = [None] * net.n
    pi[src] = 0
    for u in order:
        if pi[u] is None:
            continue
        for e in net.adj[u]:
            if net.cap[e] <= 0:
                continue
            v = net.to[e]
            nd = pi[u] + net.cost[e]
            if pi[v] is None or nd < pi[v]:
                pi[v] = nd
    return [0 if p is None else p for p in pi]


def min_cost_flow(net, src, snk, pi):
    """Primal dual method: shortest path phases, each pushing a blocking flow.

    Stops when no negative cost path from src to snk is left, so the result is
    an optimal circulation once src and snk are joined by a zero cost arc.
    """
    n = net.n
    cap = net.cap
    cost = net.cost
    to = net.to
    frm = net.frm
    adj = net.adj
    total = 0
    while True:
        dist = [None] * n
        done = bytearray(n)
        dist[src] = 0
        pq = [(0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if done[u]:
                continue
            done[u] = 1
            pu = pi[u]
            for e in adj[u]:
                if cap[e] <= 0:
                    continue
                v = to[e]
                if done[v]:
                    continue
                nd = d + cost[e] + pu - pi[v]
                if dist[v] is None or nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        if dist[snk] is None or dist[snk] + pi[snk] - pi[src] >= 0:
            break
        for v in range(n):
            if dist[v] is not None:
                pi[v] += dist[v]
        adm = bytearray(len(to))
        for e in range(len(to)):
            if cap[e] > 0 and cost[e] + pi[frm[e]] - pi[to[e]] == 0:
                adm[e] = 1
        level = [-1] * n
        level[src] = 0
        q = deque([src])
        while q:
            u = q.popleft()
            lu = level[u] + 1
            for e in adj[u]:
                if adm[e] and level[to[e]] < 0:
                    level[to[e]] = lu
                    q.append(to[e])
        if level[snk] < 0:
            break
        it = [0] * n
        path = []
        u = src
        while True:
            if u == snk:
                f = min(cap[e] for e in path)
                for e in path:
                    cap[e] -= f
                    cap[e ^ 1] += f
                    if cap[e] == 0:
                        adm[e] = 0
                total += f
                k = 0
                while adm[path[k]]:
                    k += 1
                del path[k:]
                u = src if k == 0 else to[path[k - 1]]
                continue
            moved = False
            adju = adj[u]
            lu = level[u] + 1
            while it[u] < len(adju):
                e = adju[it[u]]
                v = to[e]
                if adm[e] and level[v] == lu:
                    path.append(e)
                    u = v
                    moved = True
                    break
                it[u] += 1
            if moved:
                continue
            if u == src:
                break
            level[u] = -2
            e = path.pop()
            u = frm[e]
            it[u] += 1
    return total


def circulation_potentials(net, pi, src, snk):
    """Potentials certifying the optimal circulation.

    The successive shortest path potentials are valid for every residual arc
    but the closing arc from the sink back to the source; raising the
    potential of the nodes the source can no longer reach repairs that arc.
    """
    n = net.n
    seen = bytearray(n)
    seen[src] = 1
    stack = [src]
    while stack:
        u = stack.pop()
        for e in net.adj[u]:
            if net.cap[e] > 0:
                v = net.to[e]
                if not seen[v]:
                    seen[v] = 1
                    stack.append(v)
    if seen[snk]:
        return None
    shift = -pi[snk]
    if shift < 0:
        return None
    out = list(pi)
    for v in range(n):
        if not seen[v]:
            out[v] += shift
    return out


def potentials_are_valid(net, pot):
    for e in range(len(net.to)):
        if net.cap[e] > 0 and net.cost[e] + pot[net.frm[e]] - pot[net.to[e]] < 0:
            return False
    return True


def johnson_potentials(net):
    """Node potentials making every residual arc have a non-negative reduced cost."""
    n = net.n
    dist = [0] * n
    inq = bytearray(n)
    q = deque(range(n))
    for u in range(n):
        inq[u] = 1
    guard = 0
    limit = (n + 1) * (len(net.to) + 1) + 1000
    while q:
        u = q.popleft()
        inq[u] = 0
        du = dist[u]
        for e in net.adj[u]:
            if net.cap[e] <= 0:
                continue
            v = net.to[e]
            nd = du + net.cost[e]
            if nd < dist[v]:
                dist[v] = nd
                if not inq[v]:
                    inq[v] = 1
                    q.append(v)
        guard += 1
        if guard > limit:
            raise DataError("internal: the residual network has a negative cycle")
    return dist


# ----------------------------------------------------------------------------
# the day plan
# ----------------------------------------------------------------------------

def build(data_dir):
    plan_date, first, slot_minutes, nslots, feeder_base = load_plan(data_dir)
    end_dt = first + timedelta(minutes=slot_minutes * nslots)
    slot_dts = [first + timedelta(minutes=slot_minutes * i) for i in range(nslots)]
    slot_names = [dt.strftime(SLOT_FMT) for dt in slot_dts]
    slot_index = dict((name, i) for i, name in enumerate(slot_names))

    cab_kwh, depot_list = load_depots(data_dir)
    depot_names = [d for d, _ in depot_list]
    depot_cabinets = dict(depot_list)
    bus_types = load_bus_types(data_dir)
    weights = load_classes(data_dir)
    contracts = load_contracts(data_dir)
    fleet = load_fleet(data_dir)
    next_date = (datetime.strptime(plan_date, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")
    trip_need = load_trips(data_dir, next_date)
    versions = load_tariff(data_dir, slot_minutes)
    offsets = load_settlement_offsets(data_dir, versions, slot_minutes, depot_names)
    outages, derates, extras = load_disruption(data_dir)

    extra_need = {}
    for bus, date, kwh in extras:
        if date == next_date:
            extra_need[bus] = extra_need.get(bus, 0) + kwh

    rejected = []

    # ---- buses on the plan
    rpath = os.path.join(data_dir, "roster.csv")
    header, rows = read_rows(rpath)
    for need in ("plan_date", "bus_id", "depot", "arrive", "depart",
                 "soc_arrival_kwh", "contract_id"):
        if need not in header:
            raise DataError("%s: missing column %s" % (rpath, need))
    buses = []
    accepted_ids = set()
    for line, row in rows:
        d = row_dict(rpath, header, line, row)
        if d["plan_date"].strip() != plan_date:
            continue
        bus_id = d["bus_id"].strip()
        reg = fleet.get(bus_id)
        reason = None
        arrive = depart = None
        if reg is None:
            reason = "unknown_vehicle"
        elif reg["status"].strip() != "active":
            reason = "retired_vehicle"
        elif bus_id in accepted_ids:
            reason = "duplicate_roster_row"
        else:
            arrive = parse_dt(rpath, line, "arrive", d["arrive"])
            depart = parse_dt(rpath, line, "depart", d["depart"])
            if arrive >= depart or arrive < first or depart > end_dt:
                reason = "bad_window"
        if reason is not None:
            rejected.append(("roster.csv", line, reason))
            continue
        accepted_ids.add(bus_id)
        btype = reg["type"].strip()
        if btype not in bus_types:
            raise DataError("%s: line %d has unknown bus type %r" % (rpath, line, btype))
        max_kwh, reserve = bus_types[btype]
        soc = to_int(rpath, line, "soc_arrival_kwh", d["soc_arrival_kwh"])
        depot = d["depot"].strip()
        if depot not in depot_cabinets:
            raise DataError("%s: line %d has unknown depot %r" % (rpath, line, depot))
        contract = d["contract_id"].strip()
        cls = contracts.get(contract, "commercial") if contract else "commercial"
        if cls not in weights:
            raise DataError("%s: service class %r has no weight" % (rpath, cls))
        need_kwh = trip_need.get(bus_id, 0) + extra_need.get(bus_id, 0) + reserve - soc
        if need_kwh < 0:
            need_kwh = 0
        lo = 0
        while lo < nslots and slot_dts[lo] < arrive:
            lo += 1
        hi = lo
        while hi < nslots and slot_dts[hi] < depart:
            hi += 1
        buses.append({
            "bus_id": bus_id,
            "depot": depot,
            "class": cls,
            "weight": weights[cls],
            "max_kwh": max_kwh,
            "need": need_kwh,
            "lo": lo,
            "hi": hi,
        })
    buses.sort(key=lambda b: b["bus_id"])
    bus_index = dict((b["bus_id"], i) for i, b in enumerate(buses))
    nb = len(buses)

    # ---- published plan
    ppath = os.path.join(data_dir, "published_plan.csv")
    header, rows = read_rows(ppath)
    for need in ("plan_date", "bus_id", "slot_start", "kwh"):
        if need not in header:
            raise DataError("%s: missing column %s" % (ppath, need))
    published = {}
    for line, row in rows:
        d = row_dict(ppath, header, line, row)
        if d["plan_date"].strip() != plan_date:
            continue
        bi = bus_index.get(d["bus_id"].strip())
        if bi is None:
            continue
        si = slot_index.get(d["slot_start"].strip())
        kwh = to_int(ppath, line, "kwh", d["kwh"])
        b = buses[bi]
        if si is None or si < b["lo"] or si >= b["hi"]:
            rejected.append(("published_plan.csv", line, "published_row_outside_window"))
            continue
        published[(bi, si)] = published.get((bi, si), 0) + kwh

    # ---- limits per slot
    cabinet_cap = {}
    for depot in depot_names:
        for si in range(nslots):
            cabs = depot_cabinets[depot]
            t = slot_dts[si]
            for odep, ocount, ofrom, oto in outages:
                if odep == depot and ofrom <= t < oto:
                    cabs -= ocount
            cabinet_cap[(depot, si)] = max(cabs, 0) * cab_kwh
    feeder_cap = []
    for si in range(nslots):
        limit = feeder_base
        t = slot_dts[si]
        for dfrom, dto, val in derates:
            if dfrom <= t < dto:
                limit = val
        feeder_cap.append(limit)

    # ---- prices of the plan day
    day_prices = version_for(versions, plan_date, os.path.join(data_dir, "tariff.xml"))
    per_day = 1440 // slot_minutes
    price = {}
    for depot in depot_names:
        k = offsets[depot]
        for si in range(nslots):
            t = slot_dts[si]
            tod = (t.hour * 60 + t.minute) // slot_minutes
            price[(depot, si)] = day_prices[(tod + k) % per_day]

    # ---- lexicographic objective weights
    total_pub = sum(published.values())
    max_price = max(day_prices)
    cost_max = sum(b["need"] for b in buses) * max(max_price, 1) + 1
    C = 1
    B = total_pub + 2
    A = B * (cost_max + 1) + 1

    # ---- network
    ndepots = len(depot_names)
    depot_no = dict((d, i) for i, d in enumerate(depot_names))
    SRC = 0
    SNK = 1
    bus_node = [2 + i for i in range(nb)]
    ds_base = 2 + nb
    slot_base = ds_base + ndepots * nslots
    n_nodes = slot_base + nslots

    net = Network(n_nodes)
    for i, b in enumerate(buses):
        net.add(SRC, bus_node[i], b["need"], -A * b["weight"])
    pos_arcs = {}
    for i, b in enumerate(buses):
        depot = b["depot"]
        dn = depot_no[depot]
        mk = b["max_kwh"]
        for si in range(b["lo"], b["hi"]):
            dsn = ds_base + dn * nslots + si
            unit = B * price[(depot, si)]
            p = max(0, min(published.get((i, si), 0), mk))
            arcs = []
            if p > 0:
                arcs.append(net.add(bus_node[i], dsn, p, unit - C))
            if mk - p > 0:
                arcs.append(net.add(bus_node[i], dsn, mk - p, unit))
            if arcs:
                pos_arcs[(si, i)] = arcs
    for depot in depot_names:
        dn = depot_no[depot]
        for si in range(nslots):
            cap = cabinet_cap[(depot, si)]
            if cap > 0:
                net.add(ds_base + dn * nslots + si, slot_base + si, cap, 0)
    for si in range(nslots):
        if feeder_cap[si] > 0:
            net.add(slot_base + si, SNK, feeder_cap[si], 0)

    order = ([SRC] + bus_node
             + [ds_base + d * nslots + s for d in range(ndepots) for s in range(nslots)]
             + [slot_base + s for s in range(nslots)] + [SNK])
    pi = dag_potentials(net, order, SRC)
    flow_total = min_cost_flow(net, SRC, SNK, pi)

    pot = circulation_potentials(net, pi, SRC, SNK)

    # close the circulation: every other optimal plan differs by residual cycles
    big = flow_total + sum(b["need"] for b in buses) + 1
    e_ts = net.add(SNK, SRC, big, 0)
    net.cap[e_ts] -= flow_total
    net.cap[e_ts ^ 1] += flow_total

    if pot is None or not potentials_are_valid(net, pot):
        pot = johnson_potentials(net)
        if not potentials_are_valid(net, pot):
            raise DataError("internal: no optimal plan certificate")
    nedges = len(net.to)
    cap = net.cap
    frm = net.frm
    to = net.to
    rc = [net.cost[e] + pot[frm[e]] - pot[to[e]] for e in range(nedges)]
    adj0 = [[] for _ in range(n_nodes)]
    for e in range(nedges):
        if rc[e] == 0:
            adj0[frm[e]].append(e)
    locked = bytearray(nedges // 2)

    # ---- tie break: greatest kWh in slot order, then bus id order
    for si in range(nslots):
        for bi in range(nb):
            arcs = pos_arcs.get((si, bi))
            if not arcs:
                continue
            for e in arcs:
                locked[e >> 1] = 1
            for e in arcs:
                if rc[e] != 0:
                    continue
                while cap[e] > 0:
                    start = to[e]
                    goal = frm[e]
                    parent = {start: -1}
                    dq = deque([start])
                    found = False
                    while dq and not found:
                        u = dq.popleft()
                        for f in adj0[u]:
                            if cap[f] <= 0 or locked[f >> 1]:
                                continue
                            v = to[f]
                            if v in parent:
                                continue
                            parent[v] = f
                            if v == goal:
                                found = True
                                break
                            dq.append(v)
                    if not found:
                        break
                    path = []
                    v = goal
                    while v != start:
                        f = parent[v]
                        path.append(f)
                        v = frm[f]
                    amount = cap[e]
                    for f in path:
                        if cap[f] < amount:
                            amount = cap[f]
                    cap[e] -= amount
                    cap[e ^ 1] += amount
                    for f in path:
                        cap[f] -= amount
                        cap[f ^ 1] += amount

    plan = {}
    for (si, bi), arcs in pos_arcs.items():
        kwh = sum(net.flow(e) for e in arcs)
        if kwh:
            plan[(bi, si)] = kwh

    return {
        "plan_date": plan_date,
        "slot_names": slot_names,
        "nslots": nslots,
        "depot_names": depot_names,
        "buses": buses,
        "published": published,
        "plan": plan,
        "price": price,
        "rejected": rejected,
    }


# ----------------------------------------------------------------------------
# reports
# ----------------------------------------------------------------------------

def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def report(model, out_dir):
    plan_date = model["plan_date"]
    slot_names = model["slot_names"]
    nslots = model["nslots"]
    buses = model["buses"]
    plan = model["plan"]
    published = model["published"]
    price = model["price"]

    nb = len(buses)
    delivered = [0] * nb
    charges = [[] for _ in range(nb)]
    for si in range(nslots):
        for bi in range(nb):
            kwh = plan.get((bi, si), 0)
            if kwh:
                delivered[bi] += kwh
                charges[bi].append((si, kwh))

    changed = [False] * nb
    for bi, b in enumerate(buses):
        for si in range(b["lo"], b["hi"]):
            if plan.get((bi, si), 0) != published.get((bi, si), 0):
                changed[bi] = True
                break

    unmet = [buses[bi]["need"] - delivered[bi] for bi in range(nb)]

    audit_buses = []
    for bi, b in enumerate(buses):
        if unmet[bi] == 0:
            reason = None
        elif b["need"] > b["max_kwh"] * (b["hi"] - b["lo"]):
            reason = "window"
        else:
            reason = "supply"
        audit_buses.append({
            "bus_id": b["bus_id"],
            "depot": b["depot"],
            "class": b["class"],
            "need_kwh": b["need"],
            "delivered_kwh": delivered[bi],
            "unmet_kwh": unmet[bi],
            "unmet_reason": reason,
            "changed": changed[bi],
            "charges": [{"slot": slot_names[si], "kwh": kwh} for si, kwh in charges[bi]],
        })
    write_json(os.path.join(out_dir, "policy_audit.json"),
               {"plan_date": plan_date, "buses": audit_buses})

    feeder_by_slot = [0] * nslots
    for (bi, si), kwh in plan.items():
        feeder_by_slot[si] += kwh

    def group_report(keyfn, groups):
        out = dict((g, {"buses": 0, "energy": 0, "cost": 0, "unmet": 0,
                        "slots": [0] * nslots}) for g in groups)
        for bi, b in enumerate(buses):
            rec = out.get(keyfn(b))
            if rec is None:
                continue
            rec["buses"] += 1
            rec["unmet"] += unmet[bi]
            for si, kwh in charges[bi]:
                rec["energy"] += kwh
                rec["cost"] += price[(b["depot"], si)] * kwh
                rec["slots"][si] += kwh
        return out

    def slot_list(vals):
        return [{"slot": slot_names[si], "kwh": vals[si],
                 "feeder_kwh": feeder_by_slot[si]} for si in range(nslots)]

    depot_names = model["depot_names"]
    per_depot = group_report(lambda b: b["depot"], depot_names)
    for depot in depot_names:
        rec = per_depot[depot]
        write_json(os.path.join(out_dir, "region_%s.json" % depot), {
            "depot": depot,
            "buses": rec["buses"],
            "energy_kwh": rec["energy"],
            "cost_cents": rec["cost"],
            "unmet_kwh": rec["unmet"],
            "slots": slot_list(rec["slots"]),
        })

    per_class = group_report(lambda b: b["class"], ["commercial", "public"])
    for cls in ("commercial", "public"):
        rec = per_class[cls]
        write_json(os.path.join(out_dir, "segment_%s.json" % cls), {
            "class": cls,
            "buses": rec["buses"],
            "energy_kwh": rec["energy"],
            "cost_cents": rec["cost"],
            "unmet_kwh": rec["unmet"],
            "slots": slot_list(rec["slots"]),
        })

    weighted_unmet = sum(buses[bi]["weight"] * unmet[bi] for bi in range(nb))
    energy_cost = sum(price[(buses[bi]["depot"], si)] * kwh
                      for (bi, si), kwh in plan.items())
    moved = 0
    for (bi, si), p in published.items():
        diff = p - plan.get((bi, si), 0)
        if diff > 0:
            moved += diff

    write_json(os.path.join(out_dir, "summary.json"), {
        "plan_date": plan_date,
        "weighted_unmet_kwh": weighted_unmet,
        "energy_cost_cents": energy_cost,
        "moved_kwh": moved,
        "feeder_peak_kwh": max(feeder_by_slot) if nslots else 0,
        "feeder_kwh_by_slot": [{"slot": slot_names[si], "kwh": feeder_by_slot[si]}
                               for si in range(nslots)],
        "buses_planned": nb,
        "buses_short": sum(1 for bi in range(nb) if unmet[bi] > 0),
        "buses_changed": sum(1 for bi in range(nb) if changed[bi]),
        "records_rejected": len(model["rejected"]),
    })

    rej = sorted(model["rejected"], key=lambda r: (r[0], r[1]))
    write_json(os.path.join(out_dir, "data_quality.json"), {
        "plan_date": plan_date,
        "rejected": [{"file": f, "line": ln, "reason": why} for f, ln, why in rej],
    })


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--out", default="/app/out")
    args = ap.parse_args(argv)
    try:
        model = build(args.data)
    except DataError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    os.makedirs(args.out, exist_ok=True)
    report(model, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
