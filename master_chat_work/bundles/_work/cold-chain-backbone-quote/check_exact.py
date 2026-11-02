"""Independent recompute of the oracle's documents (G9).

Small cases: exhaustive enumeration over every link subset (quote and tie pick).
Shipped book: node-weighted Dreyfus-Wagner for the quote, plus feasibility and
charging lines rebuilt from the raw book files. Probes: removing overrides,
the closed list or numeric slot order must change the documents.
Usage: python3 check_exact.py <out dir> <ci dir> [src dir] [tie_cases.jsonl]
       python3 check_exact.py --ties <tie book dir> <expected documents dir>
"""
from __future__ import annotations

import configparser
import csv
import heapq
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from itertools import combinations
from pathlib import Path


def connected(nodes: set, links: list, need: set) -> bool:
    adj: dict = {}
    for _, a, b, _c in links:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    start = next(iter(need))
    seen = {start}
    todo = [start]
    while todo:
        v = todo.pop()
        for w in adj.get(v, []):
            if w not in seen:
                seen.add(w)
                todo.append(w)
    return need <= seen


def enumerate_case(depot, cold, charge, links):
    """links: list of (id, a, b, cost) open links. Returns (quote, chosen ids, n optima) or None."""
    need = {depot} | set(cold)
    ordered = sorted(links)
    best = None
    winners = []
    n = len(ordered)
    for mask in range(1 << n):
        chosen = [ordered[i] for i in range(n) if mask >> i & 1]
        if len(need) > 1 and not chosen:
            continue
        if chosen and not connected(set(), chosen, need):
            continue
        sites = set(need)
        for _, a, b, _c in chosen:
            sites.update((a, b))
        if len(need) > 1:
            # every activated site must hang on the network joining the depot
            if not connected(set(), chosen, sites):
                continue
        quote = sum(c for *_, c in chosen) + sum(charge[s] for s in sites)
        vector = tuple(mask >> i & 1 for i in range(n))
        if best is None or quote < best:
            best, winners = quote, [vector]
        elif quote == best:
            winners.append(vector)
    if best is None:
        return None
    pick = min(winners)
    return best, [ordered[i][0] for i in range(n) if pick[i]], len(winners)


def case_outcome(case):
    seen = set()
    for s in case["sites"]:
        if s["site"] in seen:
            return "E_DUP_SITE"
        seen.add(s["site"])
    pos = {s["site"]: s["position"] for s in case["sites"]}
    for l in case["links"]:
        if l["a"] not in pos or l["b"] not in pos:
            return "E_UNKNOWN_ENDPOINT"
    depot = next(s["site"] for s in case["sites"] if s["role"] == "depot")
    cold = [s["site"] for s in case["sites"] if s["role"] == "cold_room"]
    charge = {s["site"]: s["charge"] for s in case["sites"]}
    links = [(l["link"], l["a"], l["b"], l["cost"]) for l in case["links"]]
    if cold and not connected(set(), links, {depot, *cold}):
        return "E_NO_NETWORK"
    return enumerate_case(depot, cold, charge, links)


def dreyfus_wagner(depot, cold, charge, links):
    adj: dict = {}
    for _, a, b, c in links:
        adj.setdefault(a, []).append((b, c))
        adj.setdefault(b, []).append((a, c))
    nodes = list(charge)
    k = len(cold)
    if k == 0:
        return charge[depot]
    inf = float("inf")
    dp = [None] * (1 << k)
    for mask in range(1, 1 << k):
        row = {v: inf for v in nodes}
        if mask & (mask - 1) == 0:
            row[cold[mask.bit_length() - 1]] = charge[cold[mask.bit_length() - 1]]
        else:
            sub = (mask - 1) & mask
            while sub:
                if sub < mask ^ sub:
                    left, right = dp[sub], dp[mask ^ sub]
                    for v in nodes:
                        value = left[v] + right[v] - charge[v]
                        if value < row[v]:
                            row[v] = value
                sub = (sub - 1) & mask
        heap = [(d, v) for v, d in row.items() if d < inf]
        heapq.heapify(heap)
        while heap:
            d, v = heapq.heappop(heap)
            if d > row[v]:
                continue
            for w, c in adj.get(v, []):
                nd = d + c + charge[w]
                if nd < row[w]:
                    row[w] = nd
                    heapq.heappush(heap, (nd, w))
        dp[mask] = row
    return dp[(1 << k) - 1][depot]


def read_book(book: Path):
    rules = tomllib.loads((book / "access_rules.toml").read_text(encoding="utf-8"))
    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str
    ini.read(book / "activation.ini", encoding="utf-8")
    closed = set(rules["closed"]["links"])
    order = {name: i for i, name in enumerate(rules["corridors"]["order"])}
    projects: dict = {}
    with open(book / "sites.csv", newline="", encoding="utf-8") as h:
        for r in csv.DictReader(h):
            p = projects.setdefault(r["project"], {"sites": {}, "links": [], "place": {}})
            charge = int(ini["overrides"].get(f"{r['project']}/{r['site']}", ini["classes"][r["class"]]))
            p["sites"][r["site"]] = (r["role"], charge)
    with open(book / "layout.tsv", newline="", encoding="utf-8") as h:
        for r in csv.DictReader(h, delimiter="\t"):
            projects[r["project"]]["place"][r["site"]] = (order[r["corridor"]], int(r["slot"]), r["corridor"])
    for line in (book / "links.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["link"] not in closed:
                band = rules["tariff"][r["band"]]
                projects[r["project"]]["links"].append((r["link"], r["a"], r["b"], band["base"] + band["per_km"] * r["km"]))
    return projects


def lines_of(p, links):
    ranked = sorted(p["place"], key=lambda s: p["place"][s][:2])
    pos = {s: i + 1 for i, s in enumerate(ranked)}
    depot = next(s for s, (role, _) in p["sites"].items() if role == "depot")
    pos[depot] = 0
    cost = {l[0]: l for l in p["links"]}
    active = {depot} | {s for s, (role, _) in p["sites"].items() if role == "cold_room"}
    for lid in links:
        active.update(cost[lid][1:3])
    total = {s: p["sites"][s][1] for s in active}
    for lid in links:
        _, a, b, c = cost[lid]
        total[a if pos[a] > pos[b] else b] += c
    return depot, total


def check_book(out: Path, book: Path) -> int:
    core = json.loads((out / "module_core.json").read_text())["projects"]
    report = json.loads((out / "module_report.json").read_text())["projects"]
    projects = read_book(book)
    bad = 0
    for pid, net in core.items():
        p = projects[pid]
        depot = next(s for s, (role, _) in p["sites"].items() if role == "depot")
        cold = sorted(s for s, (role, _) in p["sites"].items() if role == "cold_room")
        charge = {s: c for s, (_, c) in p["sites"].items()}
        quote = dreyfus_wagner(depot, cold, charge, p["links"])
        chosen = [l for l in p["links"] if l[0] in set(net["links"])]
        feasible = connected(set(), chosen, {depot, *cold}) if cold else True
        _, total = lines_of(p, net["links"])
        rebuilt = sum(total.values())
        sites_ok = sorted(total) == net["sites"]
        lines_ok = all(report[pid]["sites"][s]["total"] == t for s, t in total.items() if s != depot)
        lines_ok = lines_ok and report[pid]["depot"]["total"] == total[depot]
        if not (quote == net["quote"] == rebuilt and feasible and sites_ok and lines_ok):
            bad += 1
            print("BOOK MISMATCH", pid, quote, net["quote"], rebuilt, feasible, sites_ok, lines_ok)
    print(f"book projects checked {len(core)} mismatches {bad} (Dreyfus-Wagner quote, feasibility, lines)")
    return bad


def check_cases(out: Path, cases_path: Path, label: str, expect_ties: bool = False) -> int:
    fixes = json.loads((out / "test_fixes.json").read_text())["regression_quotes"] if not expect_ties else None
    bad = ties = 0
    rows = [json.loads(x) for x in cases_path.read_text().splitlines() if x.strip()]
    for case in rows:
        got = case_outcome(case)
        if isinstance(got, str) or got is None:
            want = got if got is not None else "E_NO_NETWORK"
            if not expect_ties and fixes[case["case"]] != want:
                bad += 1
            continue
        quote, chosen, count = got
        ties += count > 1
        if expect_ties:
            if count != 2 or chosen != case["expect_links"] or quote != case["expect_quote"]:
                bad += 1
                print("TIE MISMATCH", case["case"], quote, chosen, count, case["expect_links"])
        elif fixes[case["case"]] != quote:
            bad += 1
            print("CASE MISMATCH", case["case"], quote, fixes[case["case"]])
    print(f"{label}: {len(rows)} checked by enumeration, {ties} with tied optima, mismatches {bad}")
    return bad


def probes(book: Path, src: Path) -> int:
    """Each stated input rule must move the documents when its input is altered."""
    base = Path(tempfile.mkdtemp(prefix="probe-"))

    def run(dirname: str) -> bytes:
        out = base / ("out-" + dirname)
        subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(base / dirname), "--out", str(out)],
                       env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"}, check=True)
        return b"".join((out / n).read_bytes() for n in sorted(p.name for p in out.iterdir()))

    def variant(dirname: str, edit) -> None:
        shutil.copytree(book, base / dirname)
        edit(base / dirname)

    shutil.copytree(book, base / "orig")
    ref = run("orig")

    def no_overrides(d: Path) -> None:
        text = (d / "activation.ini").read_text()
        (d / "activation.ini").write_text(text.split("[overrides]")[0] + "[overrides]\n")

    def no_closed(d: Path) -> None:
        text = (d / "access_rules.toml").read_text()
        head, _, tail = text.partition("[closed]")
        (d / "access_rules.toml").write_text(head + "[closed]\nlinks = []\n")

    def text_slots(d: Path) -> None:
        rows = (d / "layout.tsv").read_text().splitlines()
        out = [rows[0]] + ["\t".join(r.split("\t")[:3] + [str(1000 - int(r.split("\t")[3]))]) for r in rows[1:]]
        (d / "layout.tsv").write_text("\n".join(out) + "\n")

    bad = 0
    for name, edit in (("no_overrides", no_overrides), ("no_closed", no_closed), ("reversed_slots", text_slots)):
        variant(name, edit)
        moved = run(name) != ref
        print(f"probe {name}: documents moved {moved}")
        bad += not moved
    shutil.rmtree(base)
    return bad


def check_tie_book(book: Path, expected: Path) -> int:
    """Hidden tie book T: each project must have exactly two optima; the pick is confirmed by enumeration."""
    core = json.loads((expected / "module_core.json").read_text())["projects"]
    bad = 0
    for pid, p in sorted(read_book(book).items()):
        depot = next(s for s, (role, _) in p["sites"].items() if role == "depot")
        cold = [s for s, (role, _) in p["sites"].items() if role == "cold_room"]
        charge = {s: c for s, (_, c) in p["sites"].items()}
        quote, chosen, count = enumerate_case(depot, cold, charge, p["links"])
        ok = count == 2 and chosen == core[pid]["links"] and quote == core[pid]["quote"]
        bad += not ok
        print(f"tie {pid}: optima {count} quote {quote} pick {chosen} reference {core[pid]['links']} {'ok' if ok else 'MISMATCH'}")
    print(f"tie book T: {len(core)} projects, mismatches {bad}")
    return bad


def main() -> int:
    if sys.argv[1] == "--ties":
        bad = check_tie_book(Path(sys.argv[2]), Path(sys.argv[3]))
        print("CHECK_EXACT", "PASS" if bad == 0 else f"FAIL {bad}")
        return 1 if bad else 0
    out, book = Path(sys.argv[1]), Path(sys.argv[2])
    src = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    bad = check_cases(out, book / "regression_cases.jsonl", "regression cases")
    bad += check_book(out, book)
    if src:
        bad += probes(book, src)
    if len(sys.argv) > 4:
        bad += check_cases(out, Path(sys.argv[4]), "tie book T", expect_ties=True)
    print("CHECK_EXACT", "PASS" if bad == 0 else f"FAIL {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
