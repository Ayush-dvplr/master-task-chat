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
    rest = _cost_to_target(registry, target)
    if schema_id not in rest:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    tables = [
        (names.index(name), _field_cost_to_target(registry, domain, target, rest, name))
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
    while frontier:
        _, path, cost, node, state = heapq.heappop(frontier)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            return list(path)
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if edge.target not in rest or not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            if (edge.target, following) in settled:
                continue
            ahead = remainder(edge.target, following)
            if ahead is None:
                continue
            spent = cost + edge.cost
            heapq.heappush(frontier, (spent + ahead, path + (edge.edge_id,), spent, edge.target, following))
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")


def _cost_to_target(registry: Registry, target: str) -> dict[str, int]:
    """Cheapest edge-cost sum from each schema to the target, prerequisites left aside."""
    incoming: dict[str, list[Edge]] = {}
    for edge in registry.edges.values():
        if edge.source != target:
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
    registry: Registry, domain: str, target: str, rest: dict[str, int], name: str
) -> dict[tuple[str, str], int]:
    """Cheapest edge-cost sum from each (schema, state of one field) to the target.

    Only the prerequisites on ``name`` are checked and only its state is followed;
    a rename into ``name`` from a field whose state is not tracked may leave any state.
    """
    incoming: dict[tuple[str, str], list[tuple[tuple[str, str], int]]] = {}
    for edge in registry.edges.values():
        if edge.source == target or edge.target not in rest or registry.schemas.get(edge.source) != domain:
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
