#!/usr/bin/env python3
"""Overnight depot charging: build the day plan and write the planning reports.

Usage:
    python3 derive_report.py --data <data folder> --out <output folder>

Implements the rules in <data folder>/docs/charging_rules.md.
Python 3 standard library only.
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

TIME_FMT = "%Y-%m-%dT%H:%M"


class DataError(Exception):
    """Raised when a required input file is missing or cannot be read."""

    def __init__(self, filename, detail=""):
        self.filename = filename
        self.detail = detail
        msg = "cannot read %s" % filename
        if detail:
            msg += ": %s" % detail
        super(DataError, self).__init__(msg)


# ---------------------------------------------------------------- helpers

def parse_stamp(text, filename):
    try:
        return datetime.datetime.strptime(text.strip(), TIME_FMT)
    except Exception as exc:
        raise DataError(filename, "bad timestamp %r (%s)" % (text, exc))


def parse_clock(text, filename):
    """'HH:MM' -> minutes since midnight."""
    try:
        hh, mm = text.strip().split(":")
        val = int(hh) * 60 + int(mm)
    except Exception as exc:
        raise DataError(filename, "bad time of day %r (%s)" % (text, exc))
    if not 0 <= val <= 1440:
        raise DataError(filename, "time of day out of range %r" % (text,))
    return val


def read_text(path, filename):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except Exception as exc:
        raise DataError(filename, str(exc))


def read_json(path, filename):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        raise DataError(filename, str(exc))


def read_ini(path, filename):
    parser = configparser.ConfigParser()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parser.read_file(handle)
    except Exception as exc:
        raise DataError(filename, str(exc))
    return parser


def read_csv_rows(path, filename, required):
    """Return (rows, line_numbers) with the header counted as line 1."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise DataError(filename, "empty file")
            missing = [c for c in required if c not in reader.fieldnames]
            if missing:
                raise DataError(filename, "missing columns %s" % ",".join(missing))
            rows = []
            lines = []
            line = 1
            for row in reader:
                line += 1
                rows.append(row)
                lines.append(line)
    except DataError:
        raise
    except Exception as exc:
        raise DataError(filename, str(exc))
    return rows, lines


def as_int(value, filename, what):
    try:
        return int(str(value).strip())
    except Exception as exc:
        raise DataError(filename, "bad %s %r (%s)" % (what, value, exc))


# ---------------------------------------------------------------- inputs

class Plan(object):
    pass


def load_grid(data_dir):
    name = "grid.ini"
    parser = read_ini(os.path.join(data_dir, name), name)
    try:
        plan_date = parser.get("plan", "plan_date").strip()
        first_slot = parser.get("plan", "first_slot").strip()
        slot_minutes = parser.getint("plan", "slot_minutes")
        slots = parser.getint("plan", "slots")
        feeder = parser.getint("feeder", "feeder_kwh_per_slot")
    except Exception as exc:
        raise DataError(name, str(exc))
    if slot_minutes <= 0 or slots <= 0:
        raise DataError(name, "slot_minutes and slots must be positive")
    plan = Plan()
    plan.plan_date = plan_date
    plan.slot_minutes = slot_minutes
    plan.nslots = slots
    plan.first = parse_stamp(first_slot, name)
    plan.step = datetime.timedelta(minutes=slot_minutes)
    plan.times = [plan.first + i * plan.step for i in range(slots)]
    plan.names = [t.strftime(TIME_FMT) for t in plan.times]
    plan.end = plan.first + slots * plan.step
    plan.feeder_base = feeder
    try:
        datetime.datetime.strptime(plan_date, "%Y-%m-%d")
    except Exception as exc:
        raise DataError(name, "bad plan_date %r (%s)" % (plan_date, exc))
    return plan


def load_classes(data_dir):
    name = "service_classes.ini"
    parser = read_ini(os.path.join(data_dir, name), name)
    weights = {}
    for section in parser.sections():
        try:
            weights[section] = parser.getint(section, "weight")
        except Exception as exc:
            raise DataError(name, str(exc))
    if "commercial" not in weights or "public" not in weights:
        raise DataError(name, "missing commercial/public weight")
    return weights


def load_types(data_dir):
    name = "bus_types.json"
    raw = read_json(os.path.join(data_dir, name), name)
    if not isinstance(raw, dict):
        raise DataError(name, "expected an object")
    types = {}
    for key, val in raw.items():
        try:
            types[key] = (int(val["max_kwh_per_slot"]), int(val["reserve_kwh"]))
        except Exception as exc:
            raise DataError(name, "bad entry %r (%s)" % (key, exc))
    return types


def load_depots(data_dir):
    name = "depots.json"
    raw = read_json(os.path.join(data_dir, name), name)
    try:
        per_cabinet = int(raw["cabinet_kwh_per_slot"])
        depots = []
        cabinets = {}
        for entry in raw["depots"]:
            depots.append(entry["depot"])
            cabinets[entry["depot"]] = int(entry["cabinets"])
    except Exception as exc:
        raise DataError(name, str(exc))
    if not depots:
        raise DataError(name, "no depots listed")
    return per_cabinet, depots, cabinets


def load_contracts(data_dir):
    name = "contracts.json"
    raw = read_json(os.path.join(data_dir, name), name)
    try:
        entries = raw["contracts"]
        out = {}
        for entry in entries:
            out[str(entry["contract_id"]).strip()] = str(entry["class"]).strip()
    except Exception as exc:
        raise DataError(name, str(exc))
    return out


def load_fleet(data_dir):
    name = "fleet_register.csv"
    rows, _ = read_csv_rows(os.path.join(data_dir, name), name,
                            ["vehicle_id", "type", "status"])
    fleet = {}
    for row in rows:
        fleet[row["vehicle_id"].strip()] = (row["type"].strip(), row["status"].strip())
    return fleet


def load_trips(data_dir, service_date):
    name = "trips.jsonl"
    text = read_text(os.path.join(data_dir, name), name)
    need = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if str(rec["service_date"]).strip() == service_date:
                bus = str(rec["bus_id"]).strip()
                need[bus] = need.get(bus, 0) + int(rec["kwh"])
        except Exception as exc:
            raise DataError(name, "line %d (%s)" % (lineno, exc))
    return need


def load_tariff(data_dir):
    name = "tariff.xml"
    try:
        root = ET.fromstring(read_text(os.path.join(data_dir, name), name))
    except DataError:
        raise
    except Exception as exc:
        raise DataError(name, str(exc))
    versions = []
    for version in root.findall("version"):
        valid_from = (version.get("valid_from") or "").strip()
        valid_to = (version.get("valid_to") or "").strip()
        bands = []
        for band in version.findall("band"):
            start = parse_clock(band.get("from") or "", name)
            stop = parse_clock(band.get("to") or "", name)
            cents = as_int(band.get("cents_per_kwh"), name, "cents_per_kwh")
            bands.append((start, stop, cents))
        if not valid_from or not valid_to or not bands:
            raise DataError(name, "incomplete version")
        versions.append((valid_from, valid_to, bands))
    if not versions:
        raise DataError(name, "no tariff versions")
    return versions


def version_for(versions, date_text):
    hits = [v for v in versions if v[0] <= date_text <= v[1]]
    if len(hits) != 1:
        raise DataError("tariff.xml",
                        "%d versions in force on %s" % (len(hits), date_text))
    return hits[0][2]


def band_price(bands, minute):
    minute %= 1440
    for start, stop, cents in bands:
        if start < stop:
            if start <= minute < stop:
                return cents
        elif start > stop:
            if minute >= start or minute < stop:
                return cents
        else:
            return cents
    raise DataError("tariff.xml", "no band covers minute %d" % minute)


# Careful shift search: every whole-slot clock shift k in 0..95 (rule 12 family).
def meter_candidates(slot_minutes):
    out = []
    for k in range(1440 // slot_minutes):
        def shifted(bands, minute, k=k):
            return band_price(bands, minute + k * slot_minutes)
        out.append(("shift_%d" % k, shifted))
    return out


def load_settlements(data_dir):
    name = "settlements.csv"
    rows, lines = read_csv_rows(os.path.join(data_dir, name), name,
                                ["settled_date", "depot", "start", "end", "kwh", "cents"])
    out = []
    for row, lineno in zip(rows, lines):
        start = parse_stamp(row["start"], name)
        stop = parse_stamp(row["end"], name)
        kwh = as_int(row["kwh"], name, "kwh")
        cents = as_int(row["cents"], name, "cents")
        out.append((row["settled_date"].strip(), row["depot"].strip(), start, stop,
                    kwh, cents, lineno))
    if not out:
        raise DataError(name, "no settled sessions")
    return out


def pick_meters(settlements, versions, plan, depots):
    """Rule 12: find, per depot, the one way of applying a tariff that bills
    every settled session of that depot exactly its cents."""
    name = "settlements.csv"
    candidates = meter_candidates(plan.slot_minutes)
    per_depot = {}
    for depot in depots:
        per_depot[depot] = [True] * len(candidates)
    seen = set()
    for settled_date, depot, start, stop, kwh, cents, lineno in settlements:
        if depot not in per_depot:
            continue
        seen.add(depot)
        minutes = int((stop - start).total_seconds() // 60)
        if minutes <= 0 or minutes % plan.slot_minutes:
            raise DataError(name, "line %d: session is not a whole number of slots"
                            % lineno)
        count = minutes // plan.slot_minutes
        bands = version_for(versions, settled_date)
        slot_minutes_of_day = []
        cursor = start
        for _ in range(count):
            slot_minutes_of_day.append(cursor.hour * 60 + cursor.minute)
            cursor += plan.step
        for idx, (_, func) in enumerate(candidates):
            if not per_depot[depot][idx]:
                continue
            total = sum(func(bands, m) for m in slot_minutes_of_day)
            if kwh * total != cents * count:
                per_depot[depot][idx] = False
    chosen = {}
    for depot in depots:
        fits = [candidates[i][0] for i, ok in enumerate(per_depot[depot]) if ok]
        if depot not in seen:
            chosen[depot] = candidates[0]
            continue
        if not fits:
            raise DataError(name, "no tariff application fits depot %s" % depot)
        if len(fits) != 1:
            raise DataError(name, "%d shifts fit depot %s" % (len(fits), depot))
        index = [c[0] for c in candidates].index(fits[0])
        chosen[depot] = candidates[index]
    return chosen


def load_disruption(data_dir, plan):
    name = "disruption_notice.md"
    text = read_text(os.path.join(data_dir, name), name)
    cabinet_re = re.compile(
        r"^[-*]\s*(?P<depot>[^:]+):\s*(?P<count>\d+)\s+cabinets?\s+out of service\s+"
        r"from\s+(?P<start>\S+)\s+to\s+(?P<stop>\S+)\s*$", re.I)
    feeder_re = re.compile(
        r"^[-*]\s*from\s+(?P<start>\S+)\s+to\s+(?P<stop>\S+)\s*:\s*feeder limit\s+"
        r"(?P<kwh>\d+)\s*kwh per slot\s*$", re.I)
    extra_re = re.compile(
        r"^[-*]\s*(?P<bus>\S+?)\s*:\s*extra trip on\s+(?P<date>[0-9-]+)\s*,\s*"
        r"(?P<kwh>\d+)\s*kwh\s*$", re.I)
    section = None
    outages = {}
    derate = {}
    extras = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            head = line.lstrip("#").strip().lower()
            if "cabinet" in head:
                section = "cabinet"
            elif "feeder" in head:
                section = "feeder"
            elif "extra" in head:
                section = "extra"
            else:
                section = None
            continue
        if not line or not line[0] in "-*":
            continue
        if section == "cabinet":
            match = cabinet_re.match(line)
            if not match:
                raise DataError(name, "cannot read cabinet outage %r" % line)
            depot = match.group("depot").strip()
            count = int(match.group("count"))
            start = parse_stamp(match.group("start"), name)
            stop = parse_stamp(match.group("stop"), name)
            for idx, when in enumerate(plan.times):
                if start <= when < stop:
                    key = (depot, idx)
                    outages[key] = outages.get(key, 0) + count
        elif section == "feeder":
            match = feeder_re.match(line)
            if not match:
                raise DataError(name, "cannot read feeder derating %r" % line)
            start = parse_stamp(match.group("start"), name)
            stop = parse_stamp(match.group("stop"), name)
            limit = int(match.group("kwh"))
            for idx, when in enumerate(plan.times):
                if start <= when < stop:
                    derate[idx] = limit
        elif section == "extra":
            match = extra_re.match(line)
            if not match:
                raise DataError(name, "cannot read extra trip %r" % line)
            key = (match.group("bus").strip(), match.group("date").strip())
            extras[key] = extras.get(key, 0) + int(match.group("kwh"))
    return outages, derate, extras


# ---------------------------------------------------------------- the fleet

class Bus(object):
    __slots__ = ("bus_id", "depot", "cls", "weight", "need", "max_slot",
                 "first", "last", "slots", "delivered", "charges")


def build_buses(data_dir, plan, fleet, types, contracts, weights, trip_kwh,
                extras, depots):
    name = "roster.csv"
    rows, lines = read_csv_rows(os.path.join(data_dir, name), name,
                                ["plan_date", "bus_id", "depot", "arrive", "depart",
                                 "soc_arrival_kwh", "contract_id"])
    next_date = (datetime.datetime.strptime(plan.plan_date, "%Y-%m-%d")
                 + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    rejected = []
    accepted = {}
    order = []
    for row, lineno in zip(rows, lines):
        if row["plan_date"].strip() != plan.plan_date:
            continue
        bus_id = row["bus_id"].strip()
        if bus_id not in fleet:
            rejected.append((name, lineno, "unknown_vehicle"))
            continue
        bus_type, status = fleet[bus_id]
        if status != "active":
            rejected.append((name, lineno, "retired_vehicle"))
            continue
        if bus_id in accepted:
            rejected.append((name, lineno, "duplicate_roster_row"))
            continue
        arrive = parse_stamp(row["arrive"], name)
        depart = parse_stamp(row["depart"], name)
        if not arrive < depart or arrive < plan.first or depart > plan.end:
            rejected.append((name, lineno, "bad_window"))
            continue
        if bus_type not in types:
            raise DataError("bus_types.json", "unknown type %r" % bus_type)
        max_slot, reserve = types[bus_type]
        bus = Bus()
        bus.bus_id = bus_id
        bus.depot = row["depot"].strip()
        contract = row["contract_id"].strip()
        bus.cls = contracts.get(contract, "commercial") if contract else "commercial"
        if bus.cls not in weights:
            bus.cls = "commercial"
        bus.weight = weights[bus.cls]
        bus.max_slot = max_slot
        need = (trip_kwh.get(bus_id, 0) + extras.get((bus_id, next_date), 0)
                + reserve - as_int(row["soc_arrival_kwh"], name, "soc_arrival_kwh"))
        bus.need = need if need > 0 else 0
        window = [i for i in range(plan.nslots) if arrive <= plan.times[i] < depart]
        bus.slots = window
        bus.first = window[0] if window else None
        bus.last = window[-1] if window else None
        bus.delivered = 0
        bus.charges = {}
        accepted[bus_id] = bus
        order.append(bus)
        if bus.depot not in depots:
            raise DataError(name, "line %d: unknown depot %r" % (lineno, bus.depot))
    return accepted, order, rejected


def load_published(data_dir, plan, accepted):
    name = "published_plan.csv"
    rows, lines = read_csv_rows(os.path.join(data_dir, name), name,
                                ["plan_date", "bus_id", "slot_start", "kwh"])
    published = {}
    rejected = []
    index = {}
    for i, label in enumerate(plan.names):
        index[label] = i
    for row, lineno in zip(rows, lines):
        if row["plan_date"].strip() != plan.plan_date:
            continue
        bus_id = row["bus_id"].strip()
        label = row["slot_start"].strip()
        parse_stamp(label, name)
        kwh = as_int(row["kwh"], name, "kwh")
        bus = accepted.get(bus_id)
        slot = index.get(label)
        if bus is None or slot is None or slot not in bus.slots:
            rejected.append((name, lineno, "published_row_outside_window"))
            continue
        key = (bus_id, slot)
        published[key] = published.get(key, 0) + kwh
    return published, rejected


# ---------------------------------------------------------------- the plan

INF = float("inf")


class Network(object):
    def __init__(self, nodes):
        self.graph = [[] for _ in range(nodes)]
        self.frm = []
        self.to = []
        self.cap = []
        self.cost = []
        self.nodes = nodes

    def add(self, u, v, cap, cost):
        eid = len(self.to)
        self.frm.append(u)
        self.to.append(v)
        self.cap.append(cap)
        self.cost.append(cost)
        self.graph[u].append(eid)
        self.frm.append(v)
        self.to.append(u)
        self.cap.append(0)
        self.cost.append(-cost)
        self.graph[v].append(eid + 1)
        return eid


def build_network(buses, plan, depots, depot_cap, feeder_cap, price, published,
                  bus_index):
    nb = len(buses)
    nslots = plan.nslots
    ndepots = len(depots)
    depot_index = {d: i for i, d in enumerate(depots)}
    base_ds = 1 + nb
    base_f = base_ds + ndepots * nslots
    sink = base_f + nslots
    net = Network(sink + 1)

    total_pub = sum(published.values())
    max_price = max(max(row) for row in price.values()) if price else 0
    reach = 0
    for bus in buses:
        reach += min(bus.need, bus.max_slot * len(bus.slots))
    k_cost = total_pub + 1
    k_weight = k_cost * (max_price * reach + 1) + total_pub + 1

    for bus in buses:
        if bus.need > 0 and bus.slots:
            net.add(0, 1 + bus_index[bus.bus_id], bus.need, 0)
    pos_edges = {}
    for bus in buses:
        if bus.need <= 0 or not bus.slots:
            continue
        bnode = 1 + bus_index[bus.bus_id]
        didx = depot_index[bus.depot]
        row = price[bus.depot]
        for slot in bus.slots:
            dsnode = base_ds + didx * nslots + slot
            base = -k_weight * bus.weight + k_cost * row[slot]
            bonus_cap = published.get((bus.bus_id, slot), 0)
            if bonus_cap > bus.max_slot:
                bonus_cap = bus.max_slot
            pair = [-1, -1]
            if bonus_cap > 0:
                pair[0] = net.add(bnode, dsnode, bonus_cap, base - 1)
            rest = bus.max_slot - bonus_cap
            if rest > 0:
                pair[1] = net.add(bnode, dsnode, rest, base)
            pos_edges[(bus.bus_id, slot)] = pair
    for depot, didx in depot_index.items():
        for slot in range(nslots):
            cap = depot_cap[depot][slot]
            if cap > 0:
                net.add(base_ds + didx * nslots + slot, base_f + slot, cap, 0)
    for slot in range(nslots):
        if feeder_cap[slot] > 0:
            net.add(base_f + slot, sink, feeder_cap[slot], 0)
    return net, pos_edges, sink


def initial_potentials(net, source):
    """Shortest path in the forward DAG (nodes are numbered topologically)."""
    pot = [INF] * net.nodes
    pot[source] = 0
    for node in range(net.nodes):
        if pot[node] is INF or pot[node] == INF:
            continue
        base = pot[node]
        for eid in net.graph[node]:
            if net.cap[eid] <= 0:
                continue
            nxt = net.to[eid]
            val = base + net.cost[eid]
            if val < pot[nxt]:
                pot[nxt] = val
    return pot


def min_cost_flow(net, source, sink):
    pot = initial_potentials(net, source)
    reach_max = max(p for p in pot if p != INF)
    for node in range(net.nodes):
        if pot[node] == INF:
            pot[node] = reach_max
    to = net.to
    cap = net.cap
    cost = net.cost
    graph = net.graph
    while True:
        dist = [INF] * net.nodes
        prev = [-1] * net.nodes
        dist[source] = 0
        heap = [(0, source)]
        done = [False] * net.nodes
        while heap:
            d, node = heapq.heappop(heap)
            if done[node]:
                continue
            done[node] = True
            pnode = pot[node]
            for eid in graph[node]:
                if cap[eid] <= 0:
                    continue
                nxt = to[eid]
                if done[nxt]:
                    continue
                nd = d + cost[eid] + pnode - pot[nxt]
                if nd < dist[nxt]:
                    dist[nxt] = nd
                    prev[nxt] = eid
                    heapq.heappush(heap, (nd, nxt))
        if dist[sink] == INF:
            break
        far = max(dist[n] for n in range(net.nodes) if dist[n] != INF)
        for node in range(net.nodes):
            pot[node] += dist[node] if dist[node] != INF else far
        delta = INF
        node = sink
        while node != source:
            eid = prev[node]
            if cap[eid] < delta:
                delta = cap[eid]
            node = net.frm[eid]
        node = sink
        while node != source:
            eid = prev[node]
            cap[eid] -= delta
            cap[eid ^ 1] += delta
            node = net.frm[eid]
    return pot


def lexicographic_polish(net, pos_edges, pot, plan, buses, bus_index):
    """Among the plans with the same optimal cost pick the one whose kWh list,
    read slot by slot and then by bus id, is greatest."""
    to = net.to
    frm = net.frm
    cap = net.cap
    cost = net.cost
    graph = net.graph
    blocked = bytearray(len(to))
    by_slot = [[] for _ in range(plan.nslots)]
    for bus in sorted(buses, key=lambda b: b.bus_id):
        for slot in bus.slots:
            if (bus.bus_id, slot) in pos_edges:
                by_slot[slot].append(bus)

    def reduced(eid):
        return cost[eid] + pot[frm[eid]] - pot[to[eid]]

    for slot in range(plan.nslots):
        for bus in by_slot[slot]:
            pair = pos_edges[(bus.bus_id, slot)]
            target = 1 + bus_index[bus.bus_id]
            for eid in pair:
                if eid >= 0:
                    blocked[eid] = 1
                    blocked[eid ^ 1] = 1
            while True:
                use = -1
                for eid in pair:
                    if eid >= 0 and cap[eid] > 0 and reduced(eid) == 0:
                        use = eid
                        break
                if use < 0:
                    break
                start = to[use]
                prev = {start: -1}
                queue = [start]
                found = start == target
                head = 0
                while head < len(queue) and not found:
                    node = queue[head]
                    head += 1
                    for eid in graph[node]:
                        if cap[eid] <= 0 or blocked[eid]:
                            continue
                        nxt = to[eid]
                        if nxt in prev:
                            continue
                        if reduced(eid) != 0:
                            continue
                        prev[nxt] = eid
                        if nxt == target:
                            found = True
                            break
                        queue.append(nxt)
                if not found:
                    break
                delta = cap[use]
                node = target
                while node != start:
                    eid = prev[node]
                    if cap[eid] < delta:
                        delta = cap[eid]
                    node = frm[eid]
                cap[use] -= delta
                cap[use ^ 1] += delta
                node = target
                while node != start:
                    eid = prev[node]
                    cap[eid] -= delta
                    cap[eid ^ 1] += delta
                    node = frm[eid]


# ---------------------------------------------------------------- reports

def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def slot_rows(plan, values, feeder):
    return [{"slot": plan.names[i], "kwh": values[i], "feeder_kwh": feeder[i]}
            for i in range(plan.nslots)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the depot charging day plan.")
    parser.add_argument("--data", default="/app/data")
    parser.add_argument("--out", default="/app/out")
    args = parser.parse_args(argv)
    data_dir = args.data
    out_dir = args.out

    plan = load_grid(data_dir)
    weights = load_classes(data_dir)
    types = load_types(data_dir)
    per_cabinet, depots, cabinets = load_depots(data_dir)
    contracts = load_contracts(data_dir)
    fleet = load_fleet(data_dir)
    versions = load_tariff(data_dir)
    read_text(os.path.join(data_dir, "docs", "charging_rules.md"),
              os.path.join("docs", "charging_rules.md"))
    next_date = (datetime.datetime.strptime(plan.plan_date, "%Y-%m-%d")
                 + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    trip_kwh = load_trips(data_dir, next_date)
    outages, derate, extras = load_disruption(data_dir, plan)
    settlements = load_settlements(data_dir)
    meters = pick_meters(settlements, versions, plan, depots)

    bands = version_for(versions, plan.plan_date)
    price = {}
    for depot in depots:
        func = meters[depot][1]
        price[depot] = [func(bands, t.hour * 60 + t.minute) for t in plan.times]

    accepted, order, rejected = build_buses(data_dir, plan, fleet, types, contracts,
                                            weights, trip_kwh, extras, depots)
    published, pub_rejected = load_published(data_dir, plan, accepted)
    rejected = rejected + pub_rejected

    depot_cap = {}
    for depot in depots:
        row = []
        for slot in range(plan.nslots):
            live = cabinets[depot] - outages.get((depot, slot), 0)
            if live < 0:
                live = 0
            row.append(live * per_cabinet)
        depot_cap[depot] = row
    feeder_cap = [derate.get(slot, plan.feeder_base) for slot in range(plan.nslots)]

    buses = sorted(order, key=lambda b: b.bus_id)
    bus_index = {bus.bus_id: i for i, bus in enumerate(buses)}
    net, pos_edges, sink = build_network(buses, plan, depots, depot_cap, feeder_cap,
                                         price, published, bus_index)
    orig = list(net.cap)
    pot = min_cost_flow(net, 0, sink)
    lexicographic_polish(net, pos_edges, pot, plan, buses, bus_index)

    flow = {}
    for key, pair in pos_edges.items():
        total = 0
        for eid in pair:
            if eid >= 0:
                total += orig[eid] - net.cap[eid]
        if total:
            flow[key] = total
    for bus in buses:
        bus.charges = {}
        bus.delivered = 0
    for (bus_id, slot), kwh in flow.items():
        bus = accepted[bus_id]
        bus.charges[slot] = kwh
        bus.delivered += kwh

    depot_energy = {d: [0] * plan.nslots for d in depots}
    class_energy = {c: [0] * plan.nslots for c in weights}
    feeder_by_slot = [0] * plan.nslots
    depot_cost = {d: 0 for d in depots}
    class_cost = {c: 0 for c in weights}
    depot_unmet = {d: 0 for d in depots}
    class_unmet = {c: 0 for c in weights}
    depot_buses = {d: 0 for d in depots}
    class_buses = {c: 0 for c in weights}
    weighted_unmet = 0
    total_cost = 0
    buses_short = 0
    buses_changed = 0
    audit = []
    for bus in buses:
        unmet = bus.need - bus.delivered
        weighted_unmet += bus.weight * unmet
        depot_buses[bus.depot] += 1
        class_buses[bus.cls] = class_buses.get(bus.cls, 0) + 1
        depot_unmet[bus.depot] += unmet
        class_unmet[bus.cls] = class_unmet.get(bus.cls, 0) + unmet
        if unmet > 0:
            buses_short += 1
        row = price[bus.depot]
        for slot, kwh in bus.charges.items():
            depot_energy[bus.depot][slot] += kwh
            class_energy[bus.cls][slot] += kwh
            feeder_by_slot[slot] += kwh
            cents = row[slot] * kwh
            depot_cost[bus.depot] += cents
            class_cost[bus.cls] = class_cost.get(bus.cls, 0) + cents
            total_cost += cents
        changed = False
        for slot in bus.slots:
            if bus.charges.get(slot, 0) != published.get((bus.bus_id, slot), 0):
                changed = True
                break
        if changed:
            buses_changed += 1
        if unmet == 0:
            reason = None
        elif bus.need > bus.max_slot * len(bus.slots):
            reason = "window"
        else:
            reason = "supply"
        audit.append({
            "bus_id": bus.bus_id,
            "depot": bus.depot,
            "class": bus.cls,
            "need_kwh": bus.need,
            "delivered_kwh": bus.delivered,
            "unmet_kwh": unmet,
            "unmet_reason": reason,
            "changed": changed,
            "charges": [{"slot": plan.names[s], "kwh": bus.charges[s]}
                        for s in sorted(bus.charges)],
        })
    moved = 0
    for (bus_id, slot), kwh in published.items():
        got = flow.get((bus_id, slot), 0)
        if kwh > got:
            moved += kwh - got

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    write_json(out_dir, "policy_audit.json",
               {"plan_date": plan.plan_date, "buses": audit})
    for depot in depots:
        write_json(out_dir, "region_%s.json" % depot, {
            "depot": depot,
            "buses": depot_buses[depot],
            "energy_kwh": sum(depot_energy[depot]),
            "cost_cents": depot_cost[depot],
            "unmet_kwh": depot_unmet[depot],
            "slots": slot_rows(plan, depot_energy[depot], feeder_by_slot),
        })
    for cls in ("commercial", "public"):
        energy = class_energy.get(cls, [0] * plan.nslots)
        write_json(out_dir, "segment_%s.json" % cls, {
            "class": cls,
            "buses": class_buses.get(cls, 0),
            "energy_kwh": sum(energy),
            "cost_cents": class_cost.get(cls, 0),
            "unmet_kwh": class_unmet.get(cls, 0),
            "slots": slot_rows(plan, energy, feeder_by_slot),
        })
    write_json(out_dir, "summary.json", {
        "plan_date": plan.plan_date,
        "weighted_unmet_kwh": weighted_unmet,
        "energy_cost_cents": total_cost,
        "moved_kwh": moved,
        "feeder_peak_kwh": max(feeder_by_slot) if feeder_by_slot else 0,
        "feeder_kwh_by_slot": [{"slot": plan.names[i], "kwh": feeder_by_slot[i]}
                               for i in range(plan.nslots)],
        "buses_planned": len(buses),
        "buses_short": buses_short,
        "buses_changed": buses_changed,
        "records_rejected": len(rejected),
    })
    write_json(out_dir, "data_quality.json", {
        "plan_date": plan.plan_date,
        "rejected": [{"file": f, "line": l, "reason": r}
                     for f, l, r in sorted(rejected, key=lambda x: (x[0], x[1]))],
    })
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DataError as exc:
        sys.stderr.write("error: %s\n" % exc)
        sys.exit(2)
