import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bookgen
seed = int(sys.argv[1]); out = sys.argv[2]; spec = json.loads(sys.argv[3])
spec["large"] = [tuple(x) for x in spec["large"]]
files, meta = bookgen.make_book(seed, spec)
os.makedirs(out, exist_ok=True)
for k, v in files.items():
    open(os.path.join(out, k), "w").write(v)
json.dump(meta, open(os.path.join(out, "..", os.path.basename(out) + "_meta.json"), "w"), indent=1)
