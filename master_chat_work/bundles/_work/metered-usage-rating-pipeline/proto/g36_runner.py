"""Docker-only scorer: load tests/test_output.py once, keep generator and expected caches, score many programs.

Usage (inside python:3.12-slim, bundles dir mounted at /bb, rewardkit stub at /rk):
  python -B w2_runner.py cost    -> WORK/cost_table.json + proto/logs/cost_rows.json
  python -B w2_runner.py rules   -> WORK/RULE_COVERAGE.md + WORK/rule_coverage.json
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, "/rk")
PROTO = Path(__file__).resolve().parent
WORK = PROTO.parent
sys.path.insert(0, str(WORK))
import cost_table  # noqa: E402
import rewardkit  # noqa: E402

AGENT = Path("/agent")
SCRATCH = Path("/tmp/w2score")

spec = importlib.util.spec_from_file_location("t_out", str(cost_table.TESTS))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
NAMES = list(rewardkit.criteria.items)


def warm():
    t = time.time()
    T._shipped_files()
    T._hidden_files()
    for k in (1, 2, 3):
        T._long_files(k)
        T._expected("long-%d" % k, lambda k=k: T._long_files(k))
    for k in (1, 2, 3, 4):
        T._ladder_files(k)
        T._expected("ladder-%d" % k, lambda k=k: T._ladder_files(k))
    T._tier_scaled_files()
    T._small_commitment_files()
    T._near_base_files()
    print("warm %.1f s" % (time.time() - t), flush=True)


def score(label, source):
    keep = {k for k in T._CACHE if not k.startswith("run-")}
    for k in list(T._CACHE):
        if k not in keep:
            del T._CACHE[k]
    app = SCRATCH / label
    if app.exists():
        shutil.rmtree(app)
    (app / "out").mkdir(parents=True)
    shutil.copytree(cost_table.BUNDLE / "environment" / "data", app / "data")
    (app / "out" / "transform.py").write_text(source, encoding="utf-8")
    try:
        subprocess.run([sys.executable, "-B", str(app / "out" / "transform.py"), "--input", str(app / "data"),
                        "--output", str(app / "out")], capture_output=True, cwd=str(app / "out"), timeout=300)
    except subprocess.TimeoutExpired:
        pass
    T.APP_ROOT = app
    T.OUT_DIR = app / "out"
    T.PROGRAM = app / "out" / "transform.py"
    t = time.time()
    res = {}
    for name, w in NAMES:
        res[name] = (w, bool(getattr(T, name)(app)))
    pos = sum(w for w, _ in res.values() if w > 0)
    got = sum(w for w, ok in res.values() if ok and w > 0)
    out = {"pos": pos, "got": got, "pct": round(100 * got / pos, 1),
           "failed": [n for n, (w, ok) in res.items() if not ok and w > 0],
           "fired": [n for n, (w, ok) in res.items() if ok and w < 0], "sec": round(time.time() - t, 1)}
    shutil.rmtree(app, ignore_errors=True)
    print("%-28s %5.1f%% got %g/%g failed %d fired %s %.0fs" % (label, out["pct"], got, pos, len(out["failed"]),
                                                              out["fired"], out["sec"]), flush=True)
    return out


def edits_for(levers, table):
    chosen = list(levers)
    if "LV-MU-5" in chosen and "LV-MU-8" in chosen:
        chosen.remove("LV-MU-8")  # both rewrite the group block; the one-level reading is wrong on every grouped month
    return [e for k in chosen for e in table[k]]


def cost():
    solve, full, one = cost_table.SOLVE, cost_table.FULL, cost_table.ONE
    rows = {"oracle": score("oracle", solve)}
    for lever in cost_table.LEVERS:
        rows["alone " + lever] = score("alone-" + lever, cost_table.patch(solve, full[lever]))
        if lever in one:
            rows["one-fact " + lever] = score("one-" + lever, cost_table.patch(solve, one[lever]))
        others = [k for k in cost_table.LEVERS if k != lever]
        rows["all-but " + lever] = score("allbut-" + lever, cost_table.patch(solve, edits_for(others, full)))
    rows["all wrong"] = score("allwrong", cost_table.patch(solve, edits_for(cost_table.LEVERS, full)))
    for lever in cost_table.NOISE:
        rows["noise alone " + lever] = score("noise-" + lever, cost_table.patch(solve, full[lever]))
    (WORK / "cost_table_g36.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    extra = {}
    for path in sorted((PROTO / "solvers").glob("*.py")):
        extra["kill " + path.stem] = score("kill-" + path.stem, path.read_text(encoding="utf-8"))
    extra["probe program (r3 final)"] = score("probe", (AGENT / "transform.py").read_text(encoding="utf-8"))
    extra["first write (r3 step 13)"] = score("firstwrite",
                                              (AGENT / "steps" / "step13_transform.py").read_text(encoding="utf-8"))
    (PROTO / "logs" / "g36_cost_rows.json").write_text(json.dumps(extra, indent=1), encoding="utf-8")


def rules():
    import rule_coverage
    rule_coverage.score = score
    sys.argv = sys.argv[:1]
    rule_coverage.main()


if __name__ == "__main__":
    warm()
    {"cost": cost, "rules": rules}[sys.argv[1]]()
    print("ALL_DONE", flush=True)
