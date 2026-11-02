import json, random
R = random.Random(8402)
WINS = ["WIN-PRE", "WIN-AUTH", "WIN-AUTH-V099", "WIN-OLD"]
TEN = ["t-atlas", "t-borealis", "t-cinder"] + ["t-f%03d" % i for i in range(10)]


def row(i, tag, edge=False):
    rev = R.choice([1, 2])
    key = R.choice(["K042"] * 3 + ["K118"])
    win = R.choice(["WIN-AUTH"] * 4 + WINS)
    ver = "v100" if R.random() < 0.8 else R.choice(["v099", "v040"])
    st = "active" if R.random() < 0.8 else "superseded"
    to = R.randint(-5, 5) if rev == 1 else R.randint(-900, 900)
    mr = R.randint(-60, 60)
    rt = R.randint(0, 3)
    rk = R.randint(0, 20)
    if edge:
        to = R.choice([-5, 5, 0]) if rev == 1 else R.choice([-900, 900, 0, 1, -1])
        mr = R.choice([-60, 60, -40, 20, 0])
        rk = R.choice([0, 20, 20, 12, 4])
        rt = R.choice([0, 3])
    return ["OV-%s-%s%d" % (key, tag, i), key, st, win, ver, rev, to, mr, rt, rk]


cases = []
for i in range(150):
    n = R.randint(3, 9)
    cases.append({"id": "P1-%03d" % i, "profile": "P1", "seed": i, "head": [row(j, "h%d_" % i) for j in range(n)],
                  "allowance": R.randint(1, 6), "corrupt": R.choice([None, None, R.choice(TEN)]), "struct": "none"})
for i in range(100):
    k = i % 10
    n = R.randint(1, 10)
    head = [row(j, "e%d_" % i, edge=True) for j in range(n)]
    c = {"id": "P2-%03d" % i, "profile": "P2", "seed": 1000 + i, "head": head, "allowance": R.choice([1, 6, n, max(1, n - 1)]),
         "corrupt": None, "struct": "none"}
    if k == 0:   # windows boundary: a window starting exactly at the instant / ending one second later / ending at the instant
        c["windows"] = {"WIN-AUTH": R.choice([[1700000000, 1700000001, "v100"], [1699999999, 1700000000, "v100"], [1700000000, 1700005000, "v100"]])}
    elif k == 1:  # version flip of windows
        c["windows"] = {"WIN-AUTH-V099": [1699999500, 1700000500, "v100"], "WIN-PRE": [1699998000, 1700000001, "v100"]}
    elif k == 2:  # max_records rounding tie: 300 + sum = 260 (x 1.075 = 279.5)
        c["head"] = [["OV-K042-t%d" % i, "K042", "active", "WIN-AUTH", "v100", 2, 0, -40, 0, 20]] + head[:2]
        c["allowance"] = 1
    elif k == 3:  # every row of another principal before K042 rows uses up the allowance
        c["head"] = [["OV-K118-q%d_%d" % (i, j), "K118", "active", "WIN-AUTH", "v100", 2, 10, 1, 0, 1] for j in range(R.randint(1, 6))] + head
        c["allowance"] = R.randint(1, 6)
    elif k == 4:  # an atlas row naming a third principal
        c["head"] = head + [["OV-K200-z%d" % i, "K200", "active", "WIN-AUTH", "v100", 2, 5, 5, 1, 1]]
        R.shuffle(c["head"])
    elif k == 5:  # risk mutation of shipped rows (no head)
        c["head"] = None
        c["risk"] = {"OV-K042-auth": R.randint(0, 20)}
        c["allowance"] = R.randint(1, 6)
    elif k == 6:  # corrupt rows of a random tenant, incl atlas
        c["corrupt"] = R.choice(TEN)
    elif k == 7:  # superseded and inactive rows with huge deltas mixed in
        for r in c["head"]:
            if R.random() < 0.5:
                r[2] = "superseded"
    elif k == 8:  # cap exceeded: big positive max_records
        c["head"] = [["OV-K042-m%d_%d" % (i, j), "K042", "active", "WIN-AUTH", "v100", 2, 900, 60, 3, 20] for j in range(6)]
        c["allowance"] = 6
    elif k == 9:  # allowance-only change on the shipped head
        c["head"] = None
        c["allowance"] = R.randint(1, 6)
    cases.append(c)
structs = ["renamed", "cwdroot", "keyshuffle", "reindent", "quotashuffle"]
for i in range(60):
    base = dict(cases[i])
    base.update({"id": "P3-%03d" % i, "profile": "P3", "struct": structs[i % 5]})
    cases.append(base)
with open("/tmp/test_depth-20261024T2141/fz/sp_cases.jsonl", "w") as fh:
    for c in cases:
        fh.write(json.dumps(c) + "\n")
print(len(cases))
