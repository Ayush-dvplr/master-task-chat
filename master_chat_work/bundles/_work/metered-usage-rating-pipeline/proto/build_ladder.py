"""Scratch: build one tier-ladder corpus with the work generator; print shape and cost figures."""
import bisect, json, os, random, sys, time
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(here))
import gen_core as G, ref_core as R
seed, rows, nacc, ladder = (int(x) for x in sys.argv[1:5])
resellers = int(sys.argv[5]) if len(sys.argv) > 5 else 0
rng = random.Random(seed)
month = "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))
t0 = time.time(); files = G.gen_month(seed, month, rows, nacc, True, R.ref_compute, resellers=resellers, ladder=ladder); t1 = time.time()
docs = R.ref_compute(files); t2 = time.time()
card = json.loads(files["rate_card.json"])
starts = {c: [t["from"] for t in v["tiers"]] for c, v in card["products"].items()}
lines = docs["normalized.jsonl"]
pos = [ln["tier"] - 1 for ln in lines]
fwd = sum(p + 1 for p in pos)
rev = sum(len(starts[ln["product"]]) - ln["tier"] + 1 for ln in lines)
full = sum(len(starts[ln["product"]]) for ln in lines)
d = os.path.join(here, "ladder_%d" % seed)
os.makedirs(d + "/in", exist_ok=True)
for k, v in files.items():
    open(os.path.join(d, "in", k), "wb").write(v)
print(json.dumps({"seed": seed, "month": month, "rows": rows, "n": nacc, "ladder": ladder, "gen_s": round(t1 - t0, 1),
                  "ref_s": round(t2 - t1, 2), "lines": len(lines), "card_mb": round(len(files["rate_card.json"]) / 1e6, 1),
                  "distinct_tiers_used": len({(ln["product"], ln["tier"]) for ln in lines}),
                  "steps_full": full, "steps_fwd_break": fwd, "steps_rev_break": rev}), flush=True)
