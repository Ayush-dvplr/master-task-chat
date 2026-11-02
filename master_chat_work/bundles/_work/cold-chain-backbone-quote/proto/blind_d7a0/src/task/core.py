"""Quote of a project: the exact minimum node-weighted Steiner network.

Sites are swept in corridor-position order.  Because every non-depot link
spans at most four positions, only a small frontier of sites is ever open at
once; a connectivity DP over that frontier finds the optimum exactly.  The
weight of a link set is ``quote << m`` plus a bit per chosen link (the link
with the smallest id is the highest bit), so minimising the weight applies the
tie rule of the contract at the same time.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _normalise(labels: list[int]) -> tuple[int, ...]:
    """Relabel components by first appearance; 0 stays 'inactive'."""
    mapping: dict[int, int] = {}
    out = []
    for label in labels:
        if label == 0:
            out.append(0)
        else:
            if label not in mapping:
                mapping[label] = len(mapping) + 1
            out.append(mapping[label])
    return tuple(out)


def _optimum(project: Project) -> tuple[int, list[str], int]:
    n = len(project.ids)
    order = sorted(lid for lid, _pa, _pb, _cost in project.links)
    m = len(order)
    bit = {lid: 1 << (m - 1 - i) for i, lid in enumerate(order)}
    terminals = {0} | project.cold
    incoming: dict[int, list[tuple[int, int]]] = {v: [] for v in range(n)}
    last = list(range(n))
    for lid, pa, pb, cost in project.links:
        if pa == pb:
            continue
        incoming[pb].append((pa, (cost << m) | bit[lid]))
        last[pa] = max(last[pa], pb)
    frontier: list[int] = []
    states: dict[tuple[int, ...], int] = {(): 0}
    for v in range(n):
        # introduce v, active or not
        charge = project.charges[v] << m
        grown: dict[tuple[int, ...], int] = {}
        for labels, weight in states.items():
            options = [True] if v in terminals else [False, True]
            for active in options:
                new = labels + ((max(labels, default=0) + 1,) if active else (0,))
                value = weight + charge if active else weight
                if value < grown.get(new, value + 1):
                    grown[new] = value
        frontier.append(v)
        states = grown
        slot_v = len(frontier) - 1
        for u, weight_uv in incoming[v]:
            slot_u = frontier.index(u)
            nxt: dict[tuple[int, ...], int] = {}
            for labels, weight in states.items():
                if weight < nxt.get(labels, weight + 1):
                    nxt[labels] = weight
                lu, lv = labels[slot_u], labels[slot_v]
                if lu and lv and lu != lv:
                    merged = _normalise([lv if x == lu else x for x in labels])
                    value = weight + weight_uv
                    if value < nxt.get(merged, value + 1):
                        nxt[merged] = value
            states = nxt
        # forget sites with no links left to later sites (never the depot)
        for w in [x for x in frontier if x != 0 and last[x] <= v]:
            slot_w = frontier.index(w)
            nxt = {}
            for labels, weight in states.items():
                label = labels[slot_w]
                if label and labels.count(label) == 1:
                    continue  # its component could never reach the depot
                key = _normalise(list(labels[:slot_w] + labels[slot_w + 1:]))
                if weight < nxt.get(key, weight + 1):
                    nxt[key] = weight
            frontier.pop(slot_w)
            states = nxt
    best = None
    for labels, weight in states.items():
        if len({x for x in labels if x}) == 1 and (best is None or weight < best):
            best = weight
    if best is None:
        raise ValueError(f"no network for {project.pid}")
    return best, order, m


def best_network(project: Project) -> Network:
    weight, order, m = _optimum(project)
    mask = weight & ((1 << m) - 1)
    chosen = tuple(lid for i, lid in enumerate(order) if mask >> (m - 1 - i) & 1)
    lines = site_lines(project, chosen)
    quote = sum(lines.values())
    assert quote == weight >> m
    return Network(quote, chosen, tuple(sorted(project.ids[p] for p in lines)))


def site_lines(project: Project, links) -> dict[int, int]:
    """Line total per activated site: its charge plus the links booked to it.

    Each link is booked to its end with the larger corridor position.
    """
    chosen = set(links)
    active = {0} | project.cold
    booked: dict[int, int] = {}
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            active.update((pa, pb))
            booked[pb] = booked.get(pb, 0) + cost
    return {p: project.charges[p] + booked.get(p, 0) for p in sorted(active)}


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
