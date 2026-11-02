import proto, random, time, sys
n=int(sys.argv[1]); lanes=int(sys.argv[2]); ov=int(sys.argv[3])
orig=proto.norm
for r in range(3):
    night=proto.gen_night(random.Random(77+r), n, n_lanes=lanes, max_overlap=ov)
    t=time.time(); b,p,c=proto.solve_dp(night); t1=time.time()-t
    proto.norm=lambda lst,cf,s,d:(lst,cf)
    t=time.time(); b2,p2,c2=proto.solve_dp(night); t2=time.time()-t
    proto.norm=orig
    print(f"n={n} lanes={lanes} ov={ov} opt={b} count={c} norm={t1:.2f}s nonorm={t2:.2f}s same={b==b2}",flush=True)
