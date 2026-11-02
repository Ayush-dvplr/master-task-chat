"""Docker-only scorer for P12 a395eb2: trap survival, vacuity, nop, forgery price.

Usage (python:3.12-slim, bundles dir at /bb, rewardkit stub at /rk):
  python -B a395_runner.py <tests/test_output.py path> <mode: after|before> <json out>
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
HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(WORK))
import cost_table  # noqa: E402
import rewardkit  # noqa: E402

TESTS, MODE, OUT = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("t_out", str(TESTS))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
NAMES = list(rewardkit.criteria.items)
SCRATCH = Path("/tmp/a395score")

CONSTANT = '''import argparse, json, pathlib
p = argparse.ArgumentParser(); p.add_argument("--input"); p.add_argument("--output")
a = p.parse_args(); out = pathlib.Path(a.output); out.mkdir(parents=True, exist_ok=True)
for name in %r:
    (out / name).write_text("" if name.endswith(".jsonl") else "{}\\n")
''' % (T.DOCUMENTS,)

# Correct program that writes placeholders, exits 0 at once and leaves a setsid grandchild
# that writes the real documents a moment later (the QC v1 G03-3 attack).
DETACH = cost_table.SOLVE.replace('if __name__ == "__main__":', '''def _detach():
    import os
    args = sys.argv[1:]
    out = pathlib.Path(args[args.index("--output") + 1])
    out.mkdir(parents=True, exist_ok=True)
    for name in %r:
        (out / name).write_text("" if name.endswith(".jsonl") else "{}\\n")
    if os.fork():
        os._exit(0)
    os.setsid()
    if os.fork():
        os._exit(0)
    fd = os.open(os.devnull, os.O_RDWR)
    for n in (0, 1, 2):
        os.dup2(fd, n)
    time.sleep(0.3)
    main(args)
    os._exit(0)


if __name__ == "__main__" and "--detach-off" not in sys.argv:
    _detach()
if False:''' % (T.DOCUMENTS,))
assert "_detach()" in DETACH
if "import time" not in DETACH:
    DETACH = DETACH.replace("import argparse", "import argparse\nimport time", 1)

VARIANT_A = ("""def json_units(raw):
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None""", """def json_units(raw):
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None""")


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
    for k in [k for k in T._CACHE if k.startswith("run-")]:
        del T._CACHE[k]
    app = SCRATCH / label
    if app.exists():
        shutil.rmtree(app)
    (app / "out").mkdir(parents=True)
    shutil.copytree(cost_table.BUNDLE / "environment" / "data", app / "data")
    if source is None:
        shutil.rmtree(app / "out")
    else:
        (app / "out" / "transform.py").write_text(source, encoding="utf-8")
        try:
            subprocess.run([sys.executable, "-B", str(app / "out" / "transform.py"), "--input", str(app / "data"),
                            "--output", str(app / "out")], capture_output=True, cwd=str(app / "out"), timeout=300)
        except subprocess.TimeoutExpired:
            pass
        time.sleep(1 if label.startswith("detach") else 0)
    T.APP_ROOT = app
    T.OUT_DIR = app / "out"
    T.PROGRAM = app / "out" / "transform.py"
    t = time.time()
    res = {}
    for name, w in NAMES:
        res[name] = (w, bool(getattr(T, name)(app)))
    pos = sum(w for w, _ in res.values() if w > 0)
    got = sum(w for w, ok in res.values() if ok and w > 0)
    out = {"pos": pos, "got": got, "pct": round(100 * got / pos, 2),
           "passed": [n for n, (w, ok) in res.items() if ok and w > 0],
           "failed": [n for n, (w, ok) in res.items() if not ok and w > 0],
           "fired": [n for n, (w, ok) in res.items() if ok and w < 0], "sec": round(time.time() - t, 1)}
    shutil.rmtree(app, ignore_errors=True)
    print("%-24s %6.2f%% got %g/%g failed %d fired %s %.0fs" % (label, out["pct"], got, pos, len(out["failed"]),
                                                              out["fired"], out["sec"]), flush=True)
    if len(out["passed"]) <= 30:
        print("   passed: %s" % out["passed"], flush=True)
    return out


def main():
    warm()
    solve = cost_table.SOLVE
    rows = {}
    if MODE == "after":
        rows["oracle"] = score("oracle", solve)
        rows["vacuity no program"] = score("vacuity", None)
        rows["nop empty program"] = score("nop", "")
        for lever in cost_table.LEVERS + cost_table.NOISE:
            rows["alone " + lever] = score("alone-" + lever, cost_table.patch(solve, cost_table.FULL[lever]))
        rows["QC variant A"] = score("variantA", cost_table.patch(solve, [VARIANT_A]))
    if MODE == "rules2":
        loop = "        for name in REQUIRED:\n"
        rows["mutant presence checked in sorted order"] = score(
            "sorted", cost_table.patch(solve, [(loop, "        for name in sorted(REQUIRED):\n")]))
        rows["mutant reference files checked first"] = score(
            "reffirst", cost_table.patch(solve, [(loop, "        for name in REQUIRED[5:] + REQUIRED[:5]:\n")]))
        rows["mutant only collectors checked"] = score(
            "collonly", cost_table.patch(solve, [(loop, "        for name in REQUIRED[:5]:\n")]))
        OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        return
    rows["constant docs"] = score("constant", CONSTANT)
    rows["detach forge"] = score("detach", DETACH)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
    print("ALL_DONE", flush=True)
