"""Compare reference outputs of two test_output.py copies over seeds.
usage: python3 -B compare_ref.py <old.py> <new.py> [seed_name|int ...]"""
import importlib.util
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


O = load(sys.argv[1], "t_old")
N = load(sys.argv[2], "t_new")
names = sys.argv[3:] or ["SAMPLE_SEED", "EVAL_SEED", "CHALLENGE_SEED", "PROBE_SEED"]
for nm in names:
    seed = getattr(O, nm) if not nm.isdigit() else int(nm)
    root = O.write_corpus(Path(tempfile.mkdtemp()), seed)
    root2 = N.write_corpus(Path(tempfile.mkdtemp()), seed)
    same_corpus = all((root / p.relative_to(root2)).read_bytes() == p.read_bytes()
                      for p in root2.rglob("*") if p.is_file())
    a = Path(tempfile.mkdtemp())
    b = Path(tempfile.mkdtemp())
    O.ref_publish(root, a)
    N.ref_publish(root, b)
    diff = [p.name for p in sorted(a.iterdir()) if p.read_bytes() != (b / p.name).read_bytes()]
    print(nm, "corpus_same", same_corpus, "docs_differ", diff, flush=True)
print("ALL_DONE")
