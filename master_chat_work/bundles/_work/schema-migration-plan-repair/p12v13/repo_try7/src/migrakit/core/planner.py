"""Migration planning over (schema, field state)."""

from __future__ import annotations

import heapq
from typing import Callable

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
    names = registry.named_fields(domain)
    start = FieldView.from_payload(payload).states(names)
    remaining = _cost_to_target(registry, domain, names, schema_id, target, start)
    left = remaining(schema_id, start)
    if left is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    # Costs are positive and every remaining cost is exact, so taking at each step the smallest
    # edge id that keeps the total least yields the smallest edge-id list among the cheapest plans.
    plan: list[str] = []
    node, state = schema_id, start
    while node != target:
        view = FieldView(dict(zip(names, state)))
        for edge in registry.edges_from.get(node, ()):
            if edge.cost > left or not edge_allowed(registry, domain, view, edge):
                continue
            following = _advance(registry, domain, names, state, edge)
            if remaining(edge.target, following) == left - edge.cost:
                plan.append(edge.edge_id)
                node, state, left = edge.target, following, left - edge.cost
                break
    return plan


_MASKS: dict[tuple[int, ...], tuple[list[int], int, list[list[int]]]] = {}


def _masks(radices: tuple[int, ...]) -> tuple[list[int], int, list[list[int]]]:
    """Place values of a mixed-radix state index and, per field and code, the bits of states holding it."""
    if radices not in _MASKS:
        weights = []
        size = 1
        for radix in radices:
            weights.append(size)
            size *= radix
        everything = (1 << size) - 1
        rows = []
        for weight, radix in zip(weights, radices):
            row = []
            for code in range(radix):
                pattern, length = ((1 << weight) - 1) << (code * weight), weight * radix
                while length < size:
                    pattern |= pattern << length
                    length *= 2
                row.append(pattern & everything)
            rows.append(row)
        _MASKS[radices] = (weights, everything, rows)
    return _MASKS[radices]


def _cost_to_target(
    registry: Registry, domain: str, names: list[str], schema_id: str, target: str, start: tuple[str, ...]
) -> Callable[[str, tuple[str, ...]], int | None]:
    """Least cost from a schema and a field state to ``target``, or None when no plan exists.

    The costs are found backwards from ``target`` over sets of field states kept as bit sets, ordered by
    cost plus the least schema-only cost from ``schema_id``, until no unsettled set can still lie on a
    cheapest plan from ``start``. Each schema gains a bit set at most once per distinct cost, so the work
    grows with edges, costs and the size of a bit set and never with the number of paths.
    """
    joint = all(counts_present(registry, domain, name, NULL) for name in names)
    states = (ABSENT, VALUE) if joint else (ABSENT, NULL, VALUE)
    code_of = {ABSENT: 0, NULL: 1, VALUE: 1 if joint else 2}
    radix = len(states)
    weights, everything, rows = _masks((radix,) * len(names))
    index = {name: position for position, name in enumerate(names)}

    programs: dict[tuple, tuple[list[tuple], int]] = {}

    def program(edge: Edge) -> tuple[list[tuple], int]:
        """The backward steps of ``edge`` (last operation first) and the mask of states its prerequisites allow."""
        key = (edge.requires, edge.operations)
        if key in programs:
            return programs[key]
        steps: list[tuple] = []
        for operation in reversed(edge.operations):
            position = index.get(operation[1])
            if operation[0] == "cast" or position is None:
                continue
            weight = weights[position]
            if operation[0] == "drop" or (operation[0] == "rename" and operation[2] not in index):
                steps.append((0, rows[position][0], [code * weight for code in range(1, radix)]))
            elif operation[0] == "add":
                image = tuple(
                    code_of[_advance(registry, domain, [operation[1]], (state,), _only(edge, operation))[0]]
                    for state in states
                )
                parts = []
                for code in sorted(set(image)):
                    shifts = [(was - code) * weight for was in range(radix) if image[was] == code]
                    parts.append((rows[position][code], shifts))
                steps.append((1, parts))
            elif operation[2] != operation[1]:
                other = index[operation[2]]
                moves = [
                    (rows[other][code], code * weights[other], code * weight,
                     [extra * weights[other] for extra in range(1, radix)])
                    for code in range(1, radix)
                ]
                steps.append((2, rows[position][0], moves))
        mask = everything
        for kind, name in edge.requires:
            if name not in index:
                mask = mask if kind == "lacks" else 0
                continue
            mask &= sum(
                rows[index[name]][code]
                for code, state in enumerate(states)
                if counts_present(registry, domain, name, state) == (kind == "has")
            )
        programs[key] = (steps, mask)
        return programs[key]

    def before(edge: Edge, landed: int) -> int:
        """States whose move along ``edge`` is allowed and lands in ``landed``; fields outside ``names`` stay absent."""
        steps, mask = program(edge)
        bits = landed
        for step in steps:
            if step[0] == 0:
                kept = bits & step[1]
                bits = kept
                for shift in step[2]:
                    bits |= kept << shift
            elif step[0] == 1:
                found = 0
                for part_mask, shifts in step[1]:
                    part = bits & part_mask
                    if part:
                        for shift in shifts:
                            found |= part << shift if shift >= 0 else part >> -shift
                bits = found
            else:
                kept = bits & step[1]
                bits = kept
                for other_mask, down, up, spreads in step[2]:
                    part = kept & other_mask
                    if part:
                        part = (part >> down) << up
                        bits |= part
                        for shift in spreads:
                            bits |= part << shift
            if not bits:
                return 0
        return bits & mask

    reachable = {schema_id}
    waiting = [schema_id]
    incoming: dict[str, list[Edge]] = {}
    while waiting:
        node = waiting.pop()
        if node == target:
            continue
        for edge in registry.edges_from.get(node, ()):
            incoming.setdefault(edge.target, []).append(edge)
            if edge.target not in reachable:
                reachable.add(edge.target)
                waiting.append(edge.target)

    def position_of(state: tuple[str, ...]) -> int:
        return sum(code_of[value] * weight for value, weight in zip(state, weights))

    # Least cost from schema_id to each schema, ignoring field states: a lower bound on the cost
    # already spent when a plan stands at that schema.
    spent = {schema_id: 0}
    frontier = [(0, schema_id)]
    while frontier:
        cost, node = heapq.heappop(frontier)
        if cost > spent[node] or node == target:
            continue
        for edge in registry.edges_from.get(node, ()):
            if cost + edge.cost < spent.get(edge.target, cost + edge.cost + 1):
                spent[edge.target] = cost + edge.cost
                heapq.heappush(frontier, (cost + edge.cost, edge.target))

    goal = position_of(start)
    unknown = dict.fromkeys([*spent, target], everything)
    levels: dict[str, list[tuple[int, int]]] = {}
    pending = {(0, target): everything}
    queue = [(spent.get(target, 0), 0, target)]
    best = None
    while queue and (best is None or queue[0][0] <= best):
        _, cost, node = heapq.heappop(queue)
        bits = pending.pop((cost, node)) & unknown[node]
        if not bits:
            continue
        unknown[node] ^= bits
        levels.setdefault(node, []).append((cost, bits))
        if node == schema_id and (bits >> goal) & 1:
            best = cost
        for edge in incoming.get(node, ()):
            found = before(edge, bits) & unknown[edge.source]
            if found:
                key = (cost + edge.cost, edge.source)
                if key in pending:
                    pending[key] |= found
                else:
                    pending[key] = found
                    heapq.heappush(queue, (cost + edge.cost + spent[edge.source], *key))

    def remaining(node: str, state: tuple[str, ...]) -> int | None:
        if node == target:
            return 0
        position = position_of(state)
        for cost, bits in levels.get(node, ()):
            if (bits >> position) & 1:
                return cost
        return None

    return remaining


def _only(edge: Edge, operation: tuple[str, ...]) -> Edge:
    return Edge(edge.edge_id, edge.source, edge.target, (), (operation,), edge.cost)
