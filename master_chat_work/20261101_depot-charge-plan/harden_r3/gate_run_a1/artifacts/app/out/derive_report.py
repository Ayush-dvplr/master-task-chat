#!/usr/bin/env python3
"""Overnight depot charging planner.

Builds the day plan defined by docs/charging_rules.md and writes the reports.
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
from fractions import Fraction


class DataError(Exception):
    def __init__(self, filename, message):
        super().__init__("%s: %s" % (filename, message))
        self.filename = filename


# ---------------------------------------------------------------- input ----

def read_text(path, name):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise DataError(name, str(exc))


def read_rows(path, name):
    text = read_text(path, name)
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise DataError(name, "no header row")
    return [(reader.line_num, row) for row in reader]


def read_ini(path, name):
    text = read_text(path, name)
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise DataError(name, str(exc))
    return parser


def read_json(path, name):
    text = read_text(path, name)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise DataError(name, str(exc))


def parse_dt(value, name):
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M")
    except (ValueError, AttributeError):
        raise DataError(name, "bad timestamp %r" % (value,))


def try_dt(value):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%dT%H:%M")
    except (ValueError, AttributeError):
        return None


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def parse_date(value, name):
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        raise DataError(name, "bad date %r" % (value,))


# ------------------------------------------------------------- tariff -----

def time_to_minutes(value):
    hour, minute = value.strip().split(":")
    return int(hour) * 60 + int(minute)


def parse_tariff(path, name):
    text = read_text(path, name)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DataError(name, str(exc))
    versions = []
    for ver in root.iter("version"):
        valid_from = parse_date(ver.get("valid_from"), name)
        valid_to = parse_date(ver.get("valid_to"), name)
        bands = []
        for band in ver.iter("band"):
            try:
                start = time_to_minutes(band.get("from"))
                end = time_to_minutes(band.get("to"))
                cents = int(band.get("cents_per_kwh"))
            except (TypeError, ValueError, AttributeError):
                raise DataError(name, "bad band")
            bands.append((start, end, cents))
        if not bands:
            raise DataError(name, "version without bands")
        versions.append((valid_from, valid_to, bands))
    if not versions:
        raise DataError(name, "no tariff versions")
    return versions


def version_for(versions, day, name):
    for valid_from, valid_to, bands in versions:
        if valid_from <= day <= valid_to:
            return bands
    raise DataError(name, "no tariff version in force on %s" % day)


def band_price(bands, minute, name):
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
    raise DataError(name, "no tariff band for minute %d" % minute)


# -------------------------------------------------------- disruptions -----

TS = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"
CABINET_RE = re.compile(
    r"^\s*[-*]\s*(?P<depot>[^:]+):\s*(?P<count>\d+)\s+cabinets?\s+"
    r"out of service\s+from\s+(?P<start>" + TS + r")\s+to\s+(?P<end>" + TS +
    r")\s*\.?\s*$", re.IGNORECASE)
DERATE_RE = re.compile(
    r"^\s*[-*]\s*from\s+(?P<start>" + TS + r")\s+to\s+(?P<end>" + TS +
    r")\s*:\s*feeder limit\s+(?P<kwh>\d+)\s*kWh per slot\s*\.?\s*$",
    re.IGNORECASE)
EXTRA_RE = re.compile(
    r"^\s*[-*]\s*(?P<bus>[^\s:]+):\s*extra trip on\s+(?P<date>\d{4}-\d{2}-\d{2})"
    r"\s*,\s*(?P<kwh>\d+)\s*kWh\s*\.?\s*$", re.IGNORECASE)


def parse_disruptions(path, name):
    text = read_text(path, name)
    cabinets = []
    derates = []
    extras = []
    for line in text.splitlines():
        match = CABINET_RE.match(line)
        if match:
            cabinets.append((match.group("depot").strip(),
                             int(match.group("count")),
                             parse_dt(match.group("start"), name),
                             parse_dt(match.group("end"), name)))
            continue
        match = DERATE_RE.match(line)
        if match:
            derates.append((parse_dt(match.group("start"), name),
                            parse_dt(match.group("end"), name),
                            int(match.group("kwh"))))
            continue
        match = EXTRA_RE.match(line)
        if match:
            extras.append((match.group("bus"),
                           parse_date(match.group("date"), name),
                           int(match.group("kwh"))))
    return cabinets, derates, extras


# ---------------------------------------------------- min cost flow -------

class MinCostFlow:
    def __init__(self, nodes):
        self.nodes = nodes
        self.graph = [[] for _ in range(nodes)]
        self.to = []
        self.cap = []
        self.cost = []

    def add_edge(self, u, v, cap, cost):
        eid = len(self.to)
        self.to.append(v)
        self.cap.append(cap)
        self.cost.append(cost)
        self.graph[u].append(eid)
        self.to.append(u)
        self.cap.append(0)
        self.cost.append(-cost)
        self.graph[v].append(eid + 1)
        return eid

    def initial_potentials(self, source):
        dist = [None] * self.nodes
        dist[source] = 0
        inqueue = bytearray(self.nodes)
        queue = deque([source])
        inqueue[source] = 1
        to, cap, cost, graph = self.to, self.cap, self.cost, self.graph
        while queue:
            u = queue.popleft()
            inqueue[u] = 0
            du = dist[u]
            for eid in graph[u]:
                if cap[eid] <= 0:
                    continue
                v = to[eid]
                nd = du + cost[eid]
                if dist[v] is None or nd < dist[v]:
                    dist[v] = nd
                    if not inqueue[v]:
                        inqueue[v] = 1
                        queue.append(v)
        return [0 if d is None else d for d in dist]

    def solve(self, source, sink):
        """Min cost circulation by primal-dual: a blocking flow per distance."""
        pot = self.initial_potentials(source)
        to, cap, cost, graph = self.to, self.cap, self.cost, self.graph
        nodes = self.nodes
        while True:
            dist = [None] * nodes
            dist[source] = 0
            heap = [(0, source)]
            while heap:
                d, u = heapq.heappop(heap)
                du = dist[u]
                if du is None or d > du:
                    continue
                pu = pot[u]
                for eid in graph[u]:
                    if cap[eid] <= 0:
                        continue
                    v = to[eid]
                    nd = d + cost[eid] + pu - pot[v]
                    if dist[v] is None or nd < dist[v]:
                        dist[v] = nd
                        heapq.heappush(heap, (nd, v))
            if dist[sink] is None or dist[sink] + pot[sink] - pot[source] >= 0:
                break
            for v in range(nodes):
                if dist[v] is not None:
                    pot[v] += dist[v]
            self.blocking_flow(source, sink, pot)
        return pot

    def blocking_flow(self, source, sink, pot):
        """Max flow from source to sink over arcs of zero reduced cost."""
        to, cap, cost, graph = self.to, self.cap, self.cost, self.graph
        nodes = self.nodes
        while True:
            admissible = [[] for _ in range(nodes)]
            for u in range(nodes):
                pu = pot[u]
                adj = admissible[u]
                for eid in graph[u]:
                    if cap[eid] > 0 and cost[eid] + pu - pot[to[eid]] == 0:
                        adj.append(eid)
            level = [-1] * nodes
            level[source] = 0
            queue = deque([source])
            while queue:
                u = queue.popleft()
                lv = level[u] + 1
                for eid in admissible[u]:
                    v = to[eid]
                    if level[v] < 0:
                        level[v] = lv
                        queue.append(v)
            if level[sink] < 0:
                return
            it = [0] * nodes
            while True:
                # one augmenting path along the level graph
                path = []
                u = source
                while True:
                    if u == sink:
                        break
                    adj = admissible[u]
                    advanced = False
                    while it[u] < len(adj):
                        eid = adj[it[u]]
                        v = to[eid]
                        if cap[eid] > 0 and level[v] == level[u] + 1:
                            path.append(eid)
                            u = v
                            advanced = True
                            break
                        it[u] += 1
                    if advanced:
                        continue
                    if u == source:
                        break
                    level[u] = -1
                    eid = path.pop()
                    u = to[eid ^ 1]
                    it[u] += 1
                if u != sink:
                    break
                delta = min(cap[eid] for eid in path)
                for eid in path:
                    cap[eid] -= delta
                    cap[eid ^ 1] += delta

    def feasible_potentials(self):
        """Potentials giving every residual arc a non-negative reduced cost."""
        dist = [0] * self.nodes
        to, cap, cost, graph = self.to, self.cap, self.cost, self.graph
        inqueue = bytearray([1]) * self.nodes
        queue = deque(range(self.nodes))
        count = [0] * self.nodes
        limit = self.nodes + 2
        while queue:
            u = queue.popleft()
            inqueue[u] = 0
            du = dist[u]
            for eid in graph[u]:
                if cap[eid] <= 0:
                    continue
                v = to[eid]
                nd = du + cost[eid]
                if nd < dist[v]:
                    dist[v] = nd
                    if not inqueue[v]:
                        count[v] += 1
                        if count[v] > limit:
                            raise RuntimeError("negative residual cycle")
                        inqueue[v] = 1
                        queue.append(v)
        return dist


# -------------------------------------------------------------- plan ------

def build_plan(data_dir):
    grid = read_ini(os.path.join(data_dir, "grid.ini"), "grid.ini")
    try:
        plan_date = parse_date(grid["plan"]["plan_date"], "grid.ini")
        first_slot = parse_dt(grid["plan"]["first_slot"], "grid.ini")
        slot_minutes = int(grid["plan"]["slot_minutes"])
        nslots = int(grid["plan"]["slots"])
        feeder_limit = int(grid["feeder"]["feeder_kwh_per_slot"])
    except (KeyError, ValueError) as exc:
        raise DataError("grid.ini", str(exc))
    if slot_minutes <= 0 or nslots <= 0:
        raise DataError("grid.ini", "bad slot definition")

    slot_times = [first_slot + timedelta(minutes=slot_minutes * i)
                  for i in range(nslots)]
    slot_names = [fmt_dt(t) for t in slot_times]
    slot_index = {t: i for i, t in enumerate(slot_times)}
    plan_end = first_slot + timedelta(minutes=slot_minutes * nslots)

    depots_doc = read_json(os.path.join(data_dir, "depots.json"), "depots.json")
    try:
        cabinet_kwh = int(depots_doc["cabinet_kwh_per_slot"])
        depot_names = [d["depot"] for d in depots_doc["depots"]]
        cabinets = {d["depot"]: int(d["cabinets"]) for d in depots_doc["depots"]}
    except (KeyError, TypeError, ValueError) as exc:
        raise DataError("depots.json", str(exc))

    bus_types = read_json(os.path.join(data_dir, "bus_types.json"),
                          "bus_types.json")
    try:
        type_max = {k: int(v["max_kwh_per_slot"]) for k, v in bus_types.items()}
        type_reserve = {k: int(v["reserve_kwh"]) for k, v in bus_types.items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise DataError("bus_types.json", str(exc))

    classes = read_ini(os.path.join(data_dir, "service_classes.ini"),
                       "service_classes.ini")
    try:
        class_weight = {sec: int(classes[sec]["weight"])
                        for sec in classes.sections()}
    except (KeyError, ValueError) as exc:
        raise DataError("service_classes.ini", str(exc))

    contracts_doc = read_json(os.path.join(data_dir, "contracts.json"),
                              "contracts.json")
    try:
        contract_class = {c["contract_id"]: c["class"]
                          for c in contracts_doc["contracts"]}
    except (KeyError, TypeError) as exc:
        raise DataError("contracts.json", str(exc))

    fleet = {}
    for lineno, row in read_rows(os.path.join(data_dir, "fleet_register.csv"),
                                 "fleet_register.csv"):
        vid = (row.get("vehicle_id") or "").strip()
        if vid and vid not in fleet:
            fleet[vid] = row

    versions = parse_tariff(os.path.join(data_dir, "tariff.xml"), "tariff.xml")
    cabinet_outages, derates, extra_trips = parse_disruptions(
        os.path.join(data_dir, "disruption_notice.md"), "disruption_notice.md")

    rejected = []
    plan_date_str = plan_date.isoformat()
    buses = {}
    for lineno, row in read_rows(os.path.join(data_dir, "roster.csv"),
                                 "roster.csv"):
        if (row.get("plan_date") or "").strip() != plan_date_str:
            continue
        bus_id = (row.get("bus_id") or "").strip()
        reason = None
        if bus_id not in fleet:
            reason = "unknown_vehicle"
        elif (fleet[bus_id].get("status") or "").strip() != "active":
            reason = "retired_vehicle"
        elif bus_id in buses:
            reason = "duplicate_roster_row"
        else:
            arrive = try_dt(row.get("arrive"))
            depart = try_dt(row.get("depart"))
            if arrive is None or depart is None:
                reason = "bad_window"
            elif (not arrive < depart) or arrive < first_slot \
                    or depart > plan_end:
                reason = "bad_window"
        if reason is not None:
            rejected.append({"file": "roster.csv", "line": lineno,
                             "reason": reason})
            continue
        btype = (fleet[bus_id].get("type") or "").strip()
        if btype not in type_max:
            raise DataError("bus_types.json", "unknown bus type %r" % btype)
        contract_id = (row.get("contract_id") or "").strip()
        bclass = "commercial"
        if contract_id:
            bclass = contract_class.get(contract_id, "commercial")
        if bclass not in class_weight:
            raise DataError("service_classes.ini", "unknown class %r" % bclass)
        depot = (row.get("depot") or "").strip()
        if depot not in cabinets:
            raise DataError("depots.json", "unknown depot %r" % depot)
        try:
            soc = int((row.get("soc_arrival_kwh") or "").strip())
        except ValueError:
            raise DataError("roster.csv",
                            "bad soc_arrival_kwh on line %d" % lineno)
        buses[bus_id] = {
            "bus_id": bus_id,
            "depot": depot,
            "class": bclass,
            "weight": class_weight[bclass],
            "max": type_max[btype],
            "reserve": type_reserve[btype],
            "soc": soc,
            "window": [i for i, t in enumerate(slot_times)
                       if arrive <= t < depart],
            "pub": {},
        }

    service_date = (plan_date + timedelta(days=1)).isoformat()
    trip_kwh = {}
    text = read_text(os.path.join(data_dir, "trips.jsonl"), "trips.jsonl")
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
            if str(doc["service_date"]).strip() == service_date:
                bus_id = doc["bus_id"]
                trip_kwh[bus_id] = trip_kwh.get(bus_id, 0) + int(doc["kwh"])
        except (ValueError, KeyError, TypeError) as exc:
            raise DataError("trips.jsonl", "line %d: %s" % (lineno, exc))

    extra_kwh = {}
    next_day = plan_date + timedelta(days=1)
    for bus_id, day, kwh in extra_trips:
        if day == next_day:
            extra_kwh[bus_id] = extra_kwh.get(bus_id, 0) + kwh

    for bus in buses.values():
        bus["need"] = max(0, trip_kwh.get(bus["bus_id"], 0)
                          + extra_kwh.get(bus["bus_id"], 0)
                          + bus["reserve"] - bus["soc"])

    plan_bands = version_for(versions, plan_date, "tariff.xml")
    settlements = read_rows(os.path.join(data_dir, "settlements.csv"),
                            "settlements.csv")
    shifts = meter_shifts(settlements, versions, depot_names, slot_minutes,
                          first_slot)
    prices = {}
    for depot in depot_names:
        shift = shifts[depot] * slot_minutes
        prices[depot] = [
            band_price(plan_bands, t.hour * 60 + t.minute + shift, "tariff.xml")
            for t in slot_times]

    depot_cap = {}
    for depot in depot_names:
        out = [0] * nslots
        for name, count, start, end in cabinet_outages:
            if name != depot:
                continue
            for i, t in enumerate(slot_times):
                if start <= t < end:
                    out[i] += count
        depot_cap[depot] = [max(0, cabinets[depot] - out[i]) * cabinet_kwh
                            for i in range(nslots)]
    feeder = [feeder_limit] * nslots
    for start, end, kwh in derates:
        for i, t in enumerate(slot_times):
            if start <= t < end:
                feeder[i] = min(feeder[i], kwh)

    for lineno, row in read_rows(os.path.join(data_dir, "published_plan.csv"),
                                 "published_plan.csv"):
        if (row.get("plan_date") or "").strip() != plan_date_str:
            continue
        bus = buses.get((row.get("bus_id") or "").strip())
        if bus is None:
            continue
        idx = slot_index.get(try_dt(row.get("slot_start")))
        if idx is None or idx not in bus["window"]:
            rejected.append({"file": "published_plan.csv", "line": lineno,
                             "reason": "published_row_outside_window"})
            continue
        try:
            kwh = int((row.get("kwh") or "").strip())
        except ValueError:
            raise DataError("published_plan.csv", "bad kwh on line %d" % lineno)
        bus["pub"][idx] = bus["pub"].get(idx, 0) + kwh

    rejected.sort(key=lambda r: (r["file"], r["line"]))
    plan = solve_plan(buses, depot_names, depot_cap, feeder, prices, nslots)

    return {
        "plan_date": plan_date_str,
        "slot_names": slot_names,
        "nslots": nslots,
        "depot_names": depot_names,
        "buses": buses,
        "prices": prices,
        "plan": plan,
        "rejected": rejected,
    }


def grid_slots(first_slot, slot_minutes, start, end):
    """Slot starts of the plan grid that lie at or after start and before end."""
    offset = (start - first_slot).total_seconds() / 60.0
    index = int(-(-offset // slot_minutes))
    moment = first_slot + timedelta(minutes=slot_minutes * index)
    while moment < end:
        yield moment
        moment += timedelta(minutes=slot_minutes)


def meter_shifts(settlements, versions, depot_names, slot_minutes, first_slot):
    per_day = 1440 // slot_minutes
    rows_by_depot = {d: [] for d in depot_names}
    for lineno, row in settlements:
        depot = (row.get("depot") or "").strip()
        if depot not in rows_by_depot:
            continue
        try:
            start = parse_dt(row.get("start"), "settlements.csv")
            end = parse_dt(row.get("end"), "settlements.csv")
            kwh = int((row.get("kwh") or "").strip())
            cents = int((row.get("cents") or "").strip())
            day = parse_date(row.get("settled_date"), "settlements.csv")
        except (DataError, ValueError):
            raise DataError("settlements.csv", "bad row on line %d" % lineno)
        minutes = []
        for moment in grid_slots(first_slot, slot_minutes, start, end):
            minutes.append(moment.hour * 60 + moment.minute)
        if not minutes:
            continue
        rows_by_depot[depot].append((day, minutes, kwh, cents))

    shifts = {}
    for depot in depot_names:
        rows = rows_by_depot[depot]
        found = None
        for k in range(per_day):
            shift = k * slot_minutes
            ok = True
            for day, minutes, kwh, cents in rows:
                bands = version_for(versions, day, "tariff.xml")
                total = sum(band_price(bands, m + shift, "tariff.xml")
                            for m in minutes)
                if Fraction(kwh * total, len(minutes)) != cents:
                    ok = False
                    break
            if ok:
                found = k
                break
        if found is None:
            raise DataError("settlements.csv",
                            "no meter shift fits depot %s" % depot)
        shifts[depot] = found
    return shifts


def solve_plan(buses, depot_names, depot_cap, feeder, prices, nslots):
    """The day plan of rule 15, as a min cost flow with a lexicographic pass."""
    bus_ids = sorted(buses)
    nb = len(bus_ids)
    nd = len(depot_names)
    depot_pos = {d: i for i, d in enumerate(depot_names)}

    source = 0
    sink = 1
    bus_node = {b: 2 + i for i, b in enumerate(bus_ids)}
    ds_base = 2 + nb
    fs_base = ds_base + nd * nslots
    total_nodes = fs_base + nslots

    max_price = max((max(p) for p in prices.values() if p), default=0)
    total_pub = sum(sum(b["pub"].values()) for b in buses.values())
    total_need = sum(b["need"] for b in buses.values())
    w_moved = 1
    w_cost = total_pub + 1
    w_unmet = w_cost * (total_need * max_price + 2)

    mcf = MinCostFlow(total_nodes)
    pub_arc = {}
    rest_arc = {}
    for bus_id in bus_ids:
        bus = buses[bus_id]
        if bus["need"] > 0 and bus["window"]:
            mcf.add_edge(source, bus_node[bus_id], bus["need"],
                         -w_unmet * bus["weight"])
        cap = bus["max"]
        dpos = depot_pos[bus["depot"]]
        for slot in bus["window"]:
            node = ds_base + dpos * nslots + slot
            price = prices[bus["depot"]][slot]
            matched = min(bus["pub"].get(slot, 0), cap)
            if matched > 0:
                pub_arc[(bus_id, slot)] = mcf.add_edge(
                    bus_node[bus_id], node, matched,
                    price * w_cost - w_moved)
            if cap - matched > 0:
                rest_arc[(bus_id, slot)] = mcf.add_edge(
                    bus_node[bus_id], node, cap - matched, price * w_cost)
    for depot in depot_names:
        dpos = depot_pos[depot]
        for slot in range(nslots):
            cap = depot_cap[depot][slot]
            if cap > 0:
                mcf.add_edge(ds_base + dpos * nslots + slot,
                             fs_base + slot, cap, 0)
    for slot in range(nslots):
        if feeder[slot] > 0:
            mcf.add_edge(fs_base + slot, sink, feeder[slot], 0)

    pot = mcf.solve(source, sink)
    # closing the circuit lets the final pass trade energy between buses
    mcf.add_edge(sink, source, total_need + 1, 0)
    lexicographic_pass(mcf, pot, bus_ids, buses, pub_arc, rest_arc, nslots,
                       ds_base, depot_pos, bus_node)

    plan = {b: {} for b in bus_ids}
    for arcs in (pub_arc, rest_arc):
        for (bus_id, slot), eid in arcs.items():
            flow = mcf.cap[eid ^ 1]
            if flow:
                plan[bus_id][slot] = plan[bus_id].get(slot, 0) + flow
    return plan


def lexicographic_pass(mcf, pot, bus_ids, buses, pub_arc, rest_arc, nslots,
                       ds_base, depot_pos, bus_node):
    """Shift energy inside the optimal set to the lexicographically best plan."""
    to, cap, cost, graph = mcf.to, mcf.cap, mcf.cost, mcf.graph
    nedges = len(to)
    rc = [cost[e] + pot[to[e ^ 1]] - pot[to[e]] for e in range(nedges)]
    if any(rc[e] < 0 for e in range(nedges) if cap[e] > 0):
        pot = mcf.feasible_potentials()
        rc = [cost[e] + pot[to[e ^ 1]] - pot[to[e]] for e in range(nedges)]
    zero_adj = [[eid for eid in graph[u] if rc[eid] == 0]
                for u in range(mcf.nodes)]
    blocked = bytearray(nedges)

    slots_of = {}
    for bus_id in bus_ids:
        for slot in buses[bus_id]["window"]:
            slots_of.setdefault(slot, []).append(bus_id)

    visited = [-1] * mcf.nodes
    prev_edge = [-1] * mcf.nodes
    stamp = 0

    for slot in range(nslots):
        for bus_id in slots_of.get(slot, ()):
            arcs = [a for a in (pub_arc.get((bus_id, slot)),
                                rest_arc.get((bus_id, slot))) if a is not None]
            free = [a for a in arcs if rc[a] == 0 and cap[a] > 0]
            for a in arcs:
                blocked[a] = 1
                blocked[a ^ 1] = 1
            if not free:
                continue
            limit = sum(cap[a] for a in free)
            src = ds_base + depot_pos[buses[bus_id]["depot"]] * nslots + slot
            dst = bus_node[bus_id]
            while limit > 0:
                stamp += 1
                visited[src] = stamp
                queue = deque([src])
                found = False
                while queue:
                    u = queue.popleft()
                    if u == dst:
                        found = True
                        break
                    for eid in zero_adj[u]:
                        if cap[eid] <= 0 or blocked[eid]:
                            continue
                        v = to[eid]
                        if visited[v] != stamp:
                            visited[v] = stamp
                            prev_edge[v] = eid
                            queue.append(v)
                if not found:
                    break
                delta = limit
                v = dst
                while v != src:
                    eid = prev_edge[v]
                    if cap[eid] < delta:
                        delta = cap[eid]
                    v = to[eid ^ 1]
                v = dst
                while v != src:
                    eid = prev_edge[v]
                    cap[eid] -= delta
                    cap[eid ^ 1] += delta
                    v = to[eid ^ 1]
                left = delta
                for a in free:
                    if left <= 0:
                        break
                    take = cap[a] if cap[a] < left else left
                    cap[a] -= take
                    cap[a ^ 1] += take
                    left -= take
                limit -= delta
                free = [a for a in free if cap[a] > 0]
                if not free:
                    break


# ----------------------------------------------------------- reports ------

def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def write_reports(model, out_dir):
    plan_date = model["plan_date"]
    slot_names = model["slot_names"]
    nslots = model["nslots"]
    buses = model["buses"]
    plan = model["plan"]
    prices = model["prices"]
    depot_names = model["depot_names"]

    bus_ids = sorted(buses)
    feeder_by_slot = [0] * nslots
    depot_slot = {d: [0] * nslots for d in depot_names}
    class_slot = {}
    for bus_id in bus_ids:
        bus = buses[bus_id]
        class_slot.setdefault(bus["class"], [0] * nslots)
        for slot, kwh in plan[bus_id].items():
            feeder_by_slot[slot] += kwh
            depot_slot[bus["depot"]][slot] += kwh
            class_slot[bus["class"]][slot] += kwh

    audit_buses = []
    weighted_unmet = 0
    energy_cost = 0
    moved = 0
    buses_short = 0
    buses_changed = 0
    depot_energy = {d: 0 for d in depot_names}
    depot_unmet = {d: 0 for d in depot_names}
    depot_cost = {d: 0 for d in depot_names}
    depot_buses = {d: 0 for d in depot_names}
    class_energy = {}
    class_unmet = {}
    class_cost = {}
    class_buses = {}

    for bus_id in bus_ids:
        bus = buses[bus_id]
        depot = bus["depot"]
        bclass = bus["class"]
        charges = plan[bus_id]
        delivered = sum(charges.values())
        unmet = bus["need"] - delivered
        cost = sum(prices[depot][slot] * kwh for slot, kwh in charges.items())
        moved_bus = 0
        changed = False
        for slot in set(bus["pub"]) | set(charges):
            planned = charges.get(slot, 0)
            published = bus["pub"].get(slot, 0)
            if planned != published:
                changed = True
            if published > planned:
                moved_bus += published - planned
        if unmet == 0:
            reason = None
        elif bus["need"] > bus["max"] * len(bus["window"]):
            reason = "window"
        else:
            reason = "supply"
        audit_buses.append({
            "bus_id": bus_id,
            "depot": depot,
            "class": bclass,
            "need_kwh": bus["need"],
            "delivered_kwh": delivered,
            "unmet_kwh": unmet,
            "unmet_reason": reason,
            "changed": changed,
            "charges": [{"slot": slot_names[slot], "kwh": charges[slot]}
                        for slot in sorted(charges) if charges[slot] > 0],
        })
        weighted_unmet += bus["weight"] * unmet
        energy_cost += cost
        moved += moved_bus
        if unmet > 0:
            buses_short += 1
        if changed:
            buses_changed += 1
        depot_energy[depot] += delivered
        depot_unmet[depot] += unmet
        depot_cost[depot] += cost
        depot_buses[depot] += 1
        class_energy[bclass] = class_energy.get(bclass, 0) + delivered
        class_unmet[bclass] = class_unmet.get(bclass, 0) + unmet
        class_cost[bclass] = class_cost.get(bclass, 0) + cost
        class_buses[bclass] = class_buses.get(bclass, 0) + 1

    write_json(os.path.join(out_dir, "policy_audit.json"),
               {"plan_date": plan_date, "buses": audit_buses})

    for depot in depot_names:
        write_json(os.path.join(out_dir, "region_%s.json" % depot), {
            "depot": depot,
            "buses": depot_buses[depot],
            "energy_kwh": depot_energy[depot],
            "cost_cents": depot_cost[depot],
            "unmet_kwh": depot_unmet[depot],
            "slots": [{"slot": slot_names[i],
                       "kwh": depot_slot[depot][i],
                       "feeder_kwh": feeder_by_slot[i]}
                      for i in range(nslots)],
        })

    for bclass in ("commercial", "public"):
        slots = class_slot.get(bclass, [0] * nslots)
        write_json(os.path.join(out_dir, "segment_%s.json" % bclass), {
            "class": bclass,
            "buses": class_buses.get(bclass, 0),
            "energy_kwh": class_energy.get(bclass, 0),
            "cost_cents": class_cost.get(bclass, 0),
            "unmet_kwh": class_unmet.get(bclass, 0),
            "slots": [{"slot": slot_names[i],
                       "kwh": slots[i],
                       "feeder_kwh": feeder_by_slot[i]}
                      for i in range(nslots)],
        })

    write_json(os.path.join(out_dir, "summary.json"), {
        "plan_date": plan_date,
        "weighted_unmet_kwh": weighted_unmet,
        "energy_cost_cents": energy_cost,
        "moved_kwh": moved,
        "feeder_peak_kwh": max(feeder_by_slot) if feeder_by_slot else 0,
        "feeder_kwh_by_slot": [{"slot": slot_names[i], "kwh": feeder_by_slot[i]}
                               for i in range(nslots)],
        "buses_planned": len(bus_ids),
        "buses_short": buses_short,
        "buses_changed": buses_changed,
        "records_rejected": len(model["rejected"]),
    })

    write_json(os.path.join(out_dir, "data_quality.json"),
               {"plan_date": plan_date, "rejected": model["rejected"]})


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="/app/data")
    parser.add_argument("--out", default="/app/out")
    args = parser.parse_args(argv)
    try:
        model = build_plan(args.data)
    except DataError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    os.makedirs(args.out, exist_ok=True)
    write_reports(model, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
