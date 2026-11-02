import copy, time, gen, rec
PROF = dict(gen.PROFILES["dense"]); PROF["recs"] = (1200, 1200); PROF["pages"] = (24, 24)
gen.PROFILES["max"] = PROF
TB = {"TB_textbook": {"textbook_end": 1, "eager_pagelsn": 1}, "TB_end_only": {"textbook_end": 1},
      "TB_eager_only": {"eager_pagelsn": 1}, "TB_one_hop": {"one_hop": 1}}
for prof, n, seeds in (("dense", 12, (11, 12, 13)), ("restart", 12, (21, 22, 23)), ("max", 8, (31,)), ("shipped", 24, (5,))):
    for seed in seeds:
        b = gen.build_book(seed, prof, n)
        t0 = time.time(); ref = rec.docs(copy.deepcopy(b)); dt = time.time() - t0
        mx = max(len(i["records"]) for i in b["images"])
        out = []
        for k, f in TB.items():
            d = rec.docs(copy.deepcopy(b), f)
            out.append(k + ":" + ("".join(x[0] for x in ("core", "metrics", "dep", "summary") if d[x] != ref[x]) or "-"))
        print(prof, seed, "maxrecs", mx, "ref_s_per_img", round(dt / n, 4), " ".join(out))
