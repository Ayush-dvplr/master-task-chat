import sys, time, collections
import gen, rec
bad=0; n=0; st=collections.Counter()
t0=time.time()
for seed in range(int(sys.argv[1])):
    for prof in ("shipped","dense","restart"):
        b=gen.build_book(seed*7+1, prof, 2)
        for img in b["images"]:
            res=rec.recover(img)
            n+=1
            if res["status"]!="recovered": st["rej"]+=1; continue
            vals={p:d["slots"] for p,d in res["pages"].items()}
            if vals!=img["truth"]:
                bad+=1
            st["recs"]+=len(img["records"]); st["losers"]+=len(res["losers"]); st["clrs"]+=sum(1 for r in img["records"] if r["type"]=="clr")
print("images",n,"bad",bad,dict(st),round(time.time()-t0,2))
