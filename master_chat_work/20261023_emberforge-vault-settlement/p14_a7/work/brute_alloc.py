import sys, importlib.util
sys.setrecursionlimit(10000)
spec = importlib.util.spec_from_file_location("av", "agent_variant_forgeday.py"); av = importlib.util.module_from_spec(spec); spec.loader.exec_module(av)
s = av.load_season(sys.argv[1]); conv = av.derive_conventions(s.rulings); ctx = av.prepare(s); res = av.settled_season(s, conv, ctx)
A = av.Allocator(s, set(ctx["scope"]), res["balance"])
items = {it['req_id']: it for it in A.items}
def best(fixed):
    states = {(0, 0, ()) : None}  # (guild usage tuple, reagent usage tuple) -> reachable
    gl = A.guilds; rl = A.reagents
    states = {(tuple(0 for _ in gl), tuple(0 for _ in rl))}
    for grp in A.charters:
        opts = [(None, 0)]
        f = [r for r in grp if r in fixed]
        if f:
            opts = [(f[0], fixed[f[0]])] if fixed[f[0]] > 0 else [(None, 0)]
            # other members of the group get nothing when one is funded
        else:
            for r in grp:
                it = items[r]
                opts += [(r, v) for v in range(it['lo'], it['hi'] + 1)]
        new = set()
        for gu, ru in states:
            for r, v in opts:
                if r is None: new.add((gu, ru)); continue
                it = items[r]
                g2 = list(gu); g2[gl.index(it['guild'])] += v
                if g2[gl.index(it['guild'])] > A.guild_cap[it['guild']]: continue
                r2 = list(ru)
                if it['reagent'] is not None:
                    k = rl.index(it['reagent']); r2[k] += v
                    if r2[k] > A.reagent_cap[it['reagent']]: continue
                if sum(g2) > A.pool: continue
                new.add((tuple(g2), tuple(r2)))
        states = new
    return max(sum(g) for g, _ in states)
print("exact best {}:", best({}))
print("exact best RQ05=17:", best({'RQ05': 17}), "agent says", A.best_total({'RQ05': 17}))
sel = {'RQ05': (6, 17), 'RQ11': (9, 16), 'RQ01': (8, 18)}
print("capacity RQ05[6..17]+RQ11[9..16] (R02 cap 30) + RQ01[8..18] (ashen, non-scarce):", A._capacity(dict(sel), []), "true max", min(17+16, 30) + 18)
