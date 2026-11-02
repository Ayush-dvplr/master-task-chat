"""TS-24 fork probe: an engine that double-forks a run-user child which
outlives its run and tries to overwrite the paper directory it was given.
Counts run-user survivors right after _drive returns, old suite vs new."""
import importlib.util
import io
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ENGINE = r'''
import os, sys, time
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out") + 1]); data = Path(args[args.index("--data") + 1])
out.mkdir(parents=True, exist_ok=True)
(out / "01_doc.txt").write_text("x")
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        fd = os.open(os.devnull, os.O_RDWR)
        for n in (0, 1, 2):
            os.dup2(fd, n)
        time.sleep(1.5)
        try:
            (data / "paper.txt").write_text("forged")
            Path("/tmp/probe_marker").write_text("wrote")
        except OSError as exc:
            Path("/tmp/probe_marker").write_text("refused " + type(exc).__name__)
        time.sleep(60)
    os._exit(0)
os.wait()
'''


def survivors():
    found = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                status = (entry / "status").read_text()
            except OSError:
                continue
            uid = [l.split()[1] for l in status.splitlines() if l.startswith("Uid:")]
            if uid == ["65534"] and "State:\tZ" not in status:
                found.append(int(entry.name))
    return found


def probe(label, path):
    spec = importlib.util.spec_from_file_location("t_" + label, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    outroot = Path(tempfile.mkdtemp())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("src/slwopt/__init__.py", "")
        z.writestr("src/slwopt/__main__.py", ENGINE)
    (outroot / "patched_engine.zip").write_bytes(buf.getvalue())
    mod.OUTPUT_ROOT = str(outroot)
    data = mod._scratch("paper")
    (data / "paper.txt").write_text("original")
    if hasattr(mod, "_seal"):
        mod._seal(data)
    else:  # the old suite left every corpus world-writable
        os.chmod(data / "paper.txt", 0o666)
    Path("/tmp/probe_marker").unlink(missing_ok=True)
    mod._drive(data, "probe")
    after_run = survivors()
    time.sleep(3)
    marker = Path("/tmp/probe_marker")
    print(label, "survivors_after_drive", len(after_run),
          "survivors_after_3s", len(survivors()),
          "paper", (data / "paper.txt").read_text(),
          "child", marker.read_text() if marker.exists() else "none")
    for pid in survivors():
        os.kill(pid, 9)


probe("before", sys.argv[1])
probe("after", sys.argv[2])
print("ALL_DONE")
