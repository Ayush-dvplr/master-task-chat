"""Quote of a project: its cheapest network joining the depot and every cold room."""
from __future__ import annotations

from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _canonical(labels) -> tuple[int, ...]:
    """Name the parts of the frontier by first appearance; 0 is a site left out."""
    seen: dict[int, int] = {}
    return tuple(seen.setdefault(label, len(seen) + 1) if label else 0 for label in labels)


def _cheapest(project: Project) -> int:
    """The cheapest `quote * unit + vector` of a network of the project.

    A network is scored as its quote times `unit` plus its vector over the open
    links in ascending link id order, so the cheapest score carries the smallest
    quote and, among the networks of that quote, the smallest vector: the tie
    rule of the contract.  The sites are taken in corridor position order while
    the state keeps, for the frontier -- the depot and the sites a link of a
    later site can still reach -- which sites are in the network and which of
    them are joined to each other so far.  A span of at most 4 holds the
    frontier to five sites.
    """
    links = project.links
    count = len(links)
    unit = 1 << count
    terminals = {0} | project.cold
    weight = [cost * unit + (1 << (count - 1 - i)) for i, (_lid, _pa, _pb, cost) in enumerate(links)]
    charge = [c * unit for c in project.charges]
    arriving: dict[int, list[tuple[int, int]]] = {}
    last_use: dict[int, int] = {}
    for i, (_lid, pa, pb, _cost) in enumerate(links):
        arriving.setdefault(pb, []).append((i, pa))
        last_use[pa] = max(last_use.get(pa, pa), pb)
    frontier = [0]
    states = {(1,): charge[0]}
    for site in range(1, len(project.ids)):
        candidates = arriving.get(site, [])
        bag = frontier + [site]
        keep = [p for p in bag if p == 0 or last_use.get(p, p) > site]
        gone = [p for p in bag if p != 0 and last_use.get(p, p) <= site]
        following: dict[tuple[int, ...], int] = {}
        for key, base in states.items():
            start = dict(zip(frontier, key))
            fresh = max(key) + 1
            for pick in range(1 << len(candidates)):
                taken = [candidates[k] for k in range(len(candidates)) if pick >> k & 1]
                marks = dict(start)
                total = base
                name = fresh
                if taken or site in terminals:
                    marks[site] = name
                    total += charge[site]
                    name += 1
                else:
                    marks[site] = 0
                dead = False
                for i, pa in taken:
                    total += weight[i]
                    if not marks[pa]:
                        marks[pa] = name
                        total += charge[pa]
                        name += 1
                    old, new = marks[pa], marks[site]
                    if old == new:
                        dead = True  # a cycle is never cheapest and never the smallest vector
                        break
                    for p, label in marks.items():
                        if label == old:
                            marks[p] = new
                if dead:
                    continue
                for p in gone:
                    label = marks[p]
                    if not label:
                        if p in terminals:
                            dead = True
                            break
                    elif not any(marks[q] == label for q in keep):
                        dead = True  # that part of the network can no longer reach the depot
                        break
                if dead:
                    continue
                reached = _canonical([marks[p] for p in keep])
                if following.get(reached, total + 1) > total:
                    following[reached] = total
        states = following
        frontier = keep
    return states[(1,)]


def best_network(project: Project) -> Network:
    """The minimum-cost network of an accepted project."""
    count = len(project.links)
    quote, vector = divmod(_cheapest(project), 1 << count)
    picked = [i for i in range(count) if vector >> (count - 1 - i) & 1]
    chosen = tuple(project.links[i][0] for i in picked)
    active = {0} | project.cold
    for i in picked:
        active.update(project.links[i][1:3])
    return Network(quote, chosen, tuple(sorted(project.ids[p] for p in active)))


def site_lines(project: Project, links) -> dict[int, int]:
    """Total per activated site: its charge once, with each link booked to its later end."""
    chosen = set(links)
    lines = {p: project.charges[p] for p in {0} | project.cold}
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            lines.setdefault(pa, project.charges[pa])
            lines[pb] = lines.setdefault(pb, project.charges[pb]) + cost
    return lines


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
