"""Regenerate the visible corpus from tests and diff against environment/data; optionally copy. usage: regen_diff.py <bundle> [--write]"""
import sys, pathlib, tempfile, filecmp, shutil
from tk import load_T
B = pathlib.Path(sys.argv[1]); T = load_T(B)
d = pathlib.Path(tempfile.mkdtemp()) / "data"
T._build_corpus_dir(d)
D = B / "environment/data"
names = sorted({p.name for p in d.iterdir()} | {p.name for p in D.iterdir()})
diff = [n for n in names if not (d/n).exists() or not (D/n).exists() or (d/n).read_bytes() != (D/n).read_bytes()]
print("differ:", diff)
if "--write" in sys.argv:
    for n in diff:
        if (d/n).exists(): shutil.copyfile(d/n, D/n)
        else: print("ONLY IN SHIPPED", n)
    print("written")
