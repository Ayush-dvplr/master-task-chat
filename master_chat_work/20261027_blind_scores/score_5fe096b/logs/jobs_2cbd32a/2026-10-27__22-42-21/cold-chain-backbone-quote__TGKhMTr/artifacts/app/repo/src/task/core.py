"""Minimum-cost backbone network of a project and its charging lines.

Finding the network is a node-weighted Steiner tree problem: join the depot
and every cold room using open links, paying each link's cost and the
activation charge of every site the links touch.  Because every cost and
charge is positive, a cheapest network never holds a cycle, so it is a tree.

The tie rule of the contract (smallest 0/1 vector over the open links in
ascending link id order) is folded into the weights: each link also carries
one binary digit, the first link in id order the most significant one.  The
digits of a network add up to its vector read as a binary number, and they
stay below one unit of quote, so the lightest network under these weights is
the cheapest network and, among the cheapest, the one with the smallest
vector.  The weighted optimum is unique, so the result is deterministic.

The exact optimum is found with the Dreyfus-Wagner dynamic programme over
subsets of the cold rooms, rooted at the depot.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project

DEPOT = 0  # corridor position of the depot


@dataclass(frozen=True)
class Network:
    """A project's minimum-cost network: its quote, link ids and activated site ids."""

    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


@dataclass
class _Table:
    """Best tree cost per site for one subset of cold rooms, and how it was built.

    `split[v]` is the subset joined at `v` (0 when the tree is the single
    cold room `v`), `step[v]` is `(previous site, link id)` when the tree was
    extended to `v` over a link, and None otherwise.
    """

    cost: list[int]
    split: list[int]
    step: list[tuple[int, str] | None]


def _weighted_graph(project: Project) -> tuple[list[int], list[list[tuple[int, str, int]]]]:
    """Site weights and adjacency lists with the tie-break digit added to each link."""
    count = len(project.links)
    unit = 1 << count  # one unit of quote; all tie-break digits together stay below it
    ranked = sorted(project.links)  # ascending link id
    site_weight = [charge * unit for charge in project.charges]
    adjacent: list[list[tuple[int, str, int]]] = [[] for _ in project.ids]
    for rank, (lid, pa, pb, cost) in enumerate(ranked):
        weight = cost * unit + (1 << (count - 1 - rank))
        adjacent[pa].append((pb, lid, weight))
        adjacent[pb].append((pa, lid, weight))
    return site_weight, adjacent


def _grow(table: _Table, adjacent, site_weight: list[int], unreachable: int) -> None:
    """Extend every tree of the table over links (Dijkstra seeded with all sites)."""
    cost = table.cost
    heap = [(c, v) for v, c in enumerate(cost) if c < unreachable]
    heapq.heapify(heap)
    while heap:
        here_cost, here = heapq.heappop(heap)
        if here_cost > cost[here]:
            continue
        for there, lid, weight in adjacent[here]:
            candidate = here_cost + weight + site_weight[there]
            if candidate < cost[there]:
                cost[there] = candidate
                table.split[there] = -1
                table.step[there] = (here, lid)
                heapq.heappush(heap, (candidate, there))


def _steiner_links(project: Project) -> set[str]:
    """Link ids of the unique lightest tree joining the depot and every cold room."""
    terminals = sorted(project.cold)
    if not terminals:
        return set()
    site_weight, adjacent = _weighted_graph(project)
    sites = len(project.ids)
    unreachable = (sum(site_weight) + sum(w for links in adjacent for _t, _l, w in links) + 1) * 2
    full = (1 << len(terminals)) - 1
    tables: list[_Table | None] = [None] * (full + 1)

    for index, terminal in enumerate(terminals):
        table = _Table([unreachable] * sites, [-1] * sites, [None] * sites)
        table.cost[terminal] = site_weight[terminal]
        table.split[terminal] = 0
        _grow(table, adjacent, site_weight, unreachable)
        tables[1 << index] = table

    for mask in range(1, full + 1):
        if tables[mask] is not None:
            continue
        lowest = mask & -mask
        cost = [unreachable] * sites
        split = [-1] * sites
        part = (mask - 1) & mask
        while part:
            if part & lowest:
                left, right = tables[part].cost, tables[mask ^ part].cost
                for v in range(sites):
                    candidate = left[v] + right[v] - site_weight[v]
                    if candidate < cost[v]:
                        cost[v] = candidate
                        split[v] = part
            part = (part - 1) & mask
        table = _Table(cost, split, [None] * sites)
        _grow(table, adjacent, site_weight, unreachable)
        tables[mask] = table

    chosen: set[str] = set()
    pending = [(full, DEPOT)]
    while pending:
        mask, site = pending.pop()
        table = tables[mask]
        if table.step[site] is not None:
            previous, lid = table.step[site]
            chosen.add(lid)
            pending.append((mask, previous))
        elif table.split[site] > 0:
            part = table.split[site]
            pending.append((part, site))
            pending.append((mask ^ part, site))
    return chosen


def activated_sites(project: Project, links) -> set[int]:
    """Positions of the depot, every cold room and every end of the given links."""
    chosen = set(links)
    active = {DEPOT} | project.cold
    for lid, pa, pb, _cost in project.links:
        if lid in chosen:
            active.update((pa, pb))
    return active


def site_lines(project: Project, links) -> dict[int, int]:
    """Line total per activated site position.

    Each site pays its activation charge once; each link is booked to its end
    with the larger corridor position.  The depot (position 0) pays only its
    activation charge.
    """
    chosen = set(links)
    lines = {p: project.charges[p] for p in activated_sites(project, chosen)}
    for lid, _pa, pb, cost in project.links:
        if lid in chosen:
            lines[pb] += cost
    return lines


def quote_of(project: Project, links) -> int:
    """Quote of a network: its link costs plus each activated site's charge once."""
    return sum(site_lines(project, links).values())


def best_network(project: Project) -> Network:
    """The minimum-cost network of an accepted project, ties broken by the contract."""
    chosen = tuple(sorted(_steiner_links(project)))
    active = activated_sites(project, chosen)
    return Network(
        quote=quote_of(project, chosen),
        links=chosen,
        sites=tuple(sorted(project.ids[p] for p in active)),
    )
