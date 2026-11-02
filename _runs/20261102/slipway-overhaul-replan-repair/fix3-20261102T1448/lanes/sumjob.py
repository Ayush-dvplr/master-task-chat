import json,sys,glob
for j in sys.argv[1:]:
    for f in glob.glob(j+"/*/verifier/reward-details.json"):
        d=json.load(open(f))["reward"]
        c=d["components"][0]["detail"]["criteria"]
        pos=sum(x["weight"]*x["value"] for x in c if x["weight"]>0); neg=sum(x["weight"]*x["value"] for x in c if x["weight"]<0)
        hit=[f'{x["name"]}({x["weight"]:g})' for x in c if x["value"] and x["weight"]>0]
        negh=[f'{x["name"]}({x["weight"]:g})' for x in c if x["value"] and x["weight"]<0]
        r=json.load(open(f.replace("reward-details","reward")))["reward"]
        res=json.load(open(f.rsplit("/verifier/",1)[0]+"/result.json"))
        vt=res.get("verifier",{}) or {}
        from datetime import datetime as D
        t=lambda k: D.fromisoformat(vt[k].replace("Z","+00:00"))
        sec=(t("finished_at")-t("started_at")).total_seconds() if vt.get("started_at") else -1
        print(j.rsplit("/",1)[-1], "verifier_s",round(sec,1), "reward",r,"pos",pos,"neg",neg,"net",pos+neg,"/112")
        print("  pos hit:",", ".join(hit)); print("  neg hit:",", ".join(negh))
