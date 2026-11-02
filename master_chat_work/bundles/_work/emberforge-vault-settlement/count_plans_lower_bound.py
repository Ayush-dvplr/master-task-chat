import json, csv, sys
for c in sys.argv[1:]:
    d = f"fin/{c}/data"
    reqs = json.load(open(d + "/requisitions.json"))["requisitions"]
    ch = json.load(open(d + "/season_charter.json"))
    shops = {w["workshop_id"]: w for w in csv.DictReader(open(d + "/workshop_registry.csv"))}
    scarce = {r["reagent_id"] for r in csv.DictReader(open(d + "/reagent_registry.csv")) if r["scarce"] == "1"}
    tier = {int(k): int(v) for k, v in ch["tier_unit_cap"].items()}
    guilds = sorted(ch["guild_cap_units"]); cap = [int(ch["guild_cap_units"][g]) for g in guilds]; pool = int(ch["season_pool_units"])
    groups = {}
    for r in reqs:
        if r["reagent_id"] in scarce: continue  # plans that fund no scarce-reagent requisition: Q5 never binds them
        groups.setdefault(shops[r["workshop_id"]]["charter_id"], []).append(r)
    count = {(0, 0): 1}
    for name in sorted(groups):
        moves = []
        for r in groups[name]:
            gi = guilds.index(shops[r["workshop_id"]]["guild_id"])
            hi = min(int(r["units_requested"]), tier[int(shops[r["workshop_id"]]["charter_tier"])])
            moves += [(gi, v) for v in range(int(r["min_units"]), hi + 1)]
        new = dict(count)
        for (a, b), n in count.items():
            for gi, v in moves:
                s = [a, b]; s[gi] += v
                if s[gi] > cap[gi] or s[0] + s[1] > pool: continue
                t = (s[0], s[1]); new[t] = new.get(t, 0) + n
        count = new
    total = sum(count.values())
    print(c, "feasible plans that fund no scarce-reagent requisition:", total, "= %.3e" % total, "; at 1e7 plans/s: %.3e s" % (total / 1e7))
