"""Fork probe (Docker, root): python3 -B fork_probe.py TESTS_DIR OVERWRITE_PROG LABEL

Installs the overwrite attack as /app/out/derive_report.py, runs it once through the tests module's
_run_program on the shipped data, waits 1.5 s, then counts live processes of uid nobody and the
held-out files the daemon copied. Run once with the built tests and once with the pre-build tests
(control: shows the probe can see a survivor).
"""
import importlib.util
import os
import pwd
import shutil
import sys
import tempfile
import time
from pathlib import Path


def survivors():
    uid = str(pwd.getpwnam("nobody").pw_uid)
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue
        line = next((r for r in status.splitlines() if r.startswith("Uid:")), "")
        if uid in line.split()[1:2] and "State:\tZ" not in status:
            found.append(entry.name)
    return found


def main():
    tests, prog, label = sys.argv[1], sys.argv[2], sys.argv[3]
    sys.path.insert(0, tests)
    spec = importlib.util.spec_from_file_location("t_%s" % label, os.path.join(tests, "test_output.py"))
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    shutil.rmtree("/app/out", ignore_errors=True)
    os.makedirs("/app/out")
    shutil.copy(prog, "/app/out/derive_report.py")
    os.system("chmod -R a+rX /app")
    case = T._shipped_case()
    work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
    try:
        T._run_program(case["data"], work)
    except Exception as exc:
        print("run error", type(exc).__name__, exc)
    time.sleep(1.5)
    alive = survivors()
    markers = list(Path("/tmp").glob("alive_*"))
    print("FORK_PROBE %s survivors=%d markers=%d" % (label, len(alive), len(markers)))
    for pid in alive:
        try:
            os.kill(int(pid), 9)
        except OSError:
            pass
    for m in markers:
        m.unlink()


if __name__ == "__main__":
    main()
