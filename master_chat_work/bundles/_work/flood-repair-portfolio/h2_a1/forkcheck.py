"""Run the verifier's _launch on book M with the probe program; then list live processes from /proc (no ps in the verifier image).
python3 -B forkcheck.py /path/to/test_output.py  (inside the verifier image, as root, /app/out = probe)"""
import importlib.util, subprocess, sys, tempfile, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
with tempfile.TemporaryDirectory() as td:
    Path(td).chmod(0o777)
    data = t._write_book(Path(td) / "book", t.book_files("M"))
    t0 = time.time()
    try:
        proc = t._launch(data, Path(td) / "written", Path(td) / "elsewhere")
        print("returned rc", proc.returncode)
    except subprocess.TimeoutExpired as exc:
        print("TimeoutExpired after", round(time.time() - t0, 2), "s")
time.sleep(2)
import os
rows = []
for pid in sorted((p for p in os.listdir("/proc") if p.isdigit()), key=int):
    try:
        st = dict(l.split(":", 1) for l in open("/proc/%s/status" % pid).read().splitlines() if ":" in l)
        cmd = open("/proc/%s/cmdline" % pid, "rb").read().replace(b"\0", b" ").decode().strip()
    except OSError:
        continue
    uid = st["Uid"].split()[0]
    rows.append((uid, pid, st["PPid"].strip(), st["State"].strip(), cmd))
    print("uid", uid, "pid", pid, "ppid", st["PPid"].strip(), st["State"].strip(), cmd)
left = [r for r in rows if r[0] == "65534" and not r[3].startswith("Z")]
print("SURVIVORS", len(left))
print("ALL_DONE")
