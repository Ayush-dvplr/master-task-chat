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


def _tracked_fields(registry: Registry, domain: str) -> list[str]:
    """Prerequisite fields of the domain plus every field a rename can move into one of them."""
    cache = registry._plan_spaces.setdefault("tracked", {})
    if domain not in cache:
        names = set(registry.prerequisite_fields(domain))
        renames = [
            (operation[1], operation[2])
            for edge in registry.edges.values()
            if registry.schemas.get(edge.source) == domain
            for operation in edge.operations
            if operation[0] == "rename"
        ]
        changed = True
        while changed:
            changed = False
            for source, target in renames:
                if target in names and source not in names:
                    names.add(source)
                    changed = True
        cache[domain] = sorted(names)
    return cache[domain]


def _search(
    registry: Registry, domain: str, names: list[str], schema_id: str, target: str, start: tuple[str, ...]
) -> list[str] | None:
    """Cheapest plan, ties broken by the lexicographically smallest edge-id list."""
    transitions = registry._plan_spaces.setdefault("transitions", {})
    heap: list[tuple[int, tuple[str, ...], str, tuple[str, ...]]] = [(0, (), schema_id, start)]
    done: set[tuple[str, tuple[str, ...]]] = set()
    while heap:
        cost, path, node, state = heapq.heappop(heap)
        if (node, state) in done:
            continue
        done.add((node, state))
        if node == target:
            return list(path)
        view = None
        for edge in registry.edges_from.get(node, ()):
            key = (edge.edge_id, state)
            following = transitions.get(key, False)
            if following is False:
                if view is None:
                    view = FieldView(dict(zip(names, state)))
                if edge_allowed(registry, domain, view, edge):
                    following = _advance(registry, domain, names, state, edge)
                else:
                    following = None
                transitions[key] = following
            if following is None or (edge.target, following) in done:
                continue
            heapq.heappush(heap, (cost + edge.cost, path + (edge.edge_id,), edge.target, following))
    return None


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema (ties: lexicographically smallest edge-id list)."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = _tracked_fields(registry, domain)
    start = FieldView.from_payload(payload).states(names)
    plans = registry._plan_spaces.setdefault("plans", {})
    key = (schema_id, start)
    if key not in plans:
        plans[key] = _search(registry, domain, names, schema_id, target, start)
    plan = plans[key]
    if plan is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return list(plan)
