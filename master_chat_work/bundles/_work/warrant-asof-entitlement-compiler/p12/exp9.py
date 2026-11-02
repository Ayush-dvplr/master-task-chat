import sys, importlib.util, tempfile, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
zone, window = sys.argv[2], sys.argv[3]
def diff(a, b):
    return {e: len(set(a[e]) ^ set(b[e])) + sum(1 for k in set(a[e]) & set(b[e]) if a[e][k] != b[e][k]) for e in ("dev", "prod")}
for seed in [int(s) for s in sys.argv[4].split(",")]:
    c = time.time()
    conv = {"hr": "zone:" + zone, "start": "requested", "window": window}
    full = dict(t.SHIPPED_CONV, **conv)
    root = Path(tempfile.mkdtemp(prefix="exp9-"))
    try:
        t.build(root, seed, 0.05, "conv", conv)
    except Exception as e:
        print(seed, "BUILD FAIL", type(e).__name__, e, flush=True); continue
    exp = t.everything(root, conv)[1]
    out = {st: diff(exp, t.everything(root, dict(full, start=st))[1]) for st in ("decided", "recorded", "latest")}
    out["hr_site"] = diff(exp, t.everything(root, dict(full, hr="site"))[1])
    out["hr_utc"] = diff(exp, t.everything(root, dict(full, hr="utc"))[1])
    w = "half" if window == "closed" else "closed"
    out["win_" + w] = diff(exp, t.everything(root, dict(full, window=w))[1])
    ok = all(v["dev"] > 0 and v["prod"] > 0 for v in out.values())
    print(seed, "ALLBOTH" if ok else "weak", out, "secs", round(time.time() - c), flush=True)
