"""Prototype wide-region extracts (scratch only). Usage: python3 gen.py OUTDIR NAME SEED [key=value ...]"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
fake = types.ModuleType("rewardkit")
class _Any:
    def __getattr__(self, name):
        return lambda *a, **k: None


fake.criteria = _Any()
fake.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = fake
spec_ = importlib.util.spec_from_file_location("tsrc", HERE.parent / "test_output.src.py")
T = importlib.util.module_from_spec(spec_)
sys.dont_write_bytecode = True
spec_.loader.exec_module(T)

DEFAULT = {"events": 3, "lo": 18, "hi": 26, "tie": 45, "zero": 6, "mult": 10, "nlo": 2, "nhi": 5,
           "scale": 0, "hold": 4, "flat": 25, "tpct": 0, "tlo": 60, "thi": 110, "maxl": 3, "twr": 0}


def wide_spec(seed: int, P: dict, bump: dict | None = None) -> dict:
    bump = bump or {}
    rng = T.Rng(seed * 6007 + 41)
    spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "floors": [], "pools": {},
            "orphan_offer_rows": [], "orphan_profile_rows": [], "late_profile_rows": [],
            "adders": {"commercial": 0, "public": 750}, "grants": (40, 30), "draws": {}}
    prefix = f"W{seed % 90 + 10}"
    roster = {region: [f"KS{region[0]}{rng.between(100, 999)}{i:02d}" for i in range(P["hi"] + 4)]
              for region in T.REGION_CODES}
    from datetime import datetime, timedelta, timezone
    season = datetime(2026, 12, 1, tzinfo=timezone.utc)
    for k in range(P["events"]):
        eid = f"{prefix}-{100 + 37 * k:04d}"
        n = rng.between(P["nlo"], P["nhi"])
        flat = rng.chance(P["flat"])
        start = (season + timedelta(minutes=30 * k)).isoformat()
        spec["events"].append(T._event(eid, n, 0 if flat else rng.between(1, 3), 0 if flat else rng.between(0, 2),
                                       rng.pick([0, 250, 500]), start))
        for ri, region in enumerate(T.REGION_CODES):
            rng0 = rng
            rng = T.Rng(seed * 6007 + 41 + 7919 * (k * 4 + ri + 1) + 104729 * bump.get((eid, region), 0))
            count = rng.between(P["lo"], P["hi"])
            ids = list(roster[region])
            rng.shuffle(ids)
            top = [0] * n
            for i in range(count):
                sid = ids[i]
                spec["sites"].append(T._site(eid, sid, code=rng.pick(T.REGION_CODES[region]),
                                             seg=rng.pick(["C", "P", "P"]), ben=f"BEN-{rng.between(1, 6)}",
                                             auth=True, hold=rng.chance(P["hold"]), weight=rng.between(1, 4)))
                made = []
                for letter in "ABC"[:rng.between(1, P["maxl"])]:
                    mult = [rng.pick([2, 3, 5]) if rng.chance(P["mult"]) else 1 for _ in range(n)]
                    relief = [rng.between(0, 120 // m) * 5 if rng.chance(60) else 0 for m in mult]
                    recovery = [rng.between(0, 80 // m) * 5 if rng.chance(35) else 0 for m in mult]
                    made.append(T._offer(eid, sid, letter, rng.between(300, 20000), relief, recovery, mult))
                if len(made) < 3 and rng.chance(P["tie"]):
                    src = rng.pick(made) if P["twr"] else made[0]
                    made.append(T._offer(eid, sid, "Z", src["cost"], list(src["r"]), list(src["v"]),
                                         list(src["m"])))
                if len(made) < 3 and rng.chance(P["zero"]):
                    made.append(T._offer(eid, sid, "Y", 0, [0] * n, [0] * n))
                spec["offers"].extend(made)
                for t in range(n):
                    top[t] += max(o["r"][t] * o["m"][t] for o in made)
            f = count if P["scale"] == 0 else P["scale"]
            spec["targets"][(eid, region)] = [(rng.between(0, 100) * 5 * f // 4, rng.between(1, 4)) for _ in range(n)]
            spec["limits"][(eid, region)] = [(rng.between(20, 120) * 5 * f // 4, rng.between(10, 80) * 5 * f // 4)
                                             for _ in range(n)]
            if P["tpct"]:
                spec["targets"][(eid, region)] = [(top[t] * rng.between(P["tlo"], P["thi"]) // 100 // 5 * 5,
                                                   rng.between(1, 4)) for t in range(n)]
                spec["limits"][(eid, region)] = [(top[t] * rng.between(P["tpct"], P["tpct"] + 40) // 100 // 5 * 5 + 5,
                                                  rng.between(10, 80) * 5 * f // 4) for t in range(n)]
            for g in ("C", "P"):
                if rng.chance(70):
                    spec["floors"].append((eid, region, g, rng.between(0, 80) * 5 * f // 4, rng.between(1, 4)))
            spec["pools"][(eid, region)] = rng.between(160, 900)
            rng = rng0
    spec["allowances"] = {}
    return spec


if __name__ == "__main__":
    out, name, seed = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    P = dict(DEFAULT)
    for kv in sys.argv[4:]:
        k, v = kv.split("=")
        P[k] = int(v)
    folder = out / name
    if folder.exists():
        import shutil
        shutil.rmtree(folder)
    out.mkdir(parents=True, exist_ok=True)
    T.write_extract(folder, wide_spec(seed, P))
    print(folder)
