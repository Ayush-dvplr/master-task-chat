#!/usr/bin/env python3
"""Overnight depot charging planner.

Reads the data folder described in docs/charging_rules.md and writes the nine
planning reports. Standard library only.

    python3 derive_report.py --data <data folder> --out <output folder>
"""
import argparse
import configparser
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path

DEPOT_NAMES = ("North", "South", "West", "East")
CLASS_NAMES = ("commercial", "public")
STAMP = "%Y-%m-%dT%H:%M"


class InputError(Exception):
    """A declared input is missing or cannot be read; names the file."""

    def __init__(self, name, detail):
        super().__init__("%s: %s" % (name, detail))
        self.name = name


# ----------------------------------------------------------------- reading

class Folder:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, name):
        p = self.root / name
        if not p.is_file():
            raise InputError(name, "missing from the data folder")
        return p

    def text(self, name):
        try:
            return self.path(name).read_text(encoding="utf-8")
        except UnicodeDecodeError as err:
            raise InputError(name, "not UTF-8 text (%s)" % err) from err

    def rows(self, name):
        """CSV rows with their 1-based line numbers (header is line 1)."""
        lines = self.text(name).splitlines()
        reader = csv.DictReader(lines)
        out = []
        for number, row in enumerate(reader, start=2):
            if None in row or any(v is None for v in row.values()):
                raise InputError(name, "line %d has the wrong number of fields" % number)
            out.append((number, row))
        return out

    def json(self, name):
        try:
            return json.loads(self.text(name))
        except json.JSONDecodeError as err:
            raise InputError(name, "malformed JSON (%s)" % err) from err

    def ini(self, name):
        cp = configparser.ConfigParser()
        try:
            cp.read_string(self.text(name))
        except configparser.Error as err:
            raise InputError(name, "malformed INI (%s)" % err) from err
        return cp


def guarded(name, fn, *args):
    """Run a parser step; turn a bad value into an InputError naming the file."""
    try:
        return fn(*args)
    except InputError:
        raise
    except (KeyError, ValueError, TypeError, IndexError, AttributeError, ET.ParseError) as err:
        raise InputError(name, "malformed content (%s: %s)" % (type(err).__name__, err)) from err


class Clock:
    """Slot arithmetic for the plan day."""

    def __init__(self, first, minutes, count):
        self.first = first
        self.step = timedelta(minutes=minutes)
        self.minutes = minutes
        self.count = count
        self.end = first + self.step * count

    def name(self, s):
        return (self.first + self.step * s).strftime(STAMP)

    def first_at_or_after(self, moment):
        """Index of the first slot starting at or after the moment."""
        gap = (moment - self.first).total_seconds() / 60.0
        k = int(gap // self.minutes)
        if k * self.minutes < gap:
            k += 1
        return k

    def day_index(self, hh, mm):
        """Slot index (cyclic over one day) of a time of day."""
        start = self.first.hour * 60 + self.first.minute
        return ((hh * 60 + mm - start) % 1440) // self.minutes


def stamp(text):
    return datetime.strptime(text.strip(), STAMP)


def read_grid(folder):
    cp = folder.ini("grid.ini")

    def build():
        plan = cp["plan"]
        pd = date.fromisoformat(plan["plan_date"].strip())
        clock = Clock(stamp(plan["first_slot"]), int(plan["slot_minutes"]), int(plan["slots"]))
        feeder = int(cp["feeder"]["feeder_kwh_per_slot"])
        return pd, clock, feeder

    return guarded("grid.ini", build)


def span(clock, a, b):
    """Slots of the plan day covered by "from a to b"."""
    lo = max(0, clock.first_at_or_after(stamp(a)))
    hi = min(clock.count, clock.first_at_or_after(stamp(b)))
    return range(lo, max(lo, hi))


def read_notice(folder, clock):
    name = "disruption_notice.md"
    text = folder.text(name)
    pat_out = re.compile(r"^- (\w+): (\d+) cabinets out of service from (\S+) to (\S+)$")
    pat_der = re.compile(r"^- from (\S+) to (\S+): feeder limit (\d+) kWh per slot$")
    pat_ext = re.compile(r"^- (\w+): extra trip on (\S+), (\d+) kWh$")

    def build():
        outages, derates, extras = [], [], []
        for line in text.splitlines():
            line = line.strip()
            m = pat_out.match(line)
            if m:
                outages.append((m.group(1), int(m.group(2)), span(clock, m.group(3), m.group(4))))
                continue
            m = pat_der.match(line)
            if m:
                derates.append((span(clock, m.group(1), m.group(2)), int(m.group(3))))
                continue
            m = pat_ext.match(line)
            if m:
                extras.append((m.group(1), date.fromisoformat(m.group(2)), int(m.group(3))))
        return outages, derates, extras

    return guarded(name, build)


# ----------------------------------------------------------------- tariff and meters

class Tariff:
    def __init__(self, valid_from, valid_to, prices):
        self.valid_from = valid_from
        self.valid_to = valid_to
        self.prices = prices  # cents per kWh by slot of the day, from first_slot's time of day


def read_tariffs(folder, clock):
    name = "tariff.xml"
    day = 1440 // clock.minutes

    def build():
        root = ET.fromstring(folder.text(name))
        versions = []
        for v in root.iter("version"):
            prices = [None] * day
            for band in v.iter("band"):
                fh, fm = (int(t) for t in band.get("from").split(":"))
                th, tm = (int(t) for t in band.get("to").split(":"))
                lo, hi = clock.day_index(fh, fm), clock.day_index(th, tm)
                width = (hi - lo) % day or day
                for j in range(width):
                    prices[(lo + j) % day] = int(band.get("cents_per_kwh"))
            if None in prices:
                raise ValueError("version from %s leaves a time of day without a price" % v.get("valid_from"))
            versions.append(Tariff(date.fromisoformat(v.get("valid_from")), date.fromisoformat(v.get("valid_to")), prices))
        return versions

    return guarded(name, build)


def tariff_on(versions, day):
    found = [t for t in versions if t.valid_from <= day <= t.valid_to]
    if len(found) != 1:
        raise InputError("tariff.xml", "%d versions in force on %s, expected exactly one" % (len(found), day))
    return found[0]


def fit_meters(folder, clock, versions):
    """Per depot, the one way of applying a tariff that bills every settled row exactly."""
    name = "settlements.csv"
    day = 1440 // clock.minutes
    sessions = defaultdict(list)

    def build():
        for _, row in folder.rows(name):
            start, end = stamp(row["start"]), stamp(row["end"])
            parts = int((end - start).total_seconds() // 60) // clock.minutes
            first = clock.day_index(start.hour, start.minute)
            tariff = tariff_on(versions, date.fromisoformat(row["settled_date"]))
            sessions[row["depot"]].append((tariff.prices, first, parts, int(row["kwh"]), int(row["cents"])))

    guarded(name, build)
    meters = {}
    for depot in DEPOT_NAMES:
        rows = sessions.get(depot)
        if not rows:
            raise InputError(name, "no settled sessions for depot %s" % depot)
        fitting = []
        for shift in range(day):
            # kwh spread evenly over `parts` slots: billed = kwh * sum(prices) / parts
            if all(kwh * sum(p[(first + j + shift) % day] for j in range(parts)) == cents * parts
                   for p, first, parts, kwh, cents in rows):
                fitting.append(shift)
        if len(fitting) != 1:
            raise InputError(name, "depot %s settlements fit %d meter readings, expected exactly one" % (depot, len(fitting)))
        meters[depot] = fitting[0]
    return meters


# ----------------------------------------------------------------- buses

class Bus:
    __slots__ = ("bus_id", "depot", "rate", "a", "e", "need", "klass", "weight", "published")

    def __init__(self, bus_id, depot, rate, a, e, need, klass, weight):
        self.bus_id, self.depot, self.rate = bus_id, depot, rate
        self.a, self.e, self.need = a, e, need
        self.klass, self.weight = klass, weight
        self.published = {}


def read_buses(folder, pd, clock, extras):
    fleet = {}
    for _, row in folder.rows("fleet_register.csv"):
        fleet[row["vehicle_id"].strip()] = (row["type"].strip(), row["status"].strip())
    types = guarded("bus_types.json", lambda: {
        k: (int(v["max_kwh_per_slot"]), int(v["reserve_kwh"])) for k, v in folder.json("bus_types.json").items()})
    classes = guarded("contracts.json", lambda: {
        c["contract_id"]: c["class"] for c in folder.json("contracts.json")["contracts"]})
    weights_ini = folder.ini("service_classes.ini")
    weights = guarded("service_classes.ini", lambda: {k: int(weights_ini[k]["weight"]) for k in weights_ini.sections()})
    after = pd + timedelta(days=1)

    trip_kwh = defaultdict(int)

    def read_trips():
        for line in folder.text("trips.jsonl").splitlines():
            if not line.strip():
                continue
            t = json.loads(line)
            if date.fromisoformat(t["service_date"]) == after:
                trip_kwh[t["bus_id"]] += int(t["kwh"])

    guarded("trips.jsonl", read_trips)
    for bus_id, when, kwh in extras:
        if when == after:
            trip_kwh[bus_id] += kwh

    rejected, buses = [], {}

    def read_roster():
        for line_no, row in folder.rows("roster.csv"):
            if date.fromisoformat(row["plan_date"].strip()) != pd:
                continue
            bid = row["bus_id"].strip()
            arrive, depart = stamp(row["arrive"]), stamp(row["depart"])
            reason = None
            if bid not in fleet:
                reason = "unknown_vehicle"
            elif fleet[bid][1] != "active":
                reason = "retired_vehicle"
            elif bid in buses:
                reason = "duplicate_roster_row"
            elif not arrive < depart:
                reason = "bad_window"
            if reason:
                rejected.append(("roster.csv", line_no, reason))
                continue
            rate, reserve = types[fleet[bid][0]]
            need = max(0, trip_kwh[bid] + reserve - int(row["soc_arrival_kwh"]))
            klass = classes.get(row["contract_id"].strip(), "commercial") if row["contract_id"].strip() else "commercial"
            buses[bid] = Bus(bid, row["depot"].strip(), rate, clock.first_at_or_after(arrive),
                             clock.first_at_or_after(depart), need, klass, weights[klass])

    guarded("roster.csv", read_roster)

    def read_published():
        for line_no, row in folder.rows("published_plan.csv"):
            if date.fromisoformat(row["plan_date"].strip()) != pd:
                continue
            bus = buses.get(row["bus_id"].strip())
            if bus is None:
                continue
            at = stamp(row["slot_start"])
            s = clock.first_at_or_after(at)
            if not (bus.a <= s < bus.e) or clock.first + clock.step * s != at:
                rejected.append(("published_plan.csv", line_no, "published_row_outside_window"))
                continue
            bus.published[s] = bus.published.get(s, 0) + int(row["kwh"])

    guarded("published_plan.csv", read_published)
    return [buses[b] for b in sorted(buses)], rejected


def read_depots(folder, clock, outages):
    doc = folder.json("depots.json")

    def build():
        per = int(doc["cabinet_kwh_per_slot"])
        counts = {d["depot"]: int(d["cabinets"]) for d in doc["depots"]}
        caps = {}
        for depot in DEPOT_NAMES:
            working = [counts[depot]] * clock.count
            for where, n, slots in outages:
                if where == depot:
                    for s in slots:
                        working[s] -= n
            caps[depot] = [max(0, w) * per for w in working]
        return caps

    return guarded("depots.json", build)


# ----------------------------------------------------------------- planning

class Network:
    """Residual graph kept in parallel arrays; arc j and j ^ 1 are partners."""

    def __init__(self, size):
        self.out = [[] for _ in range(size)]
        self.head, self.room, self.price = [], [], []

    def arc(self, tail, head, room, price):
        j = len(self.head)
        for a, b, r, c in ((tail, head, room, price), (head, tail, 0, -price)):
            self.out[a].append(len(self.head))
            self.head.append(b)
            self.room.append(r)
            self.price.append(c)
        return j

    def tail(self, j):
        return self.head[j ^ 1]

    def cheapest_flow(self, src, dst, amount):
        """Successive shortest paths with Dijkstra on reduced prices."""
        import heapq
        size = len(self.out)
        height = [0] * size
        moved = 0
        while moved < amount:
            best = [None] * size
            via = [-1] * size
            best[src] = 0
            heap = [(0, src)]
            while heap:
                d, node = heapq.heappop(heap)
                if d > best[node]:
                    continue
                for j in self.out[node]:
                    if self.room[j] <= 0:
                        continue
                    nxt = self.head[j]
                    cand = d + self.price[j] + height[node] - height[nxt]
                    if best[nxt] is None or cand < best[nxt]:
                        best[nxt] = cand
                        via[nxt] = j
                        heapq.heappush(heap, (cand, nxt))
            if best[dst] is None:
                raise RuntimeError("no plan carries every unit of need")
            for node in range(size):
                if best[node] is not None:
                    height[node] += best[node]
            push, node = amount - moved, dst
            while node != src:
                push = min(push, self.room[via[node]])
                node = self.tail(via[node])
            node = dst
            while node != src:
                j = via[node]
                self.room[j] -= push
                self.room[j ^ 1] += push
                node = self.tail(j)
            moved += push

    def duals(self):
        """Node prices with no negative reduced price on any residual arc."""
        size = len(self.out)
        dual = [0] * size
        waiting = deque(range(size))
        queued = [True] * size
        while waiting:
            node = waiting.popleft()
            queued[node] = False
            for j in self.out[node]:
                if self.room[j] > 0:
                    nxt = self.head[j]
                    if dual[node] + self.price[j] < dual[nxt]:
                        dual[nxt] = dual[node] + self.price[j]
                        if not queued[nxt]:
                            queued[nxt] = True
                            waiting.append(nxt)
        return dual


def make_plan(buses, clock, caps, feeder_by_slot, depot_price):
    """The day plan of rule 15 as {(bus_id, slot): kWh}."""
    n = len(buses)
    slots = clock.count
    SRC, SNK = 0, 1
    first_bus = 2
    first_cell = first_bus + n                       # (depot, slot) nodes
    first_slot = first_cell + len(DEPOT_NAMES) * slots
    net = Network(first_slot + slots)
    total_need = sum(b.need for b in buses)
    total_pub = sum(sum(b.published.values()) for b in buses)
    top_price = max(max(p) for p in depot_price.values())
    # Weights that keep the three goals strictly ordered (rule 15).
    w_cost = total_pub + 1
    w_unmet = w_cost * (top_price * total_need + 1) + 1
    cells = {}
    for i, bus in enumerate(buses):
        node = first_bus + i
        net.arc(SRC, node, bus.need, 0)
        net.arc(node, SNK, bus.need, w_unmet * bus.weight)
        d = DEPOT_NAMES.index(bus.depot)
        for s in range(bus.a, bus.e):
            cell = first_cell + d * slots + s
            keep = min(bus.published.get(s, 0), bus.rate)
            unit = w_cost * depot_price[bus.depot][s]
            own = []
            if keep:
                own.append(net.arc(node, cell, keep, unit - 1))
            if bus.rate > keep:
                own.append(net.arc(node, cell, bus.rate - keep, unit))
            cells[(s, bus.bus_id)] = (own, node, cell)
    for d, depot in enumerate(DEPOT_NAMES):
        for s in range(slots):
            net.arc(first_cell + d * slots + s, first_slot + s, caps[depot][s], 0)
    for s in range(slots):
        net.arc(first_slot + s, SNK, feeder_by_slot[s], 0)
    net.cheapest_flow(SRC, SNK, total_need)
    settle_ties(net, cells)
    plan = {}
    for (s, bid), (own, _, _) in cells.items():
        k = sum(net.room[j ^ 1] for j in own)
        if k:
            plan[(bid, s)] = k
    return plan


def settle_ties(net, cells):
    """Among optimal plans, raise each (slot, bus) value in turn as far as it goes."""
    dual = net.duals()
    tight = [net.price[j] + dual[net.tail(j)] - dual[net.head[j]] == 0 for j in range(len(net.head))]
    frozen = bytearray(len(net.head))
    for key in sorted(cells):
        own, bus_node, cell = cells[key]
        for j in own:
            frozen[j] = frozen[j ^ 1] = 1
        while True:
            lift = [j for j in own if tight[j] and net.room[j] > 0]
            if not lift:
                break
            back = {cell: None}
            todo = deque([cell])
            while todo and bus_node not in back:
                node = todo.popleft()
                for j in net.out[node]:
                    if frozen[j] or not tight[j] or net.room[j] <= 0:
                        continue
                    nxt = net.head[j]
                    if nxt not in back:
                        back[nxt] = j
                        todo.append(nxt)
            if bus_node not in back:
                break
            path, node = [], bus_node
            while node != cell:
                path.append(back[node])
                node = net.tail(back[node])
            push = min([net.room[lift[0]]] + [net.room[j] for j in path])
            for j in path + [lift[0]]:
                net.room[j] -= push
                net.room[j ^ 1] += push


# ----------------------------------------------------------------- reports

def totals(group, plan, clock, depot_price, fleet_by_slot):
    energy = sum(k for (bid, _), k in plan.items() if bid in group)
    cost = sum(k * depot_price[group[bid].depot][s] for (bid, s), k in plan.items() if bid in group)
    unmet = sum(b.need - sum(plan.get((b.bus_id, s), 0) for s in range(b.a, b.e)) for b in group.values())
    per_slot = [0] * clock.count
    for (bid, s), k in plan.items():
        if bid in group:
            per_slot[s] += k
    return {
        "buses": len(group),
        "energy_kwh": energy,
        "cost_cents": cost,
        "unmet_kwh": unmet,
        "slots": [{"slot": clock.name(s), "kwh": per_slot[s], "feeder_kwh": fleet_by_slot[s]}
                  for s in range(clock.count)],
    }


def write_reports(out, pd, clock, buses, plan, rejected, depot_price):
    out.mkdir(parents=True, exist_ok=True)

    def dump(name, doc):
        (out / name).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    fleet_by_slot = [0] * clock.count
    for (_, s), k in plan.items():
        fleet_by_slot[s] += k

    audit, weighted, moved, short, changed = [], 0, 0, 0, 0
    for b in buses:
        got = {s: plan[(b.bus_id, s)] for s in range(b.a, b.e) if (b.bus_id, s) in plan}
        delivered = sum(got.values())
        unmet = b.need - delivered
        if unmet == 0:
            reason = None
        elif b.need > b.rate * (b.e - b.a):
            reason = "window"
        else:
            reason = "supply"
        differs = any(got.get(s, 0) != b.published.get(s, 0) for s in set(got) | set(b.published))
        weighted += b.weight * unmet
        moved += sum(max(0, k - got.get(s, 0)) for s, k in b.published.items())
        short += unmet > 0
        changed += differs
        audit.append({
            "bus_id": b.bus_id, "depot": b.depot, "class": b.klass,
            "need_kwh": b.need, "delivered_kwh": delivered, "unmet_kwh": unmet,
            "unmet_reason": reason, "changed": differs,
            "charges": [{"slot": clock.name(s), "kwh": got[s]} for s in sorted(got)],
        })
    dump("policy_audit.json", {"plan_date": pd.isoformat(), "buses": audit})

    for depot in DEPOT_NAMES:
        group = {b.bus_id: b for b in buses if b.depot == depot}
        dump("region_%s.json" % depot, dict({"depot": depot}, **totals(group, plan, clock, depot_price, fleet_by_slot)))
    for klass in CLASS_NAMES:
        group = {b.bus_id: b for b in buses if b.klass == klass}
        dump("segment_%s.json" % klass, dict({"class": klass}, **totals(group, plan, clock, depot_price, fleet_by_slot)))

    by_id = {b.bus_id: b for b in buses}
    cost = sum(k * depot_price[by_id[bid].depot][s] for (bid, s), k in plan.items())
    dump("summary.json", {
        "plan_date": pd.isoformat(),
        "weighted_unmet_kwh": weighted,
        "energy_cost_cents": cost,
        "moved_kwh": moved,
        "feeder_peak_kwh": max(fleet_by_slot) if fleet_by_slot else 0,
        "feeder_kwh_by_slot": [{"slot": clock.name(s), "kwh": fleet_by_slot[s]} for s in range(clock.count)],
        "buses_planned": len(buses),
        "buses_short": short,
        "buses_changed": changed,
        "records_rejected": len(rejected),
    })
    dump("data_quality.json", {
        "plan_date": pd.isoformat(),
        "rejected": [{"file": f, "line": n, "reason": r} for f, n, r in sorted(rejected)],
    })


# ----------------------------------------------------------------- main

def run(data, out):
    folder = Folder(data)
    pd, clock, feeder = read_grid(folder)
    outages, derates, extras = read_notice(folder, clock)
    versions = read_tariffs(folder, clock)
    current = tariff_on(versions, pd)
    meters = fit_meters(folder, clock, versions)
    day = 1440 // clock.minutes
    depot_price = {d: [current.prices[(s + meters[d]) % day] for s in range(clock.count)] for d in DEPOT_NAMES}
    buses, rejected = read_buses(folder, pd, clock, extras)
    for b in buses:
        if b.depot not in DEPOT_NAMES:
            raise InputError("roster.csv", "bus %s has unknown depot %r" % (b.bus_id, b.depot))
    caps = read_depots(folder, clock, outages)
    feeder_by_slot = [feeder] * clock.count
    for slots, limit in derates:
        for s in slots:
            feeder_by_slot[s] = limit
    plan = make_plan(buses, clock, caps, feeder_by_slot, depot_price)
    write_reports(Path(out), pd, clock, buses, plan, rejected, depot_price)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--out", default="/app/out")
    args = ap.parse_args(argv)
    try:
        run(args.data, args.out)
    except InputError as err:
        print("derive_report: cannot read input %s" % err, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
