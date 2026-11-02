"""sha256 of every hidden book a test template builds: python3 -B book_digests.py <template.py> [names...]."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import types
from pathlib import Path


def load(path: str):
    rk = types.ModuleType("rewardkit")

    class _C:
        def __getattr__(self, name):
            return lambda **k: None

    rk.criteria = _C()
    rk.criterion = lambda *a, **k: (lambda f: f)
    sys.modules["rewardkit"] = rk
    src = Path(path).read_text().replace("SHIPPED_DATA_LINE", "_SHIPPED_DATA = {}")
    mod = types.ModuleType("tt")
    mod.__file__ = path
    exec(compile(src, path, "exec"), mod.__dict__)
    return mod


def digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


if __name__ == "__main__":
    tt = load(sys.argv[1])
    names = sys.argv[2:] or ["fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "missing", "rejections", "ties"]
    out = {}
    for name in names:
        t = time.time()
        out[name] = digest(tt._book(name))
        print(name, out[name][:16], "%.1fs" % (time.time() - t), file=sys.stderr)
    print(json.dumps(out, indent=1, sort_keys=True))
