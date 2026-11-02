"""Time plan_migration of a delivered repo on one hidden ladder.

    python3 ladder_time.py APP_DIR LADDER_NAME CAP_SEC [RUNS]
Prints one JSON line per run: wall seconds, timed_out, and whether the plan equals the tests' reference.
"""
import json, os, sys, time, subprocess, tempfile, importlib.util
from pathlib import Path
S = Path("/tmp/smpr-hard-20261021T1730")
sys.path.insert(0, str(S / "rkstub"))
app, name, cap = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
runs = int(sys.argv[4]) if len(sys.argv) > 4 else 1
os.environ["APP_ROOT"] = str(app)
spec_ = importlib.util.spec_from_file_location("t", S / "tests_ql" / "test_output.py")
t = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(t)
spec, job, expected = t.case_ladder(name)
contracts = spec.write()
repo = t._delivered_repo()
cwd = Path(tempfile.mkdtemp(prefix="ltime-"))
(cwd / "driver.py").write_text(t._DRIVER); (cwd / "job.json").write_text(json.dumps(dict(job, contracts=str(contracts))))
py = str(Path.home() / ".local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12")
for n in range(runs):
    started = time.time()
    try:
        done = subprocess.run([py, "driver.py", "job.json"], cwd=cwd, env={"PYTHONPATH": str(repo / "src"), "PATH": os.environ["PATH"]},
                              capture_output=True, text=True, timeout=cap)
        out = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {"stderr": done.stderr[-300:]}
        print(json.dumps({"app": app.name, "ladder": name, "run": n + 1, "sec": round(time.time() - started, 3), "timed_out": False,
                          "matches_reference": out == {"ok": expected}, "plan_len": len(out.get("ok") or [])}), flush=True)
    except subprocess.TimeoutExpired:
        print(json.dumps({"app": app.name, "ladder": name, "run": n + 1, "sec": round(time.time() - started, 3), "timed_out": True, "cap": cap}), flush=True)
