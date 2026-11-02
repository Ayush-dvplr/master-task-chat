"""Kill rows for the meter-convention lever. Usage: killconv.py kind:seed ..."""
import sys, time

from conv import conv, FITTERS, fits, S
from core import solve_flow, families, DEPOTS

for spec in sys.argv[1:]:
    kind, seed = spec.split(":")
    t0 = time.time()
    inst = conv(int(seed), kind)
    tg = time.time() - t0
    t0 = time.time()
    x = solve_flow(inst)
    fam, obj = families(inst, x)
    tr = time.time() - t0
    nfit1 = {d: len([k for k in range(S) if fits(inst["tod"], [h for h in inst["hist"][d] if h[0] == 0], k)]) for d in DEPOTS}
    print("REF", spec, "gen %.1fs" % tg, "ref %.2fs" % tr, "k", inst["k"], "obj", obj,
          "sessions", sum(len(v) for v in inst["hist"].values()), "firstday_fits", nfit1, flush=True)
    for name, f in FITTERS.items():
        believed = dict(inst)
        believed["dprice"] = f(inst)
        t0 = time.time()
        xb = solve_flow(believed)
        fb, ob = families(believed, xb)
        same = [k for k in fam if fam[k] == fb[k]]
        diff = [k for k in fam if fam[k] != fb[k]]
        print("ROW", name, spec, "%.2f" % (time.time() - t0), "EXACT" if not diff else "WRONG",
              "kept %d/%d" % (len(same), len(fam)), "obj", ob, "firstdiff", diff[:1], flush=True)
print("ALL_DONE")
