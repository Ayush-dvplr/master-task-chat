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
fam=sys.argv[1]; n=int(sys.argv[2]); seed=int(sys.argv[3]); lim=float(sys.argv[4])
kw={}
for a in " ".join(sys.argv[5:]).split():
    k,v=a.split("="); kw[k]=float(v) if "." in v else int(v)
r=random.Random(seed*1000)
n_,w,cl,pr=getattr(gen,fam)(r,n,**kw)
# relabel randomly so ids carry no geometry
perm=list(range(n_)); r.shuffle(perm)
inv={perm[i]:i for i in range(n_)}
w2=[0]*n_
for i in range(n_): w2[perm[i]]=w[i]
cl2=[[perm[v] for v in c] for c in cl]; pr2=[(perm[a],perm[b]) for a,b in pr]
rank=list(range(n_))
W=mw.tiebreak_weights(w2,rank); adj=mw.build_adj(n_,cl2,pr2)
rv,rs,_=mw.ref_solve(n_,W,adj)
for rule in ["low","mindeg","maxdeg","maxw"]:
    t=time.time(); ok,v,s,c=memo_rule(n_,W,adj,lim,rule)
    print(seed,rule,"cert" if ok else "TO","%.1f"%(time.time()-t),c,("match" if ok and s==rs else ""),flush=True)
