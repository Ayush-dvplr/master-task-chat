from __future__ import annotations

import ast
import base64
import configparser
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
import zlib
from pathlib import Path

from rewardkit import criteria, criterion

BOOK_SEED = int("6150938227")
PACKAGE = "task"
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
DOCUMENTS = ("module_core.json", "module_parser.json", "module_report.json", "summary.json")
BOOK_FILES = ("sites.csv", "layout.tsv", "links.jsonl", "access_rules.toml", "activation.ini")
SECONDS_PER_PROJECT = 4
START_UP_SECONDS = 10
WIDTH = 4
VISIBLE_TESTS = {
    "test_chain_quote", "test_cli_writes_documents", "test_slot_order_is_numeric",
    "test_activation_override", "test_closed_link_is_dropped", "test_share_rounds_down",
}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

SHIPPED_DATA_LINE

_CACHE: dict[str, tuple[bool, object]] = {}


# ---------------------------------------------------------------- plumbing

def _memo(key: str, build):
    if key not in _CACHE:
        try:
            _CACHE[key] = (True, build())
        except Exception as exc:  # remembered so every check that needs it fails the same way
            _CACHE[key] = (False, exc)
    ok, value = _CACHE[key]
    if not ok:
        raise value
    return value


def _scratch(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o777)
    return path


def _open_tree(root: Path) -> None:
    for path in [root, *root.rglob("*")]:
        path.chmod(0o777 if path.is_dir() else 0o644)


def _data_dir() -> Path:
    """The agent's /app/ci, rebuilt here: the verifier container never has it."""
    def build() -> Path:
        root = _scratch("shipped-ci-")
        for rel, blob in _SHIPPED_DATA.items():
            (root / rel).write_bytes(zlib.decompress(base64.b64decode(blob)))
        _open_tree(root)
        return root
    return _memo("data", build)


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors can leave files at mode 0600. The checks run the agent's
    program as an unprivileged user, so the mode is widened first; this changes
    no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _artifact(name: str) -> Path:
    path = OUT_DIR / name
    _grant_read(str(path))
    return path


def _json_artifact(name: str):
    return json.loads(_artifact(name).read_text(encoding="utf-8"))


def _extract_archive() -> Path:
    def build() -> Path:
        archive = _artifact("patched-repo.zip")
        dest = _scratch("delivered-repo-")
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                rel = Path(info.filename)
                if info.filename.endswith("/"):
                    continue
                assert not rel.is_absolute() and ".." not in rel.parts, "unsafe archive member"
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info))
        _open_tree(dest)
        return dest
    return _memo("repo", build)


def _env(home: Path, src: Path | None) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if src is not None:
        env["PYTHONPATH"] = str(src)
    return env


def _book_projects(book: Path) -> int:
    with (book / "sites.csv").open(encoding="utf-8", newline="") as handle:
        return len({row["project"] for row in csv.DictReader(handle)})


_ISOLATED = (
    "import runpy, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "sys.argv = ['task', '--book', sys.argv[2], '--out', sys.argv[3]]\n"
    "runpy.run_module('task', run_name='__main__', alter_sys=True)\n"
)


def _run_cli(book: Path, projects: int, isolated: bool = False) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the delivered package on one book as an unprivileged user from a foreign cwd."""
    repo = _extract_archive()
    base = _scratch("run-")
    out = base / "out"
    out.mkdir()
    out.chmod(0o777)
    cwd = base / "elsewhere"
    cwd.mkdir()
    cwd.chmod(0o777)
    if isolated:
        checkout = base / "checkout two" / "repo"
        shutil.copytree(repo, checkout)
        _open_tree(base / "checkout two")
        command = [sys.executable, "-I", "-B", "-c", _ISOLATED, str(checkout / "src"), str(book), str(out)]
        env = _env(cwd, None)
    else:
        command = [sys.executable, "-B", "-m", PACKAGE, "--book", str(book), "--out", str(out)]
        env = _env(cwd, repo / "src")
    limit = SECONDS_PER_PROJECT * projects + START_UP_SECONDS
    try:
        result = subprocess.run(_untrusted_command(command), text=True, capture_output=True,
                                env=env, cwd=cwd, timeout=limit)
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(command, -9, "", "timed out after %d s" % limit)
    return result, out


# ---------------------------------------------------------------- reference reading of a book

def _read_book(root: Path) -> dict:
    """{"accepted": {pid: project}, "rejected": {pid: code}} following the contract."""
    rules = tomllib.loads((root / "access_rules.toml").read_text(encoding="utf-8"))
    place = {name: k for k, name in enumerate(rules["corridors"]["order"])}
    shut = set(rules.get("closed", {}).get("links", []))
    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str
    ini.read_string((root / "activation.ini").read_text(encoding="utf-8"))
    charge_of_class = {key: int(value) for key, value in ini["classes"].items()}
    charge_override = {key: int(value) for key, value in ini["overrides"].items()}
    with (root / "sites.csv").open(encoding="utf-8", newline="") as handle:
        site_table = list(csv.DictReader(handle))
    with (root / "layout.tsv").open(encoding="utf-8", newline="") as handle:
        where = {(r["project"], r["site"]): (r["corridor"], int(r["slot"])) for r in csv.DictReader(handle, delimiter="\t")}
    link_table = [json.loads(line) for line in (root / "links.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_project: dict[str, dict[str, list]] = {}
    for row in site_table:
        by_project.setdefault(row["project"], {"sites": [], "links": []})["sites"].append(row)
    for row in link_table:
        if row["project"] in by_project:
            by_project[row["project"]]["links"].append(row)
    accepted, rejected = {}, {}
    for pid, group in by_project.items():
        verdict = _judge_project(pid, group, where, place, shut, rules["tariff"], charge_of_class, charge_override)
        if isinstance(verdict, str):
            rejected[pid] = verdict
        else:
            accepted[pid] = verdict
    return {"accepted": accepted, "rejected": rejected}


def _judge_project(pid, group, where, place, shut, tariff, charge_of_class, charge_override):
    names = [row["site"] for row in group["sites"]]
    if len(names) != len(set(names)):
        return "E_DUP_SITE"
    depot = next(row for row in group["sites"] if row["role"] == "depot")
    rest = [row for row in group["sites"] if row["role"] != "depot"]
    rest.sort(key=lambda row: (place[where[(pid, row["site"])][0]], where[(pid, row["site"])][1]))
    order = [depot] + rest
    pos = {row["site"]: k for k, row in enumerate(order)}
    live = [row for row in group["links"] if row["link"] not in shut]
    if any(row["a"] not in pos or row["b"] not in pos for row in live):
        return "E_UNKNOWN_ENDPOINT"
    links = []
    for row in live:
        lo, hi = sorted((pos[row["a"]], pos[row["b"]]))
        if lo > 0 and hi - lo > WIDTH:
            return "E_BAD_SPAN"
        band = tariff[row["band"]]
        links.append((row["link"], lo, hi, band["base"] + band["per_km"] * row["km"]))
    cold = {pos[row["site"]] for row in rest if row["role"] == "cold_room"}
    root = list(range(len(order)))

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    for _lid, lo, hi, _cost in links:
        root[find(lo)] = find(hi)
    if any(find(c) != find(0) for c in cold):
        return "E_NO_NETWORK"
    return {
        "n": len(order) - 1,
        "ids": [row["site"] for row in order],
        "corridor": [None] + [where[(pid, row["site"])][0] for row in rest],
        "charge": [charge_override.get("%s/%s" % (pid, row["site"]), charge_of_class[row["class"]]) for row in order],
        "cold": cold,
        "links": sorted(links),
        "rows": len(group["links"]),
        "relays": sum(1 for row in rest if row["role"] == "relay"),
    }


# ---------------------------------------------------------------- reference optimum

def _relabel(pairs) -> tuple:
    names = {0: 0}
    fixed = []
    for spot, tag in sorted(pairs):
        names.setdefault(tag, len(names))
        fixed.append((spot, names[tag]))
    return tuple(fixed)


def _optimum(proj: dict):
    """(cost, number of optimal link sets, one optimal link set) or None.

    Positions are swept left to right; a state records which of the last WIDTH
    positions are switched on and which of them already hang together (tag 0 is
    the depot's piece).  Links are added when their right end is reached.
    """
    n = proj["n"]
    charge = proj["charge"]
    arriving: dict[int, list] = {v: [] for v in range(1, n + 1)}
    for lid, lo, hi, cost in proj["links"]:
        arriving[hi].append((lo, cost, lid))
    layers = [{(): (charge[0], 1, None, ())}]
    for v in range(1, n + 1):
        layer: dict[tuple, tuple] = {}
        for key, (cost, count, _back, _took) in layers[-1].items():
            tags = dict(key)
            branches = []
            if v not in proj["cold"]:
                branches.append((dict(tags), cost, ()))
            fresh = max([0, *tags.values()]) + 1
            grown = [({**tags, v: fresh}, cost + charge[v], ())]
            for lo, link_cost, lid in arriving[v]:
                if lo != 0 and lo not in tags:
                    continue
                extra = []
                for current, spent, took in grown:
                    left = 0 if lo == 0 else current[lo]
                    right = current[v]
                    if left == right:
                        continue
                    keep, drop = min(left, right), max(left, right)
                    joined = {spot: (keep if tag == drop else tag) for spot, tag in current.items()}
                    extra.append((joined, spent + link_cost, took + (lid,)))
                grown += extra
            branches += grown
            for current, spent, took in branches:
                gone = v - WIDTH
                if gone in current:
                    tag = current.pop(gone)
                    if tag != 0 and tag not in current.values():
                        continue
                nxt = _relabel(current.items())
                held = layer.get(nxt)
                if held is None or spent < held[0]:
                    layer[nxt] = (spent, count, key, took)
                elif spent == held[0]:
                    layer[nxt] = (spent, held[1] + count, held[2], held[3])
        layers.append(layer)
    ends = [(entry[0], key) for key, entry in layers[-1].items() if all(tag == 0 for _spot, tag in key)]
    if not ends:
        return None
    best = min(cost for cost, _key in ends)
    count = sum(layers[-1][key][1] for cost, key in ends if cost == best)
    key = min(key for cost, key in ends if cost == best)
    chosen = []
    for v in range(n, 0, -1):
        _cost, _count, back, took = layers[v][key]
        chosen += took
        key = back
    return best, count, sorted(chosen)


def _enumerate(proj: dict):
    """Every link subset: (cost, number of optimal sets, the optimum picked by the tie rule)."""
    links = proj["links"]
    order = sorted(range(len(links)), key=lambda k: links[k][0])
    best, count, pick = None, 0, None
    for mask in range(1 << len(links)):
        chosen = [links[k] for k in range(len(links)) if mask >> k & 1]
        cost = _network_cost(proj, chosen)
        if cost is None:
            continue
        vector = tuple(mask >> k & 1 for k in order)
        if best is None or cost < best:
            best, count, pick = cost, 1, vector
        elif cost == best:
            count += 1
            pick = min(pick, vector)
    if best is None:
        return None
    return best, count, sorted(links[k][0] for k, bit in zip(order, pick) if bit)


def _network_cost(proj: dict, chosen) -> int | None:
    """Cost of a link set if it joins the depot and every cold room, else None."""
    root = list(range(proj["n"] + 1))

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    lit = {0} | proj["cold"]
    total = 0
    for _lid, lo, hi, cost in chosen:
        root[find(lo)] = find(hi)
        lit.update((lo, hi))
        total += cost
    if any(find(p) != find(0) for p in lit):
        return None
    return total + sum(proj["charge"][p] for p in lit)


def _lines(proj: dict, chosen_ids) -> dict[int, int]:
    """Charging lines: activation once per lit site plus each link on its farther end."""
    by_id = {lid: (lo, hi, cost) for lid, lo, hi, cost in proj["links"]}
    lit = {0} | proj["cold"]
    for lid in chosen_ids:
        lo, hi, _cost = by_id[lid]
        lit.update((lo, hi))
    totals = {p: proj["charge"][p] for p in lit}
    for lid in chosen_ids:
        lo, hi, cost = by_id[lid]
        totals[hi] += cost
    return totals


def _project_rollup(proj: dict, chosen_ids, quote: int) -> dict:
    totals = _lines(proj, chosen_ids)
    corridor_sum: dict[str, int] = {}
    site_rows = {}
    for p, total in totals.items():
        if p == 0:
            continue
        name = proj["corridor"][p]
        corridor_sum[name] = corridor_sum.get(name, 0) + total
        site_rows[proj["ids"][p]] = {"corridor": name, "total": total, "share_bp": total * 10000 // quote}
    return {
        "depot": {"total": totals[0], "share_bp": totals[0] * 10000 // quote},
        "corridors": {name: {"total": t, "share_bp": t * 10000 // quote} for name, t in corridor_sum.items()},
        "sites": site_rows,
    }


def _documents(book: dict, picks: dict[str, tuple[int, list]]) -> dict[str, dict]:
    """The four documents for a parsed book, given the network of each accepted project."""
    accepted = book["accepted"]
    core, report = {}, {}
    for pid, (quote, chosen) in picks.items():
        proj = accepted[pid]
        lit = {0} | proj["cold"]
        for lid, lo, hi, _cost in proj["links"]:
            if lid in chosen:
                lit.update((lo, hi))
        core[pid] = {"quote": quote, "links": sorted(chosen), "sites": sorted(proj["ids"][p] for p in lit)}
        report[pid] = _project_rollup(proj, chosen, quote)
    corridor_totals: dict[str, int] = {}
    for entry in report.values():
        for name, row in entry["corridors"].items():
            corridor_totals[name] = corridor_totals.get(name, 0) + row["total"]
    parsed = {
        pid: {"sites": p["n"] + 1, "links": p["rows"], "open_links": len(p["links"]),
              "cold_rooms": len(p["cold"]), "relays": p["relays"]}
        for pid, p in accepted.items()
    }
    return {
        "module_core.json": {"projects": core},
        "module_parser.json": {"accepted": sorted(accepted), "rejected": book["rejected"], "projects": parsed},
        "module_report.json": {"projects": report},
        "summary.json": {
            "book_total": sum(q for q, _c in picks.values()),
            "projects_quoted": len(picks),
            "projects_rejected": len(book["rejected"]),
            "depot_total": sum(entry["depot"]["total"] for entry in report.values()),
            "corridor_totals": corridor_totals,
        },
    }


def _expected_documents(root: Path, small: bool = False) -> dict[str, dict]:
    book = _read_book(root)
    picks = {}
    for pid, proj in book["accepted"].items():
        found = _enumerate(proj) if small else _optimum(proj)
        assert found is not None, "accepted project without a network"
        picks[pid] = (found[0], found[2])
    return _documents(book, picks)


# ---------------------------------------------------------------- fresh books

CORRIDORS = ["harbour", "ringroad", "airport", "mill", "canal", "orchard"]
BANDS = {"B1": (0, 1), "B2": (2, 3), "B3": (5, 2), "B4": (1, 4), "B5": (7, 5), "B6": (3, 1)}
CLASSES = {
    "yard": 4, "yard_east": 7, "blast": 9, "chiller": 3, "freezer": 11, "store": 6,
    "hut": 5, "mast": 14, "kiosk": 2, "shed": 8, "relay_a": 12, "relay_b": 17,
    "junction": 19, "tower": 23, "vault": 27, "dock": 10,
}


def _hub_project(rng, n, n_terms, n_links, n_depot):
    """Corridor project with relay hubs; positions 0..n, at most n_terms cold rooms and n_links links."""
    act, edges, terms = {}, {}, set()
    p = 3
    while p <= n - 3 and len(terms) < n_terms:
        h = p
        k = rng.randint(3, 4)
        cand = [q for q in range(h - 3, h + 4) if 1 <= q <= n and q != h and q not in act and q not in terms]
        rng.shuffle(cand)
        members = sorted(cand[:k])
        hub_charge = rng.randint(10, 20)
        act[h] = hub_charge
        spoke = {}
        for q in members:
            if len(terms) >= n_terms:
                break
            terms.add(q)
            spoke[q] = rng.randint(1, 3)
            edges[(min(h, q), max(h, q))] = spoke[q]
        ms = sorted(spoke)
        hubtree = hub_charge + sum(spoke.values())
        for a, b in zip(ms, ms[1:]):
            if b - a <= WIDTH:
                lo = hubtree // max(1, len(ms) - 1) + 1
                hi = hub_charge + spoke[a] + spoke[b] - 1
                edges[(a, b)] = rng.randint(min(lo, hi), max(lo, hi))
        p += rng.randint(6, 9)
    for _ in range(2):
        if len(terms) + 2 > n_terms:
            break
        free = [q for q in range(2, n - 6) if all(x not in act and x not in terms for x in range(q, q + 7))]
        if not free:
            break
        q = rng.choice(free)
        t1, h1, h2, m, t3 = q, q + 1, q + 5, q + 3, q + 6
        charge = rng.randint(6, 12)
        act[h1] = charge
        act[h2] = charge
        act[m] = 2
        terms.update([t1, t3])
        edges[(t1, h1)] = 1
        edges[(h1, h2)] = 1
        edges[(h2, t3)] = 1
        edges[(t1, m)] = charge + 1
        edges[(m, t3)] = charge + 1
    free = [q for q in range(1, n + 1) if q not in terms and q not in act]
    while len(terms) < n_terms:
        q = rng.choice(free)
        free.remove(q)
        terms.add(q)
    for q in range(1, n + 1):
        if q not in act:
            act[q] = rng.randint(2, 12) if q in terms else rng.randint(4, 30)
    act[0] = rng.randint(3, 9)
    for q in range(1, n):
        if (q, q + 1) not in edges and rng.random() < 0.9 and len(edges) < n_links - n_depot:
            edges[(q, q + 1)] = rng.randint(8, 30)
    tries = 0
    while len(edges) < n_links - n_depot and tries < 5000:
        tries += 1
        a = rng.randint(1, n)
        b = a + rng.randint(2, WIDTH)
        if b <= n and (a, b) not in edges:
            edges[(a, b)] = rng.randint(8, 40)
    for q in rng.sample(range(1, n + 1), n_depot):
        edges[(0, q)] = rng.randint(12, 45)
    assert len(terms) == n_terms and len(edges) <= n_links
    assert all(a == 0 or b - a <= WIDTH for a, b in edges)
    return {"n": n, "terms": terms, "act": act, "edges": edges}


def _tiny_project(rng, n, n_terms, n_links):
    act = {0: rng.randint(1, 6)}
    terms = set(rng.sample(range(1, n + 1), n_terms))
    edges = {}
    for q in range(0, n):
        edges[(q, q + 1)] = rng.randint(3, 12)
    tries = 0
    while len(edges) < n_links and tries < 400:
        tries += 1
        a = rng.randint(0, n - 1)
        b = rng.randint(a + 1, n) if a == 0 else a + rng.randint(1, WIDTH)
        if b <= n and (a, b) not in edges:
            edges[(a, b)] = rng.randint(2, 12)
    for q in range(1, n + 1):
        act[q] = rng.randint(1, 6) if q in terms else rng.randint(1, 8)
    return {"n": n, "terms": terms, "act": act, "edges": edges}


def _as_project(P) -> dict:
    """Reference view of an abstract project (positions already fixed)."""
    links = sorted(("E%03d%03d" % (a, b), a, b, c) for (a, b), c in P["edges"].items())
    return {"n": P["n"], "charge": [P["act"][q] for q in range(P["n"] + 1)], "cold": set(P["terms"]), "links": links}


def _cost_parts(rng, cost, bands):
    options = [band for band, (base, per) in bands.items() if cost - base >= per and (cost - base) % per == 0]
    band = rng.choice(options)
    base, per = bands[band]
    return band, (cost - base) // per


def _fresh_link(rng, used):
    while True:
        lid = "L%05d" % rng.randint(10000, 99999)
        if lid not in used:
            used.add(lid)
            return lid


def _encode(rng, pid, P, used, order, corrupt=()):
    n = P["n"]
    ids = ["S%03d" % x for x in rng.sample(range(100, 1000), n + 1)]
    names = sorted(rng.sample(order, rng.randint(2, min(5, n))), key=order.index)
    cuts = sorted(rng.sample(range(2, n + 1), len(names) - 1))
    bounds = [1] + cuts + [n + 1]
    layout = []
    for k, name in enumerate(names):
        slot = rng.randint(2, 9)
        for q in range(bounds[k], bounds[k + 1]):
            layout.append([pid, ids[q], name, str(slot)])
            slot += rng.randint(1, 6)
    by_charge: dict[int, list] = {}
    for name, charge in CLASSES.items():
        by_charge.setdefault(charge, []).append(name)
    sites, overrides = [], []
    for q in range(n + 1):
        role = "depot" if q == 0 else "cold_room" if q in P["terms"] else "relay"
        charge = P["act"][q]
        if charge in by_charge and rng.random() < 0.7:
            cls = rng.choice(by_charge[charge])
        else:
            cls = rng.choice([c for c, v in CLASSES.items() if v != charge])
            overrides.append(("%s/%s" % (pid, ids[q]), charge))
        sites.append([pid, ids[q], role, cls])
    links, closed, rows = [], [], []
    for (a, b), cost in sorted(P["edges"].items()):
        lid = _fresh_link(rng, used)
        band, km = _cost_parts(rng, cost, BANDS)
        ends = [ids[a], ids[b]]
        rng.shuffle(ends)
        links.append({"project": pid, "link": lid, "a": ends[0], "b": ends[1], "band": band, "km": km})
        rows.append((a, b))
    for _ in range(min(95 - len(links), rng.randint(1, 3))):
        a = rng.randint(1, max(1, n - 5))
        b = min(n, a + rng.randint(5, 9))
        if b - a > WIDTH:
            lid = _fresh_link(rng, used)
            band, km = _cost_parts(rng, rng.randint(1, 3), BANDS)
            links.append({"project": pid, "link": lid, "a": ids[a], "b": ids[b], "band": band, "km": km})
            closed.append(lid)
    if "NONET" in corrupt:
        target = rng.choice(sorted(P["terms"]))
        closed += [row["link"] for row, ends in zip(links, rows) if target in ends]
    if "SPAN" in corrupt:
        a = rng.randint(1, n - WIDTH - 1)
        b = a + WIDTH + 1
        links.append({"project": pid, "link": _fresh_link(rng, used), "a": ids[a], "b": ids[b], "band": "B1", "km": rng.randint(20, 40)})
    if "UNKNOWN" in corrupt or "CLOSED_UNKNOWN" in corrupt:
        stranger = "S%03d" % rng.choice([x for x in range(100, 1000) if "S%03d" % x not in ids])
        lid = _fresh_link(rng, used)
        links.append({"project": pid, "link": lid, "a": ids[rng.randint(1, n)], "b": stranger, "band": "B6", "km": rng.randint(5, 20)})
        if "CLOSED_UNKNOWN" in corrupt:
            closed.append(lid)
    if "DUP" in corrupt:
        q = rng.randint(1, n)
        sites.append([pid, ids[q], sites[q][2], rng.choice(sorted(CLASSES))])
    return sites, layout, links, closed, overrides


def _render(parts, rng, order, bands) -> dict[str, str]:
    sites, layout, links, closed, overrides = [], [], [], [], []
    for s, lay, k, c, o in parts:
        sites += s
        layout += lay
        links += k
        closed += c
        overrides += o
    rng.shuffle(sites)
    rng.shuffle(layout)
    rng.shuffle(links)
    toml = ["[corridors]", "order = [" + ", ".join('"%s"' % c for c in order) + "]", ""]
    for band, (base, per) in bands.items():
        toml += ["[tariff.%s]" % band, "base = %d" % base, "per_km = %d" % per, ""]
    toml += ["[closed]", "links = ["] + ['    "%s",' % lid for lid in sorted(closed)] + ["]"]
    ini = ["[classes]"] + ["%s = %d" % kv for kv in CLASSES.items()] + ["", "[overrides]"]
    ini += ["%s = %d" % kv for kv in sorted(overrides)]
    return {
        "sites.csv": "project,site,role,class\n" + "".join(",".join(r) + "\n" for r in sites),
        "layout.tsv": "project\tsite\tcorridor\tslot\n" + "".join("\t".join(r) + "\n" for r in layout),
        "links.jsonl": "".join(json.dumps(r) + "\n" for r in links),
        "access_rules.toml": "\n".join(toml) + "\n",
        "activation.ini": "\n".join(ini) + "\n",
    }


def _hub_features(P, chosen) -> tuple[bool, bool]:
    """(some site carries two or more links, some lit site other than the depot carries none)."""
    booked: dict[int, int] = {}
    lit = set(P["terms"])
    for lid in chosen:
        a, b = int(lid[1:4]), int(lid[4:7])
        booked[b] = booked.get(b, 0) + 1
        lit.update(x for x in (a, b) if x)
    return max(booked.values()) >= 2, any(booked.get(p, 0) == 0 for p in lit)


def _fresh_book_parts(seed: int):
    """Ten hub projects with 16 or 17 cold rooms, each with exactly one optimal network."""
    rng = random.Random(seed)
    order = CORRIDORS[:]
    rng.shuffle(order)
    used: set[str] = set()
    plans = []
    pids = ["P%04d" % x for x in rng.sample(range(1000, 10000), 10)]
    for pid in pids:
        while True:
            n = rng.randint(37, 51)
            P = _hub_project(rng, n, rng.randint(16, 17), rng.randint(65, 92), rng.randint(3, 6))
            found = _optimum(_as_project(P))
            if found is None or found[1] != 1:
                continue
            if all(_hub_features(P, found[2])):
                break
        assert n + 1 <= 52 and len(P["edges"]) <= 95 and 16 <= len(P["terms"]) <= 17
        plans.append((pid, P))
    return rng, order, used, plans


def _write_book(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    _open_tree(root)
    return root


def _make_fresh(seed: int, root: Path, bands=None) -> Path:
    rng, order, used, plans = _fresh_book_parts(seed)
    parts = [_encode(rng, pid, P, used, order) for pid, P in plans]
    return _write_book(root, _render(parts, rng, order, bands or BANDS))


def _make_rescaled(seed: int, root: Path) -> Path:
    """The first fresh book with its rows reshuffled and one tariff band's per_km rescaled."""
    rng, order, used, plans = _fresh_book_parts(seed)
    parts = [_encode(rng, pid, P, used, order) for pid, P in plans]
    for band, factor in (("B4", 7), ("B2", 5), ("B6", 3), ("B3", 7)):
        bands = dict(BANDS)
        base, per = bands[band]
        bands[band] = (base, per * factor // 2 + 1)
        book = _write_book(root, _render(parts, random.Random(seed ^ 0x5A5A), order, bands))
        if all(_optimum(p)[1] == 1 for p in _read_book(book)["accepted"].values()):
            return book
    raise AssertionError("no rescaled tariff keeps every optimum single")


def _make_rejections(seed: int, root: Path) -> Path:
    rng = random.Random(seed)
    order = CORRIDORS[:]
    rng.shuffle(order)
    used: set[str] = set()
    plan = [(), ("DUP",), ("UNKNOWN",), ("SPAN",), ("NONET",), ("DUP", "SPAN"), ("UNKNOWN", "SPAN"),
            ("SPAN", "NONET"), ("CLOSED_UNKNOWN",), ()]
    parts = []
    for k, corrupt in enumerate(plan):
        while True:
            n = rng.randint(12, 24)
            P = _hub_project(rng, n, rng.randint(4, 7), int(1.7 * n), rng.randint(2, 4))
            if _optimum(_as_project(P)) is not None:
                break
        parts.append(_encode(rng, "P%04d" % (2000 + 731 * k), P, used, order, corrupt))
    return _write_book(root, _render(parts, rng, order, BANDS))


def _make_ties(seed: int, root: Path) -> Path:
    """Six small projects, each with exactly two optimal networks."""
    rng = random.Random(seed)
    order = CORRIDORS[:]
    rng.shuffle(order)
    used: set[str] = set()
    parts = []
    for k in range(6):
        while True:
            n = rng.randint(5, 7)
            P = _tiny_project(rng, n, rng.randint(2, 3), rng.randint(n + 2, 11))
            found = _enumerate(_as_project(P))
            if found is not None and found[1] == 2:
                break
        parts.append(_encode(rng, "P%04d" % (5000 + 377 * k), P, used, order))
    return _write_book(root, _render(parts, rng, order, BANDS))


def _book(name: str) -> Path:
    def build() -> Path:
        root = _scratch("book-") / "book"
        if name == "fresh_1":
            return _make_fresh(BOOK_SEED, root)
        if name == "fresh_2":
            return _make_fresh(BOOK_SEED + 1, root)
        if name == "fresh_3":
            return _make_fresh(BOOK_SEED + 2, root)
        if name == "rescaled":
            return _make_rescaled(BOOK_SEED, root)
        if name == "relocated":
            return _make_fresh(BOOK_SEED + 1, _scratch("feeds-") / "book two")
        if name == "missing":
            book = _make_fresh(BOOK_SEED + 2, root)
            (book / "activation.ini").unlink()
            (book / "layout.tsv").unlink()
            return book
        if name == "rejections":
            return _make_rejections(BOOK_SEED + 3, root)
        if name == "ties":
            return _make_ties(BOOK_SEED + 4, root)
        raise KeyError(name)
    return _memo("book:" + name, build)


def _expected(name: str) -> dict[str, dict]:
    return _memo("expected:" + name, lambda: _expected_documents(_book(name), small=name == "ties"))


def _delivered(name: str, attempt: int = 1) -> dict[str, dict]:
    """The four documents the delivered package writes for one book."""
    def build() -> dict[str, dict]:
        book = _book(name)
        result, out = _run_cli(book, _book_projects(book), isolated=name == "relocated")
        assert result.returncode == 0, "exit %s: %s" % (result.returncode, result.stderr[-400:])
        return {doc: json.loads((out / doc).read_text(encoding="utf-8")) for doc in DOCUMENTS}
    return _memo("delivered:%s:%d" % (name, attempt), build)


# ---------------------------------------------------------------- comparison helpers

def _first_difference(want, got, path: str = "$") -> str | None:
    if isinstance(want, dict) and isinstance(got, dict):
        for key in sorted(set(want) | set(got)):
            if key not in got:
                return "%s.%s missing" % (path, key)
            if key not in want:
                return "%s.%s unexpected" % (path, key)
            found = _first_difference(want[key], got[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(want, list) and isinstance(got, list):
        for k, (a, b) in enumerate(zip(want, got)):
            found = _first_difference(a, b, "%s[%d]" % (path, k))
            if found:
                return found
        return None if len(want) == len(got) else "%s length %d != %d" % (path, len(got), len(want))
    if type(want) is not type(got) or want != got:
        return "%s: %r != %r" % (path, got, want)
    return None


def _same(label: str, want, got) -> None:
    found = _first_difference(want, got)
    assert found is None, "%s differs first at %s" % (label, found)


# ---------------------------------------------------------------- checks

def _check_archive_layout():
    config = json.loads((_data_dir() / "build_config.json").read_text(encoding="utf-8"))["archive"]
    with zipfile.ZipFile(_artifact("patched-repo.zip")) as zf:
        infos = zf.infolist()
    names = [info.filename for info in infos]
    assert names == sorted(names), "members are not sorted"
    for need in ("pyproject.toml", "src/task/__init__.py", "src/task/__main__.py", "src/task/core.py",
                 "src/task/parser.py", "src/task/report.py", "tests/test_visible.py"):
        assert need in names, "missing " + need
    stored = config["compression"] == "stored"
    for info in infos:
        assert "__pycache__" not in info.filename and not info.filename.endswith(".pyc"), info.filename
        assert list(info.date_time) == list(config["timestamp"]), info.filename
        assert (info.compress_type == zipfile.ZIP_STORED) == stored, info.filename
        assert (info.external_attr >> 16) & 0o7777 == int(config["mode"], 8), info.filename
    repo = _extract_archive()
    meta = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    assert not meta["project"].get("dependencies"), "runtime dependencies listed"
    floor = meta["project"]["requires-python"].replace(" ", "")
    assert floor in (">=3.12", ">=3.11", ">=3.10", ">=3.9", ">=3.8"), floor
    assert meta["project"]["version"] == "2.18.5"
    probe = subprocess.run(_untrusted_command([sys.executable, "-B", "-c", "import task; print(task.VERSION)"]),
                           text=True, capture_output=True, env=_env(_scratch("home-"), repo / "src"),
                           cwd=_scratch("cwd-"), timeout=60)
    assert probe.stdout.strip() == "2.18.5", probe.stderr[-300:]


def _check_shipped(doc: str):
    want = _memo("expected:shipped", lambda: _expected_documents(_data_dir()))
    _same(doc, want[doc], _json_artifact(doc))


def _check_test_fixes():
    data = _data_dir()
    failing = set()
    for line in (data / "failing_tests.log").read_text(encoding="utf-8").splitlines():
        parts = line.split(" ")
        if len(parts) == 4 and parts[1].startswith("(") and parts[2] == "..." and parts[3] in ("FAIL", "ERROR"):
            failing.add(parts[0])
    quotes = {}
    for line in (data / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        quotes[case["case"]] = _case_outcome(case)
    _same("test_fixes.json", {"previously_failing": sorted(failing), "regression_quotes": quotes},
          _json_artifact("test_fixes.json"))


def _case_outcome(case: dict):
    names = [s["site"] for s in case["sites"]]
    if len(names) != len(set(names)):
        return "E_DUP_SITE"
    pos = {s["site"]: s["position"] for s in case["sites"]}
    if any(k["a"] not in pos or k["b"] not in pos for k in case["links"]):
        return "E_UNKNOWN_ENDPOINT"
    links = sorted((k["link"], *sorted((pos[k["a"]], pos[k["b"]])), k["cost"]) for k in case["links"])
    if any(lo > 0 and hi - lo > WIDTH for _l, lo, hi, _c in links):
        return "E_BAD_SPAN"
    by_pos = sorted(case["sites"], key=lambda s: s["position"])
    proj = {"n": len(by_pos) - 1, "charge": [s["charge"] for s in by_pos],
            "cold": {s["position"] for s in by_pos if s["role"] == "cold_room"}, "links": links}
    found = _optimum(proj)
    return "E_NO_NETWORK" if found is None else found[0]


def _check_repair_report():
    report = _json_artifact("repair-report.json")
    assert report["defects"] and all(
        isinstance(d["file"], str) and d["file"] and isinstance(d["summary"], str) and d["summary"]
        for d in report["defects"])
    assert report["checks"] and all(isinstance(c, str) and c for c in report["checks"])


def _check_fresh(name: str, doc: str):
    _same("%s %s" % (name, doc), _expected(name)[doc], _delivered(name)[doc])


def _check_fresh_feasible():
    """Every delivered network joins the depot and the cold rooms, and its quote is its own cost."""
    for name in ("fresh_1", "fresh_2", "fresh_3"):
        book = _read_book(_book(name))
        core = _delivered(name)["module_core.json"]["projects"]
        assert sorted(core) == sorted(book["accepted"]), name + " project set"
        for pid, entry in core.items():
            proj = book["accepted"][pid]
            chosen = [link for link in proj["links"] if link[0] in set(entry["links"])]
            assert len(chosen) == len(entry["links"]) == len(set(entry["links"])), pid + " unknown or closed link"
            cost = _network_cost(proj, chosen)
            assert cost is not None, pid + " network leaves a cold room out"
            assert entry["quote"] == cost, pid + " quote is not the cost of its own network"
            lit = {0} | proj["cold"] | {p for _l, lo, hi, _c in chosen for p in (lo, hi)}
            assert entry["sites"] == sorted(proj["ids"][p] for p in lit), pid + " activated sites"


def _check_fresh_rollups_follow_network():
    """Report lines are charged from the package's own network, whatever its cost."""
    for name in ("fresh_1", "fresh_2", "fresh_3"):
        book = _read_book(_book(name))
        got = _delivered(name)
        for pid, entry in got["module_core.json"]["projects"].items():
            want = _project_rollup(book["accepted"][pid], entry["links"], entry["quote"])
            _same("%s %s report" % (name, pid), want, got["module_report.json"]["projects"][pid])


def _check_missing_file():
    book = _book("missing")
    result, out = _run_cli(book, _book_projects(book) if (book / "sites.csv").exists() else 10)
    assert result.returncode != 0, "exit code 0 with layout.tsv and activation.ini absent"
    assert "E_MISSING_FILE layout.tsv" in result.stderr.splitlines(), result.stderr[-300:]
    assert not any((out / doc).exists() for doc in DOCUMENTS), "documents written for an incomplete book"


def _tree_digest(root: Path) -> list[tuple[str, bytes]]:
    return sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob("*") if p.is_file())


def _check_rerun_identical():
    first = _delivered("fresh_1")
    second = _delivered("fresh_1", attempt=2)
    for doc in DOCUMENTS:
        _same("second run " + doc, first[doc], second[doc])
    pristine = _make_fresh(BOOK_SEED, _scratch("pristine-") / "book")
    assert _tree_digest(_book("fresh_1")) == _tree_digest(pristine), "the book folder changed during the runs"


def _replays_shipped_output() -> bool:
    """The fresh-book run hands back the shipped book's documents."""
    fresh = _delivered("fresh_1")
    for doc in ("module_core.json", "module_report.json"):
        shipped = _json_artifact(doc)
        if fresh[doc].get("projects") and fresh[doc] == shipped:
            return True
    return False


def _visible_tests_removed() -> bool:
    path = _extract_archive() / "tests" / "test_visible.py"
    if not path.is_file():
        return True
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    if VISIBLE_TESTS - names:
        return True
    for node in ast.walk(tree):
        word = node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""
        if word in {"skip", "skipIf", "skipUnless", "skipTest", "SkipTest", "expectedFailure"}:
            return True
    return False


def _holds(check, *args) -> bool:
    try:
        check(*args)
        return True
    except Exception as exc:
        print("%s: %s" % (getattr(check, "__name__", "check"), exc), file=sys.stderr)
        return False


def _fires(probe) -> bool:
    try:
        return bool(probe())
    except Exception:
        return False


def _write_corpus(target: str) -> None:
    """Write every fresh book and its expected documents under target (author tooling)."""
    root = Path(target)
    for name in ("fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "missing", "rejections", "ties"):
        book = _book(name)
        shutil.copytree(book, root / name, dirs_exist_ok=True)
        if name != "missing":
            for doc, body in _expected(name).items():
                (root / ("%s.expected" % name)).mkdir(parents=True, exist_ok=True)
                (root / ("%s.expected" % name) / doc).write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    _write_corpus(sys.argv[1])


# ---------------------------------------------------------------- criteria

@criterion(description="patched-repo.zip follows build_config.json and the package imports as version 2.18.5 with no dependencies")
def archive_follows_build_config(workspace: Path) -> bool:
    return _holds(_check_archive_layout)


@criterion(description="module_core.json for the shipped book matches the contract whole")
def shipped_core_document(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_core.json")


@criterion(description="module_parser.json for the shipped book matches the contract whole")
def shipped_parser_document(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_parser.json")


@criterion(description="module_report.json for the shipped book matches the contract whole")
def shipped_report_document(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_report.json")


@criterion(description="summary.json for the shipped book matches the contract whole")
def shipped_summary_document(workspace: Path) -> bool:
    return _holds(_check_shipped, "summary.json")


@criterion(description="test_fixes.json names every test the log marks FAIL or ERROR and carries every regression case outcome")
def test_fixes_document(workspace: Path) -> bool:
    return _holds(_check_test_fixes)


@criterion(description="repair-report.json lists defects with file and summary and at least one check")
def repair_report_fields(workspace: Path) -> bool:
    return _holds(_check_repair_report)


@criterion(description="Fresh book 1: module_core.json written by the archived package matches whole")
def fresh_1_core(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_1", "module_core.json")


@criterion(description="Fresh book 2: module_core.json written by the archived package matches whole")
def fresh_2_core(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_2", "module_core.json")


@criterion(description="Fresh book 3: module_core.json written by the archived package matches whole")
def fresh_3_core(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_3", "module_core.json")


@criterion(description="Fresh book 1: module_report.json written by the archived package matches whole")
def fresh_1_report(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_1", "module_report.json")


@criterion(description="Fresh book 2: module_report.json written by the archived package matches whole")
def fresh_2_report(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_2", "module_report.json")


@criterion(description="Fresh book 3: module_report.json written by the archived package matches whole")
def fresh_3_report(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_3", "module_report.json")


@criterion(description="Fresh book 1: summary.json written by the archived package matches whole")
def fresh_1_summary(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_1", "summary.json")


@criterion(description="Fresh book 2: summary.json written by the archived package matches whole")
def fresh_2_summary(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_2", "summary.json")


@criterion(description="Fresh book 3: summary.json written by the archived package matches whole")
def fresh_3_summary(workspace: Path) -> bool:
    return _holds(_check_fresh, "fresh_3", "summary.json")


@criterion(description="Every network written for the fresh books joins the depot and all cold rooms and is quoted at its own cost")
def fresh_networks_feasible(workspace: Path) -> bool:
    return _holds(_check_fresh_feasible)


@criterion(description="Fresh-book report lines are charged from the package's own network")
def fresh_rollups_follow_network(workspace: Path) -> bool:
    return _holds(_check_fresh_rollups_follow_network)


@criterion(description="A reshuffled fresh book with a rescaled tariff band gives the four documents whole")
def rescaled_book_documents(workspace: Path) -> bool:
    return _holds(lambda: [_check_fresh("rescaled", doc) for doc in DOCUMENTS])


@criterion(description="A fresh book in a relocated folder, run with python -I from another directory, gives the four documents whole")
def relocated_book_documents(workspace: Path) -> bool:
    return _holds(lambda: [_check_fresh("relocated", doc) for doc in DOCUMENTS])


@criterion(description="A book without layout.tsv and activation.ini exits non-zero with E_MISSING_FILE layout.tsv and writes no document")
def missing_file_reported(workspace: Path) -> bool:
    return _holds(_check_missing_file)


@criterion(description="A fresh book of faulty projects gives module_parser.json whole")
def rejection_book_parser(workspace: Path) -> bool:
    return _holds(_check_fresh, "rejections", "module_parser.json")


@criterion(description="A fresh book of projects with two optimal networks gives module_core.json whole")
def tie_book_core(workspace: Path) -> bool:
    return _holds(_check_fresh, "ties", "module_core.json")


@criterion(description="Running the package twice on one fresh book gives identical documents and leaves the book folder unchanged")
def rerun_identical(workspace: Path) -> bool:
    return _holds(_check_rerun_identical)


@criterion(description="The fresh-book run returns the shipped book's documents")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _fires(_replays_shipped_output)


@criterion(description="The archive drops or skips a shipped visible test")
def negative_visible_tests_removed(workspace: Path) -> bool:
    return _fires(_visible_tests_removed)


criteria.archive_follows_build_config(weight=1)
criteria.shipped_core_document(weight=5)
criteria.shipped_parser_document(weight=3)
criteria.shipped_report_document(weight=5)
criteria.shipped_summary_document(weight=3)
criteria.test_fixes_document(weight=3)
criteria.repair_report_fields(weight=1)
criteria.fresh_1_core(weight=5)
criteria.fresh_2_core(weight=5)
criteria.fresh_3_core(weight=5)
criteria.fresh_1_report(weight=5)
criteria.fresh_2_report(weight=5)
criteria.fresh_3_report(weight=5)
criteria.fresh_1_summary(weight=3)
criteria.fresh_2_summary(weight=3)
criteria.fresh_3_summary(weight=3)
criteria.fresh_networks_feasible(weight=3)
criteria.fresh_rollups_follow_network(weight=3)
criteria.rescaled_book_documents(weight=5)
criteria.relocated_book_documents(weight=3)
criteria.missing_file_reported(weight=3)
criteria.rejection_book_parser(weight=3)
criteria.tie_book_core(weight=3)
criteria.rerun_identical(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_visible_tests_removed(weight=-3)
