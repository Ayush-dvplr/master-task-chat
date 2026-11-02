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
SPAN = 4


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
    for _lid, pa, pb, _cost in placed:
        if pa != 0 and pb - pa > SPAN:
            raise Rejected("E_BAD_SPAN")
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
    "src/task/core.py": r'''"""Minimum quote of a project: a sweep along the corridor positions.

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


def run_book(src: Path, book: Path, out: Path) -> None:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(book), "--out", str(out)], env=env, check=True)


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
    assert len(fixes["previously_failing"]) == len(set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", log, re.M)))
    print("check previously_failing ok")
    with tempfile.TemporaryDirectory() as again:
        run_book(src, CI, Path(again))
        for name in ("module_core.json", "module_parser.json", "module_report.json", "summary.json"):
            assert (Path(again) / name).read_bytes() == (OUT / name).read_bytes(), name
    print("check rerun ok")
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
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(src.parent / "tests"), "-p", "test_*.py"],
        env=env, check=True, capture_output=True,
    )
    print("check visible tests ok")


def main() -> int:
    config = json.loads((CI / "build_config.json").read_text(encoding="utf-8"))
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
    (OUT / "repair-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ran the package extracted from {target}")
    self_check(src)
    parsed = json.loads((OUT / "module_parser.json").read_text(encoding="utf-8"))
    print("rejected projects:", ", ".join(f"{pid} {code}" for pid, code in sorted(parsed["rejected"].items())))
    print("method: core.py sweeps the sites in corridor order and keeps, for the depot and the last four positions,")
    print("the cheapest cost of every connection pattern, so the quote is the minimum over all networks")
    shutil.rmtree(unpacked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
