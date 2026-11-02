"""Write the solve.sh / solve.py sha256 values into solution/TRUTH.md (run last)."""
import hashlib, re, sys
from pathlib import Path
B = Path(sys.argv[1])
t = (B / "solution/TRUTH.md").read_text()
for key, f in (("fix_patch_sha256", "solve.sh"), ("solve_py_sha256", "solve.py")):
    h = hashlib.sha256((B / "solution" / f).read_bytes()).hexdigest()
    t = re.sub(rf"^{key}: .*$", f"{key}: {h}", t, flags=re.M)
(B / "solution/TRUTH.md").write_text(t)
print("TRUTH hashes written")
