import sys, importlib.util, tempfile, json
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
name = sys.argv[2]
conv = t._conv_of(name); seed = [x[1] for x in t.CONV_TIERS if x[0] == name][0]
root = Path(tempfile.mkdtemp(prefix="exp4-")); t.build(root, seed, 0.05, "conv", conv)
D = t.load(root); cfg, _, _ = t.settle_config(D); W = t.World(D, cfg, conv); W.profile("prod")
print("E", W.E, "freeze", [(w["env"], t.stamp(w["start"]) - W.E, t.stamp(w["end"]) - W.E) for w in D["freeze"]], {e: cfg[e + ".freeze_applies"] for e in ("dev", "prod")})
ends = {t.stamp(w["end"]) for w in D["freeze"]}
for rid, k in W.tk.items():
    if k.get("frm") in ends or k.get("begin") in ends:
        print(rid, k["env"], k.get("state"), "frm-E", None if k.get("frm") is None else k["frm"] - W.E, "begin-E", None if k.get("begin") is None else k["begin"] - W.E)
print("need", {e: cfg[e + ".approvals_required"] for e in ("dev", "prod")})
for rid in ("T2610-80000", "T2610-80001"):
    k = W.tk[rid]
    print(rid, "ben", k["ben"], "req", k["req"], [(v[0] - W.E, v[2], v[3], W.employed(v[2], v[0]) if v[2] else None) for v in k["votes"]])
print([rid for rid in W.tk if rid.startswith("T2610-8")])
