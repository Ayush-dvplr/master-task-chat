"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .operations import apply_operations
from .records import ABSENT, NULL, FieldView, counts_present, fill_mode

_STAND_IN_VALUE = "<value>"
_RENAME, _DROP, _ADD = 0, 1, 2
_MACHINE_LIMIT = 16
_CACHE_LIMIT = 2_000_000
_machines: dict[tuple[int, str], tuple[Registry, "_Machine"]] = {}


def state_signature(registry: Registry, schema_id: str, payload: dict) -> dict[str, str]:
    """State of every prerequisite field of the record's domain, sorted by name."""
    domain = registry.domain_of(schema_id)
    return FieldView.from_payload(payload).signature(registry.prerequisite_fields(domain))


def _stand_in(names: list[str], state: tuple[str, ...]) -> dict:
    return {
        name: (None if value == NULL else _STAND_IN_VALUE)
        for name, value in zip(names, state)
        if value != ABSENT
    }


def _advance(
    registry: Registry, domain: str, names: list[str], state: tuple[str, ...], edge: Edge
) -> tuple[str, ...]:
    record = apply_operations(registry, domain, _stand_in(names, state), edge.operations)
    return FieldView.from_payload(record).states(names)


class _Machine:
    """One domain's edges compiled to work on field states alone.

    A state is the base-three code of the state of each field the domain names
    (0 absent, 1 explicit null, 2 a value); a node is a schema index. Only the
    three operations that move a field between those states are kept, since a
    cast never leaves the value state, and the prerequisites of an edge become
    two bit masks over the fields that count as present.
    """

    def __init__(self, registry: Registry, domain: str) -> None:
        self.registry = registry
        self.domain = domain
        self.names = registry.named_fields(domain)
        self.places = [3**position for position in range(len(self.names))]
        self.scale = 3 ** len(self.names)
        self.nodes: list[str] = []
        self.index: dict[str, int] = {}
        self.present_null = [counts_present(registry, domain, name, NULL) for name in self.names]
        self._fields = {name: position for position, name in enumerate(self.names)}
        self.leaving: dict[int, tuple] = {}
        self.masks: dict[int, int] = {}
        self._codes: dict[int, tuple[int, ...]] = {}
        self._cached = 0

    def node(self, schema_id: str) -> int:
        position = self.index.get(schema_id)
        if position is None:
            position = len(self.nodes)
            self.index[schema_id] = position
            self.nodes.append(schema_id)
        return position

    def state_of(self, payload: dict) -> int:
        state = 0
        for position, name in enumerate(self.names):
            if name in payload:
                state += (1 if payload[name] is None else 2) * self.places[position]
        return state

    def states_of(self, state: int) -> tuple[int, ...]:
        codes = self._codes.get(state)
        if codes is None:
            rest = state
            found = []
            for _ in self.names:
                rest, code = divmod(rest, 3)
                found.append(code)
            codes = self._codes[state] = tuple(found)
        return codes

    def mask(self, state: int) -> int:
        """Bit ``i`` is set when the ``i``-th field counts as present (N2); cached in ``masks``."""
        mask = 0
        for position, code in enumerate(self.states_of(state)):
            if code == 2 or (code == 1 and self.present_null[position]):
                mask |= 1 << position
        self.masks[state] = mask
        return mask

    def out(self, node: int) -> tuple:
        """Compile the edges leaving a node into ``leaving``: (id, cost, target, has, lacks, ops, cache)."""
        found = []
        for edge in self.registry.edges_from.get(self.nodes[node], ()):
            step = self._compile(edge)
            if step is not None:
                found.append(step)
        compiled = self.leaving[node] = tuple(found)
        return compiled

    def _compile(self, edge: Edge):
        has = lacks = 0
        for kind, name in edge.requires:
            position = self._fields.get(name)
            if position is None:
                # An untracked field is absent to the planner, as it is to _advance.
                if kind == "has":
                    return None
                continue
            if kind == "has":
                has |= 1 << position
            else:
                lacks |= 1 << position
        operations = []
        for operation in edge.operations:
            kind = operation[0]
            if kind == "rename":
                source = self._fields.get(operation[1])
                target = self._fields.get(operation[2])
                if source is None or source == target:
                    continue
                operations.append((_RENAME, source, target))
            elif kind == "drop":
                dropped = self._fields.get(operation[1])
                if dropped is not None:
                    operations.append((_DROP, dropped))
            elif kind == "add":
                filled = self._fields.get(operation[1])
                policy = self.registry.policies.get((self.domain, operation[1]))
                if filled is None or policy is None or not policy.has_default:
                    continue
                code = 1 if policy.default is None else 2
                over_null = fill_mode(self.registry, self.domain, operation[1]) == "absent_or_null"
                operations.append((_ADD, filled, code, over_null))
        return (edge.edge_id, edge.cost, self.node(edge.target), has, lacks, tuple(operations), {})

    def advance(self, step: tuple, state: int) -> int:
        """The state the operations of a compiled edge leave behind."""
        cache = step[6]
        following = cache.get(state, -1)
        if following < 0:
            codes = list(self.states_of(state))
            for operation in step[5]:
                kind = operation[0]
                if kind == _RENAME:
                    code = codes[operation[1]]
                    if code:
                        codes[operation[2]] = code
                        codes[operation[1]] = 0
                elif kind == _DROP:
                    codes[operation[1]] = 0
                else:
                    code = codes[operation[1]]
                    if code == 0 or (code == 1 and operation[3]):
                        codes[operation[1]] = operation[2]
            following = 0
            for position, code in enumerate(codes):
                following += code * self.places[position]
            if self._cached > _CACHE_LIMIT:
                self._drop_caches()
            cache[state] = following
            self._cached += 1
        return following

    def _drop_caches(self) -> None:
        for compiled in self.leaving.values():
            for step in compiled:
                step[6].clear()
        self._cached = 0


def _machine_for(registry: Registry, domain: str) -> _Machine:
    """The compiled machine of one domain, kept between calls on the same registry."""
    key = (id(registry), domain)
    held = _machines.get(key)
    if held is not None and held[0] is registry:
        return held[1]
    if len(_machines) >= _MACHINE_LIMIT:
        _machines.clear()
    machine = _Machine(registry, domain)
    _machines[key] = (registry, machine)
    return machine


def _path_of(best: dict, key: int) -> list[str]:
    """The edge ids of the best known walk to ``key``, read back from its parents."""
    path: list[str] = []
    while True:
        parent, edge_id = best[key][1:]
        if parent < 0:
            path.reverse()
            return path
        path.append(edge_id)
        key = parent


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """The cheapest plan to the canonical schema; among those, the smallest edge id list.

    The search runs over (schema, field states) instead of over paths, so a
    graph with far too many distinct paths to list is still planned in one pass.
    Edge costs are positive, so a walk costing ``c`` is only ever reached from
    cheaper walks and a cost level is settled once the cheaper levels are done;
    ties inside a level are decided on the edge id lists themselves.
    """
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    machine = _machine_for(registry, domain)
    scale = machine.scale
    goal = machine.node(target)
    start = machine.node(schema_id) * scale + machine.state_of(payload)
    best: dict[int, tuple[int, int, str | None]] = {start: (0, -1, None)}
    buckets: dict[int, list[int]] = {0: [start]}
    levels = [0]
    settled: set[int] = set()
    masks = machine.masks
    leaving = machine.leaving
    while levels:
        cost = heapq.heappop(levels)
        bucket = buckets.pop(cost, None)
        if bucket is None:
            continue
        reached: list[int] = []
        position = 0
        while position < len(bucket):
            key = bucket[position]
            position += 1
            if best[key][0] != cost or key in settled:
                continue
            settled.add(key)
            node, state = divmod(key, scale)
            if node == goal:
                reached.append(key)
                continue
            mask = masks.get(state)
            if mask is None:
                mask = machine.mask(state)
            steps = leaving.get(node)
            if steps is None:
                steps = machine.out(node)
            path: list[str] | None = None
            for step in steps:
                if mask & step[3] != step[3] or mask & step[4]:
                    continue
                moved = step[6].get(state, -1)
                if moved < 0:
                    moved = machine.advance(step, state)
                following = step[2] * scale + moved
                reach = cost + step[1]
                known = best.get(following)
                if known is None or reach < known[0]:
                    best[following] = (reach, key, step[0])
                    waiting = buckets.get(reach)
                    if waiting is None:
                        buckets[reach] = [following]
                        heapq.heappush(levels, reach)
                    else:
                        waiting.append(following)
                elif reach == known[0]:
                    if path is None:
                        path = _path_of(best, key)
                    if path + [step[0]] < _path_of(best, following):
                        best[following] = (reach, key, step[0])
        if reached:
            return min(_path_of(best, key) for key in reached)
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
