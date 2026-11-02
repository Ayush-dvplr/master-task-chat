"""score.py <prog_dir|zip> [only=name,name]: deliver a program like an agent would, then run every registered check."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, "/h")
import load_t  # noqa: E402
import rewardkit  # noqa: E402

T0 = time.time()
t = load_t.load(os.environ.get("TESTS", "/tests/test_output.py"))
prog = Path(sys.argv[1])
only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
out = Path("/app/out")
out.mkdir(parents=True, exist_ok=True)
data = Path("/app/data")
if not data.exists():
    shutil.copytree(t._shipped_dir(), data)
tool = Path("/tmp/tool")
if prog.is_dir() and (prog / "tool.zip").is_file() and os.environ.get("DELIVERED") == "1":
    for p in prog.iterdir():
        if p.is_file():
            shutil.copy(p, out / p.name)
    print(f"## delivered {prog} used as is", flush=True)
    prog = None
if prog is None:
    pass
elif prog.suffix == ".zip":
    with zipfile.ZipFile(prog) as zf:
        zf.extractall(tool)
    shutil.copy(prog, out / "tool.zip")
else:
    shutil.copytree(prog, tool, ignore=shutil.ignore_patterns("__pycache__"))
    with zipfile.ZipFile(out / "tool.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(x for x in tool.rglob("*") if x.is_file()):
            info = zipfile.ZipInfo(p.relative_to(tool).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            zf.writestr(info, p.read_bytes())
if prog is not None and os.environ.get("NODELIVER") != "1":
    cmds = []
    cfg = str(out / "config.json")
    plan = [["resolve-config", "--data", str(data), "--out", cfg]]
    plan += [["compile", "--data", str(data), "--config", cfg, "--profile", e, "--out", str(out / f"profile_{e}.json")] for e in ("dev", "prod")]
    plan += [["audit", "--data", str(data), "--config", cfg, "--out", str(out / "validation_report.json")],
             ["summarize", "--data", str(data), "--config", cfg, "--out", str(out / "summary.json")]]
    t1 = time.time()
    for args in plan:
        t2 = time.time()
        rc = subprocess.run([sys.executable, str(tool / "cli.py"), *args], capture_output=True, check=False).returncode
        print(f"## call {args[0]} {args[-1].rsplit('/', 1)[-1]} {time.time() - t2:.1f}s rc={rc}", flush=True)
        cmds.append({"argv": ["python3", "cli.py", *args], "returncode": rc})
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None  # noqa: E731
    report = {"tool": "warrant-ctl", "commands": cmds, "config_sha256": sha(out / "config.json"),
              "profile_dev_sha256": sha(out / "profile_dev.json"), "profile_prod_sha256": sha(out / "profile_prod.json"),
              "repairs": [{"module": "engine.py", "defect": "repaired"}]}
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"## deliver {prog.name} {time.time() - t1:.1f}s rc={[c['returncode'] for c in cmds]}", flush=True)
pos = got = 0
if hasattr(t, "_T0"):
    t._T0 = time.monotonic()  # the verifier budget starts when the checks start, not at delivery
if os.environ.get("BUDGET"):
    t._BUDGET_SECONDS = float(os.environ["BUDGET"])  # lever-only measurement of a slow program
if os.environ.get("CALL"):
    t._CALL_SECONDS = float(os.environ["CALL"])
for name, _, kw in rewardkit.REG:
    w = kw["weight"]
    if w > 0:
        pos += w
    if only and name not in only:
        continue
    s = time.time()
    ok = bool(getattr(t, name)(Path("/app")))
    if (w > 0 and ok) or (w < 0 and ok):
        got += w
    print(f"{name:45s} w={w:3d} {'PASS' if ok else 'fail':4s} {time.time() - s:7.1f}s", flush=True)
print(f"## SCORE {prog.name if prog else 'delivered'} {got}/{pos} = {100.0 * max(got, 0) / pos:.1f} total {time.time() - T0:.1f}s", flush=True)
