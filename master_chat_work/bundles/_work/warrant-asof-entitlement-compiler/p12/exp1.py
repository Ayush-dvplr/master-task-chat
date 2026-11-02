import sys, importlib.util, tempfile, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for name, seed, zone in [x[:3] for x in t.CONV_TIERS if x[0] in sys.argv[2].split(",")]:
    c = time.time()
    conv = {"hr": "zone:" + zone, "start": "requested", "window": "closed"}
    root = Path(tempfile.mkdtemp(prefix="exp1-"))
    t.build(root, seed, 0.05, "conv", conv)
    k = {a: v for a, v in t.observe.kills.items() if a[0] == "window"}
    a = t.everything(root, conv)[1]; b = t.everything(root, dict(conv, window="half"))[1]
    for env in ("dev", "prod"):
        ka, kb = set(a[env]), set(b[env])
        dv = [x for x in ka & kb if a[env][x] != b[env][x]]
        print(name, env, "keys", len(ka), "only_closed", len(ka - kb), "only_half", len(kb - ka), "valdiff", len(dv), sorted(ka ^ kb)[:4])
    print(name, "window kills", k, "secs", round(time.time() - c))
