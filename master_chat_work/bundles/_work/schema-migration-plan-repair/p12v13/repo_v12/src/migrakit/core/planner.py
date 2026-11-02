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
    live = _live_edges(registry, domain, names, schema_id, start)
    rest = _cost_to_target(registry, target, live)
    if schema_id not in rest:
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
            if following is None or (edge.target, following) in settled:
                continue
            ahead = remainder(edge.target, following)
            if ahead is None:
                continue
            spent = cost + edge.cost
            heapq.heappush(frontier, (spent + ahead, path + (edge.edge_id,), spent, edge.target, following))
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")


_STATE_SEARCH_LIMIT = 200_000


def _live_edges(
    registry: Registry, domain: str, names: list[str], schema_id: str, start: tuple[str, ...]
) -> set[str]:
    """Ids of the edges reachable from ``schema_id`` that some reachable field state can take.

    Field states are followed as if every reachable edge could be taken from every
    schema, so an edge left out can never be taken on any plan. When that search
    grows past ``_STATE_SEARCH_LIMIT`` steps, every reachable edge is kept.
    """
    reachable = {schema_id}
    pending = [schema_id]
    groups: dict[tuple, list[Edge]] = {}
    while pending:
        for edge in registry.edges_from.get(pending.pop(), ()):
            groups.setdefault((edge.requires, edge.operations), []).append(edge)
            if edge.target not in reachable:
                reachable.add(edge.target)
                pending.append(edge.target)
    kinds = list(groups.values())
    everything = {edge.edge_id for group in kinds for edge in group}
    taken = [False] * len(kinds)
    seen = {start}
    waiting = [start]
    steps = 0
    while waiting:
        state = waiting.pop()
        view = FieldView(dict(zip(names, state)))
        for index, group in enumerate(kinds):
            steps += 1
            if steps > _STATE_SEARCH_LIMIT:
                return everything
            if not edge_allowed(registry, domain, view, group[0]):
                continue
            taken[index] = True
            following = _advance(registry, domain, names, state, group[0])
            if following not in seen:
                seen.add(following)
                waiting.append(following)
    return {edge.edge_id for index, group in enumerate(kinds) if taken[index] for edge in group}


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
