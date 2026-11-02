"""Scratch (gate v3.6 harden a4f790c): prototype of the gated-zone core worlds.
Same family as `_g_core`: a priced corridor beside a cheap region. Here the region's exits to the
canonical schema are cheap but need a prerequisite field the region can never make present, so the
schema-graph remainder does not prune it. Reference: the same label-setting search with a stronger
remainder, max(schema-graph remainder, per-prerequisite-field projection remainders).
    python3 -B gate.py gen OUT FIRST LAST       # OUT/world_NN/{contract files, case.json}
    python3 -B gate.py seeds FIRST LAST          # shape asserts, reference seconds
    python3 -B gate.py same                      # strong reference == tests reference on every old world/case
"""
from __future__ import annotations

import hashlib
import heapq
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core2  # noqa: E402

T = core2.T
STREAM = 9000


def _field_remainders(spec, pol, dom, edges, target, rest, name):
    """Cheapest cost to the canonical schema from (schema, state of `name`), other fields unknown."""
    inc = defaultdict(list)
    for edge in edges:
        if edge[1] == target or edge[2] not in rest:
            continue
        reqs = [r.split(":") for r in filter(None, edge[3].split(";"))]
        for s in "ANV":
            if not all(T._counts(spec, pol, dom, f, s) == (k == "has") for k, f in reqs if f == name):
                continue
            outs = {s}
            for op in filter(None, edge[4].split(";")):
                kind, arg = op.split(":", 1)
                if kind == "rename":
                    a, b = arg.split(">")
                    if a == name:
                        outs = {"A"}
                    elif b == name:
                        outs = outs | {"N", "V"}
                elif kind == "drop" and arg == name:
                    outs = {"A"}
                elif kind == "add" and arg == name:
                    outs = {next(iter(T._step_states(spec, pol, dom, {name: x} if x != "A" else {}, op).values()), "A") for x in outs}
            for t in outs:
                inc[(edge[2], t)].append(((edge[1], s), int(edge[5])))
    best = {(target, s): 0 for s in "ANV"}
    heap = [(0, (target, s)) for s in "ANV"]
    while heap:
        d, here = heapq.heappop(heap)
        if d > best[here]:
            continue
        for there, cost in inc[here]:
            if d + cost < best.get(there, 1 << 62):
                best[there] = d + cost
                heapq.heappush(heap, (d + cost, there))
    return best


def strong_plan(spec, start: str, payload: dict):
    """Label-setting search over (schema, states) ordered by (cost so far plus a remainder, edge-id list);
    remainder = max(schema-graph remainder, each prerequisite field's projected remainder)."""
    dom = start.rsplit(".v", 1)[0]
    target = next(s for s in spec.canonical if s.rsplit(".v", 1)[0] == dom)
    if start == target:
        return []
    pol = T._policy_map(spec)
    edges = sorted(e for e in spec.edges if e[1].rsplit(".v", 1)[0] == dom)
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for edge in edges:
        outgoing[edge[1]].append(edge)
        incoming[edge[2]].append(edge)
    rest = {target: 0}
    heap: list = [(0, target)]
    while heap:
        d, here = heapq.heappop(heap)
        if d > rest[here]:
            continue
        for edge in incoming[here]:
            if edge[1] != target and d + int(edge[5]) < rest.get(edge[1], 1 << 62):
                rest[edge[1]] = d + int(edge[5])
                heapq.heappush(heap, (rest[edge[1]], edge[1]))
    if start not in rest:
        return None
    names = sorted({x for e in edges for part in filter(None, (e[3] + ";" + e[4]).split(";")) for x in part.split(":", 1)[1].replace(">", ":").split(":")[:2] if x not in ("int", "float", "str")})
    gates = sorted({r.split(":")[1] for e in edges for r in filter(None, e[3].split(";"))})
    proj = [(names.index(g), _field_remainders(spec, pol, dom, edges, target, rest, g)) for g in gates]

    def remainder(node):
        best = rest[node[0]]
        for i, table in proj:
            got = table.get((node[0], node[1][i]))
            if got is None:
                return None
            best = max(best, got)
        return best

    first = {n: ("N" if v is None else "V") for n, v in payload.items() if n in names}
    root = (start, tuple(first.get(n, "A") for n in names))
    h0 = remainder(root)
    if h0 is None:
        return None
    best = {root: (0, ())}
    heap = [(h0, (), root, 0)]
    done: set = set()
    while heap:
        total, path, node, spent = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node[0] == target:
            return list(path)
        states = {n: v for n, v in zip(names, node[1]) if v != "A"}
        for edge_id, _, dst, req, ops, cost in outgoing[node[0]]:
            if dst not in rest:
                continue
            ok = all(T._counts(spec, pol, dom, r.split(":")[1], states.get(r.split(":")[1], "A")) == (r.split(":")[0] == "has") for r in filter(None, req.split(";")))
            if not ok:
                continue
            after = T._step_states(spec, pol, dom, states, ops)
            nxt = (dst, tuple(after.get(n, "A") for n in names))
            if nxt in done:
                continue
            h = remainder(nxt)
            if h is None:
                continue
            label = (spent + int(cost), path + (edge_id,))
            if nxt not in best or label < best[nxt]:
                best[nxt] = label
                heapq.heappush(heap, (label[0] + h, label[1], nxt, label[0]))
    return None


def g_gate(w, number: int, stream: int = STREAM, degree: int = 5) -> None:
    """One large domain: a priced corridor beside a cheap region whose cheap exits need a field it never gets."""
    rng = T._rng(stream + number)
    for _ in range(40):
        dom = w.fresh("cr")
        fields = sorted(w.fresh("k", 4) for _ in range(10))
        need, carry, idle, gate = rng.sample(fields, 4)
        prereq = [f for f in fields if f not in (carry, idle)]
        others = [f for f in prereq if f not in (need, gate)]
        roam = [f for f in fields if f != gate]
        rows, lanes = rng.randint(10, 12), 3
        zone_size = rng.randint(1100, 1195 - rows * lanes)
        names = iter(rng.sample(range(1, 1201), 5 + rows * lanes + zone_size))
        sch = lambda: f"{dom}.v{next(names)}"
        start, plant, side, target, door = sch(), sch(), sch(), sch(), sch()
        grid = [[sch() for _ in range(lanes)] for _ in range(rows)]
        zone = [sch() for _ in range(zone_size)]
        edges: list[tuple] = []

        def edge(a, b, req, ops, cost):
            edges.append((w.fresh("q", 6), a, b, req, ops, cost))

        def req_text(chance, pool):
            return f"{rng.choice(['has', 'lacks'])}:{rng.choice(pool)}" if rng.random() < chance else ""

        def op_text(pool):
            kind = rng.choice(["rename", "rename", "add", "drop"])
            f = rng.choice(pool)
            return f"rename:{f}>{rng.choice([x for x in pool if x != f])}" if kind == "rename" else f"{kind}:{f}"

        cheap = rng.randint(2000, 9000)
        edge(start, plant, "", f"drop:{carry}", cheap)
        edge(start, plant, "", "", cheap + 500)
        for b in grid[0]:
            edge(plant, b, "", f"rename:{carry}>{need}", rng.randint(2000, 9000))
        for i in range(rows - 1):
            for a in grid[i]:
                for b in grid[i + 1]:
                    ops = op_text(others) if rng.random() < 0.4 else ""
                    if ops.startswith("rename"):
                        ops = ""
                    edge(a, b, req_text(0.35, others), ops, rng.randint(2000, 9000))
        for a in grid[-1]:
            edge(a, target, f"has:{need}", "", rng.randint(2000, 9000))
            edge(a, side, "", f"add:{need}", 20000)
        edge(side, target, f"has:{need}", "", 1)
        edge(start, target, "", "", 40_000_000)
        edge(start, door, "", f"add:{gate}", rng.randint(5_000_000, 6_000_000))
        edge(door, rng.choice(zone), "", "", rng.randint(1, 5))
        for a in [start, plant, *(n for row in grid[: rows // 2] for n in row)]:
            for _ in range(2):
                edge(a, rng.choice(zone), "", op_text(roam), rng.randint(1, 5))
        for a in zone:
            for _ in range(degree):
                ops = ";".join(op_text(roam) for _ in range(rng.randint(1, 2)))
                edge(a, rng.choice(zone), req_text(0.25, [f for f in prereq if f != gate]), ops, rng.randint(1, 4))
        for a in rng.sample(zone, 40):
            edge(a, target, f"has:{gate}", "", rng.randint(1, 5))
        policy = []
        for n, f in enumerate(fields):
            fill = "absent_or_null" if n % 3 == 0 else ""
            counts = "absent" if (n % 4 == 1 and f not in (need, gate)) else ""
            policy.append((dom, f, str(rng.randint(1, 9)), fill, counts))
        if len(edges) > 6000:
            continue
        rng.shuffle(edges)
        schemas = [start, plant, side, target, door, *(n for row in grid for n in row), *zone]
        spec = T.Spec(schemas, {target}, edges, policy=policy)
        hard = {carry: rng.randint(10, 99)}
        for f in rng.sample(others, 5):
            hard[f] = None
        for f in others:
            if f not in hard and rng.random() < 0.7:
                hard[f] = T._val(rng)
        plan = strong_plan(spec, start, hard)
        by_id = {e[0]: e for e in edges}
        if not plan or len(plan) > 80:
            continue
        cost = sum(int(by_id[x][5]) for x in plan)
        if cost >= 1_000_000 or by_id[plan[0]][4] != "" or side in {by_id[x][2] for x in plan}:
            continue
        assert len(schemas) <= 1200 and len(edges) <= 6000 and len(fields) <= 10 and len(plan) <= 80
        assert len({r.split(":")[1] for e in edges for r in filter(None, e[3].split(";"))}) <= 8
        assert all(isinstance(e[5], int) and e[5] > 0 for e in edges)
        w.schemas += schemas
        w.canonical.add(target)
        w.edges += edges
        w.policy += policy
        w.line(w.pool[0], start, hard)
        return
    raise RuntimeError("no gated core instance")


def world(index: int):
    w = T._World(100 + index - 1, ("CORE",))
    g_gate(w, index)
    return w.finish()


def main() -> None:
    mode = sys.argv[1]
    if mode in ("gen", "seeds"):
        out = Path(sys.argv[2]) if mode == "gen" else None
        first, last = map(int, sys.argv[-2:])
        for index in range(first, last + 1):
            t = time.time()
            spec, lines, *_ = world(index)
            build = round(time.time() - t, 2)
            rows = []
            for doc in lines:
                t = time.time()
                plan = strong_plan(spec, doc["schema"], doc["payload"])
                rows.append({"start": doc["schema"], "payload": doc["payload"], "plan": plan, "ref_s": round(time.time() - t, 3)})
            print(f"world_{index:02d} schemas {len(spec.schemas)} edges {len(spec.edges)} build_s {build} ref_s {[r['ref_s'] for r in rows]} plan_len {[len(r['plan'] or []) for r in rows]}", flush=True)
            if out:
                folder = out / f"world_{index:02d}"
                folder.mkdir(parents=True, exist_ok=True)
                root = spec.write()
                for f in root.iterdir():
                    (folder / f.name).write_text(f.read_text())
                (folder / "case.json").write_text(json.dumps({"index": index, "rows": rows}))
    elif mode == "one":
        import resource
        name, folder = sys.argv[2], Path(sys.argv[3])
        resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
        case = json.loads((folder / "case.json").read_text())
        spec = world(case["index"])[0]
        row = case["rows"][0]
        fn = strong_plan if name == "strong" else core2.SOLVERS.get(name) or getattr(core2._load_core(), name + "_plan")
        t = time.time()
        try:
            verdict = "exact" if fn(spec, row["start"], row["payload"]) == row["plan"] else "WRONG"
        except MemoryError:
            verdict = "MEMORY"
        print(folder.name, name, verdict, round(time.time() - t, 2), flush=True)
    elif mode == "same":
        # every call the tests make to the reference planner (generation, expected outputs, ladder)
        digest = hashlib.sha256()
        seen = {"calls": 0, "diff": 0}
        old = T._reference_plan

        def both(spec, start, payload):
            a = old(spec, start, payload)
            b = strong_plan(spec, start, payload)
            seen["calls"] += 1
            if a != b:
                seen["diff"] += 1
                print("DIFF", start, a, b, flush=True)
            return a

        T._reference_plan = both
        for name in T.WORLDS:
            digest.update(json.dumps(T._world_expected(name), sort_keys=True).encode())
        for name in T.LADDERS:
            digest.update(json.dumps(T.case_ladder(name)[2]).encode())
        print("calls", seen["calls"], "diff", seen["diff"], "expected digest", digest.hexdigest()[:16])


if __name__ == "__main__":
    main()
