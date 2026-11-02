"""Time the oracle plan_migration call on each ladder (3 runs each) to set K14's N.

    python3 measure_n.py  -> prints per-ladder timings and N = max(10, ceil(10 x slowest))
"""
import importlib.util, json, math, sys, time
from pathlib import Path
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parent / "rewardkit_stub"))
sys.path.insert(0, str(WORK / "repo_fixed" / "src"))
spec = importlib.util.spec_from_file_location("t", WORK / "test_output.src.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
import migrakit
slowest = 0.0
report = {}
for name in t.LADDERS:
    lspec, job, expected = t.case_ladder(name)
    registry = migrakit.load_contracts(lspec.write())
    runs = []
    for _ in range(3):
        start = time.perf_counter()
        plan = migrakit.plan_migration(registry, job["schema"], job["payload"])
        runs.append(time.perf_counter() - start)
        registry = migrakit.load_contracts(lspec.write())
    assert plan == expected, name
    states = len({(e[1]) for e in lspec.edges})
    report[name] = {"runs_sec": [round(r, 4) for r in runs], "edges": len(lspec.edges), "schemas": len(lspec.schemas), "plan_len": len(plan)}
    slowest = max(slowest, max(runs))
n = max(10, math.ceil(10 * slowest))
doc = {"ladders": report, "slowest_sec": round(slowest, 4), "N": n}
(WORK / "n_measure.json").write_text(json.dumps(doc, indent=1) + "\n")
print(json.dumps(doc, indent=1))
