import json, time, sys
sys.setrecursionlimit(100000)
def bits(x):
    while x:
        low = x & -x; yield low.bit_length()-1; x ^= low
def pc(x): return bin(x).count('1')
class S:
    def __init__(s, n, adj, w):
        s.n=n; s.adj=adj; s.w=w; s.memo={}
        A=[set(i for i in bits(a)) for a in adj]; alive=set(range(n)); s.rank=[0]*n; k=0
        while alive:
            v=min(alive,key=lambda x:(len(A[x]),x)); nb=A[v]
            for a in nb: A[a]|=nb; A[a].discard(a); A[a].discard(v)
            alive.discard(v); s.rank[v]=k; k+=1
    def comps(s, mask):
        adj=s.adj; out=[]; rest=mask
        while rest:
            low=rest&-rest; reach=low; fr=low
            while fr:
                nb=0
                for v in bits(fr): nb|=adj[v]
                nb&=rest&~reach; reach|=nb; fr=nb
            out.append(reach); rest&=~reach
        return out
    def reduce(s, mask):
        adj=s.adj; w=s.w; taken=0; tw=0; ch=True
        while ch:
            ch=False
            for v in bits(mask):
                if not (mask>>v)&1: continue
                nv=adj[v]&mask
                if nv==0:
                    taken|=1<<v; tw+=w[v]; mask&=~(1<<v); ch=True; continue
                wv=w[v]; sw=0
                for u in bits(nv): sw+=w[u]
                if wv>sw:
                    taken|=1<<v; tw+=wv; mask&=~(nv|(1<<v)); ch=True; continue
                cv=nv|(1<<v)
                for u in bits(nv):
                    if w[u]>wv and ((adj[u]&mask)|(1<<u))&~cv==0:
                        mask&=~(1<<v); ch=True; break
        return mask,taken,tw
    def solve(s, mask):
        if mask==0: return (0,0)
        r=s.memo.get(mask)
        if r is not None: return r
        m,taken,tw=s.reduce(mask)
        if m!=mask:
            sub=s.solve(m); r=(sub[0]+tw, sub[1]|taken)
        else:
            cs=s.comps(m)
            if len(cs)>1:
                a=0;b=0
                for c in cs:
                    x=s.solve(c); a+=x[0]; b|=x[1]
                r=(a,b)
            else:
                rank=s.rank; v=max(bits(m), key=lambda x: rank[x])
                inc=s.solve(m&~(s.adj[v]|(1<<v))); inc=(inc[0]+s.w[v], inc[1]|(1<<v))
                exc=s.solve(m&~(1<<v))
                r=inc if inc[0]>exc[0] else exc
        s.memo[mask]=r
        return r
for g in json.load(open('work/diag/graphs.json')):
    t=time.time(); s=S(g['n'],g['adj'],g['w']); r=s.solve((1<<g['n'])-1)
    print(g['n'], r[0]>>g['n'], pc(r[1]), 'memo', len(s.memo), round(time.time()-t,2))
