"""Scratch: Design 2 prototype (planner core inside the stated K14 limits).

    python3 -B core.py gen OUTDIR [count] [region]     # write instances + reference plans
    python3 -B core.py check [count] [region]          # A* reference vs tests' _reference_plan (small)
    python3 -B core.py solve REPO_SRC OUTDIR LIMIT     # time one repo's plan_migration per instance

An instance is one domain: a costly corridor to the canonical schema plus a large
cheap region whose only exits to the canonical schema are very expensive.
"""

from __future__ import annotations

import heapq
import importlib.util
import json
import os
import resource
import signal
import sys
import time
from collections import defaultdict
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "rewardkit_stub"))
_spec = importlib.util.spec_from_file_location("tests_src", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)


def core_spec(salt: int, region: int = 1000, lanes: int = 3, depth: int = 12):
    rng = T._rng(5000 + salt)
    dom = T._word(rng, "cr")
    count = 0

    def schema() -> str:
        nonlocal count
        count += 1
        return f"{dom}.v{count}"

    fields = sorted({T._word(rng, "k") for _ in range(30)})[:10]
    prereq = fields[:8]
    start = schema()
    grid = [[schema() for _ in range(lanes)] for _ in range(depth)]
    target = schema()
    zone = [schema() for _ in range(region)]
    ids = iter(T._ids(rng, 40 + depth * lanes * lanes + region * 6 + 200))
    edges = []

    def edge(a, b, req, ops, cost):
        edges.append((next(ids), a, b, req, ops, cost))

    def ops_text(k):
        out = []
        for _ in range(k):
            kind = rng.choice(["add", "drop", "rename", "add", "drop"])
            f = rng.choice(fields)
            if kind == "rename":
                out.append(f"rename:{f}>{rng.choice([x for x in fields if x != f])}")
            else:
                out.append(f"{kind}:{f}")
        return ";".join(out)

    def req_text(p):
        if rng.random() >= p:
            return ""
        return f"{rng.choice(['has', 'lacks'])}:{rng.choice(prereq)}"

    hops = [(start, n) for n in grid[0]]
    for i in range(depth - 1):
        hops.extend((a, b) for a in grid[i] for b in grid[i + 1])
    hops.extend((n, target) for n in grid[-1])
    for a, b in hops:
        edge(a, b, req_text(0.4), ops_text(rng.randint(0, 1)), rng.randint(200, 900))
    # escape lane so that every record has some plan
    edge(start, target, "", "", 40_000_000)
    entries = [start, *(n for row in grid[: depth // 2] for n in row)]
    for a in entries:
        for _ in range(2):
            edge(a, rng.choice(zone), "", ops_text(1), rng.randint(1, 5))
    for a in zone:
        for _ in range(4):
            edge(a, rng.choice(zone), req_text(0.3), ops_text(rng.randint(1, 2)), rng.randint(1, 4))
    for a in rng.sample(zone, min(6, len(zone))):
        edge(a, target, "", "", rng.randint(9_000_000, 9_900_000))
    policy = []
    for n, f in enumerate(fields):
        fill = "absent_or_null" if n % 3 == 0 else ""
        counts = "absent" if n % 4 == 1 else ""
        policy.append((dom, f, str(rng.randint(1, 9)), fill, counts))
    rng.shuffle(edges)
    schemas = [start, *(n for row in grid for n in row), target, *zone]
    payloads = []
    for _ in range(3):
        p = {}
        for f in fields:
            r = rng.random()
            if r < 0.35:
                p[f] = rng.randint(1, 99)
            elif r < 0.6:
                p[f] = None
        payloads.append(p)
    return T.Spec(schemas, {target}, edges, policy=policy), start, payloads


def astar_plan(spec, start: str, payload: dict):
    """Cheapest plan, then smallest edge id list; ordered by cost so far plus a schema-graph lower bound."""
    dom = start.rsplit(".v", 1)[0]
    target = next(s for s in spec.canonical if s.rsplit(".v", 1)[0] == dom)
    if start == target:
        return []
    pol = T._policy_map(spec)
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for e in sorted(spec.edges):
        outgoing[e[1]].append(e)
        incoming[e[2]].append(e)
    bound = {target: 0}
    heap = [(0, target)]
    while heap:
        d, s = heapq.heappop(heap)
        if d > bound[s]:
            continue
        for e in incoming[s]:
            if e[1] == target:
                continue
            nd = d + int(e[5])
            if nd < bound.get(e[1], 1 << 62):
                bound[e[1]] = nd
                heapq.heappush(heap, (nd, e[1]))
    names = sorted({x for e in spec.edges for part in filter(None, (e[3] + ";" + e[4]).split(";")) for x in part.split(":", 1)[1].replace(">", ":").split(":")[:2] if x not in ("int", "float", "str")})
    first = {n: ("N" if v is None else "V") for n, v in payload.items() if n in names}
    root = (start, tuple(first.get(n, "A") for n in names))
    if start not in bound:
        return None
    best = {root: (0, ())}
    heap = [(bound[start], (), root)]
    done = set()
    while heap:
        f, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node[0] == target:
            return list(path)
        g = f - bound[node[0]]
        states = {n: v for n, v in zip(names, node[1]) if v != "A"}
        for edge_id, _, dst, req, ops, cost in outgoing[node[0]]:
            if dst not in bound:
                continue
            ok = all(T._counts(spec, pol, dom, r.split(":")[1], states.get(r.split(":")[1], "A")) == (r.split(":")[0] == "has") for r in filter(None, req.split(";")))
            if not ok:
                continue
            nxt_states = T._step_states(spec, pol, dom, states, ops)
            nxt = (dst, tuple(nxt_states.get(n, "A") for n in names))
            if nxt in done:
                continue
            ng = g + int(cost)
            npath = path + (edge_id,)
            known = best.get(nxt)
            if known is None or (ng, npath) < known:
                best[nxt] = (ng, npath)
                heapq.heappush(heap, (ng + bound[dst], npath, nxt))
    return None


def _setup(spec, start):
    dom = start.rsplit(".v", 1)[0]
    target = next(s for s in spec.canonical if s.rsplit(".v", 1)[0] == dom)
    pol = T._policy_map(spec)
    outgoing = defaultdict(list)
    for e in sorted(spec.edges):
        outgoing[e[1]].append(e)
    return dom, target, pol, outgoing


def _allowed(spec, pol, dom, states, req):
    return all(T._counts(spec, pol, dom, r.split(":")[1], states.get(r.split(":")[1], "A")) == (r.split(":")[0] == "has") for r in filter(None, req.split(";")))


def greedy_plan(spec, start, payload):
    """Walk the cheapest allowed edge (smallest id on ties), never repeating a (schema, state)."""
    dom, target, pol, outgoing = _setup(spec, start)
    states = {n: ("N" if v is None else "V") for n, v in payload.items()}
    here, plan, seen = start, [], set()
    while here != target and len(plan) < 80:
        seen.add((here, tuple(sorted(states.items()))))
        options = []
        for e in outgoing[here]:
            if _allowed(spec, pol, dom, states, e[3]):
                nxt = T._step_states(spec, pol, dom, states, e[4])
                if (e[2], tuple(sorted(nxt.items()))) not in seen:
                    options.append((int(e[5]), e[0], e[2], nxt))
        if not options:
            return None
        _, eid, here, states = min(options, key=lambda o: (o[0], o[1]))
        plan.append(eid)
    return plan if here == target else None


def exhaustive_plan(spec, start, payload):
    """List every walk of at most 80 edges that does not repeat a (schema, state); keep the best."""
    dom, target, pol, outgoing = _setup(spec, start)
    best = [None]
    def walk(here, states, cost, path, seen):
        if here == target:
            if best[0] is None or (cost, path) < best[0]:
                best[0] = (cost, list(path))
            return
        if len(path) >= 80:
            return
        for e in outgoing[here]:
            if _allowed(spec, pol, dom, states, e[3]):
                nxt = T._step_states(spec, pol, dom, states, e[4])
                key = (e[2], tuple(sorted(nxt.items())))
                if key in seen:
                    continue
                seen.add(key)
                path.append(e[0])
                walk(e[2], nxt, cost + int(e[5]), path, seen)
                path.pop()
                seen.discard(key)
    sys.setrecursionlimit(10000)
    walk(start, {n: ("N" if v is None else "V") for n, v in payload.items()}, 0, [], set())
    return best[0][1] if best[0] else None


def schema_only_plan(spec, start, payload):
    """Cheapest schema-graph walk, prerequisites ignored."""
    dom, target, pol, outgoing = _setup(spec, start)
    heap, done = [(0, (), start)], set()
    while heap:
        cost, path, here = heapq.heappop(heap)
        if here in done:
            continue
        done.add(here)
        if here == target:
            return list(path)
        for e in outgoing[here]:
            if e[2] not in done:
                heapq.heappush(heap, (cost + int(e[5]), path + (e[0],), e[2]))
    return None


def dijkstra_plan(spec, start, payload):
    """Plain cheapest-first search over (schema, field states) with (cost, edge-id list) labels."""
    dom, target, pol, outgoing = _setup(spec, start)
    names = sorted({x for e in spec.edges for part in filter(None, (e[3] + ";" + e[4]).split(";")) for x in part.split(":", 1)[1].replace(">", ":").split(":")[:2] if x not in ("int", "float", "str")})
    first = {n: ("N" if v is None else "V") for n, v in payload.items() if n in names}
    root = (start, tuple(first.get(n, "A") for n in names))
    heap, done = [(0, (), root)], set()
    while heap:
        cost, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node[0] == target:
            return list(path)
        states = {n: v for n, v in zip(names, node[1]) if v != "A"}
        for e in outgoing[node[0]]:
            if _allowed(spec, pol, dom, states, e[3]):
                nxt = T._step_states(spec, pol, dom, states, e[4])
                key = (e[2], tuple(nxt.get(n, "A") for n in names))
                if key not in done:
                    heapq.heappush(heap, (cost + int(e[5]), path + (e[0],), key))
    return None


PROGS = {"greedy": greedy_plan, "exhaustive": exhaustive_plan, "schema_only": schema_only_plan,
         "dijkstra": dijkstra_plan, "astar": astar_plan}
SPECS: dict = {}


def main() -> None:
    mode = sys.argv[1]
    if mode == "check":
        count, region = int(sys.argv[2]), int(sys.argv[3])
        bad = 0
        for salt in range(count):
            spec, start, payloads = core_spec(salt, region=region, depth=5)
            for p in payloads:
                a, b = astar_plan(spec, start, p), T._reference_plan(spec, start, p)
                if a != b:
                    bad += 1
                    print("DIFF", salt, a, b)
        print("check done bad", bad)
    elif mode == "gen":
        out = Path(sys.argv[2])
        count, region = int(sys.argv[3]), int(sys.argv[4])
        for salt in range(count):
            spec, start, payloads = core_spec(salt, region=region)
            root = spec.write()
            folder = out / f"core_{salt:02d}"
            folder.mkdir(parents=True, exist_ok=True)
            for f in root.iterdir():
                (folder / f.name).write_text(f.read_text())
            plans, secs = [], []
            for p in payloads:
                t = time.time()
                plan = astar_plan(spec, start, p)
                secs.append(round(time.time() - t, 3))
                cost = sum(int(e[5]) for e in spec.edges if e[0] in set(plan or []))
                assert plan and cost < 1_000_000 and len(plan) <= 80, (salt, cost)
                plans.append(plan)
            (folder / "case.json").write_text(json.dumps({"start": start, "payloads": payloads, "plans": plans, "ref_seconds": secs}))
            print(folder.name, "schemas", len(spec.schemas), "edges", len(spec.edges), "ref_s", secs, "plan_len", [len(x or []) for x in plans])
    elif mode == "prog":
        prog, out, limit = sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])
        for folder in sorted(out.glob("core_*")):
            case = json.loads((folder / "case.json").read_text())
            spec = SPECS[folder.name] if folder.name in SPECS else None
            if spec is None:
                salt = int(folder.name.split("_")[1])
                spec = core_spec(salt)[0]
            pairs = list(zip(case["payloads"], case["plans"]))
            for p, want in pairs[:1] if os.environ.get("FIRST") else pairs:
                def stop(*_):
                    raise TimeoutError
                signal.signal(signal.SIGALRM, stop)
                signal.alarm(limit)
                t = time.time()
                try:
                    got = PROGS[prog](spec, case["start"], p)
                    verdict = "exact" if got == want else "WRONG"
                except TimeoutError:
                    verdict = "TIMEOUT"
                finally:
                    signal.alarm(0)
                print(folder.name, prog, verdict, round(time.time() - t, 2), flush=True)
    elif mode == "solve":
        sys.path.insert(0, sys.argv[2])
        import migrakit
        out, limit = Path(sys.argv[3]), int(sys.argv[4])
        for folder in sorted(out.glob("core_*")):
            case = json.loads((folder / "case.json").read_text())
            registry = migrakit.load_contracts(str(folder))
            pairs = list(zip(case["payloads"], case["plans"]))
            for p, want in pairs[:1] if os.environ.get("FIRST") else pairs:
                def stop(*_):
                    raise TimeoutError
                signal.signal(signal.SIGALRM, stop)
                signal.alarm(limit)
                t = time.time()
                try:
                    got = migrakit.plan_migration(registry, case["start"], p)
                    verdict = "exact" if got == want else "WRONG"
                except TimeoutError:
                    verdict = "TIMEOUT"
                except Exception as exc:  # scratch harness: report any failure as a verdict
                    verdict = "ERR " + type(exc).__name__
                finally:
                    signal.alarm(0)
                print(folder.name, verdict, round(time.time() - t, 2), "maxrss_mb", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1 << 20), flush=True)


if __name__ == "__main__":
    main()
