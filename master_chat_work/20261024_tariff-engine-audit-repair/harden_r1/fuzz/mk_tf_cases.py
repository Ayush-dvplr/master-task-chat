import json, random
rng = random.Random(0x62FFE6)
M = ["edge","span","qty","dup","ids","acctids","pad","padhead","tiers","card","nometer","shared","csvquote","blank"]
R = ["A0003","A0010","A0042"]
cases = []
for i in range(160):
    cases.append({"id":"P1-%03d"%i,"profile":"P1","seed":rng.randrange(10**5,10**6),"size":rng.choice([24,30,45,12,60]),
                  "reuse":rng.sample(R,rng.randrange(0,4))})
for i in range(120):
    k = i % len(M)
    muts = [M[k]] if i < len(M)*2 else rng.sample(M, rng.randrange(2,7))
    cases.append({"id":"P2-%03d"%i,"profile":"P2","seed":rng.randrange(10**5,10**6),"size":rng.choice([8,12,24,30]),"muts":muts})
S = ["shuffle","rotated","relocated","api","cwdroot","readonly","rescaled","crlf","missing"]
for i in range(72):
    cases.append({"id":"P3-%03d"%i,"profile":"P3","seed":rng.randrange(10**5,10**6),"size":rng.choice([24,30,45]),"struct":S[i%len(S)],
                  "muts": (["dup","qty"] if i%2 else [])})
open("tf_cases.jsonl","w").write("".join(json.dumps(c)+"\n" for c in cases))
print(len(cases))
