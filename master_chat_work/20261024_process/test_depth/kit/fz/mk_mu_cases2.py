import json, random
rng = random.Random(84011)
M = ["edge","acct","units_ok","units_bad","dupconf","ties","tier","tier_unsorted","pool","plan","pc_unsorted","offsets","pad","zero_product"]
def month(): return "%d-%02d" % (rng.randint(2025, 2030), rng.randint(1, 12))
cases = []
for i in range(80):
    h = i < 55
    cases.append({"id": "P1b-%03d" % i, "profile": "P1", "seed": rng.randint(100000, 999999), "month": month(),
                  "rows": 1600 if h else rng.randint(200, 2000), "accts": 1200 if h else rng.randint(100, 1500), "hidden": h, "muts": [], "struct": "none"})
for i in range(70):
    small = i % 5 == 0
    mo = rng.choice(["2028-02", "2027-12", "2029-01", "2026-02", month()])
    muts = [M[i % len(M)]] + rng.sample(M, rng.randint(1, 4)) if not small else rng.sample(M, 2)
    muts = sorted(set(muts), key=M.index)
    cases.append({"id": "P2b-%03d" % i, "profile": "P2", "seed": rng.randint(100000, 999999), "month": mo,
                  "rows": rng.randint(5, 40) if small else rng.choice([300, 800, 1600]),
                  "accts": rng.randint(8, 30) if small else rng.choice([200, 600, 1200]), "hidden": (i % 2 == 0) and not small, "muts": muts, "struct": "none"})
S = ["shuffle", "renamed", "nested", "cwdroot", "readonly", "tierscale", "poolhalf"]
for i in range(42):
    cases.append({"id": "P3b-%03d" % i, "profile": "P3", "seed": rng.randint(100000, 999999), "month": month(),
                  "rows": 1600, "accts": 1200, "hidden": True, "muts": [], "struct": S[i % len(S)]})
with open("mu_cases2.jsonl", "w") as f:
    for c in cases: f.write(json.dumps(c) + "\n")
print(len(cases))
