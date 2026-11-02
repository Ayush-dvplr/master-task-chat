#!/usr/bin/env python3
"""Overnight depot charging planner.

Builds the day plan defined by <data>/docs/charging_rules.md and writes the
planning reports into the output folder.

Usage:
    python3 derive_report.py --data /app/data --out /app/out
"""

import argparse
import configparser
import csv
import datetime
import heapq
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction

CLASS_FALLBACK = "commercial"


def fail(name, detail=""):
    msg = "error: cannot read %s" % name
    if detail:
        msg += ": %s" % detail
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def need_file(path, name):
    if not os.path.isfile(path):
        fail(name, "file missing")
    return path


def parse_dt(text, name, detail=""):
    try:
        return datetime.datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M")
    except Exception:
        try:
            return datetime.datetime.fromisoformat(text.strip())
        except Exception:
            fail(name, "bad timestamp %r %s" % (text, detail))


def fmt_slot(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def to_int(text, name, detail=""):
    try:
        return int(str(text).strip())
    except Exception:
        fail(name, "bad integer %r %s" % (text, detail))


# ---------------------------------------------------------------- loading ---

def load_grid(data):
    path = need_file(os.path.join(data, "grid.ini"), "grid.ini")
    cp = configparser.ConfigParser()
    try:
        cp.read(path)
    except Exception as exc:
        fail("grid.ini", str(exc))
    if not cp.has_section("plan") or not cp.has_section("feeder"):
        fail("grid.ini", "missing [plan] or [feeder]")
    try:
        plan_date = cp.get("plan", "plan_date").strip()
        first_slot = parse_dt(cp.get("plan", "first_slot"), "grid.ini")
        slot_minutes = int(cp.get("plan", "slot_minutes").strip())
        slots = int(cp.get("plan", "slots").strip())
        feeder = int(cp.get("feeder", "feeder_kwh_per_slot").strip())
    except Exception as exc:
        fail("grid.ini", str(exc))
    if slot_minutes <= 0 or slots <= 0:
        fail("grid.ini", "bad slot definition")
    return plan_date, first_slot, slot_minutes, slots, feeder


def load_json(data, name):
    path = need_file(os.path.join(data, name), name)
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as exc:
        fail(name, str(exc))


def load_depots(data):
    doc = load_json(data, "depots.json")
    try:
        per_cabinet = int(doc["cabinet_kwh_per_slot"])
        depots = []
        for entry in doc["depots"]:
            depots.append((str(entry["depot"]), int(entry["cabinets"])))
    except Exception as exc:
        fail("depots.json", str(exc))
    if not depots:
        fail("depots.json", "no depots")
    return per_cabinet, depots


def load_bus_types(data):
    doc = load_json(data, "bus_types.json")
    out = {}
    try:
        for key, val in doc.items():
            out[str(key)] = (int(val["max_kwh_per_slot"]), int(val["reserve_kwh"]))
    except Exception as exc:
        fail("bus_types.json", str(exc))
    return out


def load_classes(data):
    path = need_file(os.path.join(data, "service_classes.ini"), "service_classes.ini")
    cp = configparser.ConfigParser()
    try:
        cp.read(path)
    except Exception as exc:
        fail("service_classes.ini", str(exc))
    weights = {}
    for sec in cp.sections():
        try:
            weights[sec] = int(cp.get(sec, "weight").strip())
        except Exception as exc:
            fail("service_classes.ini", str(exc))
    if not weights:
        fail("service_classes.ini", "no classes")
    return weights


def load_contracts(data):
    doc = load_json(data, "contracts.json")
    out = {}
    try:
        entries = doc["contracts"] if isinstance(doc, dict) else doc
        for entry in entries:
            out[str(entry["contract_id"])] = str(entry["class"])
    except Exception as exc:
        fail("contracts.json", str(exc))
    return out


def read_csv_rows(data, name):
    path = need_file(os.path.join(data, name), name)
    try:
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                fail(name, "no header")
            rows = []
            line = 1
            for row in reader:
                line += 1
                rows.append((line, row))
            return rows
    except SystemExit:
        raise
    except Exception as exc:
        fail(name, str(exc))


def load_tariff(data):
    path = need_file(os.path.join(data, "tariff.xml"), "tariff.xml")
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        fail("tariff.xml", str(exc))
    versions = []
    for ver in root.iter("version"):
        bands = []
        for band in ver.iter("band"):
            try:
                frm = band.get("from").strip()
                tto = band.get("to").strip()
                cents = int(band.get("cents_per_kwh").strip())
            except Exception as exc:
                fail("tariff.xml", str(exc))
            fh_, fm_ = frm.split(":")[:2]
            th_, tm_ = tto.split(":")[:2]
            bands.append((int(fh_) * 60 + int(fm_), int(th_) * 60 + int(tm_), cents))
        if not bands:
            fail("tariff.xml", "version without bands")
        versions.append((ver.get("valid_from").strip(), ver.get("valid_to").strip(), bands))
    if not versions:
        fail("tariff.xml", "no versions")
    return versions


def band_price(bands, minute):
    minute %= 1440
    for start, end, cents in bands:
        if start < end:
            if start <= minute < end:
                return cents
        elif start > end:
            if minute >= start or minute < end:
                return cents
        else:
            return cents
    return None


def version_for(versions, date_str):
    for valid_from, valid_to, bands in versions:
        if valid_from <= date_str <= valid_to:
            return bands
    return None


def load_notice(data, plan_date):
    path = need_file(os.path.join(data, "disruption_notice.md"), "disruption_notice.md")
    try:
        with open(path) as fh:
            lines = fh.read().splitlines()
    except Exception as exc:
        fail("disruption_notice.md", str(exc))
    outages = []      # (depot, count, from_dt, to_dt)
    deratings = []    # (from_dt, to_dt, kwh)
    extra = []        # (bus_id, date_str, kwh)
    section = None
    ts = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})"
    for raw in lines:
        line = raw.strip()
        if line.startswith("#"):
            low = line.lstrip("#").strip().lower()
            if "cabinet" in low:
                section = "cab"
            elif "feeder" in low or "derat" in low:
                section = "feeder"
            elif "extra" in low or "trip" in low:
                section = "trip"
            else:
                section = None
            continue
        if not line.startswith("-"):
            continue
        body = line.lstrip("-").strip()
        if section == "cab":
            m = re.match(r"^(?P<depot>[^:]+):\s*(?P<n>\d+)\s+cabinets?\b.*?from\s+" + ts +
                         r"\s+to\s+" + ts, body, re.I)
            if not m:
                fail("disruption_notice.md", "bad cabinet line %r" % body)
            outages.append((m.group("depot").strip(), int(m.group("n")),
                            parse_dt(m.group(3), "disruption_notice.md"),
                            parse_dt(m.group(4), "disruption_notice.md")))
        elif section == "feeder":
            m = re.match(r"^from\s+" + ts + r"\s+to\s+" + ts + r"\s*:.*?(?P<kwh>\d+)\s*kWh",
                         body, re.I)
            if not m:
                fail("disruption_notice.md", "bad feeder line %r" % body)
            deratings.append((parse_dt(m.group(1), "disruption_notice.md"),
                              parse_dt(m.group(2), "disruption_notice.md"),
                              int(m.group("kwh"))))
        elif section == "trip":
            m = re.match(r"^(?P<bus>[^:]+):.*?on\s+(?P<date>\d{4}-\d{2}-\d{2}).*?(?P<kwh>\d+)\s*kWh",
                         body, re.I)
            if not m:
                fail("disruption_notice.md", "bad extra trip line %r" % body)
            extra.append((m.group("bus").strip(), m.group("date"), int(m.group("kwh"))))
    return outages, deratings, extra


# ------------------------------------------------------- min cost flow -----

class Network(object):
    """Min cost flow on a DAG with negative arc costs (successive shortest
    paths with potentials), plus a lexicographic post-pass over the set of
    optimal flows."""

    def __init__(self, nodes):
        self.n = nodes
        self.to = []
        self.cap = []
        self.cost = []
        self.adj = [[] for _ in range(nodes)]

    def add(self, u, v, cap, cost):
        idx = len(self.to)
        self.to.append(v)
        self.cap.append(cap)
        self.cost.append(cost)
        self.adj[u].append(idx)
        self.to.append(u)
        self.cap.append(0)
        self.cost.append(-cost)
        self.adj[v].append(idx + 1)
        return idx

    def tail(self, i):
        return self.to[i ^ 1]

    def init_potentials(self, src):
        """Arcs always run from a lower to a higher node index."""
        INF = float("inf")
        pot = [INF] * self.n
        pot[src] = 0
        to, cap, cost, adj = self.to, self.cap, self.cost, self.adj
        for u in range(self.n):
            pu = pot[u]
            if pu == INF:
                continue
            for i in adj[u]:
                if cap[i] > 0:
                    v = to[i]
                    nd = pu + cost[i]
                    if nd < pot[v]:
                        pot[v] = nd
        for u in range(self.n):
            if pot[u] == INF:
                pot[u] = 0
        self.pot = pot

    def solve(self, src, dst):
        to, cap, cost, adj = self.to, self.cap, self.cost, self.adj
        pot = self.pot
        n = self.n
        INF = float("inf")
        total = 0
        while True:
            dist = [INF] * n
            prevarc = [-1] * n
            dist[src] = 0
            pq = [(0, src)]
            done = [False] * n
            while pq:
                d, u = heapq.heappop(pq)
                if done[u]:
                    continue
                done[u] = True
                pu = pot[u]
                for i in adj[u]:
                    if cap[i] <= 0:
                        continue
                    v = to[i]
                    if done[v]:
                        continue
                    nd = d + cost[i] + pu - pot[v]
                    if nd < dist[v]:
                        dist[v] = nd
                        prevarc[v] = i
                        heapq.heappush(pq, (nd, v))
            if dist[dst] == INF:
                break
            dt = dist[dst]
            for v in range(n):
                dv = dist[v]
                if dv == INF:
                    pot[v] += dt
                else:
                    pot[v] += dv if dv < dt else dt
            # bottleneck
            push = None
            v = dst
            while v != src:
                i = prevarc[v]
                c = cap[i]
                if push is None or c < push:
                    push = c
                v = self.tail(i)
            v = dst
            while v != src:
                i = prevarc[v]
                cap[i] -= push
                cap[i ^ 1] += push
                v = self.tail(i)
            total += push
        return total

    # -- lexicographic pass ------------------------------------------------
    def lex_maximise(self, order):
        """`order` is the list of arc indices in the order their flow must be
        maximised.  Flow is pushed around zero reduced cost residual cycles,
        which keeps the total cost (and hence every objective) unchanged."""
        to, cap, cost, adj = self.to, self.cap, self.cost, self.adj
        pot = self.pot
        frozen = [False] * (len(self.to) // 2)
        for a in order:
            room = cap[a]
            if room <= 0 or cost[a] + pot[self.to[a ^ 1]] - pot[to[a]] != 0:
                frozen[a >> 1] = True
                continue
            frozen[a >> 1] = True
            src = to[a]
            dst = to[a ^ 1]
            moved = 0
            while moved < room:
                prevarc = [-1] * self.n
                prevarc[src] = -2
                queue = [src]
                found = False
                while queue and not found:
                    nxt = []
                    for u in queue:
                        pu = pot[u]
                        for i in adj[u]:
                            if cap[i] <= 0 or frozen[i >> 1]:
                                continue
                            v = to[i]
                            if prevarc[v] != -1:
                                continue
                            if cost[i] + pu - pot[v] != 0:
                                continue
                            prevarc[v] = i
                            if v == dst:
                                found = True
                                break
                            nxt.append(v)
                        if found:
                            break
                    queue = nxt
                if not found:
                    break
                push = room - moved
                v = dst
                while v != src:
                    i = prevarc[v]
                    if cap[i] < push:
                        push = cap[i]
                    v = to[i ^ 1]
                v = dst
                while v != src:
                    i = prevarc[v]
                    cap[i] -= push
                    cap[i ^ 1] += push
                    v = to[i ^ 1]
                cap[a] -= push
                cap[a ^ 1] += push
                moved += push


# ------------------------------------------------------------- meters ------

METER_ORDER = ["start", "end", "mid", "max", "min"]


def meter_price(kind, bands, minute, slot_minutes):
    if kind == "start":
        return band_price(bands, minute)
    if kind == "end":
        return band_price(bands, minute + slot_minutes)
    if kind == "mid":
        return band_price(bands, minute + slot_minutes // 2)
    vals = [band_price(bands, minute + k) for k in range(slot_minutes)]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return max(vals) if kind == "max" else min(vals)


def infer_meters(data, versions, depot_names, slot_minutes):
    rows = read_csv_rows(data, "settlements.csv")
    per_depot = {}
    for line, row in rows:
        depot = (row.get("depot") or "").strip()
        if depot not in per_depot:
            per_depot[depot] = []
        start = parse_dt(row.get("start") or "", "settlements.csv", "line %d" % line)
        end = parse_dt(row.get("end") or "", "settlements.csv", "line %d" % line)
        kwh = to_int(row.get("kwh"), "settlements.csv", "line %d" % line)
        cents = to_int(row.get("cents"), "settlements.csv", "line %d" % line)
        bands = version_for(versions, (row.get("settled_date") or "").strip())
        span = int((end - start).total_seconds() // 60)
        if bands is None or span <= 0 or span % slot_minutes != 0:
            continue
        per_depot[depot].append((start, span // slot_minutes, kwh, cents, bands))
    meters = {}
    for depot in depot_names:
        chosen = None
        for kind in METER_ORDER:
            ok = True
            for start, nslot, kwh, cents, bands in per_depot.get(depot, []):
                each = Fraction(kwh, nslot)
                total = Fraction(0)
                for k in range(nslot):
                    moment = start + datetime.timedelta(minutes=slot_minutes * k)
                    price = meter_price(kind, bands, moment.hour * 60 + moment.minute,
                                        slot_minutes)
                    if price is None:
                        ok = False
                        break
                    total += each * price
                if not ok or total != cents:
                    ok = False
                    break
            if ok:
                chosen = kind
                break
        meters[depot] = chosen or "start"
    return meters


# -------------------------------------------------------------- reports ----

def write_json(out_dir, name, doc):
    path = os.path.join(out_dir, name)
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--out", default="/app/out")
    args = ap.parse_args(argv)
    data = args.data
    out_dir = args.out
    if not os.path.isdir(data):
        fail(data, "data folder missing")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    plan_date, first_slot, slot_minutes, nslots, feeder_default = load_grid(data)
    step = datetime.timedelta(minutes=slot_minutes)
    slot_times = [first_slot + step * i for i in range(nslots)]
    slot_names = [fmt_slot(t) for t in slot_times]
    slot_index = dict((t, i) for i, t in enumerate(slot_times))
    day_end = first_slot + step * nslots
    next_day = (datetime.datetime.strptime(plan_date, "%Y-%m-%d") +
                datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    cabinet_kwh, depot_list = load_depots(data)
    depot_names = [d for d, _ in depot_list]
    cabinets = dict(depot_list)
    bus_types = load_bus_types(data)
    weights = load_classes(data)
    contracts = load_contracts(data)
    versions = load_tariff(data)
    bands = version_for(versions, plan_date)
    if bands is None:
        fail("tariff.xml", "no version in force on %s" % plan_date)
    outages, deratings, extra_trips = load_notice(data, plan_date)

    # fleet register
    fleet = {}
    for line, row in read_csv_rows(data, "fleet_register.csv"):
        vid = (row.get("vehicle_id") or "").strip()
        if vid and vid not in fleet:
            fleet[vid] = ((row.get("type") or "").strip(),
                          (row.get("status") or "").strip())

    # roster
    rejected = []
    buses = {}
    order = []
    for line, row in read_csv_rows(data, "roster.csv"):
        if (row.get("plan_date") or "").strip() != plan_date:
            continue
        bus_id = (row.get("bus_id") or "").strip()
        if bus_id not in fleet:
            rejected.append(("roster.csv", line, "unknown_vehicle"))
            continue
        btype, status = fleet[bus_id]
        if status != "active":
            rejected.append(("roster.csv", line, "retired_vehicle"))
            continue
        if bus_id in buses:
            rejected.append(("roster.csv", line, "duplicate_roster_row"))
            continue
        arrive = parse_dt(row.get("arrive") or "", "roster.csv", "line %d" % line)
        depart = parse_dt(row.get("depart") or "", "roster.csv", "line %d" % line)
        if not (arrive < depart) or arrive < first_slot or depart > day_end:
            rejected.append(("roster.csv", line, "bad_window"))
            continue
        if btype not in bus_types:
            fail("bus_types.json", "unknown type %r" % btype)
        window = [i for i, t in enumerate(slot_times) if arrive <= t < depart]
        buses[bus_id] = {
            "bus_id": bus_id,
            "depot": (row.get("depot") or "").strip(),
            "type": btype,
            "soc": to_int(row.get("soc_arrival_kwh"), "roster.csv", "line %d" % line),
            "contract": (row.get("contract_id") or "").strip(),
            "window": window,
        }
        order.append(bus_id)

    # trips of the day after the plan date
    trip_kwh = {}
    path = need_file(os.path.join(data, "trips.jsonl"), "trips.jsonl")
    with open(path) as fh:
        for num, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except Exception as exc:
                fail("trips.jsonl", "line %d: %s" % (num, exc))
            if str(rec.get("service_date", "")).strip() != next_day:
                continue
            bid = str(rec.get("bus_id", "")).strip()
            trip_kwh[bid] = trip_kwh.get(bid, 0) + int(rec.get("kwh", 0))
    for bid, date_str, kwh in extra_trips:
        if date_str == next_day:
            trip_kwh[bid] = trip_kwh.get(bid, 0) + kwh

    bus_ids = sorted(buses)
    for bid in bus_ids:
        info = buses[bid]
        maxslot, reserve = bus_types[info["type"]]
        info["max_kwh"] = maxslot
        need = trip_kwh.get(bid, 0) + reserve - info["soc"]
        info["need"] = need if need > 0 else 0
        klass = contracts.get(info["contract"], CLASS_FALLBACK)
        if info["contract"] == "":
            klass = CLASS_FALLBACK
        if klass not in weights:
            fail("service_classes.ini", "unknown class %r" % klass)
        info["class"] = klass
        info["weight"] = weights[klass]

    # published plan
    published = {}
    for line, row in read_csv_rows(data, "published_plan.csv"):
        if (row.get("plan_date") or "").strip() != plan_date:
            continue
        bus_id = (row.get("bus_id") or "").strip()
        slot_raw = (row.get("slot_start") or "").strip()
        kwh = to_int(row.get("kwh"), "published_plan.csv", "line %d" % line)
        info = buses.get(bus_id)
        idx = slot_index.get(parse_dt(slot_raw, "published_plan.csv", "line %d" % line))
        if info is None or idx is None or idx not in info["window"]:
            rejected.append(("published_plan.csv", line, "published_row_outside_window"))
            continue
        key = (bus_id, idx)
        published[key] = published.get(key, 0) + kwh
    rejected.sort(key=lambda r: (r[0], r[1]))

    # prices
    meters = infer_meters(data, versions, depot_names, slot_minutes)
    price = {}
    for depot in depot_names:
        kind = meters[depot]
        row = []
        for t in slot_times:
            val = meter_price(kind, bands, t.hour * 60 + t.minute, slot_minutes)
            if val is None:
                fail("tariff.xml", "no band for %s" % fmt_slot(t))
            row.append(val)
        price[depot] = row

    # capacities
    depot_cap = {}
    for depot in depot_names:
        base = cabinets[depot]
        row = []
        for t in slot_times:
            out = 0
            for dep, count, frm, tto in outages:
                if dep == depot and frm <= t < tto:
                    out += count
            left = base - out
            row.append(max(0, left) * cabinet_kwh)
        depot_cap[depot] = row
    feeder_cap = []
    for t in slot_times:
        val = feeder_default
        for frm, tto, kwh in deratings:
            if frm <= t < tto and kwh < val:
                val = kwh
        feeder_cap.append(val)

    for bid in bus_ids:
        depot = buses[bid]["depot"]
        if depot not in depot_cap:
            depot_cap[depot] = [0] * nslots
            price[depot] = [meter_price("start", bands, t.hour * 60 + t.minute,
                                        slot_minutes) or 0 for t in slot_times]

    # ----------------------------------------------------------- network ---
    moved_max = sum(published.values())
    cost_unit = moved_max + 1
    max_price = max(max(price[d]) for d in price) if price else 0
    total_need = sum(buses[b]["need"] for b in bus_ids)
    arc_guess = sum(len(buses[b]["window"]) for b in bus_ids) + 16
    unmet_unit = (cost_unit * (total_need * max_price + arc_guess * max_price + 1) +
                  (moved_max + 1) * arc_guess + 1)

    active = [b for b in bus_ids if buses[b]["need"] > 0 and buses[b]["window"]]
    node = 0
    src = node
    node += 1
    bus_node = {}
    for bid in active:
        bus_node[bid] = node
        node += 1
    cell_node = {}
    for bid in active:
        for s in buses[bid]["window"]:
            cell_node[(bid, s)] = node
            node += 1
    ds_node = {}
    for depot in sorted(depot_cap):
        for s in range(nslots):
            ds_node[(depot, s)] = node
            node += 1
    slot_node = [0] * nslots
    for s in range(nslots):
        slot_node[s] = node
        node += 1
    dst = node
    node += 1

    net = Network(node)
    for bid in active:
        info = buses[bid]
        net.add(src, bus_node[bid], info["need"], -unmet_unit * info["weight"])
    cell_arc = {}
    for bid in active:
        info = buses[bid]
        depot = info["depot"]
        mx = info["max_kwh"]
        for s in info["window"]:
            cn = cell_node[(bid, s)]
            base = cost_unit * price[depot][s]
            pub = published.get((bid, s), 0)
            cheap = pub if pub < mx else mx
            if cheap > 0:
                net.add(bus_node[bid], cn, cheap, base - 1)
            if mx - cheap > 0:
                net.add(bus_node[bid], cn, mx - cheap, base)
            cell_arc[(bid, s)] = net.add(cn, ds_node[(depot, s)], mx, 0)
    for (depot, s), nd in ds_node.items():
        cap = depot_cap[depot][s]
        if cap > 0:
            net.add(nd, slot_node[s], cap, 0)
    for s in range(nslots):
        if feeder_cap[s] > 0:
            net.add(slot_node[s], dst, feeder_cap[s], 0)

    net.init_potentials(src)
    net.solve(src, dst)
    lex = []
    for s in range(nslots):
        for bid in bus_ids:
            key = (bid, s)
            if key in cell_arc:
                lex.append(cell_arc[key])
    net.lex_maximise(lex)

    plan = {}
    for key, arc in cell_arc.items():
        val = net.cap[arc ^ 1]
        if val:
            plan[key] = val

    # ----------------------------------------------------------- reports ---
    delivered = dict((b, 0) for b in bus_ids)
    for (bid, s), kwh in plan.items():
        delivered[bid] += kwh
    audit = []
    weighted_unmet = 0
    energy_cost = 0
    moved = 0
    buses_short = 0
    buses_changed = 0
    slot_total = [0] * nslots
    depot_slot = dict((d, [0] * nslots) for d in depot_names)
    class_slot = {}
    class_tot = {}
    for klass in weights:
        class_slot[klass] = [0] * nslots
        class_tot[klass] = {"buses": 0, "energy": 0, "cost": 0, "unmet": 0}
    depot_tot = dict((d, {"buses": 0, "energy": 0, "cost": 0, "unmet": 0})
                     for d in depot_names)

    for bid in bus_ids:
        info = buses[bid]
        depot = info["depot"]
        klass = info["class"]
        need = info["need"]
        got = delivered[bid]
        unmet = need - got
        weighted_unmet += info["weight"] * unmet
        charges = []
        cost_b = 0
        for s in info["window"]:
            kwh = plan.get((bid, s), 0)
            if kwh > 0:
                charges.append({"slot": slot_names[s], "kwh": kwh})
                cost_b += kwh * price[depot][s]
                slot_total[s] += kwh
                if depot in depot_slot:
                    depot_slot[depot][s] += kwh
                class_slot[klass][s] += kwh
        energy_cost += cost_b
        changed = False
        slots_seen = set(info["window"])
        for (b2, s2) in published:
            if b2 == bid:
                slots_seen.add(s2)
        for s in slots_seen:
            pub = published.get((bid, s), 0)
            got_s = plan.get((bid, s), 0)
            if pub != got_s:
                changed = True
            if pub > got_s:
                moved += pub - got_s
        if unmet > 0:
            buses_short += 1
            if need > info["max_kwh"] * len(info["window"]):
                reason = "window"
            else:
                reason = "supply"
        else:
            reason = None
        if changed:
            buses_changed += 1
        audit.append({
            "bus_id": bid,
            "depot": depot,
            "class": klass,
            "need_kwh": need,
            "delivered_kwh": got,
            "unmet_kwh": unmet,
            "unmet_reason": reason,
            "changed": changed,
            "charges": charges,
        })
        if depot in depot_tot:
            depot_tot[depot]["buses"] += 1
            depot_tot[depot]["energy"] += got
            depot_tot[depot]["cost"] += cost_b
            depot_tot[depot]["unmet"] += unmet
        class_tot[klass]["buses"] += 1
        class_tot[klass]["energy"] += got
        class_tot[klass]["cost"] += cost_b
        class_tot[klass]["unmet"] += unmet

    write_json(out_dir, "policy_audit.json", {"plan_date": plan_date, "buses": audit})
    for depot in depot_names:
        tot = depot_tot[depot]
        write_json(out_dir, "region_%s.json" % depot, {
            "depot": depot,
            "buses": tot["buses"],
            "energy_kwh": tot["energy"],
            "cost_cents": tot["cost"],
            "unmet_kwh": tot["unmet"],
            "slots": [{"slot": slot_names[s], "kwh": depot_slot[depot][s],
                       "feeder_kwh": slot_total[s]} for s in range(nslots)],
        })
    for klass in sorted(weights):
        tot = class_tot[klass]
        write_json(out_dir, "segment_%s.json" % klass, {
            "class": klass,
            "buses": tot["buses"],
            "energy_kwh": tot["energy"],
            "cost_cents": tot["cost"],
            "unmet_kwh": tot["unmet"],
            "slots": [{"slot": slot_names[s], "kwh": class_slot[klass][s],
                       "feeder_kwh": slot_total[s]} for s in range(nslots)],
        })
    write_json(out_dir, "summary.json", {
        "plan_date": plan_date,
        "weighted_unmet_kwh": weighted_unmet,
        "energy_cost_cents": energy_cost,
        "moved_kwh": moved,
        "feeder_peak_kwh": max(slot_total) if slot_total else 0,
        "feeder_kwh_by_slot": [{"slot": slot_names[s], "kwh": slot_total[s]}
                               for s in range(nslots)],
        "buses_planned": len(bus_ids),
        "buses_short": buses_short,
        "buses_changed": buses_changed,
        "records_rejected": len(rejected),
    })
    write_json(out_dir, "data_quality.json", {
        "plan_date": plan_date,
        "rejected": [{"file": f, "line": ln, "reason": r} for f, ln, r in rejected],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
