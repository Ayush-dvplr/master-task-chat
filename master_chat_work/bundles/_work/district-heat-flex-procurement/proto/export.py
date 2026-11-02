"""Dump every event-region portfolio problem of an extract as JSON (scratch). Usage: export.py EXTRACT OUT.json"""
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SOLVE = Path(__file__).resolve().parents[3] / "district-heat-flex-procurement/solution/solve.py"
spec = importlib.util.spec_from_file_location("solve", SOLVE)
S = importlib.util.module_from_spec(spec)
sys.modules["solve"] = S
spec.loader.exec_module(S)

problems = []


def grab(ex, event, region, candidates):
    eid = event["event_id"]
    n = int(event["interval_count"])
    by_site = {}
    for o in candidates:
        by_site.setdefault(o.site.site_id, []).append(o)
    problems.append({
        "er": [eid, region], "n": n,
        "target": [list(ex.targets.get((eid, region, t + 1), (0, 0))) for t in range(n)],
        "limit": [list(ex.ceilings.get((eid, region, t + 1), (0, 0))) for t in range(n)],
        "cw": int(event["objective"]["cost_weight"]), "rw": int(event["objective"]["recovery_weight"]),
        "floors": {s: list(ex.floors.get((eid, region, s), (0, 0))) for s in ex.segments},
        "lanes": [[{"id": o.offer_id, "rel": list(o.relief), "rec": list(o.recovery), "cost": o.cost,
                    "seg": o.site.segment} for o in by_site[sid]] for sid in sorted(by_site)],
    })
    return [], 1


S.choose_portfolio = grab
if __name__ == "__main__":
    S.build(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(problems))
    print(len(problems), "problems; sites per ER", sorted(len(p["lanes"]) for p in problems))
