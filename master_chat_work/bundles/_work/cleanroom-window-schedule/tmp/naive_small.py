import sys; sys.dont_write_bytecode=True; sys.path.insert(0,'.')
import datagen, cw
files, attempts, nights, plans, ctx = datagen.build(datagen.specs(), datagen.SEED, 3000, 2600, datagen.THRESHOLDS, 60)
bays=[(b["bay_id"], b["minute_rate"]) for b in ctx["bays"]]
quals={b:set(q) for b,q in ctx["quals"].items()}
fam={b["bay_id"]: b["initial_family"] for b in ctx["bays"]}
cnt={}
for n,p in zip(nights,plans):
    if p is None: continue
    c=datagen.to_cw(n)
    q=cw.solve_night(c,bays,quals,fam,naive=True,count=False)[1]
    if q!=p:
        sz=len(n['jobs']); cnt.setdefault(sz<=12,[]).append((n['night_id'],sz,cw.crossing_windows(c,bays,fam,q)))
    J={j["job_id"]:j for j in n["jobs"]}
    for b,_ in bays:
        seq=sorted((J[i] for i,x in p.items() if x==b), key=lambda j:(j["start"],j["job_id"]))
        if seq: fam[b]=seq[-1]["family"]
for k,v in cnt.items(): print(k,len(v),v[:8])
