"""Read a quote book directory and the inline projects of the regression suite."""
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
    """Return {"projects": {pid: Project}, "rejected": {pid: code}}.

    Raises MissingBookFile for the first book file of BOOK_FILES that is absent.
    """
    root = Path(root)
    for name in BOOK_FILES:
        if not (root / name).is_file():
            raise MissingBookFile(name)
    rules = tomllib.loads((root / "access_rules.toml").read_text(encoding="utf-8"))
    rank = {name: i for i, name in enumerate(rules["corridors"]["order"])}
    tariff = rules["tariff"]
    closed = set(rules["closed"]["links"])
    activation = configparser.ConfigParser(interpolation=None)
    activation.optionxform = str  # activation keys are matched with their own case
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
