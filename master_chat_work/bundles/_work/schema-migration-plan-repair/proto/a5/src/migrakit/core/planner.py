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


def _better(best: tuple[int, list[str]] | None, candidate: tuple[int, list[str]]) -> tuple[int, list[str]]:
    """Prefer the cheaper plan, then the one whose edge id list is smaller (M8)."""
    if best is None or candidate < best:
        return candidate
    return best


def _enumerate_paths(
    registry: Registry,
    domain: str,
    names: list[str],
    source: str,
    target: str,
    state: tuple[str, ...],
) -> list[str] | None:
    """Best plan from ``source`` to ``target``, searching over (schema, field state).

    A label-setting search: labels ``(cost, edge ids)`` are popped in M8 order, and
    because every edge cost is positive, a label that loses on a (schema, field
    state) pair also loses once extended, so keeping the best label per pair is
    enough. A plan may therefore pass through a schema more than once (M7) without
    the search ever enumerating paths one by one.
    """
    best: dict[tuple[str, tuple[str, ...]], tuple[int, list[str]]] = {(source, state): (0, [])}
    queue: list[tuple[int, list[str], str, tuple[str, ...]]] = [(0, [], source, state)]
    while queue:
        cost, path, node, fields = heapq.heappop(queue)
        if best[(node, fields)] != (cost, path):
            continue
        if node == target:
            return path
        view = FieldView(dict(zip(names, fields)))
        for edge in registry.edges_from.get(node, ()):
            if not edge_allowed(registry, domain, view, edge):
                continue
            reached = (edge.target, _advance(registry, domain, names, fields, edge))
            label = (cost + edge.cost, path + [edge.edge_id])
            if _better(best.get(reached), label) == label:
                best[reached] = label
                heapq.heappush(queue, (label[0], label[1], *reached))
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
    state = FieldView.from_payload(payload).states(names)
    plan = _enumerate_paths(registry, domain, names, schema_id, target, state)
    if plan is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return plan
