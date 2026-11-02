import random, sys, time, mw, gen
from mw import Timeout
def memo_rule(n, W, adj, limit, rule, split=True):
    memo={}; deadline=time.time()+limit; cnt=[0]
    def f(mask):
        cnt[0]+=1
        if cnt[0]&1023==0 and time.time()>deadline: raise Timeout
        if mask==0: return (0,0)
        r=memo.get(mask)
        if r is not None: return r
        if split:
            comps=mw.components(adj,mask)
            if len(comps)>1:
                tv=0; ts=0
                for c in comps:
                    a,s=f(c); tv+=a; ts|=s
                memo[mask]=(tv,ts); return (tv,ts)
        vs=[v for v in range(n) if mask>>v&1]
        if rule=="low": v=vs[0]
        elif rule=="mindeg": v=min(vs,key=lambda u:(bin(adj[u]&mask).count("1"),u))
        elif rule=="maxdeg": v=max(vs,key=lambda u:(bin(adj[u]&mask).count("1"),-u))
        elif rule=="maxw": v=max(vs,key=lambda u:(W[u],-u))
        a,s=f(mask&~(1<<v)&~adj[v]); take=(a+W[v],s|(1<<v))
        skip=f(mask&~(1<<v))
        res=take if take[0]>=skip[0] else skip
        memo[mask]=res; return res
    try:
        v,s=f((1<<n)-1); return True,v,s,cnt[0]
    except Timeout: return False,None,None,cnt[0]

def reduce_bnb(n, W, adj, limit):
    """Strongest generic exact first-write: memo + component split + simplicial/degree/domination
    reductions + clique-cover bound + incumbent pruning, max-degree branching."""
    order = sorted(range(n), key=lambda v: -W[v])
    memo = {}; deadline = time.time() + limit; cnt = [0]
    def is_clique(m):
        for u in mw.bits(m):
            if (m & ~(1 << u)) & ~adj[u]:
                return False
        return True
    def f(mask):
        cnt[0] += 1
        if cnt[0] & 1023 == 0 and time.time() > deadline: raise Timeout
        if mask == 0: return (0, 0)
        r = memo.get(mask)
        if r is not None: return r
        orig = mask; cur = 0; cs = 0; changed = True
        while changed and mask:
            changed = False
            for v in mw.bits(mask):
                if not (mask >> v) & 1: continue
                nb = adj[v] & mask
                if nb == 0 or (W[v] >= max(W[u] for u in mw.bits(nb)) and is_clique(nb)):
                    cur += W[v]; cs |= 1 << v; mask &= ~(1 << v) & ~nb; changed = True
            if not changed:
                for v in mw.bits(mask):
                    Nv = (adj[v] & mask) | (1 << v)
                    for u in mw.bits(adj[v] & mask):
                        if Nv & ~((adj[u] & mask) | (1 << u)) == 0 and W[v] >= W[u]:
                            mask &= ~(1 << u); changed = True; break
                    if changed: break
        if mask == 0: res = (cur, cs)
        else:
            comps = mw.components(adj, mask)
            if len(comps) > 1:
                tv, ts = cur, cs
                for c in comps:
                    a, s = f(c); tv += a; ts |= s
                res = (tv, ts)
            else:
                v = max(mw.bits(mask), key=lambda u: (mw.popcount(adj[u] & mask), W[u]))
                a, s = f(mask & ~(1 << v) & ~adj[v]); take = (a + W[v], s | (1 << v))
                rest = mask & ~(1 << v)
                if mw.clique_cover_ub(W, adj, rest, order) > take[0]:
                    skip = f(rest); r0 = take if take[0] >= skip[0] else skip
                else: r0 = take
                res = (r0[0] + cur, r0[1] | cs)
        memo[orig] = res; return res
    try:
        v, s = f((1 << n) - 1); return True, v, s, cnt[0]
    except Timeout: return False, None, None, cnt[0]
