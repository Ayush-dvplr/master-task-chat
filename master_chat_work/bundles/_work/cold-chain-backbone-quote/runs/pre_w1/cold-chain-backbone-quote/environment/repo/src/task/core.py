"""Quote of a project: join the depot and the cold rooms by their cheapest paths."""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _adjacency(project: Project) -> dict[int, list[tuple[int, str, int]]]:
    adjacent: dict[int, list[tuple[int, str, int]]] = {p: [] for p in range(project.size + 1)}
    for lid, pa, pb, cost in project.links:
        adjacent[pa].append((pb, lid, cost))
        adjacent[pb].append((pa, lid, cost))
    return adjacent


def _paths_from(project: Project, adjacent, source: int):
    """Cheapest path from source to every site, paying link costs and entry charges."""
    distance = {source: 0}
    previous: dict[int, tuple[int, str] | None] = {source: None}
    heap = [(0, source)]
    while heap:
        here_cost, here = heapq.heappop(heap)
        if here_cost > distance[here]:
            continue
        for there, lid, cost in adjacent[here]:
            candidate = here_cost + cost + project.charges[there]
            if candidate < distance.get(there, candidate + 1):
                distance[there] = candidate
                previous[there] = (here, lid)
                heapq.heappush(heap, (candidate, there))
    return distance, previous


def _root(parent: dict[int, int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _spanning_links(project: Project, sites: set[int]) -> list[tuple[str, int, int, int]]:
    parent = {p: p for p in sites}
    kept = []
    for lid, pa, pb, cost in sorted(project.links, key=lambda link: (link[3], link[0])):
        if pa in sites and pb in sites:
            ra, rb = _root(parent, pa), _root(parent, pb)
            if ra != rb:
                parent[ra] = rb
                kept.append((lid, pa, pb, cost))
    return kept


def _trim(project: Project, links):
    required = {0} | project.cold
    links = list(links)
    while True:
        degree: dict[int, int] = {}
        for _lid, pa, pb, _cost in links:
            degree[pa] = degree.get(pa, 0) + 1
            degree[pb] = degree.get(pb, 0) + 1
        loose = [link for link in links if any(degree[p] == 1 and p not in required for p in link[1:3])]
        if not loose:
            return links
        links.remove(loose[0])


def best_network(project: Project) -> Network:
    terminals = sorted({0} | project.cold)
    adjacent = _adjacency(project)
    paths = {t: _paths_from(project, adjacent, t) for t in terminals}
    pairs = sorted(
        (paths[a][0][b], a, b) for i, a in enumerate(terminals) for b in terminals[i + 1:]
    )
    parent = {t: t for t in terminals}
    sites = set(terminals)
    for _distance, a, b in pairs:
        ra, rb = _root(parent, a), _root(parent, b)
        if ra == rb:
            continue
        parent[ra] = rb
        step = paths[a][1][b]
        while step is not None:
            sites.add(step[0])
            step = paths[a][1][step[0]]
    links = _trim(project, _spanning_links(project, sites))
    chosen = tuple(sorted(link[0] for link in links))
    active = {0} | project.cold
    for _lid, pa, pb, _cost in links:
        active.update((pa, pb))
    return Network(quote_of(project, chosen), chosen, tuple(sorted(project.ids[p] for p in active)))


def site_lines(project: Project, links) -> dict[int, int]:
    """Total per site: each link booked to its later end, with that end's charge."""
    chosen = set(links)
    lines = {0: project.charges[0]}
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            lines[pb] = lines.get(pb, 0) + cost + project.charges[pb]
    return lines


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
