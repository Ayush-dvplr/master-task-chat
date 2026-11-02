import hashlib, re, sys
from pathlib import Path
b = Path(sys.argv[1]); t = b / "solution/TRUTH.md"
s = t.read_text()
for key, f in (("fix_patch_sha256", "solve.sh"), ("solve_py_sha256", "solve.py")):
    h = hashlib.sha256((b / "solution" / f).read_bytes()).hexdigest()
    s = re.sub(rf"^{key}: [0-9a-f]{{64}}", f"{key}: {h}", s, flags=re.M)
    print(key, h)
t.write_text(s)
