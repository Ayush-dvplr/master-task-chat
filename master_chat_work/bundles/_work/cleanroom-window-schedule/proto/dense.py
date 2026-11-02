import proto, random, sys, time
proto.DURS[0]=[30,35,40,45,50,55,60]; proto.FEES[0]=(20,120)
n=int(sys.argv[1]); reps=int(sys.argv[2])
hit=0; tot=0
for r in range(reps):
    night=proto.gen_night(random.Random(900+r), n)
    t=time.time(); b,p,c=proto.solve_dp(night); dt=time.time()-t
    if b is None: continue
    tot+=1
    b2,p2,_=proto.solve_dp(night,crew=False)
    ok,net,why=proto.evaluate(night,p2)
    diff = p2!=p
    hit+=diff
    print(r,b,c,'%.2f'%dt,'nocrew_diff' if diff else 'same', why, flush=True)
print('nocrew differs',hit,'/',tot)
