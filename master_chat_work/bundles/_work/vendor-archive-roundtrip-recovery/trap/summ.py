import json,sys
rows={}
for ph in ("before","after"):
    for v in "oracle a2 L2s L2u L2e L6 L3 L5c L5i L5n".split():
        d=json.loads(open(f"{ph}.{v}.json").read().strip().splitlines()[-1]); r,w=d["res"],d["weights"]
        lost=[n for n in w if w[n]>0 and not r[n]]; fired=[n for n in w if w[n]<0 and r[n]]
        loss=sum(w[n] for n in lost); tot=sum(x for x in w.values() if x>0)
        rows[f"{ph}.{v}"]=dict(loss=loss,lost=lost,fired=fired)
        print(ph,v,"loss",loss,"/",tot,"kept",round((tot-loss)/tot,4),"fired",fired); print("   ",lost)
json.dump(rows,open("summary.json","w"),indent=1)
