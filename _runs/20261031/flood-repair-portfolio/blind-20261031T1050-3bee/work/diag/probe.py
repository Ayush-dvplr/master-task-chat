import sys, time, json, csv, collections
sys.path.insert(0, 'app')
import derive_report as d
# monkeypatch MWIS to time per round
orig = d.MWIS.solve
calls = [0]
def s(self, mask, lb):
    calls[0] += 1
    if calls[0] % 200000 == 0:
        print('calls', calls[0], 'n', self.n, 'memo', len(self.memo), 'fail', len(self.fail), time.time()-t0, flush=True)
    return orig(self, mask, lb)
d.MWIS.solve = s
oi = d.MWIS.__init__
def ini(self, n, adj, w):
    oi(self, n, adj, w); print('round n', n, 'edges', sum(bin(a).count('1') for a in adj)//2, 'calls so far', calls[0], round(time.time()-t0,2), flush=True)
d.MWIS.__init__ = ini
t0 = time.time()
d.main(['x', 'environment/data', 'work/diag/out'])
print('done', time.time()-t0)
