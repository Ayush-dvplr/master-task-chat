"""Run solve.py whole with its portfolio search replaced by a scratch solver. Usage: run_prog.py SOLVER DATA OUT"""
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import solvers  # noqa: E402

SOLVE = Path(sys.argv[4]) if len(sys.argv) > 4 else HERE.parents[2] / "district-heat-flex-procurement/solution/solve.py"
spec = importlib.util.spec_from_file_location("solve", SOLVE)
S = importlib.util.module_from_spec(spec)
sys.modules["solve"] = S
spec.loader.exec_module(S)
name = sys.argv[1]


def patched(ex, event, region, candidates):
    eid = event["event_id"]
    n = int(event["interval_count"])
    by_site = {}
    for o in candidates:
        by_site.setdefault(o.site.site_id, []).append(o)
    p = {"er": [eid, region], "n": n,
         "target": [list(ex.targets.get((eid, region, t + 1), (0, 0))) for t in range(n)],
         "limit": [list(ex.ceilings.get((eid, region, t + 1), (0, 0))) for t in range(n)],
         "cw": int(event["objective"]["cost_weight"]), "rw": int(event["objective"]["recovery_weight"]),
         "floors": {s: list(ex.floors.get((eid, region, s), (0, 0))) for s in ex.segments},
         "lanes": [[{"id": o.offer_id, "rel": list(o.relief), "rec": list(o.recovery), "cost": o.cost,
                     "seg": o.site.segment} for o in by_site[sid]] for sid in sorted(by_site)]}
    by_id = {o.offer_id: o for o in candidates}
    key, ways, ids = solvers.SOLVERS[name](p)
    return [by_id[i] for i in sorted(ids)], ways


if name != "solve":
    S.choose_portfolio = patched
sys.argv = [sys.argv[0], sys.argv[2], sys.argv[3]]
S.main(sys.argv)
