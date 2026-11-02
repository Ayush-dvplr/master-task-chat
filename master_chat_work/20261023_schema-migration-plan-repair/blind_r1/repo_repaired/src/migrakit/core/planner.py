"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .records import ABSENT, NULL, VALUE, FieldView, counts_present, fill_mode


def state_signature(registry: Registry, schema_id: str, payload: dict) -> dict[str, str]:
    """State of every prerequisite field of the record's domain, sorted by name."""
    domain = registry.domain_of(schema_id)
    return FieldView.from_payload(payload).signature(registry.prerequisite_fields(domain))


def _applies(registry: Registry, domain: str, index: dict[str, int], state: tuple[str, ...], edge: Edge) -> bool:
    for kind, name in edge.requires:
        if counts_present(registry, domain, name, state[index[name]]) != (kind == "has"):
            return False
    return True


def _transition(
    registry: Registry, domain: str, index: dict[str, int], state: tuple[str, ...], edge: Edge
) -> tuple[str, ...]:
    """Field states after the edge's operations (M4, N4); casts never change a state."""
    states = list(state)
    for operation in edge.operations:
        kind = operation[0]
        if kind == "rename":
            source, target = index[operation[1]], index[operation[2]]
            if states[source] != ABSENT and source != target:
                states[target] = states[source]
                states[source] = ABSENT
        elif kind == "drop":
            states[index[operation[1]]] = ABSENT
        elif kind == "add":
            name = operation[1]
            policy = registry.policies.get((domain, name))
            if policy is None or not policy.has_default:
                continue
            current = states[index[name]]
            if current == ABSENT or (current == NULL and fill_mode(registry, domain, name) == "absent_or_null"):
                states[index[name]] = NULL if policy.default is None else VALUE
    return tuple(states)


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema; ties go to the smallest edge-id list (M8)."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    index = {name: position for position, name in enumerate(names)}
    start = (schema_id, FieldView.from_payload(payload).states(names))
    cached = registry._plans.get(start)
    if cached is None:
        cached = _search(registry, domain, index, start, target)
        registry._plans[start] = cached
    if cached is False:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return list(cached)


def _search(registry: Registry, domain: str, index: dict[str, int], start: tuple, target: str):
    """Dijkstra over (schema, field states) with labels (cost, edge-id tuple).

    Costs are positive, so a node's smallest label is final when popped and the
    first target popped carries the cheapest, then lexicographically smallest, plan.
    """
    best: dict[tuple, tuple[int, tuple[str, ...]]] = {start: (0, ())}
    heap: list = [(0, (), start)]
    done: set[tuple] = set()
    while heap:
        cost, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        schema, state = node
        if schema == target:
            return path
        for edge in registry.edges_from.get(schema, ()):
            if registry.schemas.get(edge.target) != domain:
                continue
            if not _applies(registry, domain, index, state, edge):
                continue
            following = (edge.target, _transition(registry, domain, index, state, edge))
            if following in done:
                continue
            label = (cost + edge.cost, path + (edge.edge_id,))
            known = best.get(following)
            if known is None or label < known:
                best[following] = label
                heapq.heappush(heap, (label[0], label[1], following))
    return False
