"""Generic planner variants for the g37 cost matrix; VARIANT is rewritten per run."""

from __future__ import annotations

import heapq

from ..errors import MigrationError
from ..parser.contracts import Edge, Registry
from .operations import apply_operations
from .records import ABSENT, NULL, FieldView, counts_present, edge_allowed

VARIANT = "astar"
_STAND_IN_VALUE = "<value>"
_LIMIT = 80


def state_signature(registry: Registry, schema_id: str, payload: dict) -> dict[str, str]:
    """State of every prerequisite field of the record's domain, sorted by name."""
    domain = registry.domain_of(schema_id)
    return FieldView.from_payload(payload).signature(registry.prerequisite_fields(domain))


def _stand_in(names: list[str], state: tuple[str, ...]) -> dict:
    return {name: (None if value == NULL else _STAND_IN_VALUE) for name, value in zip(names, state) if value != ABSENT}


def _advance(registry: Registry, domain: str, names: list[str], state: tuple[str, ...], edge: Edge) -> tuple[str, ...]:
    record = apply_operations(registry, domain, _stand_in(names, state), edge.operations)
    return FieldView.from_payload(record).states(names)


def _rest(registry: Registry, target: str) -> tuple[dict[str, int], dict[str, Edge]]:
    incoming: dict[str, list[Edge]] = {}
    for edge in registry.edges.values():
        if edge.source != target:
            incoming.setdefault(edge.target, []).append(edge)
    rest, step = {target: 0}, {}
    queue = [(0, target)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > rest[node]:
            continue
        for edge in incoming.get(node, ()):
            reach = cost + edge.cost
            if edge.source not in rest or reach < rest[edge.source]:
                rest[edge.source], step[edge.source] = reach, edge
                heapq.heappush(queue, (reach, edge.source))
    return rest, step


class _Search:
    def __init__(self, registry: Registry, schema_id: str, payload: dict) -> None:
        self.registry = registry
        self.domain = registry.domain_of(schema_id)
        self.target = registry.canonical[self.domain]
        self.names = registry.named_fields(self.domain)
        self.start = FieldView.from_payload(payload).states(self.names)
        self.prereq = [self.names.index(n) for n in registry.prerequisite_fields(self.domain)]

    def moves(self, node: str, state: tuple[str, ...]):
        view = FieldView(dict(zip(self.names, state)))
        for edge in self.registry.edges_from.get(node, ()):
            if edge_allowed(self.registry, self.domain, view, edge):
                yield edge, _advance(self.registry, self.domain, self.names, state, edge)

    def mask(self, state: tuple[str, ...]) -> int:
        return sum(1 << i for i in self.prereq if counts_present(self.registry, self.domain, self.names[i], state[i]))

    def best_first(self, schema_id: str, key, bound, prune) -> list[str] | None:
        heap = [(bound(schema_id, self.start), (), 0, schema_id, self.start)]
        done: set = set()
        while heap:
            _, path, cost, node, state = heapq.heappop(heap)
            if prune(cost, node, state, done):
                continue
            if node == self.target:
                return list(path)
            for edge, following in self.moves(node, state):
                if key(edge.target, following) in done:
                    continue
                spent = cost + edge.cost
                ahead = bound(edge.target, following)
                if ahead is not None:
                    heapq.heappush(heap, (spent + ahead, path + (edge.edge_id,), spent, edge.target, following))
        return None


def _greedy(s: _Search, schema_id: str) -> tuple[int, list[str]] | None:
    node, state, cost, path, seen = schema_id, s.start, 0, [], {(schema_id, s.start)}
    for _ in range(_LIMIT):
        if node == s.target:
            return cost, path
        options = sorted((e.cost, e.edge_id, e, f) for e, f in s.moves(node, state) if (e.target, f) not in seen)
        if not options:
            return None
        _, _, edge, state = options[0]
        node, cost = edge.target, cost + edge.cost
        path.append(edge.edge_id)
        seen.add((node, state))
    return (cost, path) if node == s.target else None


def _exhaustive(s: _Search, schema_id: str) -> list[str] | None:
    best: list = []

    def walk(node, state, cost, path, seen):
        if node == s.target:
            if not best or (cost, path) < best[0]:
                best[:] = [(cost, list(path))]
            return
        if len(path) >= _LIMIT:
            return
        for edge, following in s.moves(node, state):
            if (edge.target, following) not in seen:
                seen.add((edge.target, following))
                path.append(edge.edge_id)
                walk(edge.target, following, cost + edge.cost, path, seen)
                path.pop()
                seen.discard((edge.target, following))

    walk(schema_id, s.start, 0, [], {(schema_id, s.start)})
    return best[0][1] if best else None


def _bidirectional(s: _Search, schema_id: str, step: dict[str, Edge]) -> list[str] | None:
    best, best_path = None, None
    heap, done = [(0, (), schema_id, s.start)], set()
    while heap:
        cost, path, node, state = heapq.heappop(heap)
        if best is not None and cost >= best:
            break
        if (node, state) in done:
            continue
        done.add((node, state))
        tail, total, here, now = [], 0, node, state
        while here != s.target and here in step:
            edge = step[here]
            if not edge_allowed(s.registry, s.domain, FieldView(dict(zip(s.names, now))), edge):
                break
            now = _advance(s.registry, s.domain, s.names, now, edge)
            tail.append(edge.edge_id)
            total += edge.cost
            here = edge.target
        if here == s.target and (best is None or cost + total < best):
            best, best_path = cost + total, list(path) + tail
        for edge, following in s.moves(node, state):
            if (edge.target, following) not in done:
                heapq.heappush(heap, (cost + edge.cost, path + (edge.edge_id,), edge.target, following))
    return best_path


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest feasible plan to the canonical schema; ties go to the smallest edge-id list."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    s = _Search(registry, schema_id, payload)
    rest, step = _rest(registry, target)
    full = lambda node, state: (node, state)
    zero = lambda node, state: 0

    def settle(key):
        def prune(cost, node, state, done):
            k = key(node, state)
            if k in done:
                return True
            done.add(k)
            return False
        return prune

    plan: list[str] | None
    if VARIANT == "astar":
        plan = s.best_first(schema_id, full, lambda n, st: rest.get(n), settle(full))
    elif VARIANT == "signature_keyed":
        sig = lambda n, st: (n, tuple(st[i] for i in s.prereq))
        plan = s.best_first(schema_id, sig, zero, settle(sig))
    elif VARIANT == "dominance":
        labels: dict[str, list[tuple[int, int]]] = {}

        def dominated(cost, node, state, done):
            if (node, state) in done:
                return True
            done.add((node, state))
            mask = s.mask(state)
            if any(c <= cost and (m & mask) == mask for c, m in labels.get(node, ())):
                return True
            labels.setdefault(node, []).append((cost, mask))
            return False

        plan = s.best_first(schema_id, full, zero, dominated)
    elif VARIANT == "incumbent":
        walk = _greedy(s, schema_id)
        upper = walk[0] if walk else None
        base = settle(full)
        plan = s.best_first(schema_id, full, zero, lambda c, n, st, d: (upper is not None and c > upper) or base(c, n, st, d))
    elif VARIANT == "greedy":
        walk = _greedy(s, schema_id)
        plan = walk[1] if walk else None
    elif VARIANT == "exhaustive":
        plan = _exhaustive(s, schema_id)
    elif VARIANT == "bidirectional":
        plan = _bidirectional(s, schema_id, step)
    elif VARIANT == "schema_only":
        plan = None
        if schema_id in rest:
            plan, node = [], schema_id
            while node != target:
                plan.append(step[node].edge_id)
                node = step[node].target
    else:
        raise ValueError(f"unknown variant {VARIANT}")
    if plan is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return plan
