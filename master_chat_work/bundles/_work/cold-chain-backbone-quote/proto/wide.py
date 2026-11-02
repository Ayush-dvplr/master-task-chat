"""Prototype wide-book generator: blocks joined at cut sites, positions shuffled."""
from __future__ import annotations

import random
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ref  # noqa: E402


def load_template():
    rk = types.ModuleType("rewardkit")
    class _C:
        def __getattr__(self, name):
            return lambda **k: None
    rk.criteria = _C()
    rk.criterion = lambda *a, **k: (lambda f: f)
    sys.modules["rewardkit"] = rk
    src = (HERE.parent / "test_template.py").read_text().replace("SHIPPED_DATA_LINE", "_SHIPPED_DATA = {}")
    mod = types.ModuleType("tt")
    mod.__file__ = str(HERE / "tt.py")
    exec(compile(src, "test_template.py", "exec"), mod.__dict__)
    return mod


def _block_edges(rng, verts, extra, depot_ok):
    """Cycle through verts plus `extra` chords; the depot keeps degree 2 unless depot_ok."""
    cyc = verts[:]
    rng.shuffle(cyc)
    if 0 in cyc:
        cyc.remove(0)
        cyc.insert(0, 0)
    edges = set()
    for a, b in zip(cyc, cyc[1:] + cyc[:1]):
        edges.add((min(a, b), max(a, b)))
    tries = 0
    while extra > 0 and tries < 2000:
        tries += 1
        a, b = rng.sample(verts, 2)
        if 0 in (a, b) and not depot_ok:
            continue
        e = (min(a, b), max(a, b))
        if e not in edges:
            edges.add(e)
            extra -= 1
    return edges


def wide_project(rng, n_blocks=(5, 6), size=(15, 18), cold=(4, 5), density=(2.4, 2.8)):
    act, edges, terms = {0: rng.randint(3, 9)}, {}, set()
    nxt = 1
    placed = []
    for k in range(rng.randint(*n_blocks)):
        s = rng.randint(*size)
        new = list(range(nxt, nxt + s))
        nxt += s
        top = 0 if k == 0 else rng.choice(placed)
        verts = [top] + new
        cheap = set()
        hub = new[0]
        spokes = new[1:4]
        act[hub] = rng.randint(10, 20)
        terms.update(spokes)
        sp = {}
        for q in spokes:
            sp[q] = rng.randint(1, 3)
            edges[(min(hub, q), max(hub, q))] = sp[q]
            cheap.add((min(hub, q), max(hub, q)))
        hubtree = act[hub] + sum(sp.values())
        for a, b in zip(spokes, spokes[1:]):
            lo = hubtree // 2 + 1
            hi = act[hub] + sp[a] + sp[b] - 1
            edges[(min(a, b), max(a, b))] = rng.randint(min(lo, hi), max(lo, hi))
        more = rng.randint(*cold) - 3
        terms.update(rng.sample(new[4:], more))
        for e in _block_edges(rng, verts, int(s * rng.uniform(*density)) - s, False):
            if e not in edges:
                edges[e] = rng.randint(8, 40)
        placed += new
    n = nxt - 1
    for q in range(1, n + 1):
        if q not in act:
            act[q] = rng.randint(2, 12) if q in terms else rng.randint(4, 30)
    perm = list(range(1, n + 1))
    rng.shuffle(perm)
    mp = {0: 0, **{q: perm[q - 1] for q in range(1, n + 1)}}
    return {
        "n": n,
        "terms": {mp[q] for q in terms},
        "act": {mp[q]: c for q, c in act.items()},
        "edges": {(min(mp[a], mp[b]), max(mp[a], mp[b])): c for (a, b), c in edges.items()},
    }


if __name__ == "__main__":
    tt = load_template()
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    rng = random.Random(seed)
    for i in range(int(sys.argv[2]) if len(sys.argv) > 2 else 5):
        P = wide_project(rng)
        proj = tt._as_project(P)
        t = time.time()
        got = ref.solve(proj)
        t1 = time.time() - t
        own = tt._network_cost(proj, [l for l in proj["links"] if l[0] in set(got[1])])
        t = time.time()
        u = ref.unique(proj, got)
        spans = sorted(b - a for _l, a, b, _c in proj["links"] if a)
        print(i, "n", P["n"], "cold", len(P["terms"]), "links", len(P["edges"]), "cost", got[0], own,
              "t %.3f" % t1, "uniq", u, "%.2f" % (time.time() - t), "span max", spans[-1], "median", spans[len(spans) // 2])
