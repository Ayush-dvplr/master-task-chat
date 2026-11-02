import proto, random, time, sys, signal
class TO(Exception): pass
def h(*a): raise TO()
signal.signal(signal.SIGALRM, h)
n=int(sys.argv[1]); reps=int(sys.argv[2]); seed=int(sys.argv[3]); ov=int(sys.argv[4]) if len(sys.argv)>4 else 7
def ev(night,p):
    if p is None: return 'NONE'
    ok,net,why=proto.evaluate(night,p)
    return net if ok else 'INF:'+why
for r in range(reps):
    night=proto.gen_night(random.Random(seed*10000+r), n, max_overlap=ov)
    t=time.time(); b,p,c=proto.solve_dp(night); dt=time.time()-t
    if b is None: print(r,'infeasible'); continue
    res={}
    res['greedy']=ev(night,proto.greedy_density(night))
    res['ls']=ev(night,proto.local_search(night,proto.greedy_density(night)))
    res['nocrew']=ev(night,proto.solve_dp(night,crew=False)[1])
    res['noinit']=ev(night,proto.solve_dp(night,initial=False)[1])
    res['nogap']=ev(night,proto.solve_dp(night,gapcarry=False)[1])
    res['lanebylane']=ev(night,proto.lane_by_lane(night))
    proto.NAIVE[0]=True
    res['naivenorm']=ev(night,proto.solve_dp(night)[1]); proto.NAIVE[0]=False
    orig=proto.norm; proto.norm=lambda l,cf,s,d:(l,cf)
    signal.alarm(20); t=time.time()
    try:
        proto.solve_dp(night); res['nonorm']='%.1fs'%(time.time()-t)
    except TO: res['nonorm']='>20s'
    signal.alarm(0); proto.norm=orig
    losses={k:(b-v if isinstance(v,int) else v) for k,v in res.items()}
    print(f"r{r} opt={b} cnt={c} t={dt:.2f}", losses, flush=True)
