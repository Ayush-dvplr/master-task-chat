"""Quote of a project: the cheapest network joining the depot and the cold rooms.

A network pays for its links and for the activation of every site it touches,
so the cheapest network is a node-weighted Steiner tree over the depot and the
cold rooms.  `best_network` finds it exactly with the Dreyfus-Wagner subset
dynamic programme: `_subset_tables` fills `costs[mask][site]`, the cheapest
tree holding `site` and the terminals of `mask`, by merging two cheaper trees
at `site` and then spreading the result over the graph with Dijkstra.

The contract breaks a tie between two cheapest networks on the indicator
vector of the network over the project's open links in ascending link id
order, the smaller vector winning at the first position where the two differ.
`_Ranked` therefore weighs every link and charge as `cost * scale + tie`,
where `scale` is two to the power of the number of open links and `tie` is the
bit of the link's place in that order.  Comparing two such weights compares
quotes first and indicator vectors second, so one run of the dynamic
programme settles both the quote and the tie.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project

# Above any ranked cost, yet small enough that sums of it stay cheap to add.
_UNREACHABLE = 1 << 256


@dataclass(frozen=True)
class Network:
    """A project's minimum-cost network: its quote, its links, its sites."""

    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


class _Ranked:
    """The project's graph with ranked weights (see the module docstring)."""

    def __init__(self, project: Project) -> None:
        self.size = project.size + 1
        self.scale = 1 << len(project.links)
        self.charges = [charge * self.scale for charge in project.charges]
        self.adjacent: list[list[tuple[int, int, str]]] = [[] for _ in range(self.size)]
        last = len(project.links) - 1
        for rank, (lid, pa, pb, cost) in enumerate(project.links):
            weight = cost * self.scale + (1 << (last - rank))
            self.adjacent[pa].append((pb, weight, lid))
            self.adjacent[pb].append((pa, weight, lid))


def _spread(graph: _Ranked, values: list[int]) -> list[tuple[int, str] | None]:
    """Relax `values` over the graph, charging every site a path reaches anew.

    Updates `values` in place and returns the predecessor of every site it
    improved, as a (site, link id) pair.
    """
    charges = graph.charges
    adjacent = graph.adjacent
    previous: list[tuple[int, str] | None] = [None] * graph.size
    heap = [(value, site) for site, value in enumerate(values) if value < _UNREACHABLE]
    heapq.heapify(heap)
    while heap:
        cost, here = heapq.heappop(heap)
        if cost > values[here]:
            continue
        for there, weight, lid in adjacent[here]:
            candidate = cost + weight + charges[there]
            if candidate < values[there]:
                values[there] = candidate
                previous[there] = (here, lid)
                heapq.heappush(heap, (candidate, there))
    return previous


def _splits(mask: int):
    """Yield the pairs of halves of `mask`, each unordered pair once."""
    low = mask & -mask
    rest = mask ^ low
    if not rest:
        return
    sub = (rest - 1) & rest
    while True:
        yield sub | low, rest ^ sub
        if not sub:
            return
        sub = (sub - 1) & rest


def _subset_tables(graph: _Ranked, terminals: list[int]):
    """Fill the Dreyfus-Wagner tables of costs and of Dijkstra predecessors.

    Masks run over the subsets of `terminals`; a proper submask is a smaller
    number than its mask, so one ascending pass fills the tables in order.
    """
    charges = graph.charges
    costs: dict[int, list[int]] = {}
    previous: dict[int, list[tuple[int, str] | None]] = {}
    for mask in range(1, 1 << len(terminals)):
        values = [_UNREACHABLE] * graph.size
        if mask & (mask - 1):
            for left, right in _splits(mask):
                # A tree branching at a site splits there into two cheaper
                # trees sharing that site, whose charge is then paid twice.
                lefts, rights = costs[left], costs[right]
                values = [
                    value if value <= l + r - charge else l + r - charge
                    for value, l, r, charge in zip(values, lefts, rights, charges)
                ]
        else:
            terminal = terminals[mask.bit_length() - 1]
            values[terminal] = charges[terminal]
        previous[mask] = _spread(graph, values)
        costs[mask] = values
    return costs, previous


def _links_of(graph: _Ranked, costs, previous, mask: int, site: int) -> set[str]:
    """The link ids of the tree whose cost is `costs[mask][site]`."""
    chosen: set[str] = set()
    pending = [(mask, site)]
    while pending:
        mask, site = pending.pop()
        step = previous[mask][site]
        while step is not None:
            site, lid = step
            chosen.add(lid)
            step = previous[mask][site]
        # The two halves merged at this site each paid its charge.
        target = costs[mask][site] + graph.charges[site]
        for left, right in _splits(mask):
            if costs[left][site] + costs[right][site] == target:
                pending.append((left, site))
                pending.append((right, site))
                break
    return chosen


def best_network(project: Project) -> Network:
    """The project's minimum-cost network under the contract's tie rule."""
    terminals = sorted({0} | project.cold)
    if len(terminals) == 1:
        return Network(project.charges[0], (), (project.ids[0],))
    graph = _Ranked(project)
    costs, previous = _subset_tables(graph, terminals)
    whole = (1 << len(terminals)) - 1
    root = min(range(graph.size), key=lambda site: costs[whole][site])
    chosen = _links_of(graph, costs, previous, whole, root)
    lines = site_lines(project, chosen)
    return Network(
        sum(lines.values()),
        tuple(lid for lid, _pa, _pb, _cost in project.links if lid in chosen),
        tuple(sorted(project.ids[p] for p in lines)),
    )


def site_lines(project: Project, links) -> dict[int, int]:
    """One line total per site the network activates, keyed by corridor position.

    A line is the site's activation charge plus the cost of every link booked
    to it, a link being booked to its end with the larger corridor position.
    """
    chosen = set(links)
    lines = {0: project.charges[0]}
    for position in project.cold:
        lines[position] = project.charges[position]
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            for position in (pa, pb):
                if position not in lines:
                    lines[position] = project.charges[position]
            lines[pb] += cost
    return lines


def quote_of(project: Project, links) -> int:
    """The quote of one network of the project."""
    return sum(site_lines(project, links).values())
