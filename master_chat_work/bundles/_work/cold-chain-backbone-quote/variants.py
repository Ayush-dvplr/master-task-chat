"""Build wrong-reading variants of the oracle delivery for the cost table.

Usage: variants.py <oracle app root> <variant> <target app root>
Each variant takes the repaired package, changes one reading, rebuilds the
archive per build_config and regenerates the four computed documents.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHIPPED_CORE = HERE.parent.parent / "cold-chain-backbone-quote/environment/repo/src/task/core.py"

TUNED_DW = '''

def _dw_quote(project):
    """Node-weighted Dreyfus-Wagner over cold-room subsets, tuned for CPython.

    Bitmask subsets; only splits holding the lowest cold room; merges only at
    cold rooms and sites with three or more links (a path through any other
    site is covered by the Dijkstra step); small-int sentinel; local bindings;
    the shared node charge is taken off once in the merge; one Dijkstra per subset.
    """
    import heapq
    size = len(project.charges)
    charge = list(project.charges)
    adjacent = [[] for _ in range(size)]
    for _lid, pa, pb, cost in project.links:
        adjacent[pa].append((pb, cost + charge[pb]))
        adjacent[pb].append((pa, cost + charge[pa]))
    cold = sorted(project.cold)
    k = len(cold)
    if k == 0:
        return charge[0]
    big = 10 ** 9
    joints = [v for v in range(size) if v in project.cold or len(adjacent[v]) >= 3]
    rows = [None] * (1 << k)
    push, pop = heapq.heappush, heapq.heappop
    for mask in range(1, 1 << k):
        row = [big] * size
        if mask & (mask - 1) == 0:
            t = cold[mask.bit_length() - 1]
            row[t] = charge[t]
        else:
            low = mask & -mask
            part = (mask - 1) & mask
            while part:
                if part & low:
                    x = rows[part]
                    y = rows[mask ^ part]
                    for v in joints:
                        s = x[v] + y[v]
                        if s < row[v]:
                            row[v] = s
                part = (part - 1) & mask
            for v in joints:
                if row[v] < big:
                    row[v] -= charge[v]
        heap = [(d, v) for v, d in enumerate(row) if d < big]
        heapq.heapify(heap)
        while heap:
            d, v = pop(heap)
            if d > row[v]:
                continue
            for w, c in adjacent[v]:
                nd = d + c
                if nd < row[w]:
                    row[w] = nd
                    push(heap, (nd, w))
        rows[mask] = row
    return rows[(1 << k) - 1][0]
'''

GREEDY = '''

def _greedy_links(project):
    """Grow from the depot, attaching the cheapest unconnected cold room by a shortest path."""
    import heapq
    adjacent = {}
    for lid, pa, pb, cost in project.links:
        adjacent.setdefault(pa, []).append((pb, lid, cost))
        adjacent.setdefault(pb, []).append((pa, lid, cost))
    tree = {0}
    chosen = set()
    waiting = set(project.cold)
    while waiting:
        dist = {v: 0 for v in tree}
        back = {}
        heap = [(0, v) for v in sorted(tree)]
        heapq.heapify(heap)
        while heap:
            d, v = heapq.heappop(heap)
            if d > dist[v]:
                continue
            for w, lid, cost in adjacent.get(v, []):
                nd = d + cost + (0 if w in tree else project.charges[w])
                if nd < dist.get(w, float("inf")):
                    dist[w] = nd
                    back[w] = (v, lid)
                    heapq.heappush(heap, (nd, w))
        target = min(waiting, key=lambda t: (dist[t], t))
        step = target
        while step not in tree:
            v, lid = back[step]
            chosen.add(lid)
            tree.add(step)
            step = v
        waiting -= tree
    return tuple(sorted(chosen))
'''

PER_LINK_LINES = '''

def site_lines(project, links):
    """Per-link charging: each booked link brings its later end's charge again."""
    chosen = set(links)
    lines = {0: project.charges[0]}
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            lines[pb] = lines.get(pb, 0) + cost + project.charges[pb]
    return lines
'''


def patch_core(core: Path, variant: str) -> None:
    text = core.read_text()
    if variant == "kmb":
        shipped = SHIPPED_CORE.read_text()
        start = shipped.index("def _adjacency")
        end = shipped.index("def site_lines")
        kmb = shipped[start:end].replace("def best_network", "def _kmb_network")
        text = "import heapq\n" + text.replace("from __future__ import annotations\n", "") + "\n\n" + kmb
        text += "\n\ndef best_network(project):\n    return _kmb_network(project)\n"
        text = "from __future__ import annotations\n" + text
    elif variant == "greedy":
        text += GREEDY + (
            "\n\n_exact_network = best_network\n\n\ndef best_network(project):\n"
            "    links = _greedy_links(project)\n"
            "    return Network(quote_of(project, links), links, tuple(sorted(activated(project, links))))\n")
    elif variant == "dw":
        text += TUNED_DW + (
            "\n\n_exact_network = best_network\n\n\ndef best_network(project):\n"
            "    quote = _dw_quote(project)\n"
            "    net = _exact_network(project)\n"
            "    assert net.quote == quote\n"
            "    return net\n")
    elif variant == "perlink":
        # wrong charging feeds the quote and every report line
        text += PER_LINK_LINES + (
            "\n\n_exact_network = best_network\n\n\ndef best_network(project):\n"
            "    net = _exact_network(project)\n"
            "    return Network(quote_of(project, net.links), net.links, net.sites)\n")
    elif variant == "report_only":
        text += PER_LINK_LINES
    else:
        raise SystemExit(f"unknown core variant {variant}")
    core.write_text(text)


def rezip(app: Path) -> None:
    config = json.loads((app / "ci/build_config.json").read_text())["archive"]
    out = app / "out/patched-repo.zip"
    out.unlink()
    method = zipfile.ZIP_STORED if config["compression"] == "stored" else zipfile.ZIP_DEFLATED
    repo = app / "repo"
    with zipfile.ZipFile(out, "w") as archive:
        for path in sorted(p for p in repo.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(path.relative_to(repo).as_posix(), tuple(config["timestamp"]))
            info.compress_type = method
            info.external_attr = (0o100000 | int(config["mode"], 8)) << 16
            archive.writestr(info, path.read_bytes())


def main() -> None:
    oracle, variant, target = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(oracle, target)
    if variant == "nop":
        shutil.rmtree(target / "out")
        (target / "out").mkdir()
        return
    if variant == "copier":
        # a program that hands back the shipped documents for any book
        saved = target / "repo/src/task/shipped_documents.json"
        saved.write_text(json.dumps({d: json.loads((target / "out" / d).read_text()) for d in (
            "module_core.json", "module_parser.json", "module_report.json", "summary.json")}))
        (target / "repo/src/task/__main__.py").write_text(
            "import argparse\nimport json\nfrom pathlib import Path\n\n"
            "parser = argparse.ArgumentParser()\nparser.add_argument('--book')\nparser.add_argument('--out', type=Path)\n"
            "args = parser.parse_args()\nargs.out.mkdir(parents=True, exist_ok=True)\n"
            "for name, doc in json.loads((Path(__file__).parent / 'shipped_documents.json').read_text()).items():\n"
            "    (args.out / name).write_text(json.dumps(doc, indent=2, sort_keys=True) + '\\n')\n")
    else:
        patch_core(target / "repo/src/task/core.py", variant)
    rezip(target)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONPATH": str(target / "repo/src"), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(target / "ci"), "--out", str(target / "out")],
                   env=env, check=True)


if __name__ == "__main__":
    main()
