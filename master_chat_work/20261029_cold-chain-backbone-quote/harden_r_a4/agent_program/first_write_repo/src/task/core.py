"""Cheapest backbone network of a project and the charging lines it produces.

A network is a set of open links that joins the depot to every cold room.  It
activates the depot, every cold room and every site at an end of one of its
links, and its quote is the cost of its links plus one activation charge per
activated site.  The cheapest network is therefore a Steiner tree with charges
on the sites as well as costs on the links, and `best_network` finds it exactly
with the Dreyfus-Wagner subset dynamic program, whose states are a set of cold
rooms and a site that joins them.

Ties are broken on the incidence vector of the network over the project's open
links in ascending link id order: of two vectors, the one holding 0 where the
other holds 1, at the first position where they differ, wins.  Both aims
travel in one integer search key, `quote * scale + vector`, with `scale` wide
enough to keep the two parts apart.  Comparing keys then compares quotes
first and vectors second, and adding two keys adds both parts at once.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    """The quote of a network, its link ids and the site ids it activates."""

    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def activated(project: Project, links) -> set[int]:
    """Positions a network switches on: the depot, the cold rooms, the link ends."""
    chosen = set(links)
    sites = {0} | project.cold
    for lid, pa, pb, _cost in project.links:
        if lid in chosen:
            sites.update((pa, pb))
    return sites


def site_lines(project: Project, links) -> dict[int, int]:
    """Line total of every position a network activates.

    A line holds the activation charge of its site plus the cost of the links
    booked to it, a link being booked to its end with the larger corridor
    position.  The depot sits at position 0, so its line holds its charge
    alone.
    """
    chosen = set(links)
    lines = {position: project.charges[position] for position in activated(project, chosen)}
    for lid, _pa, pb, cost in project.links:
        if lid in chosen:
            lines[pb] += cost
    return lines


def quote_of(project: Project, links) -> int:
    """Quote of a network: its link costs plus one charge per activated site."""
    return sum(site_lines(project, links).values())


def best_network(project: Project) -> Network:
    """The minimum-cost network of an accepted project, ties broken on link order."""
    cold = sorted(project.cold)
    if not cold:
        return _network(project, ())
    scale = _scale(project)
    charges = [charge * scale for charge in project.charges]
    adjacent = _adjacency(project, _link_keys(project, scale))
    vector = _cheapest_key(project, cold, charges, adjacent) % scale
    last = len(project.links) - 1
    chosen = tuple(
        lid for index, (lid, _pa, _pb, _cost) in enumerate(project.links)
        if vector >> (last - index) & 1
    )
    return _network(project, chosen)


def _network(project: Project, links) -> Network:
    """Bundle the link ids of a network with its quote and its activated sites."""
    sites = sorted(project.ids[position] for position in activated(project, links))
    return Network(quote_of(project, links), tuple(links), tuple(sites))


def _scale(project: Project) -> int:
    """Width of the vector part of a search key.

    A search key adds the vector of any one link at most once per site of the
    project, so this bound keeps the vector part clear of the quote part.
    """
    return 1 << (len(project.links) + len(project.ids).bit_length())


def _link_keys(project: Project, scale: int) -> list[int]:
    """Search key of every open link, in the order of `project.links`."""
    last = len(project.links) - 1
    return [
        cost * scale + (1 << (last - index))
        for index, (_lid, _pa, _pb, cost) in enumerate(project.links)
    ]


def _adjacency(project: Project, keys) -> list[list[tuple[int, int]]]:
    """For every position, the (neighbour, link key) pairs of its open links."""
    adjacent: list[list[tuple[int, int]]] = [[] for _ in project.ids]
    for (_lid, pa, pb, _cost), key in zip(project.links, keys):
        adjacent[pa].append((pb, key))
        adjacent[pb].append((pa, key))
    return adjacent


def _cheapest_key(project: Project, cold, charges, adjacent) -> int:
    """Search key of the cheapest network joining the depot to the cold rooms.

    `table[mask][position]` holds the key of the cheapest tree over the cold
    rooms picked out by `mask` and the site at `position`; the answer is the
    entry of the whole set of cold rooms at the depot.
    """
    full = (1 << len(cold)) - 1
    table: list[list[int | None]] = [[None] * len(project.ids) for _ in range(full + 1)]
    for index, position in enumerate(cold):
        table[1 << index][position] = charges[position]
    for mask in range(1, full + 1):
        row = table[mask]
        lowest = mask & -mask
        part = (mask - 1) & mask
        while part:
            if part & lowest:
                _join(row, table[part], table[mask ^ part], charges)
            part = (part - 1) & mask
        _grow(row, adjacent, charges)
    return table[full][0]


def _join(row, left, right, charges) -> None:
    """Join, at each position, a tree over one set of cold rooms with one over the rest.

    The position carries its charge in both trees, so one of the two is given
    back.
    """
    for position, charge in enumerate(charges):
        here, there = left[position], right[position]
        if here is None or there is None:
            continue
        joined = here + there - charge
        if row[position] is None or joined < row[position]:
            row[position] = joined


def _grow(row, adjacent, charges) -> None:
    """Extend the trees of one set of cold rooms along single links, cheapest key first."""
    heap = [(key, position) for position, key in enumerate(row) if key is not None]
    heapq.heapify(heap)
    while heap:
        key, here = heapq.heappop(heap)
        if key > row[here]:
            continue
        for there, link_key in adjacent[here]:
            candidate = key + link_key + charges[there]
            if row[there] is None or candidate < row[there]:
                row[there] = candidate
                heapq.heappush(heap, (candidate, there))
