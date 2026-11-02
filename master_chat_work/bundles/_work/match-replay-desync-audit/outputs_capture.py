"""Capture every output file the program writes on the shipped corpus and on every hidden corpus.

Usage: python3 -B outputs_capture.py <tests_dir> <data_dir> <program.py> <capture_file>
Runs every test once (so every hidden corpus is staged), then writes one line per
output file: `<corpus key> <file name> <sha256>`, sorted.
"""

import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

tests_dir, data_dir, program, capture = (Path(a) for a in sys.argv[1:5])

fake = types.ModuleType("rewardkit")


class _Criteria:
    def __getattr__(self, name):
        return lambda weight: None


fake.criteria = _Criteria()
fake.criterion = lambda description="": (lambda func: func)
sys.modules["rewardkit"] = fake

scratch = Path(tempfile.mkdtemp(prefix="mrda-cap-"))
out = scratch / "out"
out.mkdir()
shutil.copy(program, out / "optimize.py")
subprocess.run([sys.executable, str(out / "optimize.py"), str(data_dir), str(out)], check=True,
               capture_output=True)
spec = importlib.util.spec_from_file_location("test_output_cap", tests_dir / "test_output.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module._out_root = lambda: out

rows = []
for path in sorted(out.iterdir()):
    if path.is_file() and path.name != "optimize.py":
        rows.append("shipped %s %s" % (path.name, hashlib.sha256(path.read_bytes()).hexdigest()))
for name in sorted(dir(module)):
    if name.startswith("test_"):
        try:
            getattr(module, name)()
        except BaseException:
            pass
for key in sorted(module._STAGE_CACHE, key=str):
    bundle = module._STAGE_CACHE[key]
    rows.append("%s exit %d" % (key, bundle["code"]))
    for path in sorted(bundle["result"].rglob("*")):
        if path.is_file():
            rows.append("%s %s %s" % (key, path.relative_to(bundle["result"]),
                                      hashlib.sha256(path.read_bytes()).hexdigest()))
    shutil.rmtree(bundle["room"], ignore_errors=True)
capture.write_text("\n".join(rows) + "\n", encoding="utf-8")
print("corpora %d lines %d" % (len(module._STAGE_CACHE) + 1, len(rows)))
shutil.rmtree(scratch, ignore_errors=True)
