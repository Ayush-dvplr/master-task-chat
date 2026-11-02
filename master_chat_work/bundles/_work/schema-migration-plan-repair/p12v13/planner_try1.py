"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .operations import apply_operations
from .records import ABSENT, NULL, VALUE, FieldView, counts_present, edge_allowed

_STAND_IN_VALUE = "<value>"


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


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest feasible plan to the canonical schema; ties go to the smallest edge-id list."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    holds, live = _goal_sets(registry, domain, names, schema_id, target)
    rest = _cost_to_target(registry, target, live)
    if schema_id not in rest or not holds(schema_id, start):
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    tables = [
        (names.index(name), _field_cost_to_target(registry, domain, target, rest, name, live))
        for name in registry.prerequisite_fields(domain)
    ]

    def remainder(node: str, state: tuple[str, ...]) -> int | None:
        best = rest[node]
        for index, table in tables:
            cost = table.get((node, state[index]))
            if cost is None:
                return None
            best = max(best, cost)
        return best

    first = remainder(schema_id, start)
    if first is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    # Ordered by spent cost plus the cheapest possible remainder, then by edge-id list.
    frontier: list[tuple[int, tuple[str, ...], int, str, tuple[str, ...]]] = [(first, (), 0, schema_id, start)]
    settled: set[tuple[str, tuple[str, ...]]] = set()
    # The state an edge leaves depends only on the state it starts from, its prerequisites and its operations.
    moves: dict[tuple, tuple[str, ...] | None] = {}
    while frontier:
        _, path, cost, node, state = heapq.heappop(frontier)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            return list(path)
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if edge.edge_id not in live or edge.target not in rest:
                continue
            key = (state, edge.requires, edge.operations)
            if key not in moves:
                moves[key] = _advance(registry, domain, names, state, edge) if edge_allowed(registry, domain, view, edge) else None
            following = moves[key]
            if following is None or (edge.target, following) in settled or not holds(edge.target, following):
                continue
            ahead = remainder(edge.target, following)
            if ahead is None:
                continue
            spent = cost + edge.cost
            heapq.heappush(frontier, (spent + ahead, path + (edge.edge_id,), spent, edge.target, following))
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")


_MASKS: dict[tuple[int, ...], tuple[list[int], int, list[list[int]]]] = {}


def _masks(radices: tuple[int, ...]) -> tuple[list[int], int, list[list[int]]]:
    """Place values of a mixed-radix state index and, per field and code, the bits of states holding it."""
    if radices not in _MASKS:
        weights = []
        size = 1
        for radix in radices:
            weights.append(size)
            size *= radix
        everything = (1 << size) - 1
        rows = []
        for weight, radix in zip(weights, radices):
            row = []
            for code in range(radix):
                pattern, length = ((1 << weight) - 1) << (code * weight), weight * radix
                while length < size:
                    pattern |= pattern << length
                    length *= 2
                row.append(pattern & everything)
            rows.append(row)
        _MASKS[radices] = (weights, everything, rows)
    return _MASKS[radices]


def _goal_sets(registry: Registry, domain: str, names: list[str], schema_id: str, target: str):
    """For every schema reachable from ``schema_id``, the exact set of field states from which a plan to
    ``target`` exists, kept as a bit set over all field states; also the ids of the edges some such plan uses.

    The sets are a least fixpoint computed backwards from the target, one strongly connected group of
    schemas at a time, so the work grows with the number of edges times the size of a bit set and never
    with the number of paths.
    """
    joint = all(counts_present(registry, domain, name, NULL) for name in names)
    states = (ABSENT, VALUE) if joint else (ABSENT, NULL, VALUE)
    code_of = {ABSENT: 0, NULL: 1, VALUE: 1 if joint else 2}
    radix = len(states)
    weights, everything, rows = _masks((radix,) * len(names))
    index = {name: position for position, name in enumerate(names)}

    def spread(bits: int, position: int) -> int:
        weight = weights[position]
        return bits | sum(bits << (code * weight) for code in range(1, radix))

    images: dict[tuple, tuple[int, ...]] = {}

    def before(edge: Edge, after: int) -> int:
        bits = after
        for operation in reversed(edge.operations):
            if not bits:
                return 0
            if operation[0] == "cast":
                continue
            position = index.get(operation[1])
            if position is None:
                return everything
            weight = weights[position]
            if operation[0] == "drop":
                bits = spread(bits & rows[position][0], position)
            elif operation[0] == "add":
                if operation not in images:
                    images[operation] = tuple(
                        code_of[_advance(registry, domain, [operation[1]], (state,), _only(edge, operation))[0]]
                        for state in states
                    )
                bits = sum(
                    ((bits & rows[position][code]) >> (code * weight)) << (was * weight)
                    for was, code in enumerate(images[operation])
                )
            else:
                other = index.get(operation[2])
                if other is None:
                    return everything
                if other == position:
                    continue
                kept = bits & rows[position][0]
                moved = 0
                for code in range(1, radix):
                    part = (kept & rows[other][code]) >> (code * weights[other])
                    if part:
                        moved |= spread(part << (code * weight), other)
                bits = kept | moved
        for kind, name in edge.requires:
            position = index.get(name)
            if position is None:
                if kind == "has":
                    return 0
                continue
            bits &= sum(
                rows[position][code]
                for code, state in enumerate(states)
                if counts_present(registry, domain, name, state) == (kind == "has")
            )
        return bits

    reachable = {schema_id}
    pending = [schema_id]
    while pending:
        node = pending.pop()
        if node == target:
            continue
        for edge in registry.edges_from.get(node, ()):
            if edge.target not in reachable:
                reachable.add(edge.target)
                pending.append(edge.target)
    incoming: dict[str, list[Edge]] = {}
    for node in reachable:
        if node != target:
            for edge in registry.edges_from.get(node, ()):
                incoming.setdefault(edge.target, []).append(edge)
    keep = {target} if target in reachable else set()
    pending = list(keep)
    while pending:
        for edge in incoming.get(pending.pop(), ()):
            if edge.source not in keep:
                keep.add(edge.source)
                pending.append(edge.source)
    leaving = {
        node: [edge for edge in registry.edges_from.get(node, ()) if edge.target in keep]
        for node in keep
        if node != target
    }
    leaving[target] = []

    goals: dict[str, int] = {}
    cache: dict[str, tuple[int, int]] = {}

    def gather(node: str) -> int:
        found = 0
        for edge in leaving[node]:
            after = goals.get(edge.target, 0)
            hit = cache.get(edge.edge_id)
            if hit is None or hit[0] is not after:
                hit = (after, before(edge, after))
                cache[edge.edge_id] = hit
            found |= hit[1]
        return found

    # Strongly connected groups, emitted with every group they lead to already done.
    order: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    if schema_id in keep:
        work = [(schema_id, iter(leaving[schema_id]))]
        order[schema_id] = low[schema_id] = 0
        stack.append(schema_id)
        on_stack.add(schema_id)
    else:
        work = []
    while work:
        node, edges = work[-1]
        descended = False
        for edge in edges:
            following = edge.target
            if following not in order:
                order[following] = low[following] = len(order)
                stack.append(following)
                on_stack.add(following)
                work.append((following, iter(leaving[following])))
                descended = True
                break
            if following in on_stack:
                low[node] = min(low[node], order[following])
        if descended:
            continue
        work.pop()
        if work:
            parent = work[-1][0]
            low[parent] = min(low[parent], low[node])
        if low[node] != order[node]:
            continue
        group = []
        while True:
            member = stack.pop()
            on_stack.discard(member)
            group.append(member)
            if member == node:
                break
        if group == [target]:
            goals[target] = everything
            continue
        members = set(group)
        waiting = list(group)
        queued = set(group)
        while waiting:
            member = waiting.pop()
            queued.discard(member)
            found = gather(member)
            if found != goals.get(member, 0):
                goals[member] = found
                for edge in incoming.get(member, ()):
                    if edge.source in members and edge.source not in queued:
                        queued.add(edge.source)
                        waiting.append(edge.source)

    live = set()
    for node in keep:
        if goals.get(node):
            for edge in leaving[node]:
                after = goals.get(edge.target, 0)
                hit = cache.get(edge.edge_id)
                if (hit[1] if hit is not None and hit[0] is after else before(edge, after)):
                    live.add(edge.edge_id)

    def holds(node: str, state: tuple[str, ...]) -> bool:
        position = sum(code_of[value] * weight for value, weight in zip(state, weights))
        return bool((goals.get(node, 0) >> position) & 1)

    return holds, live


def _cost_to_target(registry: Registry, target: str, live: set[str]) -> dict[str, int]:
    """Cheapest edge-cost sum from each schema to the target over ``live`` edges, prerequisites left aside."""
    incoming: dict[str, list[Edge]] = {}
    for edge in registry.edges.values():
        if edge.source != target and edge.edge_id in live:
            incoming.setdefault(edge.target, []).append(edge)
    rest = {target: 0}
    queue = [(0, target)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > rest[node]:
            continue
        for edge in incoming.get(node, ()):
            reach = cost + edge.cost
            if edge.source not in rest or reach < rest[edge.source]:
                rest[edge.source] = reach
                heapq.heappush(queue, (reach, edge.source))
    return rest


def _field_cost_to_target(
    registry: Registry, domain: str, target: str, rest: dict[str, int], name: str, live: set[str]
) -> dict[tuple[str, str], int]:
    """Cheapest edge-cost sum from each (schema, state of one field) to the target.

    Only the prerequisites on ``name`` are checked and only its state is followed;
    a rename into ``name`` from a field whose state is not tracked may leave any state.
    """
    incoming: dict[tuple[str, str], list[tuple[tuple[str, str], int]]] = {}
    for edge in registry.edges.values():
        if edge.edge_id not in live or edge.source == target or edge.target not in rest or registry.schemas.get(edge.source) != domain:
            continue
        for state in (ABSENT, NULL, VALUE):
            if any(
                counts_present(registry, domain, field_name, state) != (kind == "has")
                for kind, field_name in edge.requires
                if field_name == name
            ):
                continue
            reached = {state}
            for operation in edge.operations:
                kind = operation[0]
                if kind in ("rename", "drop") and operation[1] == name:
                    reached = {ABSENT}
                elif kind == "rename" and operation[2] == name:
                    reached = reached | {NULL, VALUE}
                elif kind == "add" and operation[1] == name:
                    reached = {_advance(registry, domain, [name], (one,), _only(edge, operation))[0] for one in reached}
            for one in reached:
                incoming.setdefault((edge.target, one), []).append(((edge.source, state), edge.cost))
    best = {(target, state): 0 for state in (ABSENT, NULL, VALUE)}
    queue = [(0, node) for node in best]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > best[node]:
            continue
        for previous, step in incoming.get(node, ()):
            reach = cost + step
            if previous not in best or reach < best[previous]:
                best[previous] = reach
                heapq.heappush(queue, (reach, previous))
    return best


def _only(edge: Edge, operation: tuple[str, ...]) -> Edge:
    return Edge(edge.edge_id, edge.source, edge.target, (), (operation,), edge.cost)
