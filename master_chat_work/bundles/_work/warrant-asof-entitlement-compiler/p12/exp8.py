import sys, importlib.util, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
def diff(a, b):
    return {e: len(set(a[e]) ^ set(b[e])) + sum(1 for k in set(a[e]) & set(b[e]) if a[e][k] != b[e][k]) for e in ("dev", "prod")}
for name in sys.argv[2].split(","):
    row = [x for x in t.CONV_TIERS if x[0] == name][0]
    conv = t._conv_of(name) if hasattr(t, "_conv_of") else {"hr": "zone:" + row[2], "start": "requested"}
    full = dict(t.SHIPPED_CONV, **conv)
    root = Path(tempfile.mkdtemp(prefix="exp8-")); t.build(root, row[1], 0.05, "conv", conv)
    exp = t.everything(root, conv)[1]
    out = {}
    for st in ("decided", "recorded", "latest"):
        out[st] = diff(exp, t.everything(root, dict(full, start=st))[1])
    out["hr_site"] = diff(exp, t.everything(root, dict(full, hr="site"))[1])
    out["hr_utc"] = diff(exp, t.everything(root, dict(full, hr="utc"))[1])
    w = "half" if full.get("window", "half") == "closed" else "closed"
    out["win_" + w] = diff(exp, t.everything(root, dict(full, window=w))[1])
    print(name, full, out, flush=True)
