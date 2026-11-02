"""deb4e4a probes for TQ2-F3 and TQ2-F4 (run in Docker as uid 1000).

    python3 -B probe_deb4e4a.py OUT_JSON            driver: runs every scenario in its own process
    python3 -B probe_deb4e4a.py --one SCEN TESTS    one scenario, prints a JSON line

Scenarios: a5 (attempt-5 delivered out, visible check), a5_931 (same, delivered test asserts 9.31),
kill_return / kill_timeout (a grandchild left by agent code is gone after _run returns / times out),
run for the new tests and the pushed b0cd2c1813ba tests.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
BUNDLE = WORK.parents[1] / "tariff-engine-audit-repair"
A5 = Path(os.environ.get("A5_OUT", "/a5"))
NEW = BUNDLE / "tests" / "test_output.py"
OLD = WORK / "pushed_b0cd2c1813ba" / "tests" / "test_output.py"
MARK = "deb4e4a-probe-sleeper"


def load(tests, app):
    os.environ["APP_ROOT"] = str(app)
    sys.path.insert(0, str(WORK / "rewardkit_stub"))
    spec = importlib.util.spec_from_file_location("bundle_tests", tests)
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    return t


def app_from_a5(edit=None):
    app = Path(tempfile.mkdtemp(prefix="probe-")) / "app"
    shutil.copytree(BUNDLE / "environment" / "ci", app / "ci")
    shutil.copytree(A5, app / "out")
    if edit:
        src, dst = A5 / "patched-repo.zip", app / "out" / "patched-repo.zip"
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info)
                if info.filename == "tests/test_visible.py":
                    text = data.decode()
                    assert text.count(edit[0]) == 1, edit
                    data = text.replace(edit[0], edit[1]).encode()
                zout.writestr(info, data)
    return app


def sleepers():
    found = []
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
            except OSError:
                continue
            if MARK in cmd and "probe_deb4e4a" not in cmd:
                found.append((int(pid), cmd.strip()))
    return found


def one(scen, tests):
    tests = Path(tests)
    if scen in ("a5", "a5_931"):
        edit = None if scen == "a5" else ('[("M1", "standing", 0, 14, "9.30")]', '[("M1", "standing", 0, 14, "9.31")]')
        t = load(tests, app_from_a5(edit))
        try:
            t._check_visible_tests_pass()
            return {"visible_check": True}
        except AssertionError as error:
            return {"visible_check": False, "why": str(error)[-300:]}
    t = load(tests, Path(tempfile.mkdtemp(prefix="probe-")) / "app")
    leave = ("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(300)',"
             f"'{MARK}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print('parent done')")
    if scen == "kill_timeout":
        leave += "; time.sleep(60)"
    cwd = Path(tempfile.mkdtemp(prefix="probe-cwd-"))
    started = time.time()
    outcome = "returned"
    try:
        if scen == "kill_timeout" and hasattr(t, "_group_run"):
            t._group_run([sys.executable, "-c", leave], t._env(None), cwd, 3)
        elif scen == "kill_timeout":
            subprocess.run([sys.executable, "-c", leave], text=True, capture_output=True, env=t._env(None),
                           cwd=str(cwd), timeout=3)  # the old statement-run call shape
        else:
            t._run([sys.executable, "-c", leave], t._env(None), cwd)
    except subprocess.TimeoutExpired:
        outcome = "timeout"
    time.sleep(0.5)
    left = sleepers()
    for pid, _ in left:
        os.kill(pid, 9)
    return {"outcome": outcome, "sec": round(time.time() - started, 2), "grandchildren_left": len(left)}


def main():
    if sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2], sys.argv[3])))
        return
    rows = {}
    for label, tests in (("new", NEW), ("old", OLD)):
        for scen in ("a5", "a5_931", "kill_return", "kill_timeout"):
            done = subprocess.run([sys.executable, "-B", __file__, "--one", scen, str(tests)], capture_output=True,
                                  text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            rows[f"{label}:{scen}"] = json.loads(done.stdout.strip().splitlines()[-1]) if done.returncode == 0 \
                else {"error": done.stderr[-600:]}
            print(label, scen, rows[f"{label}:{scen}"], flush=True)
    Path(sys.argv[1]).write_text(json.dumps(rows, indent=1))
    print("ALL_DONE")


if __name__ == "__main__":
    main()
