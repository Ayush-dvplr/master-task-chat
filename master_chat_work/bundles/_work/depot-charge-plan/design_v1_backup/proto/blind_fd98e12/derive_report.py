#!/usr/bin/env python3
"""Overnight depot charging plan.

Rebuilds the overnight charging plan for the electric bus fleet after a
disruption notice and writes the nine planning reports.

Usage:
    python3 derive_report.py --data <data folder> --out <output folder>

Standard library only.  The plan is the exact optimum of the lexicographic
objective of rule 15 (weighted unmet kWh, then energy cost, then moved
energy, then the lexicographically greatest kWh vector by slot and bus id).
It is computed as a minimum cost flow whose integer arc costs encode the
first three objectives, followed by a lexicographic refinement over the
optimal face of that flow problem.
"""

import argparse
import configparser
import csv
import json
import os
import re
import sys
from collections import deque
from datetime import datetime, timedelta
from xml.etree import ElementTree

SLOT_FMT = "%Y-%m-%dT%H:%M"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def parse_dt(text):
    """Parse a 'YYYY-MM-DDTHH:MM' (or longer) timestamp, tolerating spaces."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    text = text.replace(" ", "T", 1) if ("T" not in text and " " in text) else text
    try:
        return datetime.strptime(text[:16], SLOT_FMT)
    except ValueError:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None


def to_int(text, default=0):
    if text is None:
        return default
    text = str(text).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        try:
            return int(round(float(text)))
        except ValueError:
            return default


# --------------------------------------------------------------------------
# input files
# --------------------------------------------------------------------------

def read_grid(path):
    cp = configparser.ConfigParser()
    cp.read(path)
    plan = cp["plan"] if cp.has_section("plan") else {}
    feeder = cp["feeder"] if cp.has_section("feeder") else {}
    return {
        "plan_date": plan.get("plan_date", "").strip(),
        "first_slot": plan.get("first_slot", "").strip(),
        "slot_minutes": to_int(plan.get("slot_minutes"), 15),
        "slots": to_int(plan.get("slots"), 0),
        "feeder_kwh_per_slot": to_int(feeder.get("feeder_kwh_per_slot"), 0),
    }


def read_classes(path):
    cp = configparser.ConfigParser()
    cp.read(path)
    weights = {}
    for name in cp.sections():
        weights[name] = to_int(cp[name].get("weight"), 0)
    return weights


def read_tariff(path):
    bands = []
    try:
        root = ElementTree.parse(path).getroot()
    except Exception:
        return bands
    for band in root.iter("band"):
        start = parse_dt(band.get("from"))
        end = parse_dt(band.get("to"))
        cents = to_int(band.get("cents_per_kwh"), 0)
        if start is not None and end is not None:
            bands.append((start, end, cents))
    return bands


def read_notice(path):
    """Parse the disruption notice (plan date, outages, derating, extra trips)."""
    notice = {
        "plan_date": None,
        "outages": [],      # (depot, cabinets, start, end)
        "deratings": [],     # (start, end, kwh)
        "extra_trips": [],   # (bus_id, date, kwh)
    }
    if not os.path.exists(path):
        return notice
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    head = re.search(r"disruption notice for\s+(\d{4}-\d{2}-\d{2})", text, re.I)
    if head:
        notice["plan_date"] = head.group(1)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        mo = re.match(
            r"^[-*]?\s*(\w[\w ]*?)\s*:\s*(\d+)\s+cabinets?\s+out of service\s+"
            r"from\s+(\S+)\s+to\s+(\S+)\s*$",
            line, re.I)
        if mo:
            start = parse_dt(mo.group(3))
            end = parse_dt(mo.group(4))
            if start is not None and end is not None:
                notice["outages"].append(
                    (mo.group(1).strip(), int(mo.group(2)), start, end))
            continue
        mo = re.match(
            r"^[-*]?\s*from\s+(\S+)\s+to\s+(\S+)\s*:\s*feeder limit\s+(\d+)\s*kwh",
            line, re.I)
        if mo:
            start = parse_dt(mo.group(1))
            end = parse_dt(mo.group(2))
            if start is not None and end is not None:
                notice["deratings"].append((start, end, int(mo.group(3))))
            continue
        mo = re.match(
            r"^[-*]?\s*(\S+?)\s*:\s*extra trip on\s+(\d{4}-\d{2}-\d{2})\s*,\s*(\d+)\s*kwh",
            line, re.I)
        if mo:
            notice["extra_trips"].append(
                (mo.group(1).strip(), mo.group(2), int(mo.group(3))))
            continue
    return notice


# --------------------------------------------------------------------------
# minimum cost flow (primal-dual) with a lexicographic refinement phase
# --------------------------------------------------------------------------

class McFlow(object):
    """Integer min cost flow on a residual arc array.

    Arc ``a`` and its reverse ``a ^ 1`` are stored next to each other.
    ``solve`` finds a flow of minimum total cost over *all* feasible flows
    (the flow value is free; negative cost arcs are what pull flow through).
    """

    def __init__(self, nodes):
        self.n = nodes
        self.head = [[] for _ in range(nodes)]
        self.to = []
        self.cap = []
        self.cost = []
        self.orig = []

    def add(self, u, v, cap, cost):
        a = len(self.to)
        self.to.append(v)
        self.cap.append(cap)
        self.cost.append(cost)
        self.orig.append(cap)
        self.head[u].append(a)
        self.to.append(u)
        self.cap.append(0)
        self.cost.append(-cost)
        self.orig.append(0)
        self.head[v].append(a + 1)
        return a

    # -- potentials ---------------------------------------------------------
    def init_potentials(self, source, order):
        """Shortest distances on the initial (acyclic) graph, in topo order."""
        inf = float("inf")
        pot = [inf] * self.n
        pot[source] = 0
        to, cap, cost, head = self.to, self.cap, self.cost, self.head
        for u in order:
            du = pot[u]
            if du == inf:
                continue
            for a in head[u]:
                if cap[a] > 0:
                    nd = du + cost[a]
                    if nd < pot[to[a]]:
                        pot[to[a]] = nd
        for i in range(self.n):
            if pot[i] == inf:
                pot[i] = 0
        self.pot = pot

    def _dijkstra(self, source):
        import heapq
        inf = float("inf")
        dist = [inf] * self.n
        prev = [-1] * self.n
        dist[source] = 0
        to, cap, cost, head, pot = self.to, self.cap, self.cost, self.head, self.pot
        heap = [(0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            pu = pot[u]
            for a in head[u]:
                if cap[a] <= 0:
                    continue
                v = to[a]
                nd = d + cost[a] + pu - pot[v]
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = a
                    heapq.heappush(heap, (nd, v))
        return dist, prev

    def _blocking(self, source, sink):
        """Dinic max flow over the admissible (zero reduced cost) subgraph."""
        to, cap, cost, head, pot = self.to, self.cap, self.cost, self.head, self.pot
        total = 0
        while True:
            level = [-1] * self.n
            level[source] = 0
            queue = deque([source])
            while queue:
                u = queue.popleft()
                for a in head[u]:
                    if cap[a] <= 0:
                        continue
                    v = to[a]
                    if level[v] >= 0:
                        continue
                    if cost[a] + pot[u] - pot[v] != 0:
                        continue
                    level[v] = level[u] + 1
                    queue.append(v)
            if level[sink] < 0:
                return total
            it = [0] * self.n

            def dfs(u, limit):
                if u == sink:
                    return limit
                while it[u] < len(head[u]):
                    a = head[u][it[u]]
                    v = to[a]
                    if cap[a] > 0 and level[v] == level[u] + 1 and \
                            cost[a] + pot[u] - pot[v] == 0:
                        got = dfs(v, limit if limit < cap[a] else cap[a])
                        if got > 0:
                            cap[a] -= got
                            cap[a ^ 1] += got
                            return got
                    it[u] += 1
                return 0

            while True:
                pushed = dfs(source, 1 << 62)
                if pushed <= 0:
                    break
                total += pushed

    def solve(self, source, sink):
        inf = float("inf")
        while True:
            dist, _ = self._dijkstra(source)
            dt = dist[sink]
            if dt == inf:
                dt = max([d for d in dist if d != inf] or [0])
            for i in range(self.n):
                d = dist[i]
                if d == inf or d > dt:
                    d = dt
                self.pot[i] += d
            if dist[sink] == inf or self.pot[sink] >= 0:
                return
            self._blocking(source, sink)


def lex_refine(g, positions):
    """Pick the lexicographically greatest optimum over the optimal face.

    ``positions`` is the list of (arc ids) for every (slot, bus) pair in the
    order of rule 15: slot first, then bus id.  Each pair's kWh is pushed as
    high as the optimal face allows, then frozen, before the next pair.
    """
    to, cap, cost, head, pot = g.to, g.cap, g.cost, g.head, g.pot
    blocked = [False] * len(to)
    prev = [-1] * g.n
    seen = [-1] * g.n
    stamp = 0

    for arcs in positions:
        for a in arcs:
            blocked[a] = True
            blocked[a ^ 1] = True
        if not arcs:
            continue
        progress = True
        while progress:
            progress = False
            for a in arcs:
                if cap[a] <= 0:
                    continue
                src = to[a]
                tgt = to[a ^ 1]
                if cost[a] + pot[tgt] - pot[src] != 0:
                    continue
                while cap[a] > 0:
                    stamp += 1
                    seen[src] = stamp
                    prev[src] = -1
                    queue = deque([src])
                    found = False
                    while queue:
                        u = queue.popleft()
                        if u == tgt:
                            found = True
                            break
                        pu = pot[u]
                        for b in head[u]:
                            if cap[b] <= 0 or blocked[b]:
                                continue
                            v = to[b]
                            if seen[v] == stamp:
                                continue
                            if cost[b] + pu - pot[v] != 0:
                                continue
                            seen[v] = stamp
                            prev[v] = b
                            queue.append(v)
                    if not found:
                        break
                    delta = cap[a]
                    node = tgt
                    while prev[node] >= 0:
                        b = prev[node]
                        if cap[b] < delta:
                            delta = cap[b]
                        node = to[b ^ 1]
                    cap[a] -= delta
                    cap[a ^ 1] += delta
                    node = tgt
                    while prev[node] >= 0:
                        b = prev[node]
                        cap[b] -= delta
                        cap[b ^ 1] += delta
                        node = to[b ^ 1]
                    progress = True


# --------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------

DEPOT_ORDER = ["North", "South", "West", "East"]


def build(data_dir, docs_dir):
    """Read every input and assemble the planning problem."""
    grid = read_grid(os.path.join(data_dir, "grid.ini"))
    notice = read_notice(os.path.join(data_dir, "disruption_notice.md"))

    plan_date = notice["plan_date"] or grid["plan_date"]
    slot_minutes = grid["slot_minutes"]
    nslots = grid["slots"]
    first = parse_dt(grid["first_slot"])
    if first is None:
        first = parse_dt(plan_date + "T00:00")
    slot_dt = [first + timedelta(minutes=slot_minutes * i) for i in range(nslots)]
    slot_name = [d.strftime(SLOT_FMT) for d in slot_dt]
    slot_index = {name: i for i, name in enumerate(slot_name)}
    day_end = first + timedelta(minutes=slot_minutes * nslots)

    def span_slots(start, end):
        return [i for i, d in enumerate(slot_dt) if start <= d < end]

    # prices -------------------------------------------------------------
    bands = read_tariff(os.path.join(data_dir, "tariff.xml"))
    price = [0] * nslots
    for start, end, cents in bands:
        for i in span_slots(start, end):
            price[i] = cents

    # depots -------------------------------------------------------------
    depots_raw = json.load(open(os.path.join(data_dir, "depots.json")))
    cab_kwh = to_int(depots_raw.get("cabinet_kwh_per_slot"), 0)
    cabinets = {}
    depot_names = []
    for entry in depots_raw.get("depots", []):
        name = entry["depot"]
        cabinets[name] = to_int(entry.get("cabinets"), 0)
        depot_names.append(name)
    ordered = [d for d in DEPOT_ORDER if d in cabinets]
    ordered += [d for d in depot_names if d not in ordered]

    out_count = {d: [0] * nslots for d in ordered}
    for depot, count, start, end in notice["outages"]:
        if depot not in out_count:
            continue
        for i in span_slots(start, end):
            out_count[depot][i] += count
    depot_cap = {}
    for d in ordered:
        depot_cap[d] = [max(0, cabinets[d] - out_count[d][i]) * cab_kwh
                        for i in range(nslots)]

    feeder = [grid["feeder_kwh_per_slot"]] * nslots
    for start, end, kwh in notice["deratings"]:
        for i in span_slots(start, end):
            feeder[i] = kwh

    # fleet register ------------------------------------------------------
    register = {}
    with open(os.path.join(data_dir, "fleet_register.csv"), newline="") as handle:
        for row in csv.DictReader(handle):
            register[(row.get("vehicle_id") or "").strip()] = row

    bus_types = json.load(open(os.path.join(data_dir, "bus_types.json")))

    # contracts -----------------------------------------------------------
    contract_class = {}
    contracts_raw = json.load(open(os.path.join(data_dir, "contracts.json")))
    for entry in contracts_raw.get("contracts", []):
        contract_class[entry["contract_id"]] = entry.get("class", "commercial")
    weights = read_classes(os.path.join(data_dir, "service_classes.ini"))

    # trips ---------------------------------------------------------------
    service_date = (parse_dt(plan_date + "T00:00") + timedelta(days=1)).strftime("%Y-%m-%d")
    trip_kwh = {}
    with open(os.path.join(data_dir, "trips.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("service_date") != service_date:
                continue
            bus = obj.get("bus_id")
            trip_kwh[bus] = trip_kwh.get(bus, 0) + to_int(obj.get("kwh"))
    for bus, date, kwh in notice["extra_trips"]:
        if date != service_date:
            continue
        trip_kwh[bus] = trip_kwh.get(bus, 0) + kwh

    # roster --------------------------------------------------------------
    rejected = []
    buses = {}
    accepted = set()
    with open(os.path.join(data_dir, "roster.csv"), newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            if (row.get("plan_date") or "").strip() != plan_date:
                continue
            bus = (row.get("bus_id") or "").strip()
            reason = None
            if bus not in register:
                reason = "unknown_vehicle"
            elif (register[bus].get("status") or "").strip() != "active":
                reason = "retired_vehicle"
            elif bus in accepted:
                reason = "duplicate_roster_row"
            else:
                arrive = parse_dt(row.get("arrive"))
                depart = parse_dt(row.get("depart"))
                if arrive is None or depart is None or not (arrive < depart) \
                        or arrive < first or depart > day_end:
                    reason = "bad_window"
            if reason is not None:
                rejected.append(("roster.csv", line_no, reason))
                continue
            accepted.add(bus)
            arrive = parse_dt(row.get("arrive"))
            depart = parse_dt(row.get("depart"))
            window = span_slots(arrive, depart)
            btype = (register[bus].get("type") or "").strip()
            spec = bus_types.get(btype, {})
            max_slot = to_int(spec.get("max_kwh_per_slot"), 0)
            reserve = to_int(spec.get("reserve_kwh"), 0)
            need = trip_kwh.get(bus, 0) + reserve - to_int(row.get("soc_arrival_kwh"))
            if need < 0:
                need = 0
            contract = (row.get("contract_id") or "").strip()
            klass = contract_class.get(contract, "commercial") if contract else "commercial"
            depot = (row.get("depot") or "").strip()
            buses[bus] = {
                "bus_id": bus,
                "depot": depot,
                "class": klass,
                "type": btype,
                "max_slot": max_slot,
                "need": need,
                "window": window,
                "weight": weights.get(klass, 0),
            }

    # published plan -------------------------------------------------------
    published = {}
    with open(os.path.join(data_dir, "published_plan.csv"), newline="") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            if (row.get("plan_date") or "").strip() != plan_date:
                continue
            bus = (row.get("bus_id") or "").strip()
            slot = (row.get("slot_start") or "").strip()
            info = buses.get(bus)
            index = slot_index.get(slot)
            if info is None or index is None or index not in set(info["window"]):
                rejected.append(("published_plan.csv", line_no,
                                 "published_row_outside_window"))
                continue
            key = (bus, index)
            published[key] = published.get(key, 0) + to_int(row.get("kwh"))

    return {
        "plan_date": plan_date,
        "nslots": nslots,
        "slot_name": slot_name,
        "price": price,
        "depots": ordered,
        "depot_cap": depot_cap,
        "feeder": feeder,
        "buses": buses,
        "published": published,
        "rejected": rejected,
        "weights": weights,
    }


def plan(model):
    """Compute the day plan: x[bus_id][slot] = whole kWh delivered."""
    nslots = model["nslots"]
    buses = model["buses"]
    bus_ids = sorted(buses)
    price = model["price"]
    published = model["published"]
    depots = model["depots"]

    x = {bus: [0] * nslots for bus in bus_ids}
    if not bus_ids or nslots == 0:
        return x

    moved_max = sum(published.values())
    cost_max = (max(price) if price else 0) * sum(b["need"] for b in buses.values())
    m3 = 1
    m2 = moved_max + 1
    m1 = m2 * (cost_max + 1) + m3 * moved_max + 1

    nb = len(bus_ids)
    nd = len(depots)
    source = 0
    bus_node = {bus: 1 + i for i, bus in enumerate(bus_ids)}
    ds_base = 1 + nb
    depot_pos = {d: i for i, d in enumerate(depots)}
    slot_base = ds_base + nd * nslots
    sink = slot_base + nslots
    g = McFlow(sink + 1)

    for bus in bus_ids:
        info = buses[bus]
        g.add(source, bus_node[bus], info["need"], -m1 * info["weight"])

    pos_arcs = {}
    for bus in bus_ids:
        info = buses[bus]
        depot = info["depot"]
        if depot not in depot_pos or info["max_slot"] <= 0:
            continue
        base = ds_base + depot_pos[depot] * nslots
        for s in info["window"]:
            cap_a = published.get((bus, s), 0)
            if cap_a > info["max_slot"]:
                cap_a = info["max_slot"]
            arcs = []
            if cap_a > 0:
                arcs.append(g.add(bus_node[bus], base + s, cap_a, -m3))
            rest = info["max_slot"] - cap_a
            if rest > 0:
                arcs.append(g.add(bus_node[bus], base + s, rest, 0))
            if arcs:
                pos_arcs[(bus, s)] = arcs

    for d in depots:
        base = ds_base + depot_pos[d] * nslots
        caps = model["depot_cap"][d]
        for s in range(nslots):
            if caps[s] > 0:
                g.add(base + s, slot_base + s, caps[s], 0)
    for s in range(nslots):
        if model["feeder"][s] > 0:
            g.add(slot_base + s, sink, model["feeder"][s], m2 * price[s])

    order = [source] + [bus_node[b] for b in bus_ids]
    order += [ds_base + i for i in range(nd * nslots)]
    order += [slot_base + s for s in range(nslots)]
    order += [sink]
    g.init_potentials(source, order)
    g.solve(source, sink)

    positions = []
    for s in range(nslots):
        for bus in bus_ids:
            arcs = pos_arcs.get((bus, s))
            if arcs:
                positions.append(arcs)
    lex_refine(g, positions)

    for (bus, s), arcs in pos_arcs.items():
        x[bus][s] = sum(g.orig[a] - g.cap[a] for a in arcs)
    return x


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def reports(model, x, out_dir):
    nslots = model["nslots"]
    slot_name = model["slot_name"]
    price = model["price"]
    buses = model["buses"]
    published = model["published"]
    bus_ids = sorted(buses)

    feeder_by_slot = [0] * nslots
    depot_slot = {d: [0] * nslots for d in DEPOT_ORDER}
    for d in model["depots"]:
        depot_slot.setdefault(d, [0] * nslots)
    class_slot = {"commercial": [0] * nslots, "public": [0] * nslots}

    audit = []
    totals = {}
    for key in list(depot_slot):
        totals[("depot", key)] = {"buses": 0, "energy": 0, "cost": 0, "unmet": 0}
    for key in ("commercial", "public"):
        totals[("class", key)] = {"buses": 0, "energy": 0, "cost": 0, "unmet": 0}

    weighted_unmet = 0
    energy_cost = 0
    moved = 0
    buses_short = 0
    buses_changed = 0

    for bus in bus_ids:
        info = buses[bus]
        row = x[bus]
        delivered = 0
        cost = 0
        charges = []
        changed = False
        for s in range(nslots):
            kwh = row[s]
            pub = published.get((bus, s), 0)
            if kwh != pub:
                changed = True
            if pub > kwh:
                moved += pub - kwh
            if kwh > 0:
                delivered += kwh
                cost += kwh * price[s]
                charges.append({"slot": slot_name[s], "kwh": kwh})
                feeder_by_slot[s] += kwh
                if info["depot"] in depot_slot:
                    depot_slot[info["depot"]][s] += kwh
                if info["class"] in class_slot:
                    class_slot[info["class"]][s] += kwh
        unmet = info["need"] - delivered
        if unmet < 0:
            unmet = 0
        if unmet == 0:
            reason = None
        elif info["need"] > info["max_slot"] * len(info["window"]):
            reason = "window"
        else:
            reason = "supply"
        weighted_unmet += info["weight"] * unmet
        energy_cost += cost
        if unmet > 0:
            buses_short += 1
        if changed:
            buses_changed += 1
        audit.append({
            "bus_id": bus,
            "depot": info["depot"],
            "class": info["class"],
            "need_kwh": info["need"],
            "delivered_kwh": delivered,
            "unmet_kwh": unmet,
            "unmet_reason": reason,
            "changed": changed,
            "charges": charges,
        })
        key = ("depot", info["depot"])
        if key in totals:
            totals[key]["buses"] += 1
            totals[key]["energy"] += delivered
            totals[key]["cost"] += cost
            totals[key]["unmet"] += unmet
        key = ("class", info["class"])
        if key in totals:
            totals[key]["buses"] += 1
            totals[key]["energy"] += delivered
            totals[key]["cost"] += cost
            totals[key]["unmet"] += unmet

    write_json(out_dir, "policy_audit.json",
               {"plan_date": model["plan_date"], "buses": audit})

    for depot in DEPOT_ORDER:
        agg = totals.get(("depot", depot), {"buses": 0, "energy": 0, "cost": 0, "unmet": 0})
        series = depot_slot.get(depot, [0] * nslots)
        write_json(out_dir, "region_%s.json" % depot, {
            "depot": depot,
            "buses": agg["buses"],
            "energy_kwh": agg["energy"],
            "cost_cents": agg["cost"],
            "unmet_kwh": agg["unmet"],
            "slots": [{"slot": slot_name[s], "kwh": series[s],
                       "feeder_kwh": feeder_by_slot[s]} for s in range(nslots)],
        })

    for klass in ("commercial", "public"):
        agg = totals[("class", klass)]
        series = class_slot[klass]
        write_json(out_dir, "segment_%s.json" % klass, {
            "class": klass,
            "buses": agg["buses"],
            "energy_kwh": agg["energy"],
            "cost_cents": agg["cost"],
            "unmet_kwh": agg["unmet"],
            "slots": [{"slot": slot_name[s], "kwh": series[s],
                       "feeder_kwh": feeder_by_slot[s]} for s in range(nslots)],
        })

    write_json(out_dir, "summary.json", {
        "plan_date": model["plan_date"],
        "weighted_unmet_kwh": weighted_unmet,
        "energy_cost_cents": energy_cost,
        "moved_kwh": moved,
        "feeder_peak_kwh": max(feeder_by_slot) if feeder_by_slot else 0,
        "feeder_kwh_by_slot": [{"slot": slot_name[s], "kwh": feeder_by_slot[s]}
                               for s in range(nslots)],
        "buses_planned": len(bus_ids),
        "buses_short": buses_short,
        "buses_changed": buses_changed,
        "records_rejected": len(model["rejected"]),
    })

    write_json(out_dir, "data_quality.json", {
        "plan_date": model["plan_date"],
        "rejected": [{"file": f, "line": ln, "reason": r}
                     for f, ln, r in sorted(model["rejected"],
                                            key=lambda t: (t[0], t[1]))],
    })


def main(argv=None):
    sys.setrecursionlimit(20000)
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    data_dir = args.data or "/app/environment/data/"
    out_dir = args.out or "/app/out/"
    docs_dir = os.path.join(os.path.dirname(data_dir.rstrip("/")), "docs")
    if not os.path.isdir(docs_dir):
        docs_dir = os.path.join(here, "..", "environment", "docs")
    os.makedirs(out_dir, exist_ok=True)

    model = build(data_dir, docs_dir)
    x = plan(model)
    reports(model, x, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
