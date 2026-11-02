import os, random, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/h")
import load_t
t = load_t.load(os.environ.get("TESTS", "/tests/test_output.py"))
rng = random.Random(4711)
zones = ["Site/Arden", "Site/Brisk", "Site/Cobalt", "Site/Dune", "Site/Ember"]
for i in range(3):
    z = rng.choice(zones)
print("seed 600002 zone", z)
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    g = t.generate(root, 600002, 0.05, "conv")
    t.attest_from_reference(root, g, 600002)
    D = t.load(root)
    cfg, _, _ = t.settle_config(D)
    W0 = t.World(D, dict(cfg), {"hr": "zone:" + z, "start": "requested"})
    E, R = W0.E, W0.R
    lo, hi = E - 300 * t.DAY, min(E, R) - 2 * t.HOUR
    print("zones", sorted(D["tz"]), "events", len(W0.hr_ev))
    from collections import Counter
    c = Counter()
    for eid, (pid, kind, dd) in W0.hr_ev.items():
        tz = W0.emp_tz[pid]
        a, b = W0.clock.wall(z, dd), t._epoch(*dd)
        inw = lo < min(a, b) - 3 * t.HOUR and max(a, b) + 3 * t.HOUR < hi
        c[(kind, inw, a != b, bool(W0.mine.get(pid)))] += 1
    for k, v in sorted(c.items()):
        print(k, v)
