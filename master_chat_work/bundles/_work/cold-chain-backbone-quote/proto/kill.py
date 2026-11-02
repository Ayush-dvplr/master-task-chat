"""Kill test driver.

  kill.py make <seed> <dir>      write a wide prototype book (10 projects) + expected.json
  kill.py fn <solver> <dir>      run one generic solver on every project, print per-project lines
  kill.py run <books...>         every solver and every package on every book, table to stdout
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ref  # noqa: E402
import solvers  # noqa: E402
import wide  # noqa: E402

tt = wide.load_template()
tt.WIDTH = 10 ** 9
PROJECTS = 10
LIMIT = 4 * PROJECTS + 10
PACKAGES = ["blind_2611", "blind_d7a0", "probe", "blind_2611_nospan", "blind_d7a0_nospan", "probe_nospan"]
FUNCS = ["lastuse_corridor", "lastuse_greedy", "frontier_corridor", "frontier_bfs", "dw_global", "kmb", "sph", "greedy", "naive_subset"]


def make(seed, root, **shape):
    rng = random.Random(seed)
    order = tt.CORRIDORS[:]
    rng.shuffle(order)
    used = set()
    parts = []
    for pid in ["P%04d" % x for x in rng.sample(range(1000, 10000), PROJECTS)]:
        while True:
            P = wide.wide_project(rng, **shape)
            proj = tt._as_project(P)
            got = ref.solve(proj)
            if got and ref.unique(proj, got):
                break
        parts.append(tt._encode(rng, pid, P, used, order))
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in tt._render(parts, rng, order, tt.BANDS).items():
        (root / name).write_text(text, encoding="utf-8")
    book = tt._read_book(root)
    picks = {pid: ref.solve(p) for pid, p in book["accepted"].items()}
    docs = tt._documents(book, picks)
    (root.parent / (root.name + ".expected.json")).write_text(json.dumps(docs, sort_keys=True))
    return book


def run_fn(name, root):
    book = tt._read_book(Path(root))
    for pid, proj in sorted(book["accepted"].items()):
        want = ref.solve(proj)
        t = time.time()
        if name == "frontier_corridor":
            got = solvers.frontier(tt, proj)
        elif name == "lastuse_corridor":
            got = solvers.frontier_lastuse(proj, list(range(proj["n"] + 1)))
        elif name == "lastuse_greedy":
            got = solvers.frontier_lastuse(proj, solvers.greedy_order(proj))
        elif name == "ref":
            got = ref.solve(proj)
        elif name == "ref2":
            import ref2
            got = ref2.solve(proj)
        elif name == "hybrid":
            if len(proj["cold"]) <= 14:
                got = solvers.dw_global(proj)
            else:
                got = solvers.frontier_lastuse(proj, list(range(proj["n"] + 1)))
        elif name == "frontier_bfs":
            got = solvers.frontier(tt, proj, solvers.bfs_order(proj))
        else:
            got = getattr(solvers, name)(proj)
        got = tuple(got) if got else got
        print(json.dumps({"pid": pid, "secs": round(time.time() - t, 3), "exact": got == tuple(want),
                          "cost": got[0] if got else None, "best": want[0]}), flush=True)


def _child(cmd, env=None):
    t = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=LIMIT, env=env)
        return res, time.time() - t, False
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return subprocess.CompletedProcess(cmd, -9, out, ""), time.time() - t, True


def run_all(books, funcs=None, pkgs=None):
    rows = []
    for root in books:
        root = Path(root)
        want = json.loads((root.parent / (root.name + ".expected.json")).read_text())
        for name in funcs or FUNCS:
            res, secs, late = _child([sys.executable, "-B", str(HERE / "kill.py"), "fn", name, str(root)])
            lines = [json.loads(x) for x in res.stdout.splitlines() if x.startswith("{")]
            exact = sum(x["exact"] for x in lines)
            slow = max([x["secs"] for x in lines] + [0])
            ok = not late and exact == PROJECTS
            rows.append((name, root.name, round(secs, 1), "timeout" if late else "%d/%d exact" % (exact, PROJECTS), slow, ok))
            print(rows[-1], flush=True)
        for pkg in PACKAGES if pkgs is None else pkgs:
            out = Path(tempfile.mkdtemp())
            env = {**os.environ, "PYTHONPATH": str(HERE / pkg / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
            res, secs, late = _child([sys.executable, "-B", "-m", "task", "--book", str(root), "--out", str(out)], env)
            note = "timeout" if late else "rc %d" % res.returncode
            ok = False
            if not late and res.returncode == 0:
                docs = {d: json.loads((out / d).read_text()) for d in want}
                same = [d for d in want if docs[d] == want[d]]
                core = docs["module_core.json"]["projects"]
                hit = sum(core.get(p) == v for p, v in want["module_core.json"]["projects"].items())
                note = "core %d/%d projects, docs equal: %s" % (hit, PROJECTS, ",".join(sorted(same)) or "none")
                ok = docs["module_core.json"] == want["module_core.json"]
            rows.append((pkg, root.name, round(secs, 1), note, None, ok))
            print(rows[-1], flush=True)
    return rows


if __name__ == "__main__":
    if sys.argv[1] == "make":
        b = make(int(sys.argv[2]), sys.argv[3])
        ps = b["accepted"].values()
        print("made", sys.argv[3], "projects", len(b["accepted"]), "rejected", b["rejected"],
              "cold", sorted(len(p["cold"]) for p in ps), "sites", sorted(p["n"] + 1 for p in ps))
    elif sys.argv[1] == "fn":
        run_fn(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "only":
        run_all(sys.argv[3:], sys.argv[2].split(","), [])
        print("ALL_DONE")
    else:
        run_all(sys.argv[2:])
        print("ALL_DONE")
