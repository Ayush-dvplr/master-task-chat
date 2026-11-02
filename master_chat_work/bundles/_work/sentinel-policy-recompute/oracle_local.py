"""Run solution/solve.py locally against a temp root.

Usage: oracle_local.py <root> [bundle_or_copy_dir]   (dir holds environment/data and solution/solve.py;
defaults to BUNDLE). Writes <root>/app/{data,tool,out}; scratch dirs live under <root>/tmp.
"""
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute")
root = Path(sys.argv[1]).resolve()
src = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else BUNDLE
solve_src = src / "solution" / "solve.py" if (src / "solution" / "solve.py").exists() else BUNDLE / "solution" / "solve.py"
if root.exists():
    shutil.rmtree(root)
(root / "app").mkdir(parents=True)
shutil.copytree(src / "environment" / "data", root / "app" / "data")
text = solve_src.read_text()
for old, new in (
    ('Path("/app/data/tool.zip")', repr(str(root / "app/data/tool.zip"))),
    ('Path("/app/data")', repr(str(root / "app/data"))),
    ('Path("/app/tool")', repr(str(root / "app/tool"))),
    ('Path("/app/out")', repr(str(root / "app/out"))),
    ('Path("/tmp/sentinel-resolve")', repr(str(root / "tmp/sentinel-resolve"))),
    ('Path("/tmp/sentinel-shipped-resolve")', repr(str(root / "tmp/sentinel-shipped-resolve"))),
):
    assert text.count(old) == 1, old
    text = text.replace(old, "Path(" + new + ")")
staged = root / "solve_local.py"
staged.write_text(text)
result = subprocess.run([sys.executable, str(staged)], capture_output=True, text=True)
(root / "solve.log").write_text(result.stdout + "\n--- stderr\n" + result.stderr)
print("solve exit", result.returncode)
sys.exit(result.returncode)
