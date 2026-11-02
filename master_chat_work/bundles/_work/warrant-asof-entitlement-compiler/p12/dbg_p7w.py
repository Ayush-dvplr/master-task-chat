import sys, os, subprocess, traceback
sys.path.insert(0, "/h")
import load_t
t = load_t.load("/p12/t7.py")
import shutil, zipfile
from pathlib import Path
out = Path("/app/out"); out.mkdir(parents=True, exist_ok=True)
tool = Path("/tmp/tool"); shutil.copytree("/prog", tool)
with zipfile.ZipFile(out / "tool.zip", "w") as zf:
    for p in sorted(x for x in tool.rglob("*") if x.is_file()):
        zf.write(p, p.relative_to(tool).as_posix())
t._BUDGET_SECONDS = 100000; t._CALL_SECONDS = 3000
root = t._conv_tier("conv_6")
td = t._tool_dir()
print("tooldir", td, flush=True)
orig = subprocess.Popen
class P(orig):
    def communicate(self, *a, **k):
        o, e = super().communicate(*a, **k)
        print("RC", self.returncode, (e or b"")[-600:], flush=True)
        return o, e
subprocess.Popen = P
try:
    g = t._run_all(root, "conv_6")
    print({k: (v if k == "rc" else type(v).__name__) for k, v in g.items()})
except Exception:
    traceback.print_exc()
