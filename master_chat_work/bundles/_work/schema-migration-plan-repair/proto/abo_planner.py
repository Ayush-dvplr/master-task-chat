"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .operations import apply_operations
from .records import ABSENT, NULL, FieldView, edge_allowed

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
    frontier: list[tuple[int, tuple[str, ...], str, tuple[str, ...]]] = [(0, (), schema_id, start)]
    settled: set[tuple[str, tuple[str, ...]]] = set()
    while frontier:
        cost, path, node, state = heapq.heappop(frontier)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            return list(path)
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            if (edge.target, following) in settled:
                continue
            heapq.heappush(frontier, (cost + edge.cost, path + (edge.edge_id,), edge.target, following))
    raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
