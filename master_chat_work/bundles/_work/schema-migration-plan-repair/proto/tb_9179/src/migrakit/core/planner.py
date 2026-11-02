"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .operations import apply_operations
from .records import ABSENT, NULL, FieldView, counts_present

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
    """Cheapest plan to the canonical schema; ties go to the smallest list of edge ids.

    The search runs over (schema, state of every named field), so a plan may
    revisit a schema in a different field state. Labels are (cost, edge ids);
    with positive costs, extending two labels of one node by the same edge keeps
    their order, so Dijkstra on these labels yields the M8 optimum.
    """
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    index = {name: position for position, name in enumerate(names)}
    start = FieldView.from_payload(payload).states(names)
    transitions: dict[tuple[str, tuple[str, ...]], tuple[str, ...]] = {}
    checks: dict[tuple[str, tuple[str, ...]], bool] = {}

    def allowed(edge: Edge, state: tuple[str, ...]) -> bool:
        key = (edge.edge_id, state)
        if key not in checks:
            checks[key] = all(
                counts_present(registry, domain, name, state[index[name]]) == (kind == "has")
                for kind, name in edge.requires
            )
        return checks[key]

    def advance(edge: Edge, state: tuple[str, ...]) -> tuple[str, ...]:
        key = (edge.edge_id, state)
        if key not in transitions:
            transitions[key] = _advance(registry, domain, names, state, edge)
        return transitions[key]

    best: dict[tuple[str, tuple[str, ...]], tuple[int, tuple[str, ...]]] = {(schema_id, start): (0, ())}
    heap: list[tuple[int, tuple[str, ...], str, tuple[str, ...]]] = [(0, (), schema_id, start)]
    settled: set[tuple[str, tuple[str, ...]]] = set()
    while heap:
        cost, path, node, state = heapq.heappop(heap)
        if node == target:
            return list(path)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        for edge in registry.edges_from.get(node, ()):
            if not allowed(edge, state):
                continue
            following = advance(edge, state)
            key = (edge.target, following)
            if key in settled:
                continue
            label = (cost + edge.cost, path + (edge.edge_id,))
            known = best.get(key)
            if known is not None and known <= label:
                continue
            best[key] = label
            heapq.heappush(heap, (label[0], label[1], edge.target, following))
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
