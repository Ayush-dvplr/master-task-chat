import sys, time
sys.path.insert(0, 'app')
import derive_report as d
orig = d.solve_portfolio
def wrap(n, W, adj, cm, co):
    t = time.time()
    print('round n=%d edges=%d crews=%d' % (n, sum(bin(a).count('1') for a in adj)//2, len(cm)), end=' ', flush=True)
    r = orig(n, W, adj, cm, co)
    print('%.2fs' % (time.time()-t), flush=True)
    return r
d.solve_portfolio = wrap
sys.argv = ['x', 'environment/data', 'work/probe_out']
d.main()
