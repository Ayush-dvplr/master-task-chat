"""Verifier worst case: a package that hangs on every book (oracle's shipped documents kept in out/)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from variants import rezip  # noqa: E402

oracle, target = Path(sys.argv[1]), Path(sys.argv[2])
if target.exists():
    shutil.rmtree(target)
shutil.copytree(oracle, target)
(target / "repo/src/task/__main__.py").write_text("import time\n\ntime.sleep(100000)\n")
rezip(target)
print("hang package ready")
