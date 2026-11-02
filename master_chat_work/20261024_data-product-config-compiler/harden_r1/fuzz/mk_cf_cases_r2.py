import json, random
rng = random.Random(42719)
M = ["dates","ids","jtypes","seq","text","quota","weights","nulls","logs","orphans","env"]
S = ["shuffle","rescale","shift","crlf","missing","baddate","mismatch","renamed","nested","readonly","cwdroot"]
def day():
    y = rng.choice([2025,2026,2027,2028,2029,2030]); m = rng.randint(1,12)
    d = rng.randint(1,28) if rng.random()<.7 else {2:29 if y%4==0 else 28,4:30,6:30,9:30,11:30}.get(m,31)
    return y,m,"%04d-%02d-%02d"%(y,m,d)
def case(i,p,muts,st,hidden=True):
    y,m,d = day()
    return {"id":"%s-%03d"%(p,i),"profile":p,"seed":rng.randint(100000,999999),"size":rng.randint(380,560),
            "hidden":hidden,"date":d,"release":"%04d.%02d-r%d"%(y,m,rng.randint(4,9)),"muts":muts,"struct":st}
out=[]
for i in range(150): out.append(case(i,"P1",[],"none",hidden=i%4!=3))
for i in range(110):
    muts=[M[i%len(M)]] if i<44 else rng.sample(M,rng.randint(2,len(M)))
    out.append(case(i,"P2",muts,"none"))
for i in range(66): out.append(case(i,"P3",rng.sample(M,2) if i%2 else [],S[i%len(S)]))
open("cf_cases_r2.jsonl","w").write("".join(json.dumps(c)+"\n" for c in out)); print(len(out))
