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


def _shortest_plan(
    registry: Registry, domain: str, schema_id: str, target: str, names: list[str], start: tuple[str, ...]
) -> list[str] | None:
    """Dijkstra over (schema, field state); ties broken by the smallest edge-id list."""
    heap: list = [(0, (), schema_id, start)]
    settled: set = set()
    transitions: dict = {}
    while heap:
        cost, path, node, state = heapq.heappop(heap)
        if (node, state) in settled:
            continue
        settled.add((node, state))
        if node == target:
            return list(path)
        view = FieldView({name: value for name, value in zip(names, state) if value != ABSENT})
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            key = (edge.edge_id, state)
            following = transitions.get(key)
            if following is None:
                following = _advance(registry, domain, names, state, edge)
                transitions[key] = following
            if (edge.target, following) in settled:
                continue
            heapq.heappush(heap, (cost + edge.cost, path + (edge.edge_id,), edge.target, following))
    return None


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    key = (schema_id, start)
    if key not in registry._plans:
        registry._plans[key] = _shortest_plan(registry, domain, schema_id, target, names, start)
    plan = registry._plans[key]
    if plan is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return list(plan)
