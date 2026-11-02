import ast
import copy
import csv
import json
import os
import signal
import subprocess
import sys
import tempfile

from rewardkit import criteria, criterion


def _read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_corpus(data_dir):
    pools = {}
    for row in _read_csv(os.path.join(data_dir, "pools.csv")):
        pools[row["pool"]] = {
            "mode": row["mode"],
            "lag": int(row["lag"]),
        }
    indexes = {}
    for row in _read_csv(os.path.join(data_dir, "indexes.csv")):
        indexes[row["index"]] = {
            "layout": row["layout"],
            "parent": row["parent"],
            "warmup": int(row["warmup"]),
        }
    analysts = {}
    for row in _read_csv(os.path.join(data_dir, "analysts.csv")):
        analysts[row["analyst"]] = {"clearance": row["clearance"]}
    partitions = {}
    for row in _read_csv(os.path.join(data_dir, "partitions.csv")):
        partitions[row["partition"]] = {
            "pool": row["pool"],
            "index": row["index"],
            "plan": row["plan"],
            "replica": int(row["replica"]),
        }
    lookups = []
    for row in _read_jsonl(os.path.join(data_dir, "lookups.jsonl")):
        lookups.append({
            "seq": int(row["seq"]),
            "partition": row["partition"],
            "query": row["query"],
            "analyst": row["analyst"],
            "verb": row["verb"],
            "phase": row["phase"],
            "cursor": int(row["cursor"]),
            "reach": int(row["reach"]),
            "pages": int(row["pages"]),
            "rounds": int(row["rounds"]),
        })
    return {
        "pools": pools,
        "indexes": indexes,
        "analysts": analysts,
        "partitions": partitions,
        "lookups": lookups,
    }


def charged_layout(indexes, index):
    entry = indexes[index]
    parent = entry["parent"]
    if parent:
        return indexes[parent]["layout"]
    return entry["layout"]


def governing_count(lookup):
    if lookup["pages"] > 0:
        base = lookup["pages"] * 4
    else:
        base = lookup["reach"]
    return base * (lookup["rounds"] + 1)


# Every division in the keyed adjustments rounds towards negative infinity, so
# a figure the scan plan has pushed below zero rounds away from zero here.
def _adjust_plan(figure, plan):
    if plan == "scan":
        return figure - 7
    if plan == "merge":
        return figure * 2 // 3
    if plan == "fanout":
        return figure + 11
    if plan == "stream":
        return figure - (figure % 9)
    if plan == "nested":
        return figure * 13 // 11
    if plan == "hybrid":
        return figure // 3
    return figure


def _adjust_layout(figure, layout):
    if layout == "sparse":
        return figure * 8 // 9
    if layout == "bitmap":
        return figure + 17
    if layout == "column":
        return figure * 3 // 2
    return figure


def _adjust_phase(figure, phase):
    if phase == "shoulder":
        return figure - figure // 6
    if phase == "peak":
        return figure + 9
    return figure


def _adjust_mode(figure, mode):
    if mode == "turbo":
        return figure * 19 // 17
    if mode == "cold":
        if figure > 540:
            figure = 540
        return figure - 13
    return figure


def _band(cost):
    if cost >= 320:
        return "heavy"
    if cost >= 160:
        return "warm"
    if cost >= 30:
        return "light"
    return "idle"


def _clearance_limit(clearance):
    if clearance == "principal":
        return 48
    if clearance == "staff":
        return 30
    if clearance == "rotational":
        return 14
    return 0


def _status(verb, band, debt_before, clearance):
    if verb == "refresh" or verb == "snapshot":
        return "setup"
    if verb == "purge":
        return "locked"
    if band == "idle":
        return "dropped"
    if debt_before > _clearance_limit(clearance):
        return "flagged"
    return "ok"


def _debt_step(reach, replica, run):
    step = reach // 40
    if replica == 3:
        step = step * 2
    elif replica == 2:
        step = step + 7
    if run >= 1:
        step = step + 5
    return step


def _release(credit):
    if credit <= 0:
        return 0
    return 36 if credit > 36 else credit


def resolve(corpus):
    pools = corpus["pools"]
    indexes = corpus["indexes"]
    analysts = corpus["analysts"]
    partitions = corpus["partitions"]

    state = {}
    for partition in partitions.values():
        index = partition["index"]
        if index not in state:
            state[index] = {
                "baseline": indexes[index]["warmup"],
                "debt": 0,
                "credit": 0,
                "misses": 0,
                "run": 0,
                "seen": 0,
                "waiver": 0,
                "doubled": 0,
                "locked": 0,
                "recent": [],
            }

    probes = []
    for lookup in sorted(corpus["lookups"], key=lambda row: row["seq"]):
        partition = partitions[lookup["partition"]]
        slot = state[partition["index"]]
        mode = pools[partition["pool"]]["mode"]
        layout = charged_layout(indexes, partition["index"])
        clearance = analysts[lookup["analyst"]]["clearance"]

        figure = lookup["cursor"] - slot["baseline"]
        if figure < 0:
            figure = 0
        figure = figure * 1440 // governing_count(lookup)
        if figure < 0:
            figure = 0
        figure = _adjust_plan(figure, partition["plan"])
        figure = _adjust_layout(figure, layout)
        if slot["seen"]:
            figure = _adjust_phase(figure, lookup["phase"])
        figure = _adjust_mode(figure, mode)
        released = _release(slot["credit"])
        figure = figure + released
        debt_before = slot["debt"]
        if slot["doubled"]:
            cost = figure - debt_before * 2
            slot["doubled"] = 0
        else:
            cost = figure - debt_before
        if cost < 0:
            cost = 0
        back = len(slot["recent"]) - 1
        while back >= 0:
            if slot["recent"][back][0] == lookup["query"]:
                cost = slot["recent"][back][1]
                break
            back = back - 1
        if slot["waiver"]:
            cost = cost // 2
            slot["waiver"] = 0
        if slot["locked"]:
            cost = cost * 3 // 2
        band = _band(cost)
        status = _status(lookup["verb"], band, debt_before, clearance)

        probes.append({
            "analyst": lookup["analyst"],
            "band": band,
            "cost": cost,
            "debt_before": debt_before,
            "partition": lookup["partition"],
            "query": lookup["query"],
            "seq": lookup["seq"],
            "status": status,
            "verb": lookup["verb"],
        })

        if status == "dropped":
            slot["misses"] = slot["misses"] + 1
            if slot["misses"] >= 2:
                slot["locked"] = 1
        slot["credit"] = slot["credit"] - released
        if lookup["verb"] == "refresh":
            slot["baseline"] = lookup["cursor"]
            slot["run"] = 0
        elif lookup["verb"] == "snapshot":
            banked = slot["credit"] + slot["debt"]
            slot["credit"] = 90 if banked > 90 else banked
            slot["debt"] = 0
            slot["waiver"] = 1
            slot["run"] = 0
        elif lookup["verb"] == "fetch":
            debt = slot["debt"] + _debt_step(
                lookup["reach"], partition["replica"], slot["run"])
            if debt > 120:
                debt = 120
            slot["debt"] = debt
            slot["baseline"] = slot["baseline"] + 4
            slot["run"] = slot["run"] + 1
        else:
            slot["doubled"] = 1
            slot["run"] = 0
        slot["recent"].append((lookup["query"], cost))
        if len(slot["recent"]) > 4:
            slot["recent"] = slot["recent"][1:]
        slot["seen"] = 1

    partition_rows = []
    for partition_id in sorted(partitions):
        slot = state[partitions[partition_id]["index"]]
        rows = [row for row in probes if row["partition"] == partition_id]
        counted = [row for row in rows
                   if row["status"] == "ok" or row["status"] == "flagged"]
        cost_total = 0
        peak_cost = 0
        best = None
        for row in counted:
            cost_total = cost_total + row["cost"]
            if row["cost"] > peak_cost:
                peak_cost = row["cost"]
            if best is None:
                best = row
            elif row["cost"] > best["cost"]:
                best = row
            elif row["cost"] == best["cost"] and row["seq"] > best["seq"]:
                best = row
        misses = slot["misses"]
        if misses >= 3:
            disposition = "stalled"
        elif slot["debt"] > 39:
            disposition = "held"
        else:
            disposition = "open"
        bands = {"heavy": 0, "idle": 0, "light": 0, "warm": 0}
        for row in rows:
            bands[row["band"]] = bands[row["band"]] + 1
        partition_rows.append({
            "bands": bands,
            "baseline_end": slot["baseline"],
            "cost_total": cost_total,
            "disposition": disposition,
            "fetched": sum(1 for row in rows if row["verb"] == "fetch"),
            "flagged": sum(1 for row in rows if row["status"] == "flagged"),
            "lookups": len(rows),
            "misses": misses,
            "partition": partition_id,
            "peak_cost": peak_cost,
            "top_query": best["query"] if best is not None else None,
        })
    partition_rows.sort(key=lambda row: (-row["cost_total"], row["partition"]))

    by_band = {"heavy": 0, "idle": 0, "light": 0, "warm": 0}
    by_status = {"dropped": 0, "flagged": 0, "locked": 0, "ok": 0, "setup": 0}
    for row in probes:
        by_band[row["band"]] = by_band[row["band"]] + 1
        by_status[row["status"]] = by_status[row["status"]] + 1

    top_partition = None
    top_total = None
    for row in partition_rows:
        if top_total is None or row["cost_total"] > top_total:
            top_partition = row["partition"]
            top_total = row["cost_total"]
        elif row["cost_total"] == top_total and row["partition"] > top_partition:
            top_partition = row["partition"]

    catalog = {
        "by_band": by_band,
        "by_status": by_status,
        "cost_total": sum(row["cost_total"] for row in partition_rows),
        "lookups": len(probes),
        "partitions": len(partition_rows),
        "stalled": sorted(row["partition"] for row in partition_rows
                          if row["disposition"] == "stalled"),
        "top_partition": top_partition,
    }
    return probes, partition_rows, catalog


def derive(data_dir):
    return resolve(load_corpus(data_dir))


def render_probes(probes):
    parts = []
    for row in probes:
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    return "".join(parts)


def render_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def write_reports(out_dir, probes, partition_rows, catalog):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "probes.jsonl"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_probes(probes))
    with open(os.path.join(out_dir, "partitions.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document({"partitions": partition_rows}))
    with open(os.path.join(out_dir, "catalog.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document(catalog))



_PLANS = ["seek", "scan", "merge", "fanout", "stream", "nested", "hybrid"]
_LAYOUTS = ["btree", "sparse", "bitmap", "column"]
_PHASES = ["quiet", "shoulder", "peak"]
_MODES = ["paired", "turbo", "cold"]
_CLEARANCES = ["principal", "staff", "rotational", "vendor"]
_PROBE_CURSORS = [421, 563, 703, 849, 989]
_VERBS = ["fetch", "fetch", "fetch", "fetch", "fetch", "refresh", "snapshot", "purge"]


class _Rng:
    def __init__(self, seed):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def draw(self):
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self.state >> 33) & 0x7FFFFFFF

    def below(self, limit):
        return self.draw() % limit

    def between(self, low, high):
        return low + self.below(high - low + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def shuffle(self, items):
        position = len(items) - 1
        while position > 0:
            swap = self.below(position + 1)
            items[position], items[swap] = items[swap], items[position]
            position -= 1
        return items


def _plain_count(triple):
    plan, layout, mode = triple
    return (plan == "seek") + (layout == "btree") + (mode == "paired")


def mixed_triples():
    out = []
    for position in range(28):
        plan = _PLANS[position % 7]
        wrap = position // 7
        if plan == "seek":
            layout = _LAYOUTS[1 + (position + wrap) % 3]
            mode = _MODES[1 + (position + wrap) % 2]
        else:
            layout = _LAYOUTS[(position * 3 + wrap) % 4]
            mode = _MODES[(position * 2 + wrap) % 3]
            if layout == "btree" and mode == "paired":
                mode = _MODES[1 + (position + wrap) % 2]
        triple = (plan, layout, mode)
        if triple not in out:
            out.append(triple)
    return out


def _fresh_slot(warmup):
    return {
        "baseline": warmup,
        "debt": 0,
        "credit": 0,
        "misses": 0,
        "run": 0,
        "seen": 0,
        "waiver": 0,
        "doubled": 0,
        "locked": 0,
        "recent": [],
    }


class _Case:
    def __init__(self):
        self.pools = []
        self.indexes = []
        self.analysts = []
        self.partitions = []
        self.lookups = []
        self.seq = 0
        self.state = {}
        self.meta = {}
        self.queries = {}
        self.predicted = {}

    def pool(self, name, mode, lag):
        self.pools.append((name, mode, lag))
        return name

    def index(self, name, layout, parent, warmup):
        self.indexes.append((name, layout, parent, warmup))
        return name

    def analyst(self, name, clearance):
        self.analysts.append((name, clearance))
        return name

    def _row_field(self, table, name, position):
        for row in table:
            if row[0] == name:
                return row[position]
        raise KeyError(name)

    def charged(self, index):
        parent = self._row_field(self.indexes, index, 2)
        if parent:
            return self._row_field(self.indexes, parent, 1)
        return self._row_field(self.indexes, index, 1)

    def partition(self, partition_id, pool, index, plan, replica):
        self.partitions.append((partition_id, pool, index, plan, replica))
        if index not in self.state:
            self.state[index] = _fresh_slot(self._row_field(self.indexes, index, 3))
        self.meta[partition_id] = {
            "index": index,
            "plan": plan,
            "layout": self.charged(index),
            "mode": self._row_field(self.pools, pool, 1),
            "replica": replica,
        }
        self.queries[partition_id] = 0
        return partition_id

    def checkpoint(self):
        return copy.deepcopy((self.lookups, self.seq, self.state, self.queries, self.predicted))

    def restore(self, saved):
        self.lookups, self.seq, self.state, self.queries, self.predicted = copy.deepcopy(saved)

    def slot(self, partition_id):
        return self.state[self.meta[partition_id]["index"]]

    def next_query(self, partition_id):
        position = self.queries[partition_id]
        self.queries[partition_id] = position + 1
        return "Q%s%03d" % (partition_id[-2:], position + 1)

    def normalised(self, partition_id, cursor, reach, pages, rounds):
        figure = cursor - self.slot(partition_id)["baseline"]
        if figure < 0:
            figure = 0
        count = (pages * 4 if pages > 0 else reach) * (rounds + 1)
        return figure * 1440 // count

    def _figure(self, partition_id, query, phase, cursor, reach, pages, rounds):
        meta = self.meta[partition_id]
        slot = self.slot(partition_id)
        figure = self.normalised(partition_id, cursor, reach, pages, rounds)
        figure = _adjust_plan(figure, meta["plan"])
        figure = _adjust_layout(figure, meta["layout"])
        if slot["seen"]:
            figure = _adjust_phase(figure, phase)
        figure = _adjust_mode(figure, meta["mode"])
        released = _release(slot["credit"])
        figure = figure + released
        debt_before = slot["debt"]
        if slot["doubled"]:
            cost = figure - debt_before * 2
        else:
            cost = figure - debt_before
        if cost < 0:
            cost = 0
        back = len(slot["recent"]) - 1
        while back >= 0:
            if slot["recent"][back][0] == query:
                cost = slot["recent"][back][1]
                break
            back = back - 1
        if slot["waiver"]:
            cost = cost // 2
        if slot["locked"]:
            cost = cost * 3 // 2
        return cost, released, debt_before

    def lookup(self, partition_id, analyst, verb, phase, cursor, reach,
               pages=0, rounds=1, query=None):
        meta = self.meta[partition_id]
        slot = self.slot(partition_id)
        if query is None:
            query = self.next_query(partition_id)
        cost, released, debt_before = self._figure(
            partition_id, query, phase, cursor, reach, pages, rounds)
        self.seq += 1
        self.lookups.append({
            "seq": self.seq,
            "partition": partition_id,
            "query": query,
            "analyst": analyst,
            "verb": verb,
            "phase": phase,
            "cursor": cursor,
            "reach": reach,
            "pages": pages,
            "rounds": rounds,
        })
        self.predicted[self.seq] = cost
        slot["doubled"] = 0
        slot["waiver"] = 0
        clearance = self._row_field(self.analysts, analyst, 1)
        status = _status(verb, _band(cost), debt_before, clearance)
        if status == "dropped":
            slot["misses"] = slot["misses"] + 1
            if slot["misses"] >= 2:
                slot["locked"] = 1
        slot["credit"] = slot["credit"] - released
        if verb == "refresh":
            slot["baseline"] = cursor
            slot["run"] = 0
        elif verb == "snapshot":
            banked = slot["credit"] + slot["debt"]
            slot["credit"] = 90 if banked > 90 else banked
            slot["debt"] = 0
            slot["waiver"] = 1
            slot["run"] = 0
        elif verb == "fetch":
            debt = slot["debt"] + _debt_step(reach, meta["replica"], slot["run"])
            if debt > 120:
                debt = 120
            slot["debt"] = debt
            slot["baseline"] = slot["baseline"] + 4
            slot["run"] = slot["run"] + 1
        else:
            slot["doubled"] = 1
            slot["run"] = 0
        slot["recent"].append((query, cost))
        if len(slot["recent"]) > 4:
            slot["recent"] = slot["recent"][1:]
        slot["seen"] = 1
        return self.seq

    def target(self, partition_id, analyst, verb, phase, cost, reach,
               pages=0, rounds=1, query=None):
        base = self.slot(partition_id)["baseline"]
        probe = query if query is not None else "PROBE-QUERY"
        for spread in (reach, 1200, 2400, 3600, 1800, 3000):
            best, flat = -1, 0
            for step in range(0, 200001):
                got, _released, _debt = self._figure(
                    partition_id, probe, phase, base + step, spread, pages, rounds)
                if got == cost:
                    return self.lookup(partition_id, analyst, verb, phase,
                                       base + step, spread, pages, rounds, query)
                if got > cost:
                    break
                if got > best:
                    best, flat = got, 0
                else:
                    flat += 1
                    if flat > 3000:
                        break
        raise ValueError("no cursor on %s yields cost %d" % (partition_id, cost))

    def aim(self, partition_id, analyst, verb, phase, cost, reach):
        for _attempt in range(5):
            for tone in (phase, "quiet", "peak", "shoulder"):
                try:
                    return self.target(partition_id, analyst, verb, tone, cost, reach)
                except ValueError:
                    pass
            self.strong(partition_id, analyst, "fetch" if _attempt else "refresh", phase, 2400, 60)
        raise ValueError("no cursor on %s yields cost %d" % (partition_id, cost))

    def strong(self, partition_id, analyst, verb, phase, reach, want=90,
               pages=0, rounds=1, query=None):
        base = self.slot(partition_id)["baseline"]
        probe = query if query is not None else "PROBE-QUERY"
        best, best_step, flat = -1, 0, 0
        for step in range(0, 200001):
            got, _released, _debt = self._figure(
                partition_id, probe, phase, base + step, reach, pages, rounds)
            if got >= want:
                return self.lookup(partition_id, analyst, verb, phase,
                                   base + step, reach, pages, rounds, query)
            if got > best:
                best, best_step, flat = got, step, 0
            else:
                flat += 1
                if flat > 3000:
                    break
        # The chain saturates below the wanted cost (a capped mode, a waiver or
        # a heavy debt), so settle on the first cursor that reaches its ceiling.
        return self.lookup(partition_id, analyst, verb, phase,
                           base + best_step, reach, pages, rounds, query)

    def flat(self, partition_id, analyst, verb, phase, reach, query=None):
        base = self.slot(partition_id)["baseline"]
        return self.lookup(partition_id, analyst, verb, phase, base, reach,
                           0, 1, query)

    def miss(self, partition_id, analyst, phase):
        for _attempt in range(4):
            while self.slot(partition_id)["credit"] > 0:
                self.flat(partition_id, analyst, "refresh", phase, 1200)
            base = self.slot(partition_id)["baseline"]
            for tone in (phase, "quiet", "shoulder"):
                got, _released, _debt = self._figure(
                    partition_id, "PROBE-QUERY", tone, base, 1200, 0, 1)
                if got < 30:
                    return self.lookup(partition_id, analyst, "fetch", tone, base, 1200)
            self.strong(partition_id, analyst, "fetch", phase, 2400, 60)
        raise ValueError("no cursor on %s settles in the bottom band" % partition_id)

    def nudge(self, partition_id, analyst, verb, phase, reach, level):
        base = self.slot(partition_id)["baseline"]
        for step in range(0, 5000):
            if self.normalised(partition_id, base + step, reach, 0, 1) == level:
                return self.lookup(partition_id, analyst, verb, phase,
                                   base + step, reach)
        raise ValueError("no cursor on %s normalises to %d" % (partition_id, level))

    def reach_for(self, partition_id, debt):
        slot = self.slot(partition_id)
        replica = self.meta[partition_id]["replica"]
        for reach in range(40, 16000):
            grown = slot["debt"] + _debt_step(reach, replica, slot["run"])
            if grown > 120:
                grown = 120
            if grown == debt:
                return reach
        return None

    def fund(self, partition_id, analyst, phase, debt, want):
        reach = self.reach_for(partition_id, debt)
        if reach is None:
            raise ValueError("no fetch on %s leaves a debt of %d" % (partition_id, debt))
        return self.strong(partition_id, analyst, "fetch", phase, reach, want)

    def corpus(self):
        return {
            "pools": dict((name, {"mode": mode, "lag": lag})
                          for name, mode, lag in self.pools),
            "indexes": dict((name, {"layout": layout, "parent": parent, "warmup": warmup})
                            for name, layout, parent, warmup in self.indexes),
            "analysts": dict((name, {"clearance": clearance})
                             for name, clearance in self.analysts),
            "partitions": dict((name, {"pool": pool, "index": index, "plan": plan,
                                       "replica": replica})
                               for name, pool, index, plan, replica in self.partitions),
            "lookups": [dict(row) for row in self.lookups],
        }


_WARMUPS = [120, 70, 160, 110, 95, 145, 60, 180, 130, 85]


class _Layout:
    def __init__(self, case, seed, pool_of, prefix, index_prefix):
        self.case = case
        self.rng = _Rng(seed)
        self.wrng = _Rng(seed ^ 0x2E19)
        self.triples = mixed_triples()
        self.cursor = 0
        self.count = 0
        self.pool_of = pool_of
        self.prefix = prefix
        self.index_prefix = index_prefix

    def next_partition(self, replica=None, triple=None, alias=False,
                       name=None, index=None):
        if triple is None:
            triple = self.triples[self.cursor % len(self.triples)]
            self.cursor += 1
        plan, layout, mode = triple
        self.count += 1
        partition_id = name if name is not None else "%s%02d" % (self.prefix, self.count)
        if replica is None:
            replica = (self.count % 3) + 1
        if index is None:
            index = "%s%02d" % (self.index_prefix, self.count)
            warmup = _WARMUPS[self.wrng.below(len(_WARMUPS))]
            if alias:
                parent = "%sP%02d" % (self.index_prefix, self.count)
                self.case.index(parent, layout, "", warmup + 20)
                decoy = _LAYOUTS[(_LAYOUTS.index(layout) + 2) % 4]
                self.case.index(index, decoy, parent, warmup)
            else:
                self.case.index(index, layout, "", warmup)
        self.case.partition(partition_id, self.pool_of[mode], index, plan, replica)
        return partition_id

    def triple_on(self, layout, rng):
        fitting = [triple for triple in self.triples if triple[1] == layout]
        return rng.pick(fitting)

    def fine_triple(self, rng):
        return rng.pick([triple for triple in self.triples
                         if triple[1] != "column" and triple[0] not in ("hybrid", "stream")])

    def warm_triple(self, rng):
        return rng.pick([triple for triple in self.triples if triple[2] != "cold"])


_POOL_OF = {"paired": "POL-A", "turbo": "POL-B", "cold": "POL-C"}
_FRESH_POOL = {"paired": "FPL-1", "turbo": "FPL-2", "cold": "FPL-3"}


def _wander(case, rng, partition_id, roster, low, high, phase=None):
    for _step in range(rng.between(low, high)):
        base = case.slot(partition_id)["baseline"]
        if base > 1 and rng.below(14) == 0:
            cursor = base - rng.between(1, base - 1)
        else:
            cursor = base + rng.between(40, 1150)
        reach = rng.between(380, 2900)
        pages = 0 if rng.below(3) else rng.between(40, 420)
        tone = phase if phase is not None else rng.pick(_PHASES)
        case.lookup(partition_id, rng.pick(roster), rng.pick(_VERBS),
                    tone, cursor, reach, pages, rng.between(1, 3))


def _populate(case, lay, rng, roster, by_clearance, wanderers):
    """Lay out one catalogue run.

    Every rule the engine applies is exercised somewhere in the run, but each
    piece of evidence sits inside a partition that also carries unrelated
    lookups, so no partition reads off one constant on its own.
    """
    lead = by_clearance["principal"]
    jobs = []
    for _copy in range(2):
        for edge in (320, 160, 30):
            jobs.append(("edge", edge))
            jobs.append(("edge", edge - 1))
        for clearance, limit in (("principal", 48), ("staff", 30),
                                 ("rotational", 14), ("vendor", 0)):
            jobs.append(("tolerance", by_clearance[clearance], limit))
            jobs.append(("tolerance", by_clearance[clearance], limit + 1))
        jobs.extend([("held", 39), ("held", 40), ("repeat", 4), ("repeat", 5)])
        jobs.extend([("tie", "smaller"), ("tie", "larger"), ("recycle",)])
        jobs.extend([("misses", 1), ("misses", 2), ("misses", 3), ("misses", 4)])
    jobs.append(("repeat", 2))
    jobs.extend([("credit",), ("credit",)])
    jobs.extend([
        ("negative", ("scan", "sparse", "paired"), 2),
        ("negative", ("scan", "column", "paired"), 4),
        ("negative", ("scan", "sparse", "turbo"), 2),
        ("negative", ("scan", "sparse", "paired"), 1),
    ])
    jobs.extend([("cold", ("merge", "bitmap", "cold")),
                 ("cold", ("nested", "column", "cold"))])
    jobs.extend([("shared", 2), ("shared", 3), ("parent_view",)])
    for layout in _LAYOUTS:
        jobs.append(("alias", layout))
    for _slot in range(wanderers):
        jobs.append(("wander",))
    rng.shuffle(jobs)

    def replica_for(debt):
        replica = rng.between(1, 3)
        if replica == 3 and debt % 2:
            replica = 1
        if replica == 2 and debt < 8:
            replica = 1
        return replica

    for job in jobs:
        kind = job[0]
        if kind == "wander":
            part = lay.next_partition(rng.between(1, 3))
            _wander(case, rng, part, roster, 2, 5)
        elif kind == "edge":
            part = lay.next_partition(rng.between(1, 3), lay.fine_triple(rng))
            if rng.below(2):
                case.lookup(part, rng.pick(roster), rng.pick(["refresh", "purge", "snapshot"]),
                            rng.pick(_PHASES), case.slot(part)["baseline"] + rng.between(40, 900),
                            rng.between(600, 2400))
            case.aim(part, rng.pick(roster), rng.pick(["fetch", "fetch", "purge", "refresh"]),
                     rng.pick(_PHASES), job[1], rng.between(900, 2400))
            _wander(case, rng, part, roster, 1, 2)
        elif kind == "tolerance" or kind == "held":
            debt = job[2] if kind == "tolerance" else job[1]
            part = lay.next_partition(replica_for(debt))
            _wander(case, rng, part, roster, 1, 2)
            if debt == 0 or case.reach_for(part, debt) is None:
                case.flat(part, lead, "snapshot", rng.pick(_PHASES), 1200)
            if debt > 0:
                case.fund(part, lead, rng.pick(_PHASES), debt, rng.between(60, 260))
            if kind == "tolerance":
                case.strong(part, job[1], "fetch", rng.pick(_PHASES),
                            rng.between(400, 1600), rng.between(60, 300))
                _wander(case, rng, part, roster, 0, 1)
        elif kind == "misses":
            part = lay.next_partition(rng.between(1, 3))
            _wander(case, rng, part, roster, 1, 2)
            while case.slot(part)["misses"] < job[1]:
                case.miss(part, rng.pick(roster), rng.pick(_PHASES))
                case.strong(part, lead, "fetch", rng.pick(_PHASES),
                            rng.between(600, 2400), rng.between(80, 400))
        elif kind == "repeat":
            part = lay.next_partition(rng.between(1, 3), lay.warm_triple(rng))
            _wander(case, rng, part, roster, 0, 1)
            query = case.next_query(part)
            case.strong(part, lead, "fetch", rng.pick(_PHASES), 1200,
                        rng.between(420, 700), query=query)
            for _step in range(job[1] - 1):
                case.strong(part, rng.pick(roster), rng.pick(["fetch", "fetch", "purge"]),
                            rng.pick(_PHASES), rng.between(800, 2400), rng.between(60, 200))
            case.strong(part, lead, "fetch", rng.pick(_PHASES), 1200,
                        rng.between(60, 200), query=query)
            _wander(case, rng, part, roster, 0, 1)
        elif kind == "recycle":
            part = lay.next_partition(rng.between(1, 3), lay.warm_triple(rng))
            _wander(case, rng, part, roster, 1, 1)
            query = case.next_query(part)
            case.strong(part, lead, "fetch", "quiet", 1200, rng.between(420, 640), query=query)
            case.flat(part, lead, "snapshot", "quiet", 1200)
            case.flat(part, lead, "fetch", "quiet", 1200, query=query)
            case.flat(part, lead, "fetch", "shoulder", 1200, query=query)
        elif kind == "credit":
            part = lay.next_partition(rng.between(1, 3))
            _wander(case, rng, part, roster, 0, 1)
            while case.slot(part)["debt"] < 96:
                case.strong(part, lead, "fetch", rng.pick(_PHASES),
                            rng.between(2400, 3600), rng.between(80, 300))
            case.flat(part, lead, "snapshot", rng.pick(_PHASES), 1200)
            for _step in range(3):
                case.strong(part, rng.pick(roster), rng.pick(["fetch", "refresh", "fetch"]),
                            rng.pick(_PHASES), rng.between(600, 2000), rng.between(80, 300))
        elif kind == "negative":
            part = lay.next_partition(1, job[1])
            _wander(case, rng, part, roster, 0, 1)
            while case.slot(part)["debt"] < 80:
                case.strong(part, lead, "fetch", rng.pick(_PHASES),
                            rng.between(2400, 3600), rng.between(80, 300))
            case.flat(part, lead, "snapshot", rng.pick(_PHASES), 1200)
            base = case.slot(part)["baseline"]
            case.lookup(part, lead, "refresh", rng.pick(_PHASES),
                        base + rng.between(100, 400), 1200)
            case.nudge(part, lead, "fetch", rng.pick(["quiet", "peak", "quiet"]),
                       rng.between(800, 2000), job[2])
            _wander(case, rng, part, roster, 0, 1)
        elif kind == "cold":
            part = lay.next_partition(rng.between(1, 3), job[1])
            _wander(case, rng, part, roster, 0, 1)
            for _step in range(2):
                base = case.slot(part)["baseline"]
                case.lookup(part, lead, "fetch", rng.pick(_PHASES),
                            base + rng.between(1500, 3000), rng.between(700, 1400))
            _wander(case, rng, part, roster, 0, 1)
        elif kind == "tie":
            part = lay.next_partition(rng.between(1, 3), lay.warm_triple(rng))
            base = case.slot(part)["baseline"]
            case.lookup(part, lead, "refresh", "quiet", base + rng.between(40, 300), 1200)
            first = case.next_query(part)
            second = case.next_query(part)
            if job[1] == "smaller":
                first, second = second, first
            saved = case.checkpoint()
            for _attempt in range(40):
                try:
                    cost = rng.between(420, 900)
                    case.target(part, lead, "fetch", rng.pick(_PHASES), cost, 1200, query=first)
                    case.flat(part, lead, "purge", rng.pick(_PHASES), 1200)
                    case.target(part, lead, "fetch", rng.pick(_PHASES), cost, 1200, query=second)
                    break
                except ValueError:
                    case.restore(saved)
            else:
                raise ValueError("no tie fits on %s" % part)
            case.miss(part, lead, rng.pick(_PHASES))
        elif kind == "shared":
            first = lay.next_partition(rng.between(1, 3))
            index = case.meta[first]["index"]
            members = [first]
            for _member in range(job[1] - 1):
                triple = lay.triple_on(case.meta[first]["layout"], rng)
                members.append(lay.next_partition(rng.between(1, 3), triple, index=index))
            for turn in range(3 * job[1]):
                # A later member opens on a phase that carries an adjustment, so
                # the index's exemption and a per partition one part ways.
                opening = rng.pick(["peak", "shoulder"]) if 0 < turn < job[1] else None
                _wander(case, rng, members[turn % job[1]], roster, 1, 1, opening)
        elif kind == "parent_view":
            view = lay.next_partition(rng.between(1, 3), alias=True)
            index = case.meta[view]["index"]
            parent = case._row_field(case.indexes, index, 2)
            triple = lay.triple_on(case.meta[view]["layout"], rng)
            owner = lay.next_partition(rng.between(1, 3), triple, index=parent)
            for turn in range(6):
                _wander(case, rng, (view, owner)[turn % 2], roster, 1, 1)
        elif kind == "alias":
            part = lay.next_partition(rng.between(1, 3), lay.triple_on(job[1], rng), alias=True)
            _wander(case, rng, part, roster, 2, 4)

    _probes, rows, _catalog = resolve(case.corpus())
    summit = max(row["cost_total"] for row in rows) + rng.between(300, 900)
    for shares in (3, 2):
        part = lay.next_partition(rng.between(1, 3), lay.warm_triple(rng))
        saved = case.checkpoint()
        for _attempt in range(60):
            try:
                left = summit
                for share in range(shares, 0, -1):
                    cost = left if share == 1 else left // share + rng.between(-60, 60)
                    case.target(part, lead, "fetch", rng.pick(_PHASES), cost, 1200)
                    left = left - cost
                    if shares == 2 and share == 2:
                        case.flat(part, lead, "purge", rng.pick(_PHASES), 1200)
                break
            except ValueError:
                case.restore(saved)
        else:
            raise ValueError("no split of %d fits on %s" % (summit, part))
    return case


def build_shipped():
    case = _Case()
    case.pool("POL-A", "paired", 40)
    case.pool("POL-B", "turbo", 25)
    case.pool("POL-C", "cold", 90)
    case.analyst("ANL-01", "principal")
    case.analyst("ANL-02", "principal")
    case.analyst("ANL-03", "staff")
    case.analyst("ANL-04", "rotational")
    case.analyst("ANL-05", "vendor")
    lay = _Layout(case, 0x6D42, _POOL_OF, "PRT-", "IDX-")
    roster = ["ANL-01", "ANL-02", "ANL-03", "ANL-04", "ANL-05"]
    by_clearance = {"principal": "ANL-02", "staff": "ANL-03",
                    "rotational": "ANL-04", "vendor": "ANL-05"}
    return _populate(case, lay, _Rng(0x6D43), roster, by_clearance, 7)


def _probe_case(plan, layout, mode, phase, reaches, cursors=None, replica=1):
    case = _Case()
    case.pool("PPL-1", mode, 30)
    case.index("PIX-1", layout, "", 140)
    case.analyst("PAN-1", "principal")
    case.partition("PRB-1", "PPL-1", "PIX-1", plan, replica)
    schedule = cursors if cursors is not None else _PROBE_CURSORS
    for position, cursor in enumerate(schedule):
        case.lookup("PRB-1", "PAN-1", "purge", phase, cursor, reaches[position])
    return case


def _plain_probe(replica=1):
    case = _Case()
    case.pool("PPL-1", "paired", 30)
    case.index("PIX-1", "btree", "", 140)
    case.analyst("PAN-1", "principal")
    case.partition("PRB-1", "PPL-1", "PIX-1", "seek", replica)
    return case


def _credit_then_small_figures(case, partition_id):
    case.lookup(partition_id, "PAN-1", "fetch", "quiet", 3000, 2800)
    case.lookup(partition_id, "PAN-1", "fetch", "quiet", 3000, 2800)
    case.flat(partition_id, "PAN-1", "snapshot", "quiet", 1200)
    for level in (2, 1, 4):
        case.nudge(partition_id, "PAN-1", "fetch", "quiet", 1200, level)


def build_probe(name):
    steady = [1200, 1200, 1200, 1200, 1200]
    if name == "round_gain":
        return _probe_case("seek", "btree", "paired", "quiet",
                           [600, 900, 1200, 2400, 3000],
                           [500, 500, 500, 500, 500])
    if name == "governing_count":
        case = _plain_probe()
        for pages, rounds in ((0, 1), (0, 3), (150, 1), (150, 3), (400, 2)):
            case.lookup("PRB-1", "PAN-1", "purge", "quiet", 1400, 1200, pages, rounds)
        return case
    if name == "mode_cold":
        return _probe_case("seek", "btree", "cold", "quiet", steady,
                           [700, 1300, 1900, 2500, 3100])
    if name.startswith("plan_"):
        return _probe_case(name[5:], "btree", "paired", "quiet", steady)
    if name.startswith("layout_"):
        return _probe_case("seek", name[7:], "paired", "quiet", steady)
    if name.startswith("phase_"):
        return _probe_case("seek", "btree", "paired", name[6:], steady)
    if name.startswith("mode_"):
        return _probe_case("seek", "btree", name[5:], "quiet", steady)
    if name == "parent_alias":
        case = _Case()
        case.pool("PPL-1", "paired", 30)
        case.index("PIX-0", "column", "", 160)
        case.index("PIX-1", "btree", "PIX-0", 140)
        case.analyst("PAN-1", "principal")
        case.partition("PRB-1", "PPL-1", "PIX-1", "seek", 1)
        for cursor in _PROBE_CURSORS:
            case.lookup("PRB-1", "PAN-1", "purge", "quiet", cursor, 1200)
        return case
    if name == "credit_release":
        case = _plain_probe()
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 2800)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 2800)
        case.flat("PRB-1", "PAN-1", "snapshot", "quiet", 1200)
        for _step in range(4):
            case.target("PRB-1", "PAN-1", "refresh", "quiet", 240, 1200)
        return case
    if name == "negative_rounding":
        case = _Case()
        case.pool("PPL-1", "paired", 30)
        case.pool("PPL-2", "turbo", 30)
        case.index("PIX-1", "sparse", "", 140)
        case.index("PIX-2", "column", "", 140)
        case.analyst("PAN-1", "principal")
        case.partition("PRB-1", "PPL-1", "PIX-1", "scan", 1)
        case.partition("PRB-2", "PPL-2", "PIX-2", "scan", 1)
        _credit_then_small_figures(case, "PRB-1")
        _credit_then_small_figures(case, "PRB-2")
        return case
    if name == "debt_accrual":
        case = _Case()
        case.pool("PPL-1", "paired", 30)
        case.analyst("PAN-1", "principal")
        for replica in (1, 2, 3):
            case.index("PIX-%d" % replica, "btree", "", 140)
            case.partition("PRB-%d" % replica, "PPL-1", "PIX-%d" % replica, "seek", replica)
        for reach in (900, 1630, 2400, 3990):
            for replica in (1, 2, 3):
                case.lookup("PRB-%d" % replica, "PAN-1", "fetch", "quiet", 9000, reach)
        return case
    if name == "first_lookup":
        case = _plain_probe()
        for _step in range(4):
            case.lookup("PRB-1", "PAN-1", "purge", "peak", 620, 1200)
        return case
    if name == "repeat_query":
        case = _plain_probe()
        case.strong("PRB-1", "PAN-1", "purge", "quiet", 1200, 400, query="QT-1")
        for _step in range(3):
            case.strong("PRB-1", "PAN-1", "purge", "quiet", 1200, 100)
        case.strong("PRB-1", "PAN-1", "purge", "quiet", 1200, 100, query="QT-1")
        case.strong("PRB-1", "PAN-1", "purge", "quiet", 1200, 500, query="QT-2")
        for _step in range(4):
            case.strong("PRB-1", "PAN-1", "purge", "quiet", 1200, 100)
        case.strong("PRB-1", "PAN-1", "purge", "quiet", 1200, 100, query="QT-2")
        case.flat("PRB-1", "PAN-1", "snapshot", "quiet", 1200)
        case.flat("PRB-1", "PAN-1", "purge", "quiet", 1200, query="QT-2")
        case.flat("PRB-1", "PAN-1", "purge", "quiet", 1200, query="QT-2")
        return case
    if name == "baseline_drift":
        case = _plain_probe()
        for _step in range(5):
            case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 5000, 900)
        return case
    if name == "doubled_relief":
        case = _plain_probe()
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 1200)
        case.lookup("PRB-1", "PAN-1", "purge", "quiet", 3000, 1200)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 1200)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 1200)
        return case
    if name == "miss_lock":
        case = _plain_probe()
        case.flat("PRB-1", "PAN-1", "fetch", "quiet", 1200)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 1200)
        case.flat("PRB-1", "PAN-1", "fetch", "quiet", 1200)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3001, 1200)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3002, 1200)
        return case
    if name == "shared_index":
        case = _Case()
        case.pool("PPL-1", "paired", 30)
        case.index("PIX-1", "btree", "", 140)
        case.analyst("PAN-1", "principal")
        case.partition("PRB-1", "PPL-1", "PIX-1", "seek", 1)
        case.partition("PRB-2", "PPL-1", "PIX-1", "seek", 1)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 1200)
        case.lookup("PRB-2", "PAN-1", "fetch", "quiet", 3000, 1200)
        case.lookup("PRB-1", "PAN-1", "fetch", "quiet", 3000, 1200)
        case.lookup("PRB-2", "PAN-1", "fetch", "quiet", 3000, 1200)
        return case
    if name == "tie_breaks":
        case = _Case()
        case.pool("PPL-1", "paired", 30)
        case.analyst("PAN-1", "principal")
        for position in (1, 2, 3):
            case.index("PIX-%d" % position, "btree", "", 140)
            case.partition("PRB-%d" % position, "PPL-1", "PIX-%d" % position, "seek", 1)
        case.target("PRB-1", "PAN-1", "fetch", "quiet", 300, 1200, query="QT-5")
        case.target("PRB-1", "PAN-1", "fetch", "quiet", 300, 1200, query="QT-2")
        case.target("PRB-2", "PAN-1", "fetch", "quiet", 300, 1200, query="QT-3")
        case.target("PRB-2", "PAN-1", "fetch", "quiet", 300, 1200, query="QT-7")
        case.target("PRB-3", "PAN-1", "fetch", "quiet", 150, 1200, query="QT-1")
        return case
    raise KeyError(name)


def build_unseen(seed, size=None):
    rng = _Rng(seed ^ 0x4B7E)
    case = _Case()
    for position in range(3):
        case.pool("FPL-%d" % (position + 1), _MODES[position], rng.between(10, 95))
    roster = []
    for position in range(4):
        roster.append(case.analyst("FAN-%d" % (position + 1), _CLEARANCES[position]))
    lay = _Layout(case, seed ^ 0x1C4D, _FRESH_POOL, "FPR-", "FIX-")
    by_clearance = dict(zip(_CLEARANCES, roster))
    wanderers = size if size is not None else rng.below(5)
    return _populate(case, lay, rng, roster, by_clearance, wanderers)


def _shuffled(lookups, seed):
    order = list(lookups)
    rng = _Rng(seed ^ 0x3D5B)
    position = len(order) - 1
    while position > 0:
        swap = rng.below(position + 1)
        order[position], order[swap] = order[swap], order[position]
        position -= 1
    return order


def write_case(root, case, seed=23):
    os.makedirs(root, exist_ok=True)

    def emit(name, text):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    lines = ["pool,mode,lag"]
    for name, mode, lag in case.pools:
        lines.append("%s,%s,%d" % (name, mode, lag))
    emit("pools.csv", "\n".join(lines) + "\n")

    lines = ["index,layout,parent,warmup"]
    for name, layout, parent, warmup in case.indexes:
        lines.append("%s,%s,%s,%d" % (name, layout, parent, warmup))
    emit("indexes.csv", "\n".join(lines) + "\n")

    lines = ["analyst,clearance"]
    for name, clearance in case.analysts:
        lines.append("%s,%s" % (name, clearance))
    emit("analysts.csv", "\n".join(lines) + "\n")

    lines = ["partition,pool,index,plan,replica"]
    for partition_id, pool, index, plan, replica in case.partitions:
        lines.append("%s,%s,%s,%s,%d" % (partition_id, pool, index, plan, replica))
    emit("partitions.csv", "\n".join(lines) + "\n")

    parts = []
    for row in _shuffled(case.lookups, seed):
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    emit("lookups.jsonl", "".join(parts))
    return case


APP_ROOT = os.environ.get("APP_ROOT", "/app")
OUT_DIR = os.path.join(APP_ROOT, "out")
SCRIPT = os.path.join(OUT_DIR, "broker.py")

PROBE_KEYS = ["analyst", "band", "cost", "debt_before", "partition", "query",
              "seq", "status", "verb"]
PARTITION_KEYS = ["bands", "baseline_end", "cost_total", "disposition",
                  "fetched", "flagged", "lookups", "misses", "partition",
                  "peak_cost", "top_query"]
CATALOG_KEYS = ["by_band", "by_status", "cost_total", "lookups", "partitions",
                "stalled", "top_partition"]

SHAPE_SEED = 6610001
FORM_SEED = 6610002
REPEAT_SEED = 6610003
CORPUS_SEEDS = [9910011, 9910022, 9910033, 9910044, 9910055, 9910066,
                9910077, 9910088, 9910099, 9910110, 9910121]

_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}


def _inside_sandbox(path):
    resolved = os.path.realpath(path)
    return resolved != _TMP_ROOT and resolved.startswith(_TMP_ROOT + os.sep)


def _open_up(path):
    node = os.path.realpath(path)
    while _inside_sandbox(node):
        try:
            os.chmod(node, (os.stat(node).st_mode & 0o7777) | 0o111 | 0o044)
        except OSError:
            pass
        node = os.path.dirname(node)


def _grant_read(path):
    try:
        extra = 0o055 if os.path.isdir(path) else 0o044
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | extra)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, AttributeError):
        try:
            proc.kill()
        except OSError:
            pass


def _launch(argv, scratch, budget=60):
    stdout_path = os.path.join(scratch, "stdout.txt")
    stderr_path = os.path.join(scratch, "stderr.txt")
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
    }
    with open(stdout_path, "wb") as sink, open(stderr_path, "wb") as errsink:
        proc = subprocess.Popen(
            _demoted(argv),
            stdout=sink,
            stderr=errsink,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            raise AssertionError("the delivered program ran past its time budget")
        finally:
            # Reap the whole group on every path, so nothing the delivered
            # program detached outlives this check and rewrites the reward.
            _terminate(proc)
    with open(stderr_path, "rb") as handle:
        return code, handle.read().decode("utf-8", "replace")


def _case_for(label, seed):
    if label.startswith("probe:"):
        return build_probe(label[6:])
    return build_unseen(seed)


def _expected(data):
    probes, partition_rows, catalog = derive(data)
    return {
        "probes.jsonl": render_probes(probes),
        "partitions.json": render_document({"partitions": partition_rows}),
        "catalog.json": render_document(catalog),
    }


def _materialise(label, seed):
    work = tempfile.mkdtemp(prefix="cpr-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    write_case(data, _case_for(label, seed), seed)
    os.makedirs(out)
    os.makedirs(scratch)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    for name in os.listdir(data):
        os.chmod(os.path.join(data, name), 0o644)
    return work, data, out, scratch


def _run(label, seed):
    if label in _RUNS:
        return _RUNS[label]
    assert os.path.isfile(SCRIPT), "no reusable program was delivered"
    _open_up(SCRIPT)
    _grant_read(APP_ROOT)
    _grant_read(OUT_DIR)
    _grant_read(SCRIPT)
    work, data, out, scratch = _materialise(label, seed)
    expected = _expected(data)
    code, err = _launch([sys.executable, SCRIPT, data, out], scratch)
    _RUNS[label] = (data, out, scratch, code, err, expected)
    return _RUNS[label]


def _artifact(out, name):
    path = os.path.join(out, name)
    assert os.path.isfile(path), "the program wrote no %s" % name
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def _ledger(label, seed):
    _data, out, _scratch, code, err, expected = _run(label, seed)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    for name in ("probes.jsonl", "partitions.json", "catalog.json"):
        assert _artifact(out, name) == expected[name], "%s disagrees with the reference" % name


def _probe(name, reports=("probes.jsonl",)):
    _data, out, _scratch, code, err, expected = _run("probe:" + name, 5)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    for report in reports:
        assert _artifact(out, report) == expected[report], "%s disagrees with the reference" % report


def _delivered_source():
    assert os.path.isfile(SCRIPT), "no reusable program was delivered"
    _grant_read(SCRIPT)
    with open(SCRIPT, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def _check_program_writes_the_three_reports_from_two_directory_arguments():
    """POSITIVE: driven with an input and an output directory the program writes the three documented reports."""
    _data, out, _scratch, code, err, _expect = _run("shape", SHAPE_SEED)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    rows = [line for line in _artifact(out, "probes.jsonl").splitlines() if line]
    assert rows
    for line in rows:
        assert sorted(json.loads(line)) == PROBE_KEYS
    document = json.loads(_artifact(out, "partitions.json"))
    assert sorted(document) == ["partitions"]
    assert document["partitions"]
    for row in document["partitions"]:
        assert sorted(row) == PARTITION_KEYS
    assert sorted(json.loads(_artifact(out, "catalog.json"))) == CATALOG_KEYS


def _check_report_serialization_carries_the_documented_byte_form():
    """POSITIVE: each report file is the documented serialization of the content it carries."""
    _data, out, _scratch, code, err, _expect = _run("form", FORM_SEED)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    text = _artifact(out, "probes.jsonl")
    rows = [json.loads(line) for line in text.splitlines() if line]
    assert rows
    assert text == render_probes(rows)
    for name in ("partitions.json", "catalog.json"):
        body = _artifact(out, name)
        assert body == render_document(json.loads(body))


def _check_round_normalisation_gain():
    """POSITIVE: the round normalisation gain matches the reference on a probe of one cursor across five reaches."""
    _probe("round_gain")


def _check_governing_count_column():
    """POSITIVE: the governing count of the normalisation stage matches the reference on a probe that varies the size columns."""
    _probe("governing_count")


def _check_plan_adjustment_scan():
    """POSITIVE: the scan plan adjustment matches the reference on a scan only probe."""
    _probe("plan_scan")


def _check_plan_adjustment_merge():
    """POSITIVE: the merge plan adjustment matches the reference on a merge only probe."""
    _probe("plan_merge")


def _check_plan_adjustment_fanout():
    """POSITIVE: the fanout plan adjustment matches the reference on a fanout only probe."""
    _probe("plan_fanout")


def _check_plan_adjustment_stream():
    """POSITIVE: the stream plan adjustment matches the reference on a stream only probe."""
    _probe("plan_stream")


def _check_plan_adjustment_nested():
    """POSITIVE: the nested plan adjustment matches the reference on a nested only probe."""
    _probe("plan_nested")


def _check_plan_adjustment_hybrid():
    """POSITIVE: the hybrid plan adjustment matches the reference on a hybrid only probe."""
    _probe("plan_hybrid")


def _check_layout_adjustment_sparse():
    """POSITIVE: the sparse layout adjustment matches the reference on a sparse only probe."""
    _probe("layout_sparse")


def _check_layout_adjustment_bitmap():
    """POSITIVE: the bitmap layout adjustment matches the reference on a bitmap only probe."""
    _probe("layout_bitmap")


def _check_layout_adjustment_column():
    """POSITIVE: the column layout adjustment matches the reference on a column only probe."""
    _probe("layout_column")


def _check_charged_layout_follows_the_parent_index():
    """POSITIVE: the charged layout of a derived index matches the reference on a parent bearing probe."""
    _probe("parent_alias")


def _check_phase_adjustment_peak():
    """POSITIVE: the peak phase adjustment matches the reference on a peak only probe."""
    _probe("phase_peak")


def _check_phase_adjustment_shoulder():
    """POSITIVE: the shoulder phase adjustment matches the reference on a shoulder only probe."""
    _probe("phase_shoulder")


def _check_first_lookup_phase_exemption():
    """POSITIVE: the phase adjustment on an index's opening lookup matches the reference on a peak only probe."""
    _probe("first_lookup")


def _check_mode_adjustment_turbo():
    """POSITIVE: the turbo mode adjustment matches the reference on a turbo only probe."""
    _probe("mode_turbo")


def _check_mode_adjustment_cold():
    """POSITIVE: the cold mode adjustment matches the reference on a cold only probe that reaches large figures."""
    _probe("mode_cold")


def _check_rounding_of_figures_below_zero():
    """POSITIVE: the keyed adjustments round a figure the scan plan pushed below zero as the reference does."""
    _probe("negative_rounding")


def _check_debt_accrual_by_replica():
    """POSITIVE: the debt each fetch adds, per replica and up to the ceiling, matches the reference."""
    _probe("debt_accrual")


def _check_tie_breaks_and_row_order():
    """POSITIVE: both tie breaks and the partition row order match the reference on a tied probe."""
    _probe("tie_breaks", ("probes.jsonl", "partitions.json", "catalog.json"))


def _check_credit_release_drawdown():
    """POSITIVE: the credit release and its drawdown match the reference on a snapshot then fetch probe."""
    _probe("credit_release")


def _check_repeat_query_trailing_record():
    """POSITIVE: the trailing record's reach and the entry a returning query takes match the reference on a returning query probe."""
    _probe("repeat_query")


def _check_baseline_drift_after_each_fetch():
    """POSITIVE: the baseline movement a fetch leaves behind matches the reference on a fixed cursor fetch probe."""
    _probe("baseline_drift")


def _check_doubled_relief_after_a_purge():
    """POSITIVE: the relief the lookup after a purge takes matches the reference on a purge bearing probe."""
    _probe("doubled_relief")


def _check_miss_lock_surcharge():
    """POSITIVE: the surcharge a locked index carries matches the reference on a miss bearing probe."""
    _probe("miss_lock")


def _check_carried_state_follows_the_named_index():
    """POSITIVE: the state two partitions on one index share matches the reference on a shared index probe."""
    _probe("shared_index")


def _check_full_ledger_on_unseen_run_alpha():
    """POSITIVE: the three reports match the reference ledger on an unseen catalogue run."""
    _ledger("c01", CORPUS_SEEDS[0])


def _check_full_ledger_on_unseen_run_bravo():
    """POSITIVE: the three reports match the reference ledger on a second unseen catalogue run."""
    _ledger("c02", CORPUS_SEEDS[1])


def _check_full_ledger_on_unseen_run_charlie():
    """POSITIVE: the three reports match the reference ledger on a third unseen catalogue run."""
    _ledger("c03", CORPUS_SEEDS[2])


def _check_full_ledger_on_unseen_run_delta():
    """POSITIVE: the three reports match the reference ledger on a fourth unseen catalogue run."""
    _ledger("c04", CORPUS_SEEDS[3])


def _check_full_ledger_on_unseen_run_echo():
    """POSITIVE: the three reports match the reference ledger on a fifth unseen catalogue run."""
    _ledger("c05", CORPUS_SEEDS[4])


def _check_full_ledger_on_unseen_run_foxtrot():
    """POSITIVE: the three reports match the reference ledger on a sixth unseen catalogue run."""
    _ledger("c06", CORPUS_SEEDS[5])


def _check_full_ledger_on_unseen_run_golf():
    """POSITIVE: the three reports match the reference ledger on a seventh unseen catalogue run."""
    _ledger("c07", CORPUS_SEEDS[6])


def _check_full_ledger_on_unseen_run_hotel():
    """POSITIVE: the three reports match the reference ledger on an eighth unseen catalogue run."""
    _ledger("c08", CORPUS_SEEDS[7])


def _check_full_ledger_on_unseen_run_india():
    """POSITIVE: the three reports match the reference ledger on a ninth unseen catalogue run."""
    _ledger("c09", CORPUS_SEEDS[8])


def _check_full_ledger_on_unseen_run_juliet():
    """POSITIVE: the three reports match the reference ledger on a tenth unseen catalogue run."""
    _ledger("c10", CORPUS_SEEDS[9])


def _check_full_ledger_on_unseen_run_kilo():
    """POSITIVE: the three reports match the reference ledger on an eleventh unseen catalogue run."""
    _ledger("c11", CORPUS_SEEDS[10])


def _check_negative_hardcoded_sample_answers():
    """NEGATIVE: the delivered program carries the shipped run's partition identifiers as literal answers."""
    # Holds when the cheat happened; the negative weight does the punishing.
    source = _delivered_source()
    shipped = {row[0] for row in build_shipped().partitions}
    literals = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
    assert len(shipped & literals) >= 5


def _check_negative_third_party_dependency():
    """NEGATIVE: the delivered program pulls in a module outside the standard library."""
    # Holds when the cheat happened; the negative weight does the punishing.
    tree = ast.parse(_delivered_source())
    wanted = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            wanted.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            wanted.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in ("__import__", "import_module") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    wanted.add(first.value.split(".")[0])
    assert wanted - set(sys.stdlib_module_names)


def _check_negative_nondeterministic_output():
    """NEGATIVE: repeated runs of the delivered program over one input write differing bytes."""
    # Holds when the cheat happened; the negative weight does the punishing.
    _data, out, scratch, code, err, _expect = _run("repeat", REPEAT_SEED)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    work = os.path.dirname(out)
    data = os.path.join(work, "data")
    first = {name: _artifact(out, name)
             for name in ("probes.jsonl", "partitions.json", "catalog.json")}
    drifted = False
    for attempt in range(4):
        # Two reruns overwrite the first run's reports and two write into an
        # empty directory of their own, so neither appending to existing files
        # nor skipping work when they already exist can hide drift.
        if attempt < 2:
            target = out
        else:
            target = os.path.join(work, "again-%d" % attempt)
            os.makedirs(target)
            os.chmod(target, 0o777)
        again, _err = _launch([sys.executable, SCRIPT, data, target], scratch)
        if again != 0:
            drifted = True
            break
        for name, body in first.items():
            path = os.path.join(target, name)
            if not os.path.isfile(path) or _artifact(target, name) != body:
                drifted = True
    assert drifted


# --- rewardkit criteria ---------------------------------------------------
#
# Each criterion below is a thin wrapper over the matching _check_* function.
# The check bodies signal failure by raising, and every comparison they make is
# exact. The wrapper converts any exception into the bool rewardkit requires, so
# no check can abort the run.


def _bind_workspace(workspace):
    """Point the artifact constants at the workspace rewardkit hands us."""
    global APP_ROOT, OUT_DIR, SCRIPT
    APP_ROOT = str(workspace)
    OUT_DIR = os.path.join(APP_ROOT, "out")
    SCRIPT = os.path.join(OUT_DIR, "broker.py")


def _guard(check, workspace):
    """Run one check against the workspace and report it as a bool."""
    _bind_workspace(workspace)
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="POSITIVE: driven with an input and an output directory the program writes the three documented reports.")
def program_writes_the_three_reports_from_two_directory_arguments(workspace):
    return _guard(_check_program_writes_the_three_reports_from_two_directory_arguments, workspace)


@criterion(description="POSITIVE: each report file is the documented serialization of the content it carries.")
def report_serialization_carries_the_documented_byte_form(workspace):
    return _guard(_check_report_serialization_carries_the_documented_byte_form, workspace)


@criterion(description="POSITIVE: the round normalisation gain matches the reference on a probe of one cursor across five reaches.")
def round_normalisation_gain(workspace):
    return _guard(_check_round_normalisation_gain, workspace)


@criterion(description="POSITIVE: the governing count of the normalisation stage matches the reference on a probe that varies the size columns.")
def governing_count_column(workspace):
    return _guard(_check_governing_count_column, workspace)


@criterion(description="POSITIVE: the scan plan adjustment matches the reference on a scan only probe.")
def plan_adjustment_scan(workspace):
    return _guard(_check_plan_adjustment_scan, workspace)


@criterion(description="POSITIVE: the merge plan adjustment matches the reference on a merge only probe.")
def plan_adjustment_merge(workspace):
    return _guard(_check_plan_adjustment_merge, workspace)


@criterion(description="POSITIVE: the fanout plan adjustment matches the reference on a fanout only probe.")
def plan_adjustment_fanout(workspace):
    return _guard(_check_plan_adjustment_fanout, workspace)


@criterion(description="POSITIVE: the stream plan adjustment matches the reference on a stream only probe.")
def plan_adjustment_stream(workspace):
    return _guard(_check_plan_adjustment_stream, workspace)


@criterion(description="POSITIVE: the nested plan adjustment matches the reference on a nested only probe.")
def plan_adjustment_nested(workspace):
    return _guard(_check_plan_adjustment_nested, workspace)


@criterion(description="POSITIVE: the hybrid plan adjustment matches the reference on a hybrid only probe.")
def plan_adjustment_hybrid(workspace):
    return _guard(_check_plan_adjustment_hybrid, workspace)


@criterion(description="POSITIVE: the sparse layout adjustment matches the reference on a sparse only probe.")
def layout_adjustment_sparse(workspace):
    return _guard(_check_layout_adjustment_sparse, workspace)


@criterion(description="POSITIVE: the bitmap layout adjustment matches the reference on a bitmap only probe.")
def layout_adjustment_bitmap(workspace):
    return _guard(_check_layout_adjustment_bitmap, workspace)


@criterion(description="POSITIVE: the column layout adjustment matches the reference on a column only probe.")
def layout_adjustment_column(workspace):
    return _guard(_check_layout_adjustment_column, workspace)


@criterion(description="POSITIVE: the charged layout of a derived index matches the reference on a parent bearing probe.")
def charged_layout_follows_the_parent_index(workspace):
    return _guard(_check_charged_layout_follows_the_parent_index, workspace)


@criterion(description="POSITIVE: the peak phase adjustment matches the reference on a peak only probe.")
def phase_adjustment_peak(workspace):
    return _guard(_check_phase_adjustment_peak, workspace)


@criterion(description="POSITIVE: the shoulder phase adjustment matches the reference on a shoulder only probe.")
def phase_adjustment_shoulder(workspace):
    return _guard(_check_phase_adjustment_shoulder, workspace)


@criterion(description="POSITIVE: the phase adjustment on an index's opening lookup matches the reference on a peak only probe.")
def first_lookup_phase_exemption(workspace):
    return _guard(_check_first_lookup_phase_exemption, workspace)


@criterion(description="POSITIVE: the turbo mode adjustment matches the reference on a turbo only probe.")
def mode_adjustment_turbo(workspace):
    return _guard(_check_mode_adjustment_turbo, workspace)


@criterion(description="POSITIVE: the cold mode adjustment matches the reference on a cold only probe that reaches large figures.")
def mode_adjustment_cold(workspace):
    return _guard(_check_mode_adjustment_cold, workspace)


@criterion(description="POSITIVE: the keyed adjustments round a figure the scan plan pushed below zero as the reference does.")
def rounding_of_figures_below_zero(workspace):
    return _guard(_check_rounding_of_figures_below_zero, workspace)


@criterion(description="POSITIVE: the debt each fetch adds, per replica and up to the ceiling, matches the reference.")
def debt_accrual_by_replica(workspace):
    return _guard(_check_debt_accrual_by_replica, workspace)


@criterion(description="POSITIVE: both tie breaks and the partition row order match the reference on a tied probe.")
def tie_breaks_and_row_order(workspace):
    return _guard(_check_tie_breaks_and_row_order, workspace)


@criterion(description="POSITIVE: the credit release and its drawdown match the reference on a snapshot then fetch probe.")
def credit_release_drawdown(workspace):
    return _guard(_check_credit_release_drawdown, workspace)


@criterion(description="POSITIVE: the trailing record's reach and the entry a returning query takes match the reference on a returning query probe.")
def repeat_query_trailing_record(workspace):
    return _guard(_check_repeat_query_trailing_record, workspace)


@criterion(description="POSITIVE: the baseline movement a fetch leaves behind matches the reference on a fixed cursor fetch probe.")
def baseline_drift_after_each_fetch(workspace):
    return _guard(_check_baseline_drift_after_each_fetch, workspace)


@criterion(description="POSITIVE: the relief the lookup after a purge takes matches the reference on a purge bearing probe.")
def doubled_relief_after_a_purge(workspace):
    return _guard(_check_doubled_relief_after_a_purge, workspace)


@criterion(description="POSITIVE: the surcharge a locked index carries matches the reference on a miss bearing probe.")
def miss_lock_surcharge(workspace):
    return _guard(_check_miss_lock_surcharge, workspace)


@criterion(description="POSITIVE: the state two partitions on one index share matches the reference on a shared index probe.")
def carried_state_follows_the_named_index(workspace):
    return _guard(_check_carried_state_follows_the_named_index, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on an unseen catalogue run.")
def full_ledger_on_unseen_run_alpha(workspace):
    return _guard(_check_full_ledger_on_unseen_run_alpha, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a second unseen catalogue run.")
def full_ledger_on_unseen_run_bravo(workspace):
    return _guard(_check_full_ledger_on_unseen_run_bravo, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a third unseen catalogue run.")
def full_ledger_on_unseen_run_charlie(workspace):
    return _guard(_check_full_ledger_on_unseen_run_charlie, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a fourth unseen catalogue run.")
def full_ledger_on_unseen_run_delta(workspace):
    return _guard(_check_full_ledger_on_unseen_run_delta, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a fifth unseen catalogue run.")
def full_ledger_on_unseen_run_echo(workspace):
    return _guard(_check_full_ledger_on_unseen_run_echo, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a sixth unseen catalogue run.")
def full_ledger_on_unseen_run_foxtrot(workspace):
    return _guard(_check_full_ledger_on_unseen_run_foxtrot, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a seventh unseen catalogue run.")
def full_ledger_on_unseen_run_golf(workspace):
    return _guard(_check_full_ledger_on_unseen_run_golf, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on an eighth unseen catalogue run.")
def full_ledger_on_unseen_run_hotel(workspace):
    return _guard(_check_full_ledger_on_unseen_run_hotel, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a ninth unseen catalogue run.")
def full_ledger_on_unseen_run_india(workspace):
    return _guard(_check_full_ledger_on_unseen_run_india, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on a tenth unseen catalogue run.")
def full_ledger_on_unseen_run_juliet(workspace):
    return _guard(_check_full_ledger_on_unseen_run_juliet, workspace)


@criterion(description="POSITIVE: the three reports match the reference ledger on an eleventh unseen catalogue run.")
def full_ledger_on_unseen_run_kilo(workspace):
    return _guard(_check_full_ledger_on_unseen_run_kilo, workspace)


@criterion(description="NEGATIVE: the delivered program carries the shipped run's partition identifiers as literal answers.")
def negative_hardcoded_sample_answers(workspace):
    return _guard(_check_negative_hardcoded_sample_answers, workspace)


@criterion(description="NEGATIVE: the delivered program pulls in a module outside the standard library.")
def negative_third_party_dependency(workspace):
    return _guard(_check_negative_third_party_dependency, workspace)


@criterion(description="NEGATIVE: repeated runs of the delivered program over one input write differing bytes.")
def negative_nondeterministic_output(workspace):
    return _guard(_check_negative_nondeterministic_output, workspace)


criteria.program_writes_the_three_reports_from_two_directory_arguments(weight=1)
criteria.report_serialization_carries_the_documented_byte_form(weight=1)
criteria.round_normalisation_gain(weight=1)
criteria.governing_count_column(weight=1)
criteria.plan_adjustment_scan(weight=1)
criteria.plan_adjustment_merge(weight=1)
criteria.plan_adjustment_fanout(weight=1)
criteria.plan_adjustment_stream(weight=1)
criteria.plan_adjustment_nested(weight=1)
criteria.plan_adjustment_hybrid(weight=1)
criteria.layout_adjustment_sparse(weight=1)
criteria.layout_adjustment_bitmap(weight=1)
criteria.layout_adjustment_column(weight=1)
criteria.charged_layout_follows_the_parent_index(weight=1)
criteria.phase_adjustment_peak(weight=1)
criteria.phase_adjustment_shoulder(weight=1)
criteria.first_lookup_phase_exemption(weight=1)
criteria.mode_adjustment_turbo(weight=1)
criteria.mode_adjustment_cold(weight=1)
criteria.rounding_of_figures_below_zero(weight=1)
criteria.debt_accrual_by_replica(weight=1)
criteria.tie_breaks_and_row_order(weight=1)
criteria.credit_release_drawdown(weight=1)
criteria.repeat_query_trailing_record(weight=1)
criteria.baseline_drift_after_each_fetch(weight=1)
criteria.doubled_relief_after_a_purge(weight=1)
criteria.miss_lock_surcharge(weight=1)
criteria.carried_state_follows_the_named_index(weight=1)
criteria.full_ledger_on_unseen_run_alpha(weight=5)
criteria.full_ledger_on_unseen_run_bravo(weight=5)
criteria.full_ledger_on_unseen_run_charlie(weight=5)
criteria.full_ledger_on_unseen_run_delta(weight=5)
criteria.full_ledger_on_unseen_run_echo(weight=5)
criteria.full_ledger_on_unseen_run_foxtrot(weight=5)
criteria.full_ledger_on_unseen_run_golf(weight=5)
criteria.full_ledger_on_unseen_run_hotel(weight=5)
criteria.full_ledger_on_unseen_run_india(weight=5)
criteria.full_ledger_on_unseen_run_juliet(weight=5)
criteria.full_ledger_on_unseen_run_kilo(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
