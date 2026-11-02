"""Scratch: build prototype long corpora + expected docs; check old hidden corpus unchanged."""
import hashlib, json, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import t_proto as T

def digest(files):
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode()); h.update(files[k])
    return h.hexdigest()

if "--check-old" in sys.argv:
    import t_orig as O
    a = O.gen_month(O.HIDDEN_SEED, O._hidden_month(), 1600, 1200, True, O.ref_compute)
    b = T.gen_month(T.HIDDEN_SEED, T._hidden_month(), 1600, 1200, True, T.ref_compute)
    print("old hidden identical:", digest(a) == digest(b), digest(a)[:16])
    ea, eb = O.ref_compute(a), T.ref_compute(a)
    print("ref identical on old hidden:", json.dumps(ea, sort_keys=True, default=str) == json.dumps(eb, sort_keys=True, default=str))
    sys.exit()

seed, rows, nacc, chain = (int(x) for x in sys.argv[1:5])
rng = random.Random(seed)
month = "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))
t0 = time.time()
files = T.gen_month(seed, month, rows, nacc, True, T.ref_compute, chain=chain)
t1 = time.time()
docs = T.ref_compute(files)
t2 = time.time()
d = "corpus_%d" % seed
os.makedirs(d + "/in", exist_ok=True); os.makedirs(d + "/exp", exist_ok=True)
for k, v in files.items():
    open(os.path.join(d, "in", k), "wb").write(v)
json.dump(docs, open(d + "/exp/docs.json", "w"), default=str, sort_keys=True)
n = len(docs["normalized.jsonl"])
print(json.dumps({"seed": seed, "month": month, "gen_s": round(t1 - t0, 2), "ref_s": round(t2 - t1, 2), "lines": n,
                  "accounts": nacc, "chain": chain, "digest": digest(files)[:16],
                  "sizes": {k: len(v) for k, v in files.items()}}))
