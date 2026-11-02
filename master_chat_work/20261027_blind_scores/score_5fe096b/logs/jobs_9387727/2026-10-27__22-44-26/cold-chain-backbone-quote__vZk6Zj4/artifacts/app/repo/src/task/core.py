"""Minimum-cost backbone network of a project.

A network joins the depot and every cold room over open links.  Its quote is
the cost of its links plus the activation charge of every site it touches, so
the cheapest network is a node-weighted Steiner tree on the depot and the cold
rooms.  It is found exactly with the Dreyfus-Wagner subset recursion: for every
set of cold rooms and every site, the cheapest tree holding them all.

Ties between networks of equal quote go to the smaller link vector (open links
in ascending id order, 1 for a link in the network).  Every weight is scaled up
by 2**m (m open links) and link number i adds 2**(m - 1 - i), so the scaled
total of a network is its quote followed by its link vector read as a binary
number.  The cheapest scaled network is then unique and is the one the
contract asks for.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project

INFINITY = float("inf")


@dataclass(frozen=True)
class Network:
    """The minimum-cost network of a project."""

    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


@dataclass(frozen=True)
class _Graph:
    """Scaled site weights and, per site, its (neighbour, link index, weight)."""

    site_weight: list[int]
    adjacent: list[list[tuple[int, int, int]]]


def _scaled_graph(project: Project) -> _Graph:
    """Weights that rank networks by quote first and link vector second."""
    bits = len(project.links)
    site_weight = [charge << bits for charge in project.charges]
    adjacent: list[list[tuple[int, int, int]]] = [[] for _ in project.ids]
    for index, (_lid, end_a, end_b, cost) in enumerate(project.links):
        if end_a == end_b:
            continue
        weight = (cost << bits) + (1 << (bits - 1 - index))
        adjacent[end_a].append((end_b, index, weight))
        adjacent[end_b].append((end_a, index, weight))
    return _Graph(site_weight, adjacent)


def _grow(graph: _Graph, best: list, back: list) -> None:
    """Extend the trees of one cold-room set along links (Dijkstra)."""
    heap = [(value, site) for site, value in enumerate(best) if value != INFINITY]
    heapq.heapify(heap)
    while heap:
        value, here = heapq.heappop(heap)
        if value > best[here]:
            continue
        for there, index, weight in graph.adjacent[here]:
            candidate = value + weight + graph.site_weight[there]
            if candidate < best[there]:
                best[there] = candidate
                back[there] = ("link", here, index)
                heapq.heappush(heap, (candidate, there))


def _merge(graph: _Graph, table: dict, mask: int) -> tuple[list, list]:
    """Join two trees that cover complementary parts of `mask` at one site."""
    size = len(graph.site_weight)
    best: list = [INFINITY] * size
    back: list = [None] * size
    lowest = mask & -mask
    part = (mask - 1) & mask
    while part:
        if part & lowest:
            left, right = table[part], table[mask ^ part]
            for site in range(size):
                value = left[site] + right[site] - graph.site_weight[site]
                if value < best[site]:
                    best[site] = value
                    back[site] = ("split", part)
        part = (part - 1) & mask
    return best, back


def _steiner_tables(graph: _Graph, terminals: list[int]) -> tuple[dict, dict]:
    """Cheapest scaled tree for every set of terminals and every site."""
    size = len(graph.site_weight)
    table: dict[int, list] = {}
    backs: dict[int, list] = {}
    for mask in range(1, 1 << len(terminals)):
        if mask & (mask - 1):
            best, back = _merge(graph, table, mask)
        else:
            terminal = terminals[mask.bit_length() - 1]
            best = [INFINITY] * size
            back = [None] * size
            best[terminal] = graph.site_weight[terminal]
            back[terminal] = ("leaf",)
        _grow(graph, best, back)
        table[mask] = best
        backs[mask] = back
    return table, backs


def _tree_links(backs: dict, mask: int, root: int) -> set[int]:
    """Link indices of the tree recorded for (mask, root)."""
    chosen: set[int] = set()
    pending = [(mask, root)]
    while pending:
        mask, site = pending.pop()
        step = backs[mask][site]
        if step[0] == "link":
            chosen.add(step[2])
            pending.append((mask, step[1]))
        elif step[0] == "split":
            pending.append((step[1], site))
            pending.append((mask ^ step[1], site))
    return chosen


def best_network(project: Project) -> Network:
    """The minimum-cost network of an accepted project, ties broken by link vector."""
    depot = project.depot
    terminals = sorted(project.cold)
    chosen: set[int] = set()
    if terminals:
        graph = _scaled_graph(project)
        table, backs = _steiner_tables(graph, terminals)
        full = (1 << len(terminals)) - 1
        if table[full][depot] == INFINITY:
            raise ValueError(f"project {project.pid} has no network")
        chosen = _tree_links(backs, full, depot)
    links = tuple(project.links[index][0] for index in sorted(chosen))
    lines = site_lines(project, links)
    sites = tuple(sorted(project.ids[site] for site in lines))
    return Network(sum(lines.values()), links, sites)


def site_lines(project: Project, links) -> dict[int, int]:
    """Line total per activated site position.

    Each link is booked to its end with the larger corridor position; a line is
    the site's activation charge plus the links booked to it.
    """
    chosen = set(links)
    booked = {project.depot: 0}
    booked.update((site, 0) for site in project.cold)
    for lid, end_a, end_b, cost in project.links:
        if lid in chosen:
            booked.setdefault(end_a, 0)
            later = max(end_a, end_b)
            booked[later] = booked.get(later, 0) + cost
    return {site: project.charges[site] + booked[site] for site in sorted(booked)}


def quote_of(project: Project, links) -> int:
    """Quote of the network made of `links`."""
    return sum(site_lines(project, links).values())
