"""Minimum quote of a project: a sweep along the corridor positions.

Every non-depot link spans at most SPAN positions, so at position i only the
depot and the sites i-SPAN+1 .. i can still gain a link to a later site.  A
state records which of those frontier sites are active and which of them are
already joined to each other; the depot is always active and always slot 0.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser import SPAN, Project

WIDTH = SPAN  # frontier slots besides the depot


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _canon(labels) -> tuple[int, ...]:
    names: dict[int, int] = {}
    out = []
    for label in labels:
        if label == 0:
            out.append(0)
        else:
            out.append(names.setdefault(label, len(names) + 1))
    return tuple(out)


def _keep(layer, labels, cost, count, parent, chosen) -> None:
    """Drop the oldest frontier slot and store the state if that slot may leave."""
    leaving = labels[1]
    if leaving and leaving not in (labels[0],) + labels[2:]:
        return  # an active site would leave the frontier cut off from everything
    state = _canon((labels[0],) + labels[2:])
    current = layer.get(state)
    if current is None or cost < current[0]:
        layer[state] = (cost, count, parent, chosen)
    elif cost == current[0]:
        layer[state] = (cost, current[1] + count, current[2], current[3])


def sweep(project: Project, banned=frozenset()):
    """Return (quote, number of optimal networks, chosen link ids) or None."""
    back: dict[int, list[tuple[int, str, int]]] = {i: [] for i in range(1, project.size + 1)}
    for lid, pa, pb, cost in project.links:
        if lid not in banned:
            back[pb].append((pa, lid, cost))
    cold = project.cold
    start = (1,) + (0,) * WIDTH
    layers = [{start: (project.charges[0], 1, None, ())}]
    for i in range(1, project.size + 1):
        layer: dict = {}
        for state, (cost, count, _parent, _chosen) in layers[-1].items():
            if i not in cold:
                _keep(layer, state + (0,), cost, count, state, ())
            usable = []
            for pa, lid, link_cost in back[i]:
                slot = 0 if pa == 0 else pa - i + WIDTH + 1
                if state[slot]:
                    usable.append((slot, lid, link_cost))
            base = cost + project.charges[i]
            fresh = max(state) + 1
            for mask in range(1 << len(usable)):
                labels = list(state) + [fresh]
                extra = 0
                chosen = []
                for k, (slot, lid, link_cost) in enumerate(usable):
                    if not mask >> k & 1:
                        continue
                    old, new = labels[slot], labels[-1]
                    if old == new:
                        break  # closes a cycle
                    labels = [new if x == old else x for x in labels]
                    extra += link_cost
                    chosen.append(lid)
                else:
                    _keep(layer, tuple(labels), base + extra, count, state, tuple(chosen))
        layers.append(layer)
    best = None
    for state, (cost, count, _parent, _chosen) in layers[-1].items():
        if all(x in (0, state[0]) for x in state):
            if best is None or cost < best[0]:
                best = [cost, count, state]
            elif cost == best[0]:
                best[1] += count
    if best is None:
        return None
    links: list[str] = []
    state = best[2]
    for layer in reversed(layers[1:]):
        _cost, _count, parent, chosen = layer[state]
        links.extend(chosen)
        state = parent
    return best[0], best[1], tuple(sorted(links))


def best_network(project: Project) -> Network:
    """Minimum-quote network; among equal quotes the smaller link vector wins."""
    quote, count, links = sweep(project)
    banned: set[str] = set()
    if count > 1:
        for lid, _pa, _pb, _cost in sorted(project.links):
            if lid not in links:
                banned.add(lid)
                continue
            trial = sweep(project, frozenset(banned | {lid}))
            if trial is not None and trial[0] == quote:
                banned.add(lid)
                links = trial[2]
    return Network(quote, links, tuple(sorted(activated(project, links))))


def activated(project: Project, links) -> set[str]:
    chosen = set(links)
    active = {0} | project.cold
    for lid, pa, pb, _cost in project.links:
        if lid in chosen:
            active.update((pa, pb))
    return {project.ids[p] for p in active}


def site_lines(project: Project, links) -> dict[int, int]:
    """Total per activated position: its activation charge once, plus its booked links."""
    chosen = set(links)
    lines = {0: project.charges[0]}
    for p in project.cold:
        lines[p] = project.charges[p]
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            for p in (pa, pb):
                lines.setdefault(p, project.charges[p])
            lines[pb] += cost
    return lines


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
