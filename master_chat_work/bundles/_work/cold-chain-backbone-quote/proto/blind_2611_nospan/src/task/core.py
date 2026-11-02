"""Quote of a project: the exact minimum-cost network joining the depot and the cold rooms.

Open links between two non-depot sites never join positions more than a few
apart, so the sites are swept in position order while a small frontier (the
depot plus the most recent sites) is kept with its connectivity.  Each state
value is ``quote << m | vector`` where ``vector`` is the network's link vector
read as a binary number (ascending link id order, first link most
significant); minimising it gives the smallest quote and, among equal quotes,
the network whose vector is smaller at the first difference.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _canon(key: tuple[int, ...]) -> tuple[int, ...]:
    relabel: dict[int, int] = {}
    out = []
    for label in key:
        if label == 0:
            out.append(0)
        else:
            if label not in relabel:
                relabel[label] = len(relabel) + 1
            out.append(relabel[label])
    return tuple(out)


def _keep(states: dict, key: tuple[int, ...], value: int) -> None:
    old = states.get(key)
    if old is None or value < old:
        states[key] = value


def best_network(project: Project) -> Network:
    count = len(project.ids)
    cold = project.cold
    order = sorted(lid for lid, _pa, _pb, _cost in project.links)
    shift = len(order)
    bit = {lid: 1 << (shift - 1 - r) for r, lid in enumerate(order)}
    incoming: dict[int, list[tuple[int, int]]] = {v: [] for v in range(count)}
    width = 1
    for lid, pa, pb, cost in project.links:
        if pa == pb:
            continue
        incoming[pb].append((pa, (cost << shift) | bit[lid]))
        if pa != 0:
            width = max(width, pb - pa)

    def forget(states: dict) -> dict:
        kept: dict = {}
        for key, value in states.items():
            label = key[1]
            if label != 0 and label != key[0] and label not in key[2:]:
                continue
            _keep(kept, _canon(key[:1] + key[2:]), value)
        return kept

    front: list[int] = []
    states: dict[tuple[int, ...], int] = {(1,): project.charges[0] << shift}
    for v in range(1, count):
        grown: dict = {}
        for key, value in states.items():
            if v not in cold:
                _keep(grown, key + (0,), value)
            _keep(grown, key + (max(key) + 1,), value + (project.charges[v] << shift))
        states = grown
        front.append(v)
        iv = len(front)
        for u, weight in incoming[v]:
            iu = 0 if u == 0 else 1 + front.index(u)
            joined = dict(states)
            for key, value in states.items():
                a, b = key[iu], key[iv]
                if a and b and a != b:
                    merged = _canon(tuple(a if label == b else label for label in key))
                    _keep(joined, merged, value + weight)
            states = joined
        while front and front[0] <= v - width:
            states = forget(states)
            front.pop(0)
    while front:
        states = forget(states)
        front.pop(0)
    value = states[(1,)]
    vector = value & ((1 << shift) - 1)
    chosen = tuple(lid for lid in order if vector & bit[lid])
    active = {0} | cold
    picked = set(chosen)
    for lid, pa, pb, _cost in project.links:
        if lid in picked:
            active.update((pa, pb))
    return Network(quote_of(project, chosen), chosen, tuple(sorted(project.ids[p] for p in active)))


def site_lines(project: Project, links) -> dict[int, int]:
    """Line total per activated site: its charge plus the links booked to its later end."""
    chosen = set(links)
    lines = {0: project.charges[0]}
    for p in project.cold:
        lines[p] = project.charges[p]
    for _lid, pa, pb, _cost in project.links:
        if _lid in chosen:
            for p in (pa, pb):
                if p not in lines:
                    lines[p] = project.charges[p]
    for lid, _pa, pb, cost in project.links:
        if lid in chosen:
            lines[pb] += cost
    return lines


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
