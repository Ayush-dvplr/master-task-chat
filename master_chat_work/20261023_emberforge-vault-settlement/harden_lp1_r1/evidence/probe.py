import sys, pathlib, tempfile, json
sys.argv=[sys.argv[0], sys.argv[1]] + sys.argv[2:]
import variants as VV
T=VV.T
for name in sys.argv[2:]:
    seed, params, mut = T.SEASONS[name]
    d = pathlib.Path(tempfile.mkdtemp())/"data"
    T._build_corpus_dir(d, params=params, mutate=mut, main_seed=seed)
    corp=T.load(d,"")
    held = sorted(r["reagent_id"] for r in corp["reagents"] if r["scarce"])[0] if isinstance(corp,dict) and "reagents" in corp else None
    w=T.settle(corp, params)
    r=VV.V["REFLEX_all3"].settle(VV.V["REFLEX_all3"].load(d,""), params.__class__(*params) if False else VV.V["REFLEX_all3"].Params(params.schedule,params.quantiser,params.order,params.base))
    def clos(res):
        return {x["reagent_id"]:x["closing_units"] for x in res["vault_audit.json"]["reagents"] if x["scarce"]}
    print(name, "held", held)
    print(" truth", clos(w)); print(" reflx", clos(r))
    reqs=json.loads((d/"requisitions.json").read_text())["requisitions"]
    print(" reqs on held", sum(1 for q in reqs if q["reagent_id"]==held), "sum requested", sum(q["units_requested"] for q in reqs if q["reagent_id"]==held))
    print(" alloc truth", w["allocation.json"]["allocated_total"], "reflex", r["allocation.json"]["allocated_total"], "pool", w["allocation.json"]["pool_units"])
