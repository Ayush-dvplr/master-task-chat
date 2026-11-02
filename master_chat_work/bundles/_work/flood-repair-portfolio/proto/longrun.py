import random, sys, time, mw, gen
fam=sys.argv[1]; n=int(sys.argv[2]); seed=int(sys.argv[3]); which=sys.argv[4]; lim=float(sys.argv[5])
kw={}
for a in " ".join(sys.argv[6:]).split():
    k,v=a.split("="); kw[k]=float(v) if "." in v else int(v)
r=random.Random(seed*1000)
n_,w,cl,pr=getattr(gen,fam)(r,n,**kw)
perm=list(range(n_)); r.shuffle(perm)
W=mw.tiebreak_weights(w,perm); adj=mw.build_adj(n_,cl,pr)
rv,rs,_=mw.ref_solve(n_,W,adj)
t=time.time()
if which=="memo": ok,v,s,c=mw.bnb_memo(n_,W,adj,lim)
elif which=="classic": ok,v,s,c=mw.bnb_classic(n_,W,adj,lim)
elif which=="ordered": ok,v,s,c=mw.memo_ordered(n_,W,adj,lim)
print(which, "certified" if ok else "timeout", "%.1fs"%(time.time()-t), "nodes",c, "match" if ok and s==rs else "", flush=True)
