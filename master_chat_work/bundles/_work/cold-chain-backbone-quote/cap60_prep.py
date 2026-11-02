"""Build an app tree from a repo folder: rezip per build_config and regenerate the 4 docs on the shipped book."""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, "/w")
import variants
app = Path(sys.argv[1])
for cache in app.rglob("__pycache__"):
    import shutil; shutil.rmtree(cache)
(app / "out").mkdir(exist_ok=True)
(app / "out/patched-repo.zip").touch()
variants.rezip(app)
env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONPATH": str(app / "repo/src"), "PYTHONDONTWRITEBYTECODE": "1"}
subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(app / "ci"), "--out", str(app / "out")], env=env, check=True, timeout=394)
print("prepped", app)
