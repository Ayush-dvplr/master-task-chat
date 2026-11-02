import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/h")
import load_t
t = load_t.load(os.environ.get("TESTS", "/tests/test_output.py"))
z = "Site/Ember"; conv = {"hr": "zone:" + z, "start": "requested"}
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    g = t.generate(root, 600002, 0.05, "conv")
    t.attest_from_reference(root, g, 600002)
    D = t.load(root)
    cfg, _, _ = t.settle_config(D)
    W0 = t.World(D, dict(cfg), conv)
    E, R = W0.E, W0.R
    lo, hi = E - 300 * t.DAY, min(E, R) - 2 * t.HOUR
    memo = {}
    for eid, (pid, kind, dd) in sorted(W0.hr_ev.items()):
        a, b = W0.clock.wall(z, dd), t._epoch(*dd)
        if a == b or not (lo < min(a, b) - 3 * t.HOUR and max(a, b) + 3 * t.HOUR < hi):
            continue
        mid = (a + b) // 2
        out = []
        for at in (min(a,b) - 3*t.HOUR, mid, max(a,b) + 3*t.HOUR):
            for cv in (conv, dict(conv, hr="utc")):
                c = t.gateway_cfg(D, at, memo)
                Wx = t.World(D, c, dict(t.SHIPPED_CONV, **cv))
                ks = sorted(k for e in t.GATE_ENVS for k in Wx.profile(e)["keys"] if k.startswith(pid + "|"))
                st = Wx.profile("prod")["status"].get(pid)
                out.append((len(ks), st))
        print(eid, pid, kind, dd, W0.emp_tz[pid], out, flush=True)
