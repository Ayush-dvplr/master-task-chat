"""Kill-table solvers on prototype corpora. Usage: kill2.py MODE CORPUS.json OUT.json
MODE: ref | K1 | K2 | K4 | K4w | K4q"""
import json
import sys
import time
from datetime import date

from core2 import CALENDARS, HEADLINE, KA_ALL, KD_ALL, OWN, Q_ALL, TARIFFS, conv_of, fit, recompute

HOURS = [(s, e) for s in range(0, 1440, 60) for e in range(0, 1440, 60) if s != e]
DOMS = {
    "ref": dict(),
    "K2": dict(domA=[1, 15, 30], domD=[1, 5, 10], wins=HOURS),
    "K4": dict(domA=[1, 15, 30], domD=[1, 5, 10], wins=[(1320, 360)]),
    "K4w": dict(domA=[1, 15, 16, 30], domD=[1, 5, 6, 10], wins=HOURS),
    "K4q": dict(domA=KA_ALL, domD=KD_ALL, wins=HOURS),
}


def solve(mode, doc):
    cals = {k: {date.fromisoformat(d) for d in v} for k, v in doc["calendars"].items()}
    out = {}
    for st in doc["stations"]:
        name = st["station"]
        if mode == "K1":
            kw = dict(domA=[HEADLINE["kA"]], domD=[HEADLINE["kD"]], domS=[HEADLINE["S"]],
                      domB=[HEADLINE["B"]], domH=[OWN[name]], wins=[HEADLINE["N"]])
        else:
            kw = dict(DOMS[mode])
            if mode == "K4":
                kw["domH"] = [OWN[name]]
        fits = fit(st, cals, **kw)
        if mode == "K2":
            if fits:
                k = min(fits)  # natural order of the loops
                conv, tars = conv_of(k), [f[0] for f in fits[k]]
            else:
                conv, tars = None, ["none"] * len(st["period_starts"])
        elif len(fits) == 1:
            k = next(iter(fits))
            conv = conv_of(k)
            tars = [f[0] if len(f) == 1 else "many" for f in fits[k]]
        else:
            conv, tars = None, ["many" if fits else "none"] * len(st["period_starts"])
        res = recompute(st, cals, conv, [t if isinstance(t, tuple) else None for t in tars])
        out[name] = {"tariffs": [list(t) if isinstance(t, tuple) else t for t in tars],
                     "recomputed": res, "n_fits": len(fits)}
    return out


if __name__ == "__main__":
    t0 = time.time()
    mode, src, dst = sys.argv[1:4]
    doc = json.load(open(src))
    out = solve(mode, doc)
    json.dump(out, open(dst, "w"))
    print(mode, src.rsplit("/", 1)[-1], "%.1fs" % (time.time() - t0), {k: v["n_fits"] for k, v in out.items()})
