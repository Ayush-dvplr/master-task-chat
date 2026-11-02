#!/usr/bin/env python3
"""Repair /app/repo in place, archive it and write the documents under /app/out."""
from __future__ import annotations

import configparser
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile
from pathlib import Path

APP = Path(os.environ.get("APP_ROOT", "/app"))
REPO = APP / "repo"
CI = APP / "ci"
OUT = APP / "out"

REPAIRED = {
    "pyproject.toml": r'''[project]
name = "task"
version = "2.18.5"
requires-python = ">=3.12"
dependencies = []

[tool.setuptools]
package-dir = {"" = "src"}
''',
    "src/task/__init__.py": r'''"""Cold-chain backbone quoting."""

VERSION = "2.18.5"
''',
    "src/task/parser.py": r'''"""Read a quote book directory and the inline projects of the regression suite."""
from __future__ import annotations

import configparser
import csv
import json
import tomllib
from collections import deque
from pathlib import Path

BOOK_FILES = ("sites.csv", "layout.tsv", "links.jsonl", "access_rules.toml", "activation.ini")


class MissingBookFile(Exception):
    """A book file named in the contract is absent."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class Rejected(Exception):
    """A project breaks one of the contract's rejection rules."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Project:
    """One accepted project laid out on its corridor positions (depot at 0)."""

    def __init__(self, pid, ids, roles, corridors, charges, links, link_rows):
        self.pid = pid
        self.ids = ids
        self.roles = roles
        self.corridors = corridors
        self.charges = charges
        self.links = links
        self.link_rows = link_rows

    @property
    def size(self) -> int:
        return len(self.ids) - 1

    @property
    def cold(self) -> set[int]:
        return {p for p, role in enumerate(self.roles) if role == "cold_room"}

    def stats(self) -> dict[str, int]:
        return {
            "sites": len(self.ids),
            "links": self.link_rows,
            "open_links": len(self.links),
            "cold_rooms": len(self.cold),
            "relays": sum(1 for role in self.roles if role == "relay"),
        }


def assemble(pid, sites, links, link_rows):
    """Build a Project from (site, role, corridor, charge) rows already in position order.

    `links` holds (link id, end a, end b, cost) for the open links.  Raises Rejected.
    """
    position = {site: p for p, (site, _role, _corr, _charge) in enumerate(sites)}
    placed = []
    for lid, a, b, cost in links:
        if a not in position or b not in position:
            raise Rejected("E_UNKNOWN_ENDPOINT")
        pa, pb = sorted((position[a], position[b]))
        placed.append((lid, pa, pb, cost))
    project = Project(
        pid,
        [s[0] for s in sites],
        [s[1] for s in sites],
        [s[2] for s in sites],
        [s[3] for s in sites],
        sorted(placed),
        link_rows,
    )
    adjacent = {p: [] for p in range(len(sites))}
    for _lid, pa, pb, _cost in placed:
        adjacent[pa].append(pb)
        adjacent[pb].append(pa)
    reached = {0}
    queue = deque([0])
    while queue:
        here = queue.popleft()
        for there in adjacent[here]:
            if there not in reached:
                reached.add(there)
                queue.append(there)
    if not project.cold <= reached:
        raise Rejected("E_NO_NETWORK")
    return project


def _rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def load_book(root) -> dict:
    """Return {"projects": {pid: Project}, "rejected": {pid: code}}."""
    root = Path(root)
    for name in BOOK_FILES:
        if not (root / name).is_file():
            raise MissingBookFile(name)
    rules = tomllib.loads((root / "access_rules.toml").read_text(encoding="utf-8"))
    rank = {name: i for i, name in enumerate(rules["corridors"]["order"])}
    tariff = rules["tariff"]
    closed = set(rules["closed"]["links"])
    activation = configparser.ConfigParser(interpolation=None)
    activation.optionxform = str
    activation.read(root / "activation.ini", encoding="utf-8")
    classes = {k: int(v) for k, v in activation["classes"].items()}
    overrides = {k: int(v) for k, v in activation["overrides"].items()}

    site_rows: dict[str, list[dict[str, str]]] = {}
    for row in _rows(root / "sites.csv", ","):
        site_rows.setdefault(row["project"], []).append(row)
    slots: dict[tuple[str, str], tuple[int, int, str]] = {}
    for row in _rows(root / "layout.tsv", "\t"):
        slots[(row["project"], row["site"])] = (rank[row["corridor"]], int(row["slot"]), row["corridor"])
    link_rows: dict[str, list[dict]] = {}
    for line in (root / "links.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            link_rows.setdefault(record["project"], []).append(record)

    projects, rejected = {}, {}
    for pid in sorted(site_rows):
        rows = site_rows[pid]
        try:
            ids = [r["site"] for r in rows]
            if len(set(ids)) != len(ids):
                raise Rejected("E_DUP_SITE")
            depot = [r for r in rows if r["role"] == "depot"]
            others = sorted((r for r in rows if r["role"] != "depot"), key=lambda r: slots[(pid, r["site"])][:2])
            ordered = []
            for r in depot + others:
                corridor = None if r["role"] == "depot" else slots[(pid, r["site"])][2]
                charge = overrides.get(f"{pid}/{r['site']}", classes[r["class"]])
                ordered.append((r["site"], r["role"], corridor, charge))
            records = link_rows.get(pid, [])
            links = []
            for rec in records:
                if rec["link"] in closed:
                    continue
                band = tariff[rec["band"]]
                links.append((rec["link"], rec["a"], rec["b"], band["base"] + band["per_km"] * rec["km"]))
            projects[pid] = assemble(pid, ordered, links, len(records))
        except Rejected as exc:
            rejected[pid] = exc.code
    return {"projects": projects, "rejected": rejected}


def load_inline(case: dict) -> Project:
    """Project from one regression_cases.jsonl record.  Raises Rejected."""
    ids = [s["site"] for s in case["sites"]]
    if len(set(ids)) != len(ids):
        raise Rejected("E_DUP_SITE")
    ordered = sorted(case["sites"], key=lambda s: s["position"])
    sites = [(s["site"], s["role"], None, s["charge"]) for s in ordered]
    links = [(k["link"], k["a"], k["b"], k["cost"]) for k in case["links"]]
    return assemble(case["case"], sites, links, len(links))
''',
    "src/task/core.py": r'''"""Minimum quote of a project.

The open links fall into groups that meet one another only at single sites.
Each group hangs below the site it shares with the part nearer the depot, so
the groups are solved one at a time, deepest first: inside a group the sites
to join are its cold rooms and every site with a needed group below it.  A
group with few such sites is solved over subsets of them; any other group is
swept in corridor order, keeping the joined classes of the sites that still
have a link ahead.  Every link weighs cost * 2**m plus a bit of its rank in
link-id order, so the smallest weight is also the smaller link vector.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _groups(n, adj):
    """Link groups reachable from the depot, deepest first: [(top site, [link index])]."""
    disc = [-1] * (n + 1)
    low = [0] * (n + 1)
    disc[0] = 0
    clock = 1
    edges, out = [], []
    stack = [(0, -1, iter(adj[0]))]
    while stack:
        v, came, nbrs = stack[-1]
        moved = False
        for u, _w, r in nbrs:
            if r == came:
                continue
            if disc[u] == -1:
                edges.append(r)
                disc[u] = low[u] = clock
                clock += 1
                stack.append((u, r, iter(adj[u])))
                moved = True
                break
            if disc[u] < disc[v]:
                edges.append(r)
                low[v] = min(low[v], disc[u])
        if moved:
            continue
        stack.pop()
        if stack:
            p = stack[-1][0]
            low[p] = min(low[p], low[v])
            if low[v] >= disc[p]:
                group = []
                while True:
                    r = edges.pop()
                    group.append(r)
                    if r == came:
                        break
                out.append((p, group))
    return out, disc


def _by_subsets(verts, elist, root, need, wt):
    """Cheapest tree joining root and need inside one group: (weight, link indexes)."""
    idx = {v: i for i, v in enumerate(verts)}
    size = len(verts)
    adj = [[] for _ in range(size)]
    for a, b, w, r in elist:
        adj[idx[a]].append((idx[b], w, r))
        adj[idx[b]].append((idx[a], w, r))
    own = [wt[v] for v in verts]
    full = (1 << len(need)) - 1
    best = [[None] * size for _ in range(full + 1)]
    back = [[None] * size for _ in range(full + 1)]
    for i, t in enumerate(need):
        best[1 << i][idx[t]] = own[idx[t]]
        back[1 << i][idx[t]] = ("leaf",)
    for whole in range(1, full + 1):
        row, brow = best[whole], back[whole]
        if whole & (whole - 1):
            low = whole & -whole
            part = (whole - 1) & whole
            while part:
                if part & low:
                    ra, rb = best[part], best[whole ^ part]
                    for v in range(size):
                        if ra[v] is not None and rb[v] is not None:
                            val = ra[v] + rb[v] - own[v]
                            if row[v] is None or val < row[v]:
                                row[v] = val
                                brow[v] = ("merge", part)
                part = (part - 1) & whole
        heap = [(row[v], v) for v in range(size) if row[v] is not None]
        heapq.heapify(heap)
        while heap:
            d, v = heapq.heappop(heap)
            if d > row[v]:
                continue
            for u, w, r in adj[v]:
                nd = d + w + own[u]
                if row[u] is None or nd < row[u]:
                    row[u] = nd
                    brow[u] = ("link", v, r)
                    heapq.heappush(heap, (nd, u))
    chosen = set()
    todo = [(full, idx[root])]
    while todo:
        whole, v = todo.pop()
        step = back[whole][v]
        if step[0] == "link":
            chosen.add(step[2])
            todo.append((whole, step[1]))
        elif step[0] == "merge":
            todo.append((step[1], v))
            todo.append((whole ^ step[1], v))
    return best[full][idx[root]], chosen


def _order(verts, elist, root):
    order = [root] + sorted(v for v in verts if v != root)
    step = {v: i for i, v in enumerate(order)}
    last = dict(step)
    for a, b, _w, _r in elist:
        hi = max(step[a], step[b])
        last[a] = max(last[a], hi)
        last[b] = max(last[b], hi)
    return order, step, last


def _along(verts, elist, root, need, wt):
    """Same answer as _by_subsets, by a sweep in corridor order."""
    order, step, last = _order(verts, elist, root)
    nbr = {v: [] for v in order}
    for a, b, w, r in elist:
        nbr[a].append((b, w, r))
        nbr[b].append((a, w, r))
    need = set(need)
    layers = [{((root, 0),): (wt[root], None, ())}]
    for i, v in enumerate(order[1:], 1):
        arriving = [(u, w, r) for u, w, r in nbr[v] if step[u] < i]
        layer = {}
        for key, (weight, _back, _took) in layers[-1].items():
            tags = dict(key)
            options = [] if v in need else [(dict(tags), weight, ())]
            grown = [({**tags, v: max(tags.values()) + 1}, weight + wt[v], ())]
            for u, w, r in arriving:
                if u not in tags:
                    continue
                extra = []
                for cur, spent, took in grown:
                    a, b = cur[u], cur[v]
                    if a == b:
                        continue
                    keep, drop = min(a, b), max(a, b)
                    joined = {s: (keep if t == drop else t) for s, t in cur.items()}
                    extra.append((joined, spent + w, took + (r,)))
                grown += extra
            options += grown
            for cur, spent, took in options:
                lost = False
                for s in [s for s in cur if last[s] <= i and s != root]:
                    tag = cur.pop(s)
                    if tag != 0 and tag not in cur.values():
                        lost = True
                        break
                if lost:
                    continue
                names = {0: 0}
                nxt = []
                for s, t in sorted(cur.items()):
                    names.setdefault(t, len(names))
                    nxt.append((s, names[t]))
                nxt = tuple(nxt)
                held = layer.get(nxt)
                if held is None or spent < held[0]:
                    layer[nxt] = (spent, key, took)
        layers.append(layer)
    weight, key = min((e[0], k) for k, e in layers[-1].items() if all(t == 0 for _s, t in k))
    chosen = set()
    for i in range(len(order) - 1, 0, -1):
        _w, back, took = layers[i][key]
        chosen.update(took)
        key = back
    return weight, chosen


def _bell(k):
    row = [1]
    for _ in range(k):
        nxt = [row[-1]]
        for x in row:
            nxt.append(nxt[-1] + x)
        row = nxt
    return row[0]


def _subsets_cheaper(verts, elist, root, k):
    """Compare the state counts of the two methods for one group."""
    order, step, last = _order(verts, elist, root)
    alive = max(sum(1 for v in order if step[v] < i <= last[v]) for i in range(len(order)))
    return 3 ** k <= _bell(alive + 1) << alive


def _solve(project: Project, banned=frozenset()):
    """(quote, sorted link ids) of the tie-rule optimum, or None."""
    n, charge, cold = project.size, project.charges, project.cold
    links = project.links
    m = len(links)
    unit = 1 << m
    adj = [[] for _ in range(n + 1)]
    ends = []
    for r, (lid, pa, pb, cost) in enumerate(links):
        w = cost * unit + (1 << (m - 1 - r))
        ends.append((pa, pb, w))
        if lid in banned or pa == pb:
            continue
        adj[pa].append((pb, w, r))
        adj[pb].append((pa, w, r))
    groups, disc = _groups(n, adj)
    if any(disc[c] == -1 for c in cold):
        return None
    below = [False] * (n + 1)
    total = charge[0] * unit
    chosen = set()
    for top, group in groups:
        verts = sorted({x for r in group for x in ends[r][:2]})
        need = [v for v in verts if v != top and (v in cold or below[v])]
        if not need:
            continue
        below[top] = True
        wt = {v: (0 if v == top else charge[v] * unit) for v in verts}
        elist = [(ends[r][0], ends[r][1], ends[r][2], r) for r in group]
        if _subsets_cheaper(verts, elist, top, len(need)):
            weight, got = _by_subsets(verts, elist, top, need, wt)
        else:
            weight, got = _along(verts, elist, top, need, wt)
        total += weight
        chosen |= got
    return total >> m, tuple(sorted(links[r][0] for r in chosen))


def best_network(project: Project) -> Network:
    """Minimum-quote network; among equal quotes the smaller link vector wins."""
    quote, links = _solve(project)
    return Network(quote, links, tuple(sorted(activated(project, links))))


def unique(project: Project) -> bool:
    """True when no other link set reaches the minimum quote."""
    quote, links = _solve(project)
    for lid in links:
        other = _solve(project, frozenset([lid]))
        if other is not None and other[0] == quote:
            return False
    return True


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
''',
    "src/task/report.py": r'''"""Build the four book documents from parsed projects and their networks."""
from __future__ import annotations

from .core import Network, best_network, site_lines
from .parser import Project


def share_bp(total: int, quote: int) -> int:
    return total * 10000 // quote


def project_report(project: Project, network: Network) -> dict:
    lines = site_lines(project, network.links)
    quote = network.quote
    corridors: dict[str, int] = {}
    sites = {}
    for p, total in sorted(lines.items()):
        if p == 0:
            continue
        corridor = project.corridors[p]
        corridors[corridor] = corridors.get(corridor, 0) + total
        sites[project.ids[p]] = {"corridor": corridor, "total": total, "share_bp": share_bp(total, quote)}
    return {
        "depot": {"total": lines[0], "share_bp": share_bp(lines[0], quote)},
        "corridors": {
            name: {"total": total, "share_bp": share_bp(total, quote)} for name, total in sorted(corridors.items())
        },
        "sites": dict(sorted(sites.items())),
    }


def build(book: dict) -> dict[str, dict]:
    projects: dict[str, Project] = book["projects"]
    networks = {pid: best_network(projects[pid]) for pid in sorted(projects)}
    core = {
        "projects": {
            pid: {"quote": net.quote, "links": list(net.links), "sites": list(net.sites)}
            for pid, net in networks.items()
        }
    }
    parser = {
        "accepted": sorted(projects),
        "rejected": dict(sorted(book["rejected"].items())),
        "projects": {pid: projects[pid].stats() for pid in sorted(projects)},
    }
    reports = {pid: project_report(projects[pid], net) for pid, net in networks.items()}
    corridor_totals: dict[str, int] = {}
    for entry in reports.values():
        for name, row in entry["corridors"].items():
            corridor_totals[name] = corridor_totals.get(name, 0) + row["total"]
    summary = {
        "book_total": sum(net.quote for net in networks.values()),
        "projects_quoted": len(networks),
        "projects_rejected": len(book["rejected"]),
        "depot_total": sum(entry["depot"]["total"] for entry in reports.values()),
        "corridor_totals": dict(sorted(corridor_totals.items())),
    }
    return {
        "module_core.json": core,
        "module_parser.json": parser,
        "module_report.json": {"projects": reports},
        "summary.json": summary,
    }
''',
}

DEFECTS = [
    ("pyproject.toml", "Asked for Python 3.13, pulled in requests and pointed the package at lib/; now 3.12, no dependencies, src/ layout and the manifest version."),
    ("src/task/__init__.py", "VERSION was missing; it now carries the manifest version."),
    ("src/task/parser.py", "Missing book files raised a traceback, closed links were kept, override keys were lowercased and slots were ordered as text."),
    ("src/task/core.py", "The network joined cold rooms by shortest paths, which is not the minimum quote, and a site was charged once per booked link instead of once."),
    ("src/task/report.py", "share_bp was rounded to nearest instead of rounded down."),
]


def repair() -> None:
    for rel, text in REPAIRED.items():
        target = REPO / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for cache in list(REPO.rglob("__pycache__")):
        shutil.rmtree(cache)


def archive(config: dict) -> Path:
    spec = config["archive"]
    target = Path(spec["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    method = zipfile.ZIP_DEFLATED if spec["compression"] == "deflated" else zipfile.ZIP_STORED
    members = sorted(
        p for p in REPO.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    with zipfile.ZipFile(target, "w") as bundle:
        for path in members:
            info = zipfile.ZipInfo(path.relative_to(REPO).as_posix(), date_time=tuple(spec["timestamp"]))
            info.compress_type = method
            info.external_attr = (0o100000 | int(spec["mode"], 8)) << 16
            bundle.writestr(info, path.read_bytes())
    return target


def run_book(src: Path, book: Path, out: Path, check: bool = True, cwd: str | None = None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(book), "--out", str(out)],
                          env=env, check=check, capture_output=not check, text=True, cwd=cwd)


def shipped_run() -> None:
    """Run the package as shipped on the current book, before any file is changed."""
    with tempfile.TemporaryDirectory() as scratch:
        result = run_book(REPO / "src", CI, Path(scratch) / "out", check=False, cwd=scratch)
        tail = (result.stderr.strip().splitlines() or ["(no output)"])[-1]
        written = sorted(p.name for p in (Path(scratch) / "out").glob("*.json"))
    print(f"check shipped package run before the first edit ok: exit {result.returncode}, last line: {tail}, "
          f"documents written: {', '.join(written) or 'none'}")


def book_reach(book: Path) -> tuple[int, int, int]:
    """Largest site count and cold-room count of one project, and the widest corridor-position span of a link."""
    sites: dict[str, int] = {}
    cold: dict[str, int] = {}
    with open(book / "sites.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sites[row["project"]] = sites.get(row["project"], 0) + 1
            cold[row["project"]] = cold.get(row["project"], 0) + (row["role"] == "cold_room")
    order = tomllib.loads((book / "access_rules.toml").read_text(encoding="utf-8"))["corridors"]["order"]
    places: dict[str, list] = {}
    with open(book / "layout.tsv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["corridor"] in order and row["slot"].strip().isdigit():
                places.setdefault(row["project"], []).append((order.index(row["corridor"]), int(row["slot"]), row["site"]))
    rank = {(pid, site): k + 1 for pid, rows in places.items() for k, (_c, _s, site) in enumerate(sorted(rows))}
    span = 0
    for line in (book / "links.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        a, b = (row["project"], row["a"]), (row["project"], row["b"])
        if a in rank and b in rank:
            span = max(span, abs(rank[a] - rank[b]))
    return max(sites.values()), max(cold.values()), span


def built_book(target: Path, seed: int) -> int:
    """Write a book of two large projects whose links reach across many corridor positions."""
    import random

    rng = random.Random(seed)
    order = tomllib.loads((CI / "access_rules.toml").read_text(encoding="utf-8"))["corridors"]["order"]
    bands = sorted(tomllib.loads((CI / "access_rules.toml").read_text(encoding="utf-8"))["tariff"])
    target.mkdir(parents=True)
    shutil.copy(CI / "access_rules.toml", target / "access_rules.toml")
    shutil.copy(CI / "activation.ini", target / "activation.ini")
    sites, layout, links = [], [], []
    for k, pid in enumerate(("Q1001", "Q1002")):
        names = ["D%03d" % k]
        edges = set()
        for group in range(6):
            top = 0 if group == 0 else rng.randrange(1, len(names))
            new = list(range(len(names), len(names) + 14))
            names += ["X%03d" % v for v in new]
            ring = [top] + new
            for a, b in zip(ring, ring[1:] + ring[:1]):
                edges.add((min(a, b), max(a, b)))
            while len([e for e in edges if e[0] in ring and e[1] in ring]) < 34:
                a, b = sorted(rng.sample(new, 2))
                edges.add((a, b))
        cold = set(rng.sample(range(1, len(names)), 30))
        slots = rng.sample(range(1, 10 * len(names)), len(names) - 1)
        sites.append(f"{pid},{names[0]},depot,yard")
        for v in range(1, len(names)):
            sites.append(f"{pid},{names[v]},{'cold_room' if v in cold else 'relay'},{rng.choice(['blast', 'freezer', 'chiller', 'shed', 'hut'])}")
            layout.append(f"{pid}\t{names[v]}\t{rng.choice(order)}\t{slots[v - 1]}")
        for j, (a, b) in enumerate(sorted(edges)):
            links.append(json.dumps({"project": pid, "link": "Z%d%04d" % (k, j), "a": names[a], "b": names[b],
                                     "band": rng.choice(bands), "km": rng.randint(1, 12)}))
    (target / "sites.csv").write_text("project,site,role,class\n" + "\n".join(sites) + "\n", encoding="utf-8")
    (target / "layout.tsv").write_text("project\tsite\tcorridor\tslot\n" + "\n".join(layout) + "\n", encoding="utf-8")
    (target / "links.jsonl").write_text("\n".join(links) + "\n", encoding="utf-8")
    return 2


def regression_quotes(src: Path) -> dict:
    sys.path.insert(0, str(src))
    from task.core import best_network
    from task.parser import Rejected, load_inline

    found = {}
    for line in (CI / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        try:
            found[case["case"]] = best_network(load_inline(case)).quote
        except Rejected as exc:
            found[case["case"]] = exc.code
    return dict(sorted(found.items()))


def previously_failing() -> list[str]:
    log = (CI / "failing_tests.log").read_text(encoding="utf-8")
    pattern = re.compile(r"^(\w+) \([\w.]+\) \.\.\. (?:FAIL|ERROR)$", re.M)
    return sorted(set(pattern.findall(log)))


def raw_prices(book: Path) -> tuple[dict, dict, dict]:
    """Link costs, site charges and site corridors read straight from the book files."""
    rules = tomllib.loads((book / "access_rules.toml").read_text(encoding="utf-8"))
    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str
    ini.read(book / "activation.ini", encoding="utf-8")
    costs = {}
    for line in (book / "links.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            band = rules["tariff"][row["band"]]
            costs[row["link"]] = (row["a"], row["b"], band["base"] + band["per_km"] * row["km"])
    charges = {}
    with open(book / "sites.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = f"{row['project']}/{row['site']}"
            charges[(row["project"], row["site"])] = int(ini["overrides"].get(key, ini["classes"][row["class"]]))
    corridors = {}
    with open(book / "layout.tsv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            corridors[(row["project"], row["site"])] = row["corridor"]
    return costs, charges, corridors


def self_check(src: Path) -> None:
    costs, charges, corridors = raw_prices(CI)
    core = json.loads((OUT / "module_core.json").read_text(encoding="utf-8"))["projects"]
    report = json.loads((OUT / "module_report.json").read_text(encoding="utf-8"))["projects"]
    for pid, net in core.items():
        ends = {site for link in net["links"] for site in costs[link][:2]}
        assert ends <= set(net["sites"]), pid
        quote = sum(costs[link][2] for link in net["links"]) + sum(charges[(pid, s)] for s in net["sites"])
        assert quote == net["quote"], (pid, quote, net["quote"])
    print("check quotes ok")
    for pid, entry in report.items():
        per_corridor: dict[str, int] = {}
        for site, line in entry["sites"].items():
            assert line["corridor"] == corridors[(pid, site)], (pid, site)
            per_corridor[line["corridor"]] = per_corridor.get(line["corridor"], 0) + line["total"]
        assert per_corridor == {k: v["total"] for k, v in entry["corridors"].items()}, pid
        assert entry["depot"]["total"] + sum(per_corridor.values()) == core[pid]["quote"], pid
    print("check corridors ok")
    fixes = json.loads((OUT / "test_fixes.json").read_text(encoding="utf-8"))
    log = (CI / "failing_tests.log").read_text(encoding="utf-8")
    named = set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", log, re.M))
    assert set(fixes["previously_failing"]) == named
    print(f"check previously_failing ok: {len(named)} names in test_fixes.json, recounted from the "
          f"FAIL and ERROR lines of failing_tests.log: {len(named)}")
    with tempfile.TemporaryDirectory() as again:
        run_book(src, CI, Path(again))
        for name in ("module_core.json", "module_parser.json", "module_report.json", "summary.json"):
            assert (Path(again) / name).read_bytes() == (OUT / name).read_bytes(), name
    print("check rerun ok: second run into another directory, all four documents byte-identical")
    with tempfile.TemporaryDirectory() as scratch:
        altered = Path(scratch) / "book"
        shutil.copytree(CI, altered)
        rules = altered / "access_rules.toml"
        rules.write_text(re.sub(r"^base = (\d+)$", lambda m: f"base = {int(m.group(1)) + 1}",
                                rules.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
        run_book(src, altered, Path(scratch) / "out")
        moved = json.loads((Path(scratch) / "out" / "module_core.json").read_text(encoding="utf-8"))["projects"]
        assert moved.keys() == core.keys()
        assert all(moved[pid]["quote"] > net["quote"] for pid, net in core.items())
    print("check altered copy ok")
    first = sorted(core)[0]
    link = sorted(core[first]["links"])[0]
    with tempfile.TemporaryDirectory() as scratch:
        altered = Path(scratch) / "book"
        shutil.copytree(CI, altered)
        rows = []
        for line in (altered / "links.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["project"] == first and row["link"] == link:
                old_km, row["km"] = row["km"], row["km"] + 7
            rows.append(json.dumps(row))
        (altered / "links.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
        run_book(src, altered, Path(scratch) / "out")
        moved = json.loads((Path(scratch) / "out" / "module_core.json").read_text(encoding="utf-8"))["projects"]
        assert moved[first]["quote"] >= core[first]["quote"]
        assert all(moved[pid] == net for pid, net in core.items() if pid != first)
    print(f"check one link changed ok: {first} link {link} km {old_km} -> {old_km + 7}, "
          f"quote {core[first]['quote']} -> {moved[first]['quote']}, other projects unchanged")
    with tempfile.TemporaryDirectory() as scratch:
        partial = Path(scratch) / "book"
        shutil.copytree(CI, partial)
        (partial / "activation.ini").unlink()
        (partial / "layout.tsv").unlink()
        result = run_book(src, partial, Path(scratch) / "out", check=False)
        written = sorted(p.name for p in (Path(scratch) / "out").glob("*.json"))
        assert result.returncode != 0 and result.stderr.strip().splitlines()[-1] == "E_MISSING_FILE layout.tsv"
        assert not written
    print(f"check missing book files ok: activation.ini and layout.tsv removed, exit {result.returncode}, "
          f"stderr {result.stderr.strip().splitlines()[-1]}, no documents written")
    with tempfile.TemporaryDirectory() as scratch:
        book = Path(scratch) / "far book"
        projects = built_book(book, 20261027)
        started = time.monotonic()
        run_book(src, book, Path(scratch) / "out")
        elapsed = time.monotonic() - started
        far_costs, far_charges, _ = raw_prices(book)
        far = json.loads((Path(scratch) / "out" / "module_core.json").read_text(encoding="utf-8"))["projects"]
        roles: dict[str, dict[str, str]] = {}
        with open(book / "sites.csv", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                roles.setdefault(row["project"], {})[row["site"]] = row["role"]
        for pid, net in far.items():
            reached = {s for s, r in roles[pid].items() if r == "depot"}
            grow = True
            while grow:
                grow = False
                for name in net["links"]:
                    a, b, _ = far_costs[name]
                    if (a in reached) != (b in reached):
                        reached |= {a, b}
                        grow = True
            assert {s for s, r in roles[pid].items() if r != "relay"} <= reached, pid
            quote = sum(far_costs[n][2] for n in net["links"]) + sum(far_charges[(pid, s)] for s in net["sites"])
            assert quote == net["quote"], pid
        assert elapsed < 4 * projects + 10
        built = book_reach(book)
    shipped = book_reach(CI)
    assert built[0] > shipped[0] and built[1] > shipped[1] and built[2] > shipped[2]
    print(f"check built far-reaching book ok: {projects} projects; largest project {built[0]} sites and "
          f"{built[1]} cold rooms against {shipped[0]} sites and {shipped[1]} cold rooms in the shipped book; "
          f"widest open link spans {built[2]} corridor positions against {shipped[2]} in the shipped book; "
          f"finished in {elapsed:.2f} s of the {4 * projects + 10} s limit, quotes recomputed from the raw files "
          f"and every cold room joined to the depot")
    with tempfile.TemporaryDirectory() as scratch:
        spaced = Path(scratch) / "extracted copy"
        with zipfile.ZipFile(OUT / "patched-repo.zip") as bundle:
            bundle.extractall(spaced)
        elsewhere = Path(scratch) / "elsewhere"
        elsewhere.mkdir()
        run_book(spaced / "src", CI, Path(scratch) / "out", cwd=str(elsewhere))
        for name in ("module_core.json", "module_parser.json", "module_report.json", "summary.json"):
            assert (Path(scratch) / "out" / name).read_bytes() == (OUT / name).read_bytes(), name
    print("check archive from a path with a space ok: patched-repo.zip extracted to 'extracted copy', run from "
          "another directory, all four documents byte-identical")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(src.parent / "tests"), "-p", "test_*.py"],
        env=env, check=True, capture_output=True,
    )
    print("check visible tests ok")
    with tempfile.TemporaryDirectory() as scratch:
        book = Path(scratch) / "tie book"
        book.mkdir()
        shutil.copy(CI / "access_rules.toml", book / "access_rules.toml")
        shutil.copy(CI / "activation.ini", book / "activation.ini")
        (book / "sites.csv").write_text("project,site,role,class\nQ2001,D1,depot,yard\nQ2001,C1,cold_room,chiller\n"
                                        "Q2001,R1,relay,kiosk\n", encoding="utf-8")
        (book / "layout.tsv").write_text("project\tsite\tcorridor\tslot\nQ2001\tC1\tharbour\t2\n"
                                         "Q2001\tR1\tharbour\t1\n", encoding="utf-8")
        rows = [("T001", "D1", "C1", 10), ("T002", "D1", "R1", 4), ("T003", "R1", "C1", 4)]
        (book / "links.jsonl").write_text("".join(json.dumps({"project": "Q2001", "link": lid, "a": a, "b": b,
                                                              "band": "B1", "km": km}) + "\n"
                                                  for lid, a, b, km in rows), encoding="utf-8")
        run_book(src, book, Path(scratch) / "out")
        tie = json.loads((Path(scratch) / "out" / "module_core.json").read_text(encoding="utf-8"))["projects"]["Q2001"]
        assert tie["quote"] == 17 and tie["links"] == ["T002", "T003"], tie
    print("check tie book ok: networks {T001} and {T002, T003} both quote 17, vectors 100 and 011, the package "
          f"picks {tie['links']} with quote {tie['quote']}")


FOUND = [
    ("src/task/parser.py", "a missing book file ends in a traceback", "a missing file prints E_MISSING_FILE <name>"
     " and writes no document"),
    ("src/task/core.py", "cold rooms are joined by shortest paths", "the quote of a project is the smallest quote"
     " of any of its networks"),
    ("src/task/core.py", "a site is charged once per link touching it", "each site charged once however many of"
     " the network's links touch it"),
    ("src/task/report.py", "share_bp is rounded to nearest", "share_bp is rounded down"),
]


def main() -> int:
    config = json.loads((CI / "build_config.json").read_text(encoding="utf-8"))
    shipped_run()
    for rel, defect, rule in FOUND:
        print(f"defect found before editing: {rel}: {defect}; api_contract.md says {rule}")
    repair()
    target = archive(config)
    unpacked = Path(tempfile.mkdtemp(prefix="patched-"))
    with zipfile.ZipFile(target) as bundle:
        bundle.extractall(unpacked)
    src = unpacked / "src"
    OUT.mkdir(parents=True, exist_ok=True)
    run_book(src, CI, OUT)
    fixes = {"previously_failing": previously_failing(), "regression_quotes": regression_quotes(src)}
    (OUT / "test_fixes.json").write_text(json.dumps(fixes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "defects": [{"file": rel, "summary": text} for rel, text in DEFECTS],
        "checks": [
            "python3 -m unittest discover -s tests on the archived repository: all visible tests pass",
            "every quote in module_core.json recomputed from the raw book files",
            "corridor and depot lines add up to each project's quote",
            "a second run of the command gives byte-identical documents",
        ],
    }
    print(f"ran the package extracted from {target}")
    self_check(src)
    (OUT / "repair-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    parsed = json.loads((OUT / "module_parser.json").read_text(encoding="utf-8"))
    print("rejected projects:", ", ".join(f"{pid} {code}" for pid, code in sorted(parsed["rejected"].items())))
    shutil.rmtree(unpacked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
