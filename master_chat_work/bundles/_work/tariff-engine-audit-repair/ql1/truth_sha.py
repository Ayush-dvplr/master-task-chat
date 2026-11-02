"""Recompute the two sha lines in solution/TRUTH.md (run last)."""
import hashlib, re
from pathlib import Path
B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
p = B / "solution/TRUTH.md"; s = p.read_text()
for key, f in (("fix_patch_sha256", "solve.sh"), ("solve_py_sha256", "solve.py")):
    h = hashlib.sha256((B / "solution" / f).read_bytes()).hexdigest()
    s, n = re.subn(rf"^{key}: [0-9a-f]{{64}}", f"{key}: {h}", s, flags=re.M); assert n == 1, key
    print(key, h)
p.write_text(s)
