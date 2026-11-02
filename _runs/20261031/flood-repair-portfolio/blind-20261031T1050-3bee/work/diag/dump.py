import sys, json
sys.path.insert(0, 'app')
import derive_report as d
g=[]
oi = d.MWIS.__init__
def ini(self, n, adj, w):
    oi(self, n, adj, w)
    if n>=150: g.append({'n':n,'adj':adj,'w':w})

d.MWIS.__init__ = ini
class Stop(Exception): pass
def solve(self, m, lb): return (0,0)
d.MWIS.solve=solve
d.main(['x','environment/data','work/diag/out'])
json.dump(g, open('work/diag/graphs.json','w'))
for x in g:
    degs=sorted(bin(a).count('1') for a in x['adj']); print(x['n'], degs[-10:], degs[:10])
