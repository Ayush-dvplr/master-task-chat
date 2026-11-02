#!/usr/bin/env python3
"""Overnight depot charging plan.

Reads the planning data folder, rebuilds the optimal day plan after the
disruption notice and writes the nine planning reports.

Standard library only.
"""

import argparse
import collections
import configparser
import csv
import datetime as dt
import heapq
import json
import os
import re
import xml.etree.ElementTree as ET

TS = "%Y-%m-%dT%H:%M"
DEPOT_ORDER = ["North", "South", "West", "East"]


def parse_ts(text):
    return dt.datetime.strptime(text.strip(), TS)


def tod_minutes(stamp):
    return stamp.hour * 60 + stamp.minute


def hhmm_to_minutes(text):
    text = text.strip()
    h, m = text.split(":")
    return int(h) * 60 + int(m)


# ----------------------------------------------------------------- inputs


def load_grid(path):
    cp = configparser.ConfigParser()
    cp.read(path)
    plan = cp["plan"]
    return {
        "plan_date": plan["plan_date"].strip(),
        "first_slot": parse_ts(plan["first_slot"]),
        "slot_minutes": int(plan["slot_minutes"]),
        "slots": int(plan["slots"]),
        "feeder_kwh_per_slot": int(cp["feeder"]["feeder_kwh_per_slot"]),
    }


def load_notice(path):
    """Parse the disruption notice."""
    out = {"plan_date": None, "cabinets": [], "feeder": [], "extra": []}
    if not os.path.exists(path):
        return out
    text = open(path, encoding="utf-8").read()
    m = re.search(r"isruption notice for\s+(\d{4}-\d{2}-\d{2})", text)
    if m:
        out["plan_date"] = m.group(1)
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        m = re.match(
            r"^(\S+)\s*:\s*(\d+)\s+cabinets?\s+out of service\s+from\s+(\S+)\s+to\s+(\S+)\s*$",
            body,
        )
        if m:
            out["cabinets"].append(
                (m.group(1), int(m.group(2)), parse_ts(m.group(3)), parse_ts(m.group(4)))
            )
            continue
        m = re.match(
            r"^from\s+(\S+)\s+to\s+(\S+)\s*:\s*feeder limit\s+(\d+)\s*kWh",
            body,
            re.I,
        )
        if m:
            out["feeder"].append(
                (parse_ts(m.group(1)), parse_ts(m.group(2)), int(m.group(3)))
            )
            continue
        m = re.match(
            r"^(\S+)\s*:\s*extra trip on\s+(\d{4}-\d{2}-\d{2})\s*,\s*(\d+)\s*kWh",
            body,
            re.I,
        )
        if m:
            out["extra"].append((m.group(1), m.group(2), int(m.group(3))))
    return out


def load_tariff(path):
    """Return a list of (valid_from, valid_to, bands) with bands as
    (from_minutes, to_minutes, cents)."""
    root = ET.parse(path).getroot()
    versions = []
    for ver in root.findall("version"):
        bands = []
        for band in ver.findall("band"):
            bands.append(
                (
                    hhmm_to_minutes(band.get("from")),
                    hhmm_to_minutes(band.get("to")),
                    int(band.get("cents_per_kwh")),
                )
            )
        versions.append((ver.get("valid_from"), ver.get("valid_to"), bands))
    return versions


def bands_for_date(versions, date_text):
    for lo, hi, bands in versions:
        if lo <= date_text <= hi:
            return bands
    return None


def band_price(bands, minutes):
    minutes %= 1440
    for lo, hi, cents in bands:
        if lo < hi:
            if lo <= minutes < hi:
                return cents
        elif lo > hi:
            if minutes >= lo or minutes < hi:
                return cents
        else:
            return cents
    return None


# ------------------------------------------------------------ meter rules
#
# Rule 12: each depot's meter has its own way of applying a tariff to a slot.
# The candidates below are the ways a band table can be read for a slot; the
# settlements of a depot single one out.


def meter_start(bands, start_minutes, slot_minutes):
    return band_price(bands, start_minutes)


def meter_end(bands, start_minutes, slot_minutes):
    return band_price(bands, start_minutes + slot_minutes)


def meter_mid(bands, start_minutes, slot_minutes):
    return band_price(bands, start_minutes + slot_minutes // 2)


def meter_max(bands, start_minutes, slot_minutes):
    return max(
        band_price(bands, start_minutes + k) for k in range(max(1, slot_minutes))
    )


def meter_min(bands, start_minutes, slot_minutes):
    return min(
        band_price(bands, start_minutes + k) for k in range(max(1, slot_minutes))
    )


METERS = [
    ("slot_start", meter_start),
    ("slot_mid", meter_mid),
    ("slot_max", meter_max),
    ("slot_min", meter_min),
    ("slot_end", meter_end),
]


def pick_meters(settle_rows, versions, slot_minutes, depots):
    """For every depot, the meter under which all its settlements bill out
    exactly their cents."""
    by_depot = {d: [] for d in depots}
    for row in settle_rows:
        if row["depot"] in by_depot:
            by_depot[row["depot"]].append(row)
    chosen = {}
    for depot in depots:
        rows = by_depot.get(depot, [])
        ok = []
        for name, fn in METERS:
            good = True
            for row in rows:
                bands = bands_for_date(versions, row["settled_date"])
                if bands is None:
                    good = False
                    break
                start = parse_ts(row["start"])
                end = parse_ts(row["end"])
                span = int((end - start).total_seconds() // 60)
                count = span // slot_minutes
                kwh = int(row["kwh"])
                if count <= 0 or kwh % count:
                    good = False
                    break
                share = kwh // count
                total = 0
                for k in range(count):
                    moment = start + dt.timedelta(minutes=slot_minutes * k)
                    total += share * fn(bands, tod_minutes(moment), slot_minutes)
                if total != int(row["cents"]):
                    good = False
                    break
            if good:
                ok.append((name, fn))
        chosen[depot] = ok[0] if ok else METERS[0]
    return chosen


# ------------------------------------------------------------------- flow


class MinCostFlow(object):
    """Successive shortest paths with potentials, plus a lexicographic
    refinement over the face of optimal solutions."""

    def __init__(self, n):
        self.n = n
        self.to = []
        self.cap = []
        self.cost = []
        self.adj = [[] for _ in range(n)]

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

    def flow_of(self, idx):
        return self.cap[idx ^ 1]

    def init_potentials(self, order, src):
        """Shortest distances on the arc set, relaxed in topological order."""
        INF = float("inf")
        pot = [INF] * self.n
        pot[src] = 0
        for u in order:
            if pot[u] is INF or pot[u] == INF:
                continue
            base = pot[u]
            for idx in self.adj[u]:
                if self.cap[idx] <= 0:
                    continue
                v = self.to[idx]
                val = base + self.cost[idx]
                if val < pot[v]:
                    pot[v] = val
        for i in range(self.n):
            if pot[i] == INF:
                pot[i] = 0
        self.pot = pot

    def solve(self, src, snk):
        to, cap, cost, adj = self.to, self.cap, self.cost, self.adj
        pot = self.pot
        n = self.n
        INF = float("inf")
        while True:
            dist = [INF] * n
            prevarc = [-1] * n
            dist[src] = 0
            done = [False] * n
            heap = [(0, src)]
            while heap:
                d, u = heapq.heappop(heap)
                if done[u]:
                    continue
                done[u] = True
                pu = pot[u]
                for idx in adj[u]:
                    if cap[idx] <= 0:
                        continue
                    v = to[idx]
                    if done[v]:
                        continue
                    nd = d + cost[idx] + pu - pot[v]
                    if nd < dist[v]:
                        dist[v] = nd
                        prevarc[v] = idx
                        heapq.heappush(heap, (nd, v))
            if dist[snk] == INF:
                break
            dsnk = dist[snk]
            if dsnk + pot[snk] - pot[src] >= 0:
                break
            for i in range(n):
                di = dist[i]
                pot[i] += dsnk if di == INF or di > dsnk else di
            # the shortest path itself, then any further admissible path
            path = []
            v = snk
            while v != src:
                idx = prevarc[v]
                path.append(idx)
                v = to[idx ^ 1]
            self._push(path)
            while True:
                path = self._find_admissible(src, snk)
                if path is None:
                    break
                self._push(path)

    def _push(self, path):
        cap = self.cap
        delta = min(cap[i] for i in path)
        for i in path:
            cap[i] -= delta
            cap[i ^ 1] += delta

    def _find_admissible(self, src, snk, blocked=None, skip=None):
        """A simple path of zero reduced cost residual arcs, or None."""
        to, cap, cost, adj = self.to, self.cap, self.cost, self.adj
        pot = self.pot
        seen = [False] * self.n
        seen[src] = True
        stack = [(src, 0)]
        path = []
        while stack:
            u, j = stack[-1]
            if u == snk:
                return list(path)
            arcs = adj[u]
            moved = False
            while j < len(arcs):
                idx = arcs[j]
                j += 1
                if cap[idx] <= 0:
                    continue
                if blocked is not None and (idx >> 1) in blocked:
                    continue
                if skip is not None and (idx >> 1) == skip:
                    continue
                v = to[idx]
                if seen[v]:
                    continue
                if cost[idx] + pot[u] - pot[v] != 0:
                    continue
                stack[-1] = (u, j)
                seen[v] = True
                path.append(idx)
                stack.append((v, 0))
                moved = True
                break
            if moved:
                continue
            stack.pop()
            if path:
                path.pop()
        return None

    def refresh_potentials(self):
        """Potentials with non negative reduced cost on every residual arc."""
        n = self.n
        to, cap, cost, adj = self.to, self.cap, self.cost, self.adj
        pot = [0] * n
        inq = [True] * n
        queue = collections.deque(range(n))
        count = [0] * n
        while queue:
            u = queue.popleft()
            inq[u] = False
            pu = pot[u]
            for idx in adj[u]:
                if cap[idx] <= 0:
                    continue
                v = to[idx]
                val = pu + cost[idx]
                if val < pot[v]:
                    pot[v] = val
                    if not inq[v]:
                        inq[v] = True
                        queue.append(v)
                        count[v] += 1
                        if count[v] > n + 2:
                            raise RuntimeError("negative cycle in residual graph")
        self.pot = pot

    def raise_arc(self, idx, frozen):
        to, cap = self.to, self.cap
        tail = to[idx ^ 1]
        head = to[idx]
        gained = 0
        while cap[idx] > 0:
            path = self._find_admissible(head, tail, frozen, idx >> 1)
            if path is None:
                break
            delta = min(cap[idx], min(cap[i] for i in path))
            cap[idx] -= delta
            cap[idx ^ 1] += delta
            for i in path:
                cap[i] -= delta
                cap[i ^ 1] += delta
            gained += delta
        return gained

    def reduced(self, idx):
        return self.cost[idx] + self.pot[self.to[idx ^ 1]] - self.pot[self.to[idx]]


# ------------------------------------------------------------------ model


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def build(data_dir):
    grid = load_grid(os.path.join(data_dir, "grid.ini"))
    notice = load_notice(os.path.join(data_dir, "disruption_notice.md"))
    plan_date = notice["plan_date"] or grid["plan_date"]

    shift = dt.datetime.strptime(plan_date, "%Y-%m-%d").date() - dt.datetime.strptime(
        grid["plan_date"], "%Y-%m-%d"
    ).date()
    first_slot = grid["first_slot"] + shift
    step = grid["slot_minutes"]
    nslots = grid["slots"]
    slot_times = [first_slot + dt.timedelta(minutes=step * i) for i in range(nslots)]
    slot_names = [t.strftime(TS) for t in slot_times]
    slot_index = {t: i for i, t in enumerate(slot_times)}
    day_end = first_slot + dt.timedelta(minutes=step * nslots)

    depots_raw = json.load(open(os.path.join(data_dir, "depots.json"), encoding="utf-8"))
    cab_kwh = int(depots_raw["cabinet_kwh_per_slot"])
    cabinets = {d["depot"]: int(d["cabinets"]) for d in depots_raw["depots"]}
    depots = [d for d in DEPOT_ORDER if d in cabinets]
    for d in sorted(cabinets):
        if d not in depots:
            depots.append(d)

    out_cab = {(d, i): 0 for d in depots for i in range(nslots)}
    for depot, count, lo, hi in notice["cabinets"]:
        if depot not in cabinets:
            continue
        for i, t in enumerate(slot_times):
            if lo <= t < hi:
                out_cab[(depot, i)] += count
    depot_cap = {}
    for d in depots:
        for i in range(nslots):
            live = max(0, cabinets[d] - out_cab[(d, i)])
            depot_cap[(d, i)] = live * cab_kwh

    feeder = [grid["feeder_kwh_per_slot"]] * nslots
    for lo, hi, limit in notice["feeder"]:
        for i, t in enumerate(slot_times):
            if lo <= t < hi:
                feeder[i] = limit

    versions = load_tariff(os.path.join(data_dir, "tariff.xml"))
    bands = bands_for_date(versions, plan_date)
    settle = read_csv(os.path.join(data_dir, "settlements.csv"))
    meters = pick_meters(settle, versions, step, depots)
    price = {}
    for d in depots:
        fn = meters[d][1]
        for i, t in enumerate(slot_times):
            price[(d, i)] = fn(bands, tod_minutes(t), step)

    types = json.load(open(os.path.join(data_dir, "bus_types.json"), encoding="utf-8"))
    register = {}
    for row in read_csv(os.path.join(data_dir, "fleet_register.csv")):
        register.setdefault(row["vehicle_id"], row)
    contracts = {}
    craw = json.load(open(os.path.join(data_dir, "contracts.json"), encoding="utf-8"))
    for item in craw["contracts"]:
        contracts[item["contract_id"]] = item["class"]
    classes = configparser.ConfigParser()
    classes.read(os.path.join(data_dir, "service_classes.ini"))
    weights = {name: int(classes[name]["weight"]) for name in classes.sections()}

    next_day = (
        dt.datetime.strptime(plan_date, "%Y-%m-%d") + dt.timedelta(days=1)
    ).strftime("%Y-%m-%d")
    trip_kwh = {}
    with open(os.path.join(data_dir, "trips.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            trip = json.loads(line)
            if trip["service_date"] == next_day:
                trip_kwh[trip["bus_id"]] = trip_kwh.get(trip["bus_id"], 0) + int(
                    trip["kwh"]
                )
    for bus_id, date_text, kwh in notice["extra"]:
        if date_text == next_day:
            trip_kwh[bus_id] = trip_kwh.get(bus_id, 0) + kwh

    rejected = []
    buses = []
    accepted = set()
    for line_no, row in enumerate(
        read_csv(os.path.join(data_dir, "roster.csv")), start=2
    ):
        if row["plan_date"] != plan_date:
            continue
        bus_id = row["bus_id"]
        reason = None
        if bus_id not in register:
            reason = "unknown_vehicle"
        elif register[bus_id]["status"] != "active":
            reason = "retired_vehicle"
        elif bus_id in accepted:
            reason = "duplicate_roster_row"
        else:
            arrive = parse_ts(row["arrive"])
            depart = parse_ts(row["depart"])
            if (
                not arrive < depart
                or arrive < first_slot
                or depart > day_end
            ):
                reason = "bad_window"
        if reason is not None:
            rejected.append(("roster.csv", line_no, reason))
            continue
        accepted.add(bus_id)
        kind = register[bus_id]["type"]
        window = [i for i, t in enumerate(slot_times) if arrive <= t < depart]
        need = (
            trip_kwh.get(bus_id, 0)
            + int(types[kind]["reserve_kwh"])
            - int(row["soc_arrival_kwh"])
        )
        cls = contracts.get(row.get("contract_id", "") or "", "commercial")
        buses.append(
            {
                "bus_id": bus_id,
                "depot": row["depot"],
                "type": kind,
                "class": cls,
                "weight": weights.get(cls, 1),
                "need": max(0, need),
                "window": window,
                "window_set": set(window),
                "max_slot": int(types[kind]["max_kwh_per_slot"]),
            }
        )
    buses.sort(key=lambda b: b["bus_id"])
    by_id = {b["bus_id"]: b for b in buses}

    published = {}
    for line_no, row in enumerate(
        read_csv(os.path.join(data_dir, "published_plan.csv")), start=2
    ):
        if row["plan_date"] != plan_date:
            continue
        bus = by_id.get(row["bus_id"])
        slot = slot_index.get(parse_ts(row["slot_start"]))
        if bus is None or slot is None or slot not in bus["window_set"]:
            rejected.append(("published_plan.csv", line_no, "published_row_outside_window"))
            continue
        key = (row["bus_id"], slot)
        published[key] = published.get(key, 0) + int(row["kwh"])

    return {
        "plan_date": plan_date,
        "nslots": nslots,
        "slot_names": slot_names,
        "depots": depots,
        "depot_cap": depot_cap,
        "feeder": feeder,
        "price": price,
        "buses": buses,
        "published": published,
        "rejected": rejected,
        "weights": weights,
    }


# ------------------------------------------------------------------- plan


def solve_plan(model):
    buses = model["buses"]
    depots = model["depots"]
    nslots = model["nslots"]
    price = model["price"]
    published = model["published"]
    nbus = len(buses)
    ndep = len(depots)
    dep_idx = {d: i for i, d in enumerate(depots)}

    moved_total = sum(published.values())
    max_price = max(price.values()) if price else 0
    cost_max = sum(model["feeder"]) * max_price
    m_moved = 1
    m_cost = moved_total + 1
    m_unmet = m_cost * (cost_max + 1)

    src = 0
    bus_node = [1 + i for i in range(nbus)]
    ds_base = 1 + nbus
    slot_base = ds_base + ndep * nslots
    snk = slot_base + nslots
    net = MinCostFlow(snk + 1)

    for i, bus in enumerate(buses):
        net.add(src, bus_node[i], bus["need"], -m_unmet * bus["weight"])
    pos_arcs = {}
    for i, bus in enumerate(buses):
        d = dep_idx.get(bus["depot"])
        if d is None:
            continue
        cap_slot = bus["max_slot"]
        for s in bus["window"]:
            node = ds_base + d * nslots + s
            pub = min(published.get((bus["bus_id"], s), 0), cap_slot)
            arcs = []
            if pub > 0:
                arcs.append(net.add(bus_node[i], node, pub, -m_moved))
            if cap_slot - pub > 0:
                arcs.append(net.add(bus_node[i], node, cap_slot - pub, 0))
            if arcs:
                pos_arcs[(s, i)] = arcs
    for d in depots:
        for s in range(nslots):
            net.add(
                ds_base + dep_idx[d] * nslots + s,
                slot_base + s,
                model["depot_cap"][(d, s)],
                m_cost * price[(d, s)],
            )
    for s in range(nslots):
        net.add(slot_base + s, snk, model["feeder"][s], 0)

    order = (
        [src]
        + bus_node
        + [ds_base + k for k in range(ndep * nslots)]
        + [slot_base + s for s in range(nslots)]
        + [snk]
    )
    net.init_potentials(order, src)
    net.solve(src, snk)
    net.add(snk, src, sum(bus["need"] for bus in buses) + 1, 0)
    net.refresh_potentials()

    frozen = set()
    for s in range(nslots):
        for i in range(nbus):
            arcs = pos_arcs.get((s, i))
            if not arcs:
                continue
            for idx in arcs:
                if net.cap[idx] > 0 and net.reduced(idx) == 0:
                    net.raise_arc(idx, frozen)
            for idx in arcs:
                frozen.add(idx >> 1)

    plan = {}
    for (s, i), arcs in pos_arcs.items():
        total = sum(net.flow_of(idx) for idx in arcs)
        if total:
            plan[(buses[i]["bus_id"], s)] = total
    return plan


# ---------------------------------------------------------------- reports


def dump(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_reports(model, plan, out_dir):
    buses = model["buses"]
    nslots = model["nslots"]
    names = model["slot_names"]
    price = model["price"]
    published = model["published"]
    plan_date = model["plan_date"]

    feeder_by_slot = [0] * nslots
    depot_slot = {d: [0] * nslots for d in model["depots"]}
    class_slot = {}
    depot_cost = {d: 0 for d in model["depots"]}
    class_cost = {}
    depot_unmet = {d: 0 for d in model["depots"]}
    class_unmet = {}
    depot_buses = {d: 0 for d in model["depots"]}
    class_buses = {}

    audit = []
    weighted_unmet = 0
    energy_cost = 0
    moved = 0
    buses_short = 0
    buses_changed = 0

    for bus in buses:
        cls = bus["class"]
        class_slot.setdefault(cls, [0] * nslots)
        class_cost.setdefault(cls, 0)
        class_unmet.setdefault(cls, 0)
        class_buses[cls] = class_buses.get(cls, 0) + 1
        depot_buses[bus["depot"]] = depot_buses.get(bus["depot"], 0) + 1

        charges = []
        delivered = 0
        changed = False
        for s in bus["window"]:
            kwh = plan.get((bus["bus_id"], s), 0)
            pub = published.get((bus["bus_id"], s), 0)
            if pub > kwh:
                moved += pub - kwh
            if pub != kwh:
                changed = True
            if kwh:
                delivered += kwh
                charges.append({"slot": names[s], "kwh": kwh})
                cents = kwh * price[(bus["depot"], s)]
                energy_cost += cents
                feeder_by_slot[s] += kwh
                depot_slot[bus["depot"]][s] += kwh
                depot_cost[bus["depot"]] += cents
                class_slot[cls][s] += kwh
                class_cost[cls] += cents
        unmet = bus["need"] - delivered
        weighted_unmet += bus["weight"] * unmet
        depot_unmet[bus["depot"]] += unmet
        class_unmet[cls] += unmet
        if unmet > 0:
            buses_short += 1
            if bus["need"] > bus["max_slot"] * len(bus["window"]):
                reason = "window"
            else:
                reason = "supply"
        else:
            reason = None
        if changed:
            buses_changed += 1
        audit.append(
            {
                "bus_id": bus["bus_id"],
                "depot": bus["depot"],
                "class": cls,
                "need_kwh": bus["need"],
                "delivered_kwh": delivered,
                "unmet_kwh": unmet,
                "unmet_reason": reason,
                "changed": changed,
                "charges": charges,
            }
        )

    dump(out_dir, "policy_audit.json", {"plan_date": plan_date, "buses": audit})

    rejected = sorted(model["rejected"], key=lambda r: (r[0], r[1]))
    dump(
        out_dir,
        "data_quality.json",
        {
            "plan_date": plan_date,
            "rejected": [
                {"file": f, "line": line, "reason": reason}
                for f, line, reason in rejected
            ],
        },
    )

    for depot in model["depots"]:
        dump(
            out_dir,
            "region_%s.json" % depot,
            {
                "depot": depot,
                "buses": depot_buses.get(depot, 0),
                "energy_kwh": sum(depot_slot[depot]),
                "cost_cents": depot_cost.get(depot, 0),
                "unmet_kwh": depot_unmet.get(depot, 0),
                "slots": [
                    {
                        "slot": names[s],
                        "kwh": depot_slot[depot][s],
                        "feeder_kwh": feeder_by_slot[s],
                    }
                    for s in range(nslots)
                ],
            },
        )

    for cls in sorted(set(list(model["weights"].keys()) + list(class_buses.keys()))):
        series = class_slot.get(cls, [0] * nslots)
        dump(
            out_dir,
            "segment_%s.json" % cls,
            {
                "class": cls,
                "buses": class_buses.get(cls, 0),
                "energy_kwh": sum(series),
                "cost_cents": class_cost.get(cls, 0),
                "unmet_kwh": class_unmet.get(cls, 0),
                "slots": [
                    {
                        "slot": names[s],
                        "kwh": series[s],
                        "feeder_kwh": feeder_by_slot[s],
                    }
                    for s in range(nslots)
                ],
            },
        )

    dump(
        out_dir,
        "summary.json",
        {
            "plan_date": plan_date,
            "weighted_unmet_kwh": weighted_unmet,
            "energy_cost_cents": energy_cost,
            "moved_kwh": moved,
            "feeder_peak_kwh": max(feeder_by_slot) if feeder_by_slot else 0,
            "feeder_kwh_by_slot": [
                {"slot": names[s], "kwh": feeder_by_slot[s]} for s in range(nslots)
            ],
            "buses_planned": len(buses),
            "buses_short": buses_short,
            "buses_changed": buses_changed,
            "records_rejected": len(model["rejected"]),
        },
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/environment/data")
    ap.add_argument("--out", default="/app/out")
    args = ap.parse_args()
    out_dir = args.out
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    model = build(args.data)
    plan = solve_plan(model)
    write_reports(model, plan, out_dir)


if __name__ == "__main__":
    main()
