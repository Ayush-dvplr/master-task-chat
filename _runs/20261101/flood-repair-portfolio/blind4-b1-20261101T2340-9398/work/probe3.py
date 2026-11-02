import sys
sys.path.insert(0, 'app')
import derive_report as d
def tw(n, W, adj, cm, co):
    if n > 100:
        g = {i: set(j for j in range(n) if adj[i]>>j&1) for i in range(n)}
        width = 0; alive=set(range(n))
        while alive:
            def fill(v):
                nb=list(g[v]); c=0
                for a in range(len(nb)):
                    for b in range(a+1,len(nb)):
                        if nb[b] not in g[nb[a]]: c+=1
                return c
            v = min(alive, key=lambda v:(fill(v), len(g[v])))
            nb = g[v]; width=max(width,len(nb))
            for a in nb:
                g[a] |= nb; g[a].discard(a); g[a].discard(v)
            alive.discard(v); del g[v]
        print('n',n,'minfill width',width, flush=True)
        raise SystemExit
    return 0
d.solve_portfolio = tw
sys.argv = ['x', 'environment/data', 'work/probe_out']
d.main()
