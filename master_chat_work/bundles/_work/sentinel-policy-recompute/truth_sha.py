"""Rewrite the sha256 lines in solution/TRUTH.md Provenance (run as the last edit)."""
import hashlib, re, sys
from pathlib import Path
b = Path(sys.argv[1]); p = b / "solution" / "TRUTH.md"; s = p.read_text()
def sub(m):
    return f"- sha256 `{m.group(1)}`: `{hashlib.sha256((b / m.group(1)).read_bytes()).hexdigest()}`"
s2, n = re.subn(r"^- sha256 `([^`]+)`: `[0-9a-f]{64}`$", sub, s, flags=re.M)
assert n == 3, n
p.write_text(s2); print("truth shas", n)
