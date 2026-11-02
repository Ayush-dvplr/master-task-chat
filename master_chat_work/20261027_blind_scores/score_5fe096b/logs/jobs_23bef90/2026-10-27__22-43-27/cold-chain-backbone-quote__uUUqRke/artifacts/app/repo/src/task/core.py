"""Quote of a project: the minimum-cost network joining the depot and its cold rooms.

A network is a set of open links that joins the depot (position 0) and every
cold room. Its quote is the cost of its links plus the activation charge of
every site it activates (the depot, the cold rooms and every end of one of its
links), each site charged once.  Finding the cheapest network is the
node-weighted Steiner tree problem.  Projects have few cold rooms, so it is
solved exactly with the Dreyfus-Wagner dynamic programme over subsets of the
cold rooms, rooted at the depot.

Tie rule.  Among the cheapest networks the contract picks the one whose 0/1
vector over the open links (ascending link id) is smaller at the first
position where the vectors differ.  That rule is folded into the weights:
every cost and charge is multiplied by ``2 ** m`` (``m`` open links) and the
link at index ``i`` of the id-sorted list adds ``2 ** (m - 1 - i)``.  The
scaled weight of a network is then ``quote * 2 ** m`` plus its vector read as
a binary number, so the scaled optimum is unique and is the contract's
minimum-cost network.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _scaled_weights(project: Project) -> tuple[list[int], list[int]]:
    """Node and link weights that encode the quote and the tie rule (see module doc)."""
    count = len(project.links)
    scale = 1 << count
    node_weight = [charge * scale for charge in project.charges]
    by_id = sorted(range(count), key=lambda index: project.links[index][0])
    tie_bit = [0] * count
    for rank, index in enumerate(by_id):
        tie_bit[index] = 1 << (count - 1 - rank)
    link_weight = [link[3] * scale + tie_bit[index] for index, link in enumerate(project.links)]
    return node_weight, link_weight


def _adjacency(project: Project) -> list[list[tuple[int, int]]]:
    """For each position, the (neighbour position, link index) pairs of its open links."""
    adjacent: list[list[tuple[int, int]]] = [[] for _ in project.ids]
    for index, (_lid, pa, pb, _cost) in enumerate(project.links):
        if pa != pb:  # a loop never joins anything
            adjacent[pa].append((pb, index))
            adjacent[pb].append((pa, index))
    return adjacent


def _steiner_links(project: Project) -> set[int]:
    """Indices of the links of the minimum-cost network (Dreyfus-Wagner).

    ``best[mask][v]`` is the smallest scaled weight of a tree that contains the
    cold rooms in ``mask`` and the site ``v``, counting every site of the tree
    once and every link once; ``how[mask][v]`` records how it was built.
    """
    terminals = sorted(project.cold)
    if not terminals:
        return set()
    node_weight, link_weight = _scaled_weights(project)
    adjacent = _adjacency(project)
    size = len(project.ids)
    full = (1 << len(terminals)) - 1
    best: list[list[float]] = [[]] * (full + 1)
    how: list[list[tuple | None]] = [[]] * (full + 1)

    for mask in range(1, full + 1):
        weight: list[float] = [math.inf] * size
        step: list[tuple | None] = [None] * size
        low = mask & -mask
        if mask == low:
            terminal = terminals[low.bit_length() - 1]
            weight[terminal] = node_weight[terminal]
            step[terminal] = ("leaf",)
        else:
            # Join two trees that share the site v; v was counted twice.
            # The part holding the lowest cold room is enumerated, so each split is seen once.
            rest = mask ^ low
            sub = (rest - 1) & rest
            while True:
                part = low | sub
                left, right = best[part], best[mask ^ part]
                for v in range(size):
                    joined = left[v] + right[v] - node_weight[v]
                    if joined < weight[v]:
                        weight[v] = joined
                        step[v] = ("join", part)
                if sub == 0:
                    break
                sub = (sub - 1) & rest
        # Grow every tree along open links (Dijkstra over the sites).
        heap = [(w, v) for v, w in enumerate(weight) if w != math.inf]
        heapq.heapify(heap)
        while heap:
            here_weight, here = heapq.heappop(heap)
            if here_weight > weight[here]:
                continue
            for there, index in adjacent[here]:
                grown = here_weight + link_weight[index] + node_weight[there]
                if grown < weight[there]:
                    weight[there] = grown
                    step[there] = ("link", here, index)
                    heapq.heappush(heap, (grown, there))
        best[mask], how[mask] = weight, step

    chosen: set[int] = set()
    pending = [(full, 0)]
    while pending:
        mask, v = pending.pop()
        move = how[mask][v]
        if move[0] == "join":
            pending.append((move[1], v))
            pending.append((mask ^ move[1], v))
        elif move[0] == "link":
            chosen.add(move[2])
            pending.append((mask, move[1]))
    return chosen


def best_network(project: Project) -> Network:
    """The project's minimum-cost network, its quote and the sites it activates."""
    chosen = tuple(sorted(project.links[index][0] for index in _steiner_links(project)))
    lines = site_lines(project, chosen)
    return Network(sum(lines.values()), chosen, tuple(sorted(project.ids[p] for p in lines)))


def site_lines(project: Project, links) -> dict[int, int]:
    """Line total per activated site position for the network made of ``links`` (link ids).

    Every activated site pays its activation charge once; each link is booked
    to its end with the larger corridor position.
    """
    chosen = set(links)
    activated = {0} | project.cold
    for lid, pa, pb, _cost in project.links:
        if lid in chosen:
            activated.update((pa, pb))
    lines = {p: project.charges[p] for p in activated}
    for lid, _pa, pb, cost in project.links:
        if lid in chosen:
            lines[pb] += cost  # links are stored with pa <= pb
    return lines


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
