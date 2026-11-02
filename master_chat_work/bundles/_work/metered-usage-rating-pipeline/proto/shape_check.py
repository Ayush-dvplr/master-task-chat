"""Scratch: 300-seed shape check of the account/group block of gen_core.gen_month (shipped, hidden, long shapes)."""
import json, random, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, "/w")
import gen_core as G

SHAPES = [("shipped", 2400, False, 0), ("hidden", 1200, True, 0),
          ("long1", 76000, True, 11000), ("long2", 80000, True, 11500), ("long3", 84000, True, 12000)]


def block(seed, n_accounts, hidden, resellers):
    rng = random.Random(seed)
    pool_ids = rng.sample(range(10000, 100000 if resellers else 70000), n_accounts + 5)
    accounts, order = {}, []
    for num in pool_ids:
        acct = "AC%05d" % num
        seg = rng.choices(G.GEN_SEGMENTS, G.GEN_SEG_WEIGHTS)[0]
        plan = "committed" if rng.random() < 0.6 else "payg"
        accounts[acct] = [seg, plan]
        order.append(acct)
    normal = order[:-5]
    heavy = set(rng.sample(normal, max(1, n_accounts * 12 // 100)))
    grng = random.Random(seed * 7919 + 17)
    parent = {a: "" for a in order}
    text = {a: "" for a in order}
    info = {}
    if hidden:
        fh, fl = G._gen_small_groups(grng, normal, heavy, 10 if resellers else 25, parent, text, 0.5)
        if resellers:
            trng = random.Random(seed * 104729 + 29)
            trng.shuffle(fl)
            subs = fl[:resellers * 3 // 2]
            customers = fh + fl[resellers * 3 // 2:]
            trng.shuffle(customers)
            assert len(subs) >= resellers * 3 // 2 and len(customers) >= resellers * 4, "reseller room"
            tree = G._gen_reseller_tree(trng, subs, customers, resellers, parent, text)
            kids = {}
            for a in tree[1:]:
                kids.setdefault(parent[a], []).append(a)
            info["tree"] = len(tree)
            info["branching_nodes"] = sum(1 for v in kids.values() if len(v) >= 2)
        depth = G._gen_depths(order, parent)
        assert sum(1 for a in order if depth[a] >= 2) >= len(normal) // 40, "chains"
        if resellers:
            assert max(depth.values()) >= resellers * 3 // 4, "reseller depth"
            assert len(tree) >= resellers * 4, "reseller customers"
            assert info["branching_nodes"] >= resellers // 2, "branching"
    else:
        G._gen_small_groups(grng, normal, heavy, 5, parent, text, 0.3)
        depth = G._gen_depths(order, parent)
        assert max(depth.values()) <= 3
        assert sum(1 for a in order if depth[a] >= 2) >= 10
    grouped = [a for a in order if parent[a]]
    info["variant"] = sum(1 for a in grouped if text[a] != parent[a])
    info["plain"] = len(grouped) - info["variant"]
    info["max_depth"] = max(depth.values())
    info["depth3"] = sum(1 for a in order if depth[a] == 3)
    assert info["variant"] >= 1 and info["plain"] >= 1, "both spellings"
    return info


out = {}
for name, n, hidden, res in SHAPES:
    t0 = time.time()
    lo = {}
    for seed in range(1, 301):
        info = block(seed * 7 + 3, n, hidden, res)
        for k, v in info.items():
            lo[k] = min(lo.get(k, v), v)
        lo.setdefault("max_of_max_depth", 0)
        lo["max_of_max_depth"] = max(lo["max_of_max_depth"], info["max_depth"])
    out[name] = {"seeds": 300, "min": lo, "seconds": round(time.time() - t0, 1)}
    print(json.dumps({name: out[name]}), flush=True)
print("SHAPE_OK")
