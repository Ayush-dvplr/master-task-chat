import json, random
r = random.Random(8405)
out = []
fixes = [[], ["prec"], ["env"], ["ident"], ["prec", "env", "ident"]]
for i in range(150):
    out.append({"id": "P1-%03d" % i, "profile": "P1", "seed": r.randint(10**7, 10**8 - 1), "fix": fixes[i % 5], "muts": [], "struct": "none"})
mset = [["waivers"], ["revision"], ["waivers", "revision"]]
for i in range(100):
    fx = r.sample(["prec", "env", "ident", "env2"], r.randint(0, 3))
    out.append({"id": "P2-%03d" % i, "profile": "P2", "seed": r.randint(10**7, 10**8 - 1), "fix": fx, "muts": mset[i % 3] if i % 10 else ["env2_only"][:0], "struct": "none"})
structs = ["reverse", "renamed", "cwdroot", "readonly"]
for i in range(64):
    out.append({"id": "P3-%03d" % i, "profile": "P3", "seed": r.randint(10**7, 10**8 - 1), "fix": fixes[i % 5], "muts": (["waivers"] if i % 2 else []), "struct": structs[i % 4]})
open("cm_cases.jsonl", "w").write("".join(json.dumps(c) + "\n" for c in out))
print(len(out))
