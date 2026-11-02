import sys, json, importlib.util
sys.setrecursionlimit(10000)
spec = importlib.util.spec_from_file_location("av", "agent_variant_forgeday.py"); av = importlib.util.module_from_spec(spec); spec.loader.exec_module(av)
data = sys.argv[1]
s = av.load_season(data); conv = av.derive_conventions(s.rulings); ctx = av.prepare(s); res = av.settled_season(s, conv, ctx)
A = av.Allocator(s, set(ctx["scope"]), res["balance"])
print("pool", A.pool, "guild_cap", A.guild_cap, "reagent_cap", A.reagent_cap)
for it in A.items: print(it)
print("charters", A.charters)
oracle = json.load(open(sys.argv[2]))["assignments"]
plan = {a["req_id"]: a["allocated_units"] for a in oracle if a["allocated_units"] > 0}
sel = {r: (v, v) for r, v in plan.items()}
print("oracle plan", plan, "sum", sum(plan.values()))
print("agent capacity of oracle plan:", A._capacity(sel, []))
print("best_total({}) =", A.best_total({}))
print("best_total({'RQ05':17}) =", A.best_total({'RQ05':17}))
import itertools
# exhaustive check: brute force over plans with RQ05=17 fixed (at most one per charter), lo..hi
items={it['req_id']:it for it in A.items}
def feasible_max(fixed):
    # DP brute force: enumerate choices per charter group (none or one req with value), bounded
    groups=[g for g in A.charters]
    best=[-1]
    def rec(i, chosen):
        if i==len(groups):
            tot=sum(chosen.values())
            if tot>A.pool: return
            gu={};ru={}
            for r,v in chosen.items():
                it=items[r]; gu[it['guild']]=gu.get(it['guild'],0)+v
                if it['reagent']: ru[it['reagent']]=ru.get(it['reagent'],0)+v
            if any(gu[g]>A.guild_cap[g] for g in gu) or any(ru[r]>A.reagent_cap[r] for r in ru): return
            best[0]=max(best[0],tot); return
        g=groups[i]
        f=[r for r in g if r in fixed]
        if f:
            chosen[f[0]]=fixed[f[0]]; rec(i+1,chosen); del chosen[f[0]]; return
        rec(i+1,chosen)
        for r in g:
            it=items[r]
            for v in (it['lo'],it['hi']) if it['hi']-it['lo']>0 else (it['hi'],):
                pass
            for v in range(it['lo'],it['hi']+1):
                chosen[r]=v
                # prune by pool
                if sum(chosen.values())<=A.pool: rec(i+1,chosen)
                del chosen[r]
    rec(0,{})
    return best[0]
