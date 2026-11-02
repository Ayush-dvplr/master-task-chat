"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .records import ABSENT, NULL, VALUE, FieldView, fill_mode, null_counts_as


def state_signature(registry: Registry, schema_id: str, payload: dict) -> dict[str, str]:
    """State of every prerequisite field of the record's domain, sorted by name."""
    domain = registry.domain_of(schema_id)
    return FieldView.from_payload(payload).signature(registry.prerequisite_fields(domain))


def _edge_table(registry: Registry, domain: str, positions: dict[str, int], edge: Edge) -> tuple[tuple, tuple]:
    """The prerequisites and the state moves of one edge, as positions in a state tuple.

    Planning only follows field states, so the operations of an edge become moves
    on the state tuple: a cast never changes a state, and ``add`` either fills a
    field or leaves it alone whatever the default value is.
    """
    checks = []
    for kind, name in edge.requires:
        if null_counts_as(registry, domain, name) == "present":
            accepted = (VALUE, NULL) if kind == "has" else (ABSENT,)
        else:
            accepted = (VALUE,) if kind == "has" else (ABSENT, NULL)
        checks.append((positions[name], frozenset(accepted)))
    moves = []
    for operation in edge.operations:
        kind = operation[0]
        if kind == "rename":
            moves.append(("rename", positions[operation[1]], positions[operation[2]]))
        elif kind == "drop":
            moves.append(("drop", positions[operation[1]], None))
        elif kind == "add":
            policy = registry.policies.get((domain, operation[1]))
            if policy is None or not policy.has_default:
                continue
            filled = NULL if policy.default is None else VALUE
            over_null = fill_mode(registry, domain, operation[1]) == "absent_or_null"
            moves.append(("add", positions[operation[1]], (filled, over_null)))
    return tuple(checks), tuple(moves)


def _tables(registry: Registry, domain: str, names: list[str]) -> tuple[dict[str, int], dict]:
    cache = registry.state_tables(domain)
    if "positions" not in cache:
        cache["positions"] = {name: index for index, name in enumerate(names)}
        cache["edges"] = {}
    return cache["positions"], cache["edges"]


def _allowed(state: tuple[str, ...], checks: tuple) -> bool:
    for index, accepted in checks:
        if state[index] not in accepted:
            return False
    return True


def _advance(state: tuple[str, ...], moves: tuple) -> tuple[str, ...]:
    if not moves:
        return state
    following = list(state)
    for kind, index, extra in moves:
        if kind == "rename":
            if following[index] != ABSENT:
                following[extra] = following[index]
                if extra != index:
                    following[index] = ABSENT
        elif kind == "drop":
            following[index] = ABSENT
        else:
            filled, over_null = extra
            if following[index] == ABSENT or (over_null and following[index] == NULL):
                following[index] = filled
    return tuple(following)


def _explore(
    registry: Registry, domain: str, names: list[str], start: tuple[str, tuple[str, ...]], target: str
) -> tuple[dict, dict, int | None]:
    """Expand every (schema, state) node a cheapest plan can use, with their costs.

    The search is an A* over (schema, field state) nodes bounded by the cost of
    the schemas alone (``Registry.schema_costs``), so field states are only
    unfolded while they can still lead to a cheapest plan. Costs are positive, so
    a node at ``target`` ends a plan and is never expanded.
    """
    bound = registry.schema_costs(domain)
    if start[0] not in bound:
        return {}, {}, None
    positions, tables = _tables(registry, domain, names)
    graph: dict[tuple[str, tuple[str, ...]], list[tuple[str, int, tuple[str, tuple[str, ...]]]]] = {}
    cheapest = {start: 0}
    queue = [(bound[start[0]], 0, start)]
    total: int | None = None
    while queue:
        estimate, spent, node = heapq.heappop(queue)
        if total is not None and estimate > total:
            break
        if node in graph:
            continue
        graph[node] = outgoing = []
        if node[0] == target:
            if total is None:
                total = spent
            continue
        schema, state = node
        for edge in registry.edges_from.get(schema, ()):
            table = tables.get(edge.edge_id)
            if table is None:
                table = tables[edge.edge_id] = _edge_table(registry, domain, positions, edge)
            checks, moves = table
            if not _allowed(state, checks):
                continue
            reached = (edge.target, _advance(state, moves))
            outgoing.append((edge.edge_id, edge.cost, reached))
            ahead = spent + edge.cost
            if edge.target in bound and ahead < cheapest.get(reached, ahead + 1):
                cheapest[reached] = ahead
                heapq.heappush(queue, (ahead + bound[edge.target], ahead, reached))
    return graph, cheapest, total


def _distance_to_target(graph: dict, target: str, cheapest: dict, total: int) -> dict:
    """Cost of the cheapest run to a node at ``target``, for the nodes a cheapest plan can use.

    A node whose cheapest arrival plus its cheapest run to the target exceeds
    ``total`` lies on no cheapest plan, so it is left out.
    """
    incoming: dict = {}
    for node, outgoing in graph.items():
        spent = cheapest[node]
        for _, cost, reached in outgoing:
            if spent + cost <= total:
                incoming.setdefault(reached, []).append((cost, node))
    distance: dict = {}
    queue = [(0, node) for node in graph if node[0] == target]
    heapq.heapify(queue)
    while queue:
        cost, node = heapq.heappop(queue)
        if node in distance:
            continue
        distance[node] = cost
        for step, previous in incoming.get(node, ()):
            if previous not in distance and cheapest[previous] + step + cost <= total:
                heapq.heappush(queue, (cost + step, previous))
    return distance


def _cheapest_plan(graph: dict, distance: dict, start: tuple[str, tuple[str, ...]], target: str) -> list[str]:
    """The cheapest plan, breaking ties on the edge id list (M8)."""
    plan: list[str] = []
    node = start
    while node[0] != target:
        best: tuple[str, tuple[str, tuple[str, ...]]] | None = None
        for edge_id, cost, reached in graph[node]:
            if reached in distance and cost + distance[reached] == distance[node]:
                if best is None or edge_id < best[0]:
                    best = (edge_id, reached)
        plan.append(best[0])
        node = best[1]
    return plan


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    start = (schema_id, FieldView.from_payload(payload).states(names))
    graph, cheapest, total = _explore(registry, domain, names, start, target)
    if total is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    distance = _distance_to_target(graph, target, cheapest, total)
    return _cheapest_plan(graph, distance, start, target)
