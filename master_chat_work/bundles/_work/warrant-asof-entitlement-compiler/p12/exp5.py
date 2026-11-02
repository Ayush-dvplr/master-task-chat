import sys, importlib.util, tempfile
from pathlib import Path
from collections import Counter
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
ENV = sys.argv[3]
for name in sys.argv[2].split(","):
    conv = t._conv_of(name); seed = [x[1] for x in t.CONV_TIERS if x[0] == name][0]
    root = Path(tempfile.mkdtemp(prefix="exp5-")); g = t.generate(root, seed, 0.05, "conv"); t.attest_from_reference(root, g, seed)
    D = t.load(root); cfg = t.settle_config(D)[0]; W = t.World(D, cfg, dict(conv, window="half")); pr = W.profile(ENV); E = W.E
    c = Counter()
    for rid, k in W.tk.items():
        if k["env"] != ENV: continue
        c[k.get("state")] += 1
        if k.get("state") == "approved":
            c["has_begin"] += "begin" in k
            if "begin" in k and k["begin"] < E < k["end"]: c["covers_E"] += 1
            if "begin" in k and E - 20 * t.DAY < k["begin"] < E < k["end"]: c["recent_cover"] += 1; c["ben_" + str(pr["status"].get(k["ben"]))] += 1
    print(name, dict(c), "freeze_applies", cfg[ENV + ".freeze_applies"], "att_req", cfg[ENV + ".attestation_required"])
