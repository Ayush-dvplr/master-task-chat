"""Migration planning over (schema, field state)."""

from __future__ import annotations

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
    """Prefer the cheaper plan, then the shorter one; keep the first plan found otherwise."""
    if best is None:
        return candidate
    if (candidate[0], len(candidate[1])) < (best[0], len(best[1])):
        return candidate
    return best


def _enumerate_paths(
    registry: Registry,
    domain: str,
    origin: FieldView,
    node: str,
    target: str,
    names: list[str],
    state: tuple[str, ...],
    path: list[str],
    visited: set[str],
    cost: int,
    best: list,
) -> None:
    if node == target:
        best[0] = _better(best[0], (cost, list(path)))
        return
    for edge in registry.edges_from.get(node, ()):
        if edge.target in visited:
            continue
        if not edge_allowed(registry, domain, origin, edge):
            continue
        visited.add(edge.target)
        path.append(edge.edge_id)
        following = _advance(registry, domain, names, state, edge)
        _enumerate_paths(registry, domain, origin, edge.target, target, names, following, path, visited, cost + edge.cost, best)
        path.pop()
        visited.discard(edge.target)


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    origin = FieldView.from_payload(payload)
    best: list = [None]
    _enumerate_paths(registry, domain, origin, schema_id, target, names, origin.states(names), [], {schema_id}, 0, best)
    if best[0] is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return best[0][1]
