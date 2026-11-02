"""Scratch: Design 2 final gadget (_g_core) + kill solvers.

    python3 -B core2.py seeds N                 # generator asserts over N seeds
    python3 -B core2.py gen OUTDIR [first last] # core worlds -> contract folder + case.json
    python3 -B core2.py one NAME CASEDIR LIMIT  # run one solver on one case in this process
    python3 -B core2.py solve REPO_SRC CASEDIR  # one repo's plan_migration on the hard payload
    python3 -B core2.py reach CASEDIR CAP        # count reachable (schema, state) nodes up to CAP
"""

from __future__ import annotations

import heapq
import importlib.util
import json
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "rewardkit_stub"))
_spec = importlib.util.spec_from_file_location("tests_src", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)
_rng, _World, Spec, _val = T._rng, T._World, T.Spec, T._val

CORE_WORLDS = 8


# ---------------------------------------------------------------- the generator and reference now live in the tests
_bounded_plan = T._reference_plan


def core_world(index: int):
    """World number `index`, built exactly as the tests build world_<index> (index 29..36 are graded)."""
    names = list(T.WORLDS)
    if index <= len(names) and "CORE" in T.WORLDS[names[index - 1]]:
        return T._world(names[index - 1])
    w = _World(100 + index - 1, ("CORE",))
    T._g_core(w, index)
    return w.finish()
# ---------------------------------------------------------------- end of port


class Machine:
    """Compiled planner state: one int per (schema, field states); A=0 N=1 V=2 per base-3 digit."""

    def __init__(self, spec, start):
        self.dom = start.rsplit(".v", 1)[0]
        self.target = next(s for s in spec.canonical if s.rsplit(".v", 1)[0] == self.dom)
        pol = T._policy_map(spec)
        edges = sorted(e for e in spec.edges if e[1].rsplit(".v", 1)[0] == self.dom)
        self.names = sorted({x for e in edges for part in filter(None, (e[3] + ";" + e[4]).split(";"))
                             for x in part.split(":", 1)[1].replace(">", ":").split(":")[:2] if x not in ("int", "float", "str")})
        idx = {n: i for i, n in enumerate(self.names)}
        self.pw = [3 ** i for i in range(len(self.names))]
        self.size = 3 ** len(self.names)
        nullpresent = []
        overnull = []
        for n in self.names:
            row = pol.get((self.dom, n))
            nullpresent.append(T._counts(spec, pol, self.dom, n, "N"))
            overnull.append(bool(row) and (row[3] or spec.fill) == "absent_or_null")
            if not (row and row[2]):
                overnull[-1] = None  # add does nothing without a default
        self.nullpresent, self.overnull = nullpresent, overnull
        self.prereq = sorted({idx[r.split(":")[1]] for e in edges for r in filter(None, e[3].split(";"))})
        self.schema_ix = {s: i for i, s in enumerate(sorted({e[1] for e in edges} | {e[2] for e in edges} | {start}))}
        self.schemas = sorted(self.schema_ix, key=self.schema_ix.get)
        self.rank = {e[0]: i for i, e in enumerate(edges)}
        self.ids = [e[0] for e in edges]
        self.cost = [int(e[5]) for e in edges]
        self.out = defaultdict(list)
        self.inc = defaultdict(list)
        for i, e in enumerate(edges):
            req = [(idx[r.split(":")[1]], r.split(":")[0] == "has") for r in filter(None, e[3].split(";"))]
            ops = []
            for part in filter(None, e[4].split(";")):
                kind, rest = part.split(":", 1)
                if kind == "rename":
                    a, b = rest.split(">")
                    ops.append((0, idx[a], idx[b]))
                elif kind == "drop":
                    ops.append((1, idx[rest], 0))
                elif kind == "add":
                    ops.append((2, idx[rest], 0))
            self.out[self.schema_ix[e[1]]].append((i, self.schema_ix[e[2]], req, ops, int(e[5])))
            self.inc[self.schema_ix[e[2]]].append((i, self.schema_ix[e[1]], int(e[5])))
        self.tix = self.schema_ix[self.target]

    def digit(self, s, i):
        return (s // self.pw[i]) % 3

    def present(self, s, i):
        d = (s // self.pw[i]) % 3
        return d == 2 or (d == 1 and self.nullpresent[i])

    def allowed(self, s, req):
        for i, has in req:
            if self.present(s, i) != has:
                return False
        return True

    def step(self, s, ops):
        pw = self.pw
        for kind, a, b in ops:
            da = (s // pw[a]) % 3
            if kind == 0:
                if da:
                    db = (s // pw[b]) % 3
                    s = s - da * pw[a] - db * pw[b] + da * pw[b]
            elif kind == 1:
                s -= da * pw[a]
            else:
                mode = self.overnull[a]
                if mode is not None and (da == 0 or (da == 1 and mode)):
                    s += (2 - da) * pw[a]
        return s

    def root(self, start, payload):
        s = 0
        for n, v in payload.items():
            if n in self.names:
                s += (1 if v is None else 2) * self.pw[self.names.index(n)]
        return self.schema_ix[start] * self.size + s

    def plan(self, path):
        return [self.ids[i] for i in path]


def fast_dijkstra(spec, start, payload):
    """(a) plain cheapest-first over int nodes, tuple heap, stop at first target pop."""
    m = Machine(spec, start)
    root, size, tix = m.root(start, payload), m.size, m.tix
    heap, done = [(0, (), root)], set()
    while heap:
        g, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        sc, s = divmod(node, size)
        if sc == tix:
            return m.plan(path)
        for i, dst, req, ops, c in m.out[sc]:
            if m.allowed(s, req):
                nxt = dst * size + m.step(s, ops)
                if nxt not in done:
                    heapq.heappush(heap, (g + c, path + (i,), nxt))
    return None


def dominance(spec, start, payload):
    """(b) cheapest-first; a label is skipped when a settled label at the same schema has
    a superset of present prerequisite fields at no greater cost."""
    m = Machine(spec, start)
    root, size, tix = m.root(start, payload), m.size, m.tix
    heap, done = [(0, (), root)], set()
    settled = defaultdict(list)
    while heap:
        g, path, node = heapq.heappop(heap)
        if node in done:
            continue
        sc, s = divmod(node, size)
        mask = sum(1 << i for i in m.prereq if m.present(s, i))
        if any(g2 <= g and (mask2 & mask) == mask for g2, mask2 in settled[sc]):
            done.add(node)
            continue
        done.add(node)
        settled[sc].append((g, mask))
        if sc == tix:
            return m.plan(path)
        for i, dst, req, ops, c in m.out[sc]:
            if m.allowed(s, req):
                nxt = dst * size + m.step(s, ops)
                if nxt not in done:
                    heapq.heappush(heap, (g + c, path + (i,), nxt))
    return None


def incumbent(spec, start, payload):
    """(c) greedy walk gives an upper cost; cheapest-first then drops labels above it."""
    m = Machine(spec, start)
    root, size, tix = m.root(start, payload), m.size, m.tix
    upper, node, seen, cost = 1 << 62, root, {root}, 0
    for _ in range(80):
        sc, s = divmod(node, size)
        if sc == tix:
            upper = cost
            break
        moves = sorted((c, i, dst * size + m.step(s, ops)) for i, dst, req, ops, c in m.out[sc] if m.allowed(s, req))
        moves = [x for x in moves if x[2] not in seen]
        if not moves:
            break
        c, i, node = moves[0]
        seen.add(node)
        cost += c
    heap, done = [(0, (), root)], set()
    while heap:
        g, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        sc, s = divmod(node, size)
        if sc == tix:
            return m.plan(path)
        for i, dst, req, ops, c in m.out[sc]:
            if g + c <= upper and m.allowed(s, req):
                nxt = dst * size + m.step(s, ops)
                if nxt not in done:
                    heapq.heappush(heap, (g + c, path + (i,), nxt))
    return None


def bidirectional(spec, start, payload):
    """(d) forward over (schema, states), backward over schemas from the canonical schema;
    a meeting is checked by replaying the backward half; stop when top_f + top_b >= best."""
    m = Machine(spec, start)
    root, size, tix = m.root(start, payload), m.size, m.tix
    fheap, fdone = [(0, (), root)], set()
    bheap, bdist, bnext, bdone = [(0, tix)], {tix: 0}, {}, set()
    best, best_path = 1 << 62, None

    def suffix(sc, s):
        path, total = [], 0
        while sc != tix:
            i, dst = bnext[sc]
            e = next(x for x in m.out[sc] if x[0] == i)
            if not m.allowed(s, e[2]):
                return None
            s = m.step(s, e[3])
            path.append(i)
            total += e[4]
            sc = dst
        return total, path

    while fheap:
        top_b = bheap[0][0] if bheap else 1 << 62
        if fheap[0][0] + min(top_b, 1 << 61) >= best and best < 1 << 62 and (not bheap or fheap[0][0] + top_b >= best):
            break
        if bheap:
            d, sc = heapq.heappop(bheap)
            if sc not in bdone:
                bdone.add(sc)
                for i, src, c in m.inc[sc]:
                    if src != tix and d + c < bdist.get(src, 1 << 62):
                        bdist[src] = d + c
                        bnext[src] = (i, sc)
                        heapq.heappush(bheap, (d + c, src))
        g, path, node = heapq.heappop(fheap)
        if node in fdone:
            continue
        fdone.add(node)
        sc, s = divmod(node, size)
        if sc == tix:
            if g < best:
                best, best_path = g, list(path)
            continue
        if sc in bdone:
            got = suffix(sc, s)
            if got and g + got[0] < best:
                best, best_path = g + got[0], list(path) + got[1]
        for i, dst, req, ops, c in m.out[sc]:
            if m.allowed(s, req):
                nxt = dst * size + m.step(s, ops)
                if nxt not in fdone:
                    heapq.heappush(fheap, (g + c, path + (i,), nxt))
    return m.plan(best_path) if best_path is not None else None


def signature_keyed(spec, start, payload):
    """(e) cheapest-first keyed by (schema, prerequisite-field states) only."""
    m = Machine(spec, start)
    root, size, tix = m.root(start, payload), m.size, m.tix
    key = lambda sc, s: (sc, tuple(m.digit(s, i) for i in m.prereq))
    heap, done = [(0, (), root)], set()
    while heap:
        g, path, node = heapq.heappop(heap)
        sc, s = divmod(node, size)
        k = key(sc, s)
        if k in done:
            continue
        done.add(k)
        if sc == tix:
            return m.plan(path)
        for i, dst, req, ops, c in m.out[sc]:
            if m.allowed(s, req):
                s2 = m.step(s, ops)
                if key(dst, s2) not in done:
                    heapq.heappush(heap, (g + c, path + (i,), dst * size + s2))
    return None


def _load_core():
    spec = importlib.util.spec_from_file_location("core1", Path(__file__).with_name("core.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SOLVERS = {"reference": _bounded_plan, "a_fast_dijkstra": fast_dijkstra, "b_dominance": dominance,
           "c_incumbent": incumbent, "d_bidirectional": bidirectional, "e_signature_keyed": signature_keyed}


def _case(folder: Path):
    case = json.loads((folder / "case.json").read_text())
    index = case["index"]
    spec, lines, *_ = core_world(index)
    return spec, case


def main() -> None:
    mode = sys.argv[1]
    if mode == "seeds":
        count = int(sys.argv[2])
        t0 = time.time()
        worst = 0.0
        for index in range(1, count + 1):
            t = time.time()
            spec, lines, *_ = core_world(index)
            worst = max(worst, time.time() - t)
        print("seeds ok", count, "worst_build_s", round(worst, 2), "total_s", round(time.time() - t0, 1))
    elif mode == "gen":
        out = Path(sys.argv[2])
        first, last = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (29, 36)
        for index in range(first, last + 1):
            spec, lines, *_ = core_world(index)
            folder = out / f"world_{index:02d}"
            folder.mkdir(parents=True, exist_ok=True)
            root = spec.write()
            for f in root.iterdir():
                (folder / f.name).write_text(f.read_text())
            rows = []
            for doc in lines:
                t = time.time()
                plan = _bounded_plan(spec, doc["schema"], doc["payload"])
                rows.append({"start": doc["schema"], "payload": doc["payload"], "plan": plan, "ref_s": round(time.time() - t, 3)})
            (folder / "case.json").write_text(json.dumps({"index": index, "rows": rows}))
            print(folder.name, "schemas", len(spec.schemas), "edges", len(spec.edges),
                  "ref_s", [r["ref_s"] for r in rows], "plan_len", [len(r["plan"] or []) for r in rows], flush=True)
    elif mode == "one":
        name, folder, limit = sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
        spec, case = _case(folder)
        row = case["rows"][0]
        if name in SOLVERS:
            fn = SOLVERS[name]
        else:
            fn = getattr(_load_core(), name + "_plan")
        t = time.time()
        try:
            got = fn(spec, row["start"], row["payload"])
            verdict = "exact" if got == row["plan"] else "WRONG"
        except MemoryError:
            verdict = "MEMORY"
        print(folder.name, name, verdict, round(time.time() - t, 2), flush=True)
    elif mode == "solve":
        sys.path.insert(0, sys.argv[2])
        import migrakit
        folder = Path(sys.argv[3])
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
        case = json.loads((folder / "case.json").read_text())
        registry = migrakit.load_contracts(str(folder))
        row = case["rows"][0]
        t = time.time()
        try:
            got = migrakit.plan_migration(registry, row["start"], row["payload"])
            verdict = "exact" if got == row["plan"] else "WRONG"
        except MemoryError:
            verdict = "MEMORY"
        print(folder.name, sys.argv[2].split("/")[-2], verdict, round(time.time() - t, 2), flush=True)
    elif mode == "reach":
        folder, cap = Path(sys.argv[2]), int(sys.argv[3])
        spec, case = _case(folder)
        row = case["rows"][0]
        m = Machine(spec, row["start"])
        root = m.root(row["start"], row["payload"])
        seen, stack = {root}, [root]
        t = time.time()
        while stack and len(seen) < cap:
            sc, s = divmod(stack.pop(), m.size)
            for i, dst, req, ops, c in m.out[sc]:
                if m.allowed(s, req):
                    nxt = dst * m.size + m.step(s, ops)
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
        print(folder.name, "reachable", len(seen), "capped" if stack else "full", round(time.time() - t, 1))


if __name__ == "__main__":
    main()
