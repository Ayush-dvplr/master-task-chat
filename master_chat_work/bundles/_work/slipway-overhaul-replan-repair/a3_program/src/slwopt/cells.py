"""The derived state of one round, held as seven layers of cells.

Each cell carries a key over the inputs it reads and a value whose digest
decides whether a cascade that reaches it carries on. The key holds every
input the cell reads and nothing it does not read, which is what keeps a
change to a title out of the optimiser and a change to a capacity out of the
closures.
"""
from . import cache, charge, closure, graph, normalise, search

LAYERS = ["norm", "rule", "closure", "demand", "charge", "group", "solve"]
RANK = {name: index for index, name in enumerate(LAYERS)}
MARK = "|"


def named(layer, name):
    return layer + MARK + name


def fresh_counters():
    return {"visited": {layer: 0 for layer in LAYERS},
            "recomputed": {layer: 0 for layer in LAYERS},
            "revalidated": {layer: 0 for layer in LAYERS},
            "subsets_examined": 0}


class Round:
    """The model the round opens with, and the cells derived from it."""

    def __init__(self, root):
        self.root = root
        self.params = normalise.parameters(root)
        alias, self.aliases_active = normalise.crosswalk(root)
        self.alias = alias
        self.jobs, aside = normalise.register(root, self.params, alias)
        self.journal = graph.journal(root, alias)
        accepted, rejected = graph.sift(self.journal, self.jobs)
        cycle = graph.in_a_cycle(accepted, sorted(self.jobs))
        if cycle:
            for name in cycle:
                aside.append((name, "JOB-CYCLE", self.jobs[name]["precinct"]))
                del self.jobs[name]
            accepted, rejected = graph.sift(self.journal, self.jobs)
        self.accepted = accepted
        self.edge_rejected = sorted(rejected)
        self.aside = sorted(aside)
        self.groups, group_rejected = graph.groups(root, self.jobs)
        self.group_rejected = sorted(group_rejected)
        self.meta = {name: {field: self.jobs[name][field]
                            for field in charge.PRESENTATION_FIELDS}
                     for name in self.jobs}
        self.rules = {}
        for record in graph.reading.records(root / "conditional_charge_rules.jsonl"):
            if record.get("state") == "in_force":
                self.rules[record["rule_id"]] = dict(record)
        self.capacity = self._capacity(root)
        self.carryover = self._carryover(root)
        self.precincts = sorted({self.jobs[name]["precinct"]
                                 for name in self.jobs})
        self.depth = {}
        for precinct in self.precincts:
            self._rank(precinct)
        self.cells = {}
        self.store = cache.Store(self.params["retention"])
        self.inverse = {}

    def _capacity(self, root):
        index = self.params["round_index"]
        held = {}
        for row in graph.reading.delimited(root / "pool_capacity_history.tsv",
                                           graph.reading.TAB):
            if row["state"] != "in_force" or int(row["effective_round"]) > index:
                continue
            marker = (row["precinct"], row["pool"])
            standing = held.get(marker)
            if standing is None or int(row["effective_round"]) >= standing[0]:
                held[marker] = (int(row["effective_round"]), int(row["capacity"]))
        return {marker: value[1] for marker, value in held.items()}

    def _carryover(self, root):
        out = {}
        for row in graph.reading.delimited(root / "carried_commitment_ledger.csv"):
            if row["state"] == "binding":
                out[row["commitment_id"]] = {"precinct": row["precinct"],
                                             "pool": row["pool"],
                                             "quantity": int(row["quantity"])}
        return out

    def in_precinct(self, precinct):
        return [name for name in sorted(self.jobs)
                if self.jobs[name]["precinct"] == precinct]

    def _rank(self, precinct):
        names = self.in_precinct(precinct)
        self.depth.update(graph.depths(self.accepted, names))

    def refresh_edges(self, precinct):
        """Rebuild the accepted prerequisite lists of one precinct."""
        fresh = graph.within(self.journal, self.jobs, precinct)
        for name in list(self.accepted):
            if name in self.jobs and self.jobs[name]["precinct"] == precinct:
                del self.accepted[name]
        self.accepted.update(fresh)
        self._rank(precinct)

    # -- the cell table -------------------------------------------------
    def inputs_of(self, marker):
        layer, name = marker.split(MARK, 1)
        if layer == "norm":
            return charge.norm_inputs(self, name)
        if layer == "rule":
            return charge.rule_inputs(self, name)
        if layer == "closure":
            return closure.closure_inputs(self, name, self.cells)
        if layer == "demand":
            return closure.demand_inputs(self, name, self.cells)
        if layer == "charge":
            return charge.charge_inputs(self, name, self.cells)
        if layer == "group":
            return charge.group_inputs(self, name, self.cells)
        return search.solve_inputs(self, name, self.cells)

    def value_of(self, marker):
        layer, name = marker.split(MARK, 1)
        if layer == "norm":
            return charge.norm(self, name)
        if layer == "rule":
            return charge.rule(self, name)
        if layer == "closure":
            return closure.closure(self, name, self.cells)
        if layer == "demand":
            return closure.demand(self, name, self.cells)
        if layer == "charge":
            return charge.charge(self, name, self.cells)
        if layer == "group":
            return charge.group(self, name, self.cells)
        return search.sweep(self, name, self.cells)

    def order_of(self, marker):
        layer, name = marker.split(MARK, 1)
        depth = self.depth.get(name, 0) if layer == "closure" else 0
        return (RANK[layer], depth, marker)

    def readers_of(self, marker):
        """The cells that read this one."""
        layer, name = marker.split(MARK, 1)
        if layer == "norm":
            precinct = self.jobs[name]["precinct"]
            out = [named("closure", name), named("demand", name),
                   named("charge", name)]
            for other in sorted(graph.readers_of(self.accepted, name,
                                                 self.jobs, precinct)):
                out.append(named("demand", other))
            for group_id in sorted(self.groups):
                if name in self.groups[group_id]["members"]:
                    out.append(named("group", group_id))
            out.append(named("solve", precinct))
            return out
        if layer == "rule":
            return [named("solve", self.rules[name]["precinct"])]
        if layer == "closure":
            precinct = self.jobs[name]["precinct"]
            out = [named("demand", name)]
            for other in sorted(self.accepted):
                if name in self.accepted[other] and other in self.jobs:
                    out.append(named("closure", other))
            out.append(named("solve", precinct))
            return out
        if layer in ("demand", "charge"):
            return [named("solve", self.jobs[name]["precinct"])]
        if layer == "group":
            return [named("solve", self.groups[name]["precinct"])]
        return []

    # -- visiting -------------------------------------------------------
    def visit(self, marker, counters, trail):
        layer = marker.split(MARK, 1)[0]
        key = normalise.digest(self.inputs_of(marker))
        counters["visited"][layer] += 1
        held = self.store.take(marker, key)
        if held is None:
            value = self.value_of(marker)
            digest = normalise.digest(value)
            self.store.put(marker, key, value, digest)
            counters["recomputed"][layer] += 1
            if layer == "solve":
                counters["subsets_examined"] += value["subsets_examined"]
            trail.append((marker, "recomputed"))
        else:
            value, digest = held
            trail.append((marker, "read_from_store"))
        standing = self.cells.get(marker)
        self.cells[marker] = {"key": key, "value": normalise.copy_of(value),
                              "digest": digest}
        if standing is not None and standing["digest"] == digest:
            counters["revalidated"][layer] += 1
            trail[-1] = (marker, "revalidated")
            return False
        return True

    def cascade(self, seeds, counters):
        waiting = set(seeds)
        done = set()
        trail = []
        moved = []
        while waiting:
            marker = min(waiting, key=self.order_of)
            waiting.discard(marker)
            if marker in done:
                continue
            done.add(marker)
            if self.visit(marker, counters, trail):
                moved.append(marker)
                for reader in self.readers_of(marker):
                    if reader not in done and reader in self.cells:
                        waiting.add(reader)
        return trail, moved

    def open_round(self):
        """Stages p04 to p12. Every cell built once, in canonical order."""
        counters = fresh_counters()
        markers = []
        for name in sorted(self.jobs):
            markers.append(named("norm", name))
            markers.append(named("closure", name))
            markers.append(named("demand", name))
            markers.append(named("charge", name))
        for rule_id in sorted(self.rules):
            markers.append(named("rule", rule_id))
        for group_id in sorted(self.groups):
            markers.append(named("group", group_id))
        for precinct in self.precincts:
            markers.append(named("solve", precinct))
        trail = []
        for marker in sorted(markers, key=self.order_of):
            self.visit(marker, counters, trail)
        return counters

    def layer_totals(self):
        out = {layer: 0 for layer in LAYERS}
        for marker in self.cells:
            out[marker.split(MARK, 1)[0]] += 1
        return out
