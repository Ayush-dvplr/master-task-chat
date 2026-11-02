import sys
p = sys.argv[1]
s = open(p).read()

new_funcs = '''
CAP = 4


def _indep_sets(nodes, adj):
    out = []

    def rec(i, cur, banned):
        if i == len(nodes):
            out.append(frozenset(cur))
            return
        v = nodes[i]
        rec(i + 1, cur, banned)
        if v not in banned:
            cur.append(v)
            rec(i + 1, cur, banned | adj[v])
            cur.pop()
    rec(0, [], frozenset())
    return out


def _capped_rivals(members, nodes, adj, w, pid, comps):
    """Best capped and uncapped portfolios of a gadget, plus rival portfolios it must differ from."""
    sets = _indep_sets(nodes, adj)
    mem = set(members)

    def best(cands):
        cands = list(cands)
        top = max(sum(w[v] for v in s) for s in cands)
        tied = [s for s in cands if sum(w[v] for v in s) == top]
        return min(tied, key=lambda s: sorted(pid[v] for v in s))

    def nm(s):
        return len(s & mem)
    res = {}
    res["unc"] = best(sets)
    capped = [s for s in sets if nm(s) <= CAP]
    res["opt"] = best(capped)
    tot = sorted((sum(w[v] for v in s) for s in capped), reverse=True)
    res["_unique"] = len(tot) < 2 or tot[0] > tot[1]
    order_b = sorted(members, key=lambda v: (-w[v], pid[v]))
    keep = set(order_b[:CAP])
    res["filter_top_benefit"] = best(s for s in sets if (s & mem) <= keep)
    keep = set(sorted(members, key=lambda v: pid[v])[:CAP])
    res["filter_first_ids"] = best(s for s in sets if (s & mem) <= keep)
    s = set(res["unc"])
    while nm(s) > CAP:
        s.discard(min(s & mem, key=lambda v: (w[v], pid[v])))
    res["post_drop_lowest"] = frozenset(s)
    banned = set()
    s = res["unc"]
    while nm(s) > CAP:
        banned.add(min(s & mem, key=lambda v: (w[v], pid[v])))
        s = best(x for x in sets if not (x & banned))
    res["post_resolve_lowest"] = s
    s = res["unc"]
    top = set(sorted(s & mem, key=lambda v: (-w[v], pid[v]))[:CAP])
    res["post_keep_top"] = best(x for x in sets if (x & mem) <= top)
    banned = set()
    s = res["unc"]
    while nm(s) > CAP:
        opts = []
        for m in sorted(s & mem, key=lambda v: pid[v]):
            opts.append((best(x for x in sets if not (x & (banned | {m}))), m))
        top = max(sum(w[v] for v in x) for x, _ in opts)
        m = [m for x, m in opts if sum(w[v] for v in x) == top][0]
        banned.add(m)
        s = best(x for x in sets if not (x & banned))
    res["post_greedy_gain"] = s
    pc = set()
    for comp in comps:
        cs = set(comp)
        local = [s & cs for s in sets]
        pc |= best(x for x in set(local) if nm(x) <= CAP)
    res["per_component_cap"] = frozenset(pc)
    return res


def _capped_round(book, crng):
    saved = book.rng
    book.rng = crng
    try:
        return _capped_round_inner(book, crng)
    finally:
        book.rng = saved


def _capped_round_inner(book, rng):
    n, edges, _ = _small_graph(book, "")
    rnd = book.build_round(n, edges, False)
    used_crews = {r[2] for r in rnd["prop_rows"]}
    named = {r[1] for r in rnd["prop_rows"]} | {x for e in rnd["excl_rows"] for x in e}
    crew = rng.choice([c for c in book.shared if c not in used_crews])
    for attempt in range(400):
        k = rng.randint(6, 8)
        segs = []
        left = k
        while left:
            s = rng.randint(1, min(4, left))
            segs.append(s)
            left -= s
        if len(segs) < 2:
            continue
        members, comps, xs = [], [], []
        nxt = k
        mi = 0
        gedges = []
        for s in segs:
            comp = []
            prev = None
            for j in range(s):
                m = mi
                mi += 1
                members.append(m)
                comp.append(m)
                if prev is not None:
                    x = nxt
                    nxt += 1
                    xs.append(x)
                    comp.append(x)
                    gedges += [(prev, x), (x, m)]
                prev = m
            comps.append(comp)
        nodes = list(range(nxt))
        adj = {v: set() for v in nodes}
        for a, b in gedges:
            adj[a].add(b)
            adj[b].add(a)
        free = [s for s in book.sites if s["site"] not in named]
        sites = rng.sample(free, len(nodes))
        val = {v: book.value_small(sites[v]) for v in nodes}
        w = {v: book.benefit(sites[v], *val[v]) for v in nodes}
        pids_tmp = sorted(_codes_peek(book, rng, len(nodes)))
        perm = list(nodes)
        rng.shuffle(perm)
        pid = {v: pids_tmp[perm[v]] for v in nodes}
        res = _capped_rivals(members, nodes, adj, w, pid, comps)
        unc, opt = res["unc"], res["opt"]
        mem = set(members)
        if len(unc & mem) < CAP + 2 or not res["_unique"]:
            continue
        if any(not (adj[m] & opt) for m in mem - opt):
            continue
        bad = [name for name, s in res.items() if not name.startswith("_") and name not in ("unc", "opt") and s == opt]
        if bad:
            continue
        diff = set()
        for name, s in res.items():
            if not name.startswith("_") and name != "opt":
                diff |= set(s) ^ set(opt)
        if not any(val[v][0] in ("commercial", "public") for v in diff):
            continue
        break
    else:
        raise ValueError("no capped gadget")
    for v in nodes:
        book.taken.add(pid[v])
        book.all_pids.append(pid[v])
    ex = rng.sample([c for c in book.exclusive if c not in used_crews], len(xs))
    crew_of = {m: crew for m in members}
    for i, x in enumerate(xs):
        crew_of[x] = ex[i]
    base = rnd["n"]
    idx = {v: base + i for i, v in enumerate(nodes)}
    for v in nodes:
        sg, ov, hh = val[v]
        rnd["prop_rows"].insert(rng.randint(0, len(rnd["prop_rows"])), [pid[v], sites[v]["site"], crew_of[v], str(hh), ov])
        rnd["seg_rows"].insert(rng.randint(0, len(rnd["seg_rows"])), [pid[v], sg])
    for a, b in gedges:
        pa, pb = (pid[a], pid[b]) if rng.random() < 0.5 else (pid[b], pid[a])
        rnd["excl_rows"].insert(rng.randint(0, len(rnd["excl_rows"])), [pa, pb])
    rnd["pids"] = rnd["pids"] + [pid[v] for v in nodes]
    rnd["edges"] |= {_pair(idx[a], idx[b]) for a, b in gedges}
    rnd["n"] = base + len(nodes)
    got = book.derive(rnd)
    want = {_pair(rnd["pids"][a], rnd["pids"][b]) for a, b in rnd["edges"]}
    assert got == want, "capped gadget changed conflicts"
    rnd["capped"] = {"crew": crew, "k": k, "segs": segs, "members": sorted(pid[m] for m in members),
                     "opt": sorted(pid[v] for v in opt), "unc": sorted(pid[v] for v in unc),
                     "attempts": attempt + 1}
    rnd["audit"] = _audit(book, rnd, book.spec["audit_small"])
    return rnd


def _codes_peek(book, rng, n):
    out = []
    while len(out) < n:
        c = "P" + str(rng.randint(100000, 999999))
        if c not in book.taken and c not in out:
            out.append(c)
    return out

'''
anchor = "\n\ndef make_book(seed, spec):\n"
assert s.count(anchor) == 1
s = s.replace(anchor, "\n" + new_funcs + "\ndef make_book(seed, spec):\n")
old_end = '''        rnd["audit"] = _audit(book, rnd, spec["audit_large"] if rnd["large"] else spec["audit_small"])
    return _assemble(book, rounds)
'''
new_end = '''        rnd["audit"] = _audit(book, rnd, spec["audit_large"] if rnd["large"] else spec["audit_small"])
    crng = _Rng(seed * 31 + 7177)
    capped = [_capped_round(book, crng) for _ in range(spec.get("capped", 0))]
    files, meta = _assemble(book, rounds + capped)
    meta["capped"] = {r["round"]: r["capped"] for r in capped}
    return files, meta
'''
assert s.count(old_end) == 1
s = s.replace(old_end, new_end)
open(p, "w").write(s)
print("ok")
