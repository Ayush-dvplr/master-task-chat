"""Wave 1 cost-table deliveries: python3 -B w1_variants.py <oracle app> <variant> <target app>.

A solver variant keeps the oracle package and swaps core.best_network for one
generic solver from proto/solvers.py; a package variant swaps the whole
src/task directory for an earlier program (span limit lifted). The archive and
the four documents are rebuilt from the swapped package on the shipped book.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import variants

HERE = Path(__file__).resolve().parent
PROTO = HERE / "proto"
SOLVERS = ("lastuse_corridor", "lastuse_greedy", "frontier_corridor", "frontier_bfs", "dw_global",
           "kmb", "sph", "greedy", "naive_subset", "hybrid")
PACKAGES = ("blind_2611_nospan", "blind_d7a0_nospan", "probe_nospan", "blind_2611", "blind_d7a0", "probe")


def _old_frontier() -> str:
    text = (HERE / "runs/pre_w1/test_template.py").read_text()
    tree = ast.parse(text)
    keep = [ast.get_source_segment(text, node) for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in ("_relabel", "_optimum")]
    return "WIDTH = 4\n\n\n" + "\n\n\n".join(keep) + "\n"


def alt_module() -> str:
    ref = (PROTO / "ref.py").read_text()
    solvers = (PROTO / "solvers.py").read_text().replace("import ref\n", "").replace("ref._dw(", "_dw(")
    solvers = solvers.replace("from __future__ import annotations\n", "")
    return "\n\n".join([ref, solvers, _old_frontier(), '''
import sys as _sys


def run(name, proj):
    me = _sys.modules[__name__]
    if name == "lastuse_corridor":
        return frontier_lastuse(proj, list(range(proj["n"] + 1)))
    if name == "lastuse_greedy":
        return frontier_lastuse(proj, greedy_order(proj))
    if name == "frontier_corridor":
        return frontier(me, proj)
    if name == "frontier_bfs":
        return frontier(me, proj, bfs_order(proj))
    if name == "hybrid":
        if len(proj["cold"]) <= 14:
            return dw_global(proj)
        return frontier_lastuse(proj, list(range(proj["n"] + 1)))
    return {"dw_global": dw_global, "kmb": kmb, "sph": sph, "greedy": greedy,
            "naive_subset": naive_subset}[name](proj)
'''])


PATCH = '''

from . import _alt


def best_network(project: Project) -> Network:
    proj = {"n": project.size, "charge": list(project.charges), "cold": set(project.cold),
            "links": list(project.links)}
    quote, links = _alt.run(%r, proj)
    links = tuple(links)
    return Network(quote_of(project, links), links, tuple(sorted(activated(project, links))))
'''


def main() -> None:
    oracle, variant, target = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(oracle, target)
    task = target / "repo/src/task"
    if variant in SOLVERS:
        (task / "_alt.py").write_text(alt_module())
        core = task / "core.py"
        core.write_text(core.read_text() + PATCH % variant)
    elif variant in PACKAGES:
        shutil.rmtree(task)
        shutil.copytree(PROTO / variant / "src/task", task)
    else:
        raise SystemExit("unknown variant " + variant)
    for cache in target.rglob("__pycache__"):
        shutil.rmtree(cache)
    variants.rezip(target)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONPATH": str(target / "repo/src"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    limit = 4 * 96 + 10
    try:
        subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(target / "ci"), "--out",
                        str(target / "out")], env=env, check=True, timeout=limit)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        for name in ("module_core.json", "module_parser.json", "module_report.json", "summary.json"):
            (target / "out" / name).unlink(missing_ok=True)
        print(variant, "did not finish the shipped book within", limit, "s:", type(exc).__name__)


if __name__ == "__main__":
    main()
