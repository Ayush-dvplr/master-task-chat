import json, collections, sys
R=[json.loads(l) for l in open("tf_out.jsonl")]
progs=["agent","oracle","VA_qty_coerce","VA_month_calendar","VA_month_30","VA_half_up","VA_credit_rounded"]
gen=[r for r in R if "gen_error" in r]; ok=[r for r in R if "gen_error" not in r]
print("cases",len(R),"gen_error",len(gen),"valid",len(ok),"ref_error",sum(1 for r in ok if "ref_error" in r))
tab={}
for p in progs:
    c=collections.Counter(); tot=collections.Counter()
    for r in ok:
        ph=r["profile"]; tot[ph]+=1; tot["ALL"]+=1
        if r.get(p,{}).get("diff"): c[ph]+=1; c["ALL"]+=1
    tab[p]={k:(c[k],tot[k],round(100*c[k]/tot[k],1)) for k in ("P1","P2","P3","ALL")}
    print(p.ljust(18)," ".join("%s %d/%d=%.1f%%"%(k,*tab[p][k]) for k in ("P1","P2","P3","ALL")))
json.dump(tab,open("summary.json","w"),indent=1)
