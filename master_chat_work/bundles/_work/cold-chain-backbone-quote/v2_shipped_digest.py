"""Canonical digest of the four documents the UNEDITED shipped package writes for fresh_1 and fresh_2 (Docker only)."""
import hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
from book_digests import load
tt = load(sys.argv[1]); repo = Path(sys.argv[2])
for name in ("fresh_1", "fresh_2"):
    book = tt._book(name)
    out = Path(tempfile.mkdtemp()) / "out"; out.mkdir()
    env = dict(os.environ, PYTHONPATH=str(repo / "src"))
    r = subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(book), "--out", str(out)], env=env, cwd=tempfile.mkdtemp(), capture_output=True, text=True)
    docs = {d: json.loads((out / d).read_text(encoding="utf-8")) for d in tt.DOCUMENTS}
    print(name, r.returncode, hashlib.sha256(json.dumps(docs, sort_keys=True).encode()).hexdigest(), flush=True)
print("ALL_DONE")
