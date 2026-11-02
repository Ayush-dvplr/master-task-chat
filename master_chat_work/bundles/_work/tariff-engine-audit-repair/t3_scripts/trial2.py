import random, vouch, sys
sys.path.insert(0,'.')
from load import load
m = load(); exec(open('stmt_block.py').read(), m.__dict__)
bad=0
for t in range(400):
    r=random.Random(t); n=r.randrange(1,11); T=r.randrange(0,3000)
    vs=[(f"{r.choice('AB')}{r.randrange(1,30)}", r.randrange(1,900)) for _ in range(n)]
    vs=list(dict(vs).items())
    w=m._redeem(T,vs)
    for f in (vouch.naive, vouch.dictdp, vouch.arraydp, vouch.dfs):
        if f(T,vs)!=w: bad+=1; print(f.__name__, T, vs, w, f(T,vs)); break
print("bad", bad)
