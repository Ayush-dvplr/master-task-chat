"""Scratch: old hidden corpora from the work generator must equal the bundle test module's corpora."""
import hashlib, importlib.util, os, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
sys.path.insert(1, os.path.dirname(here))
import gen_core as G
spec = importlib.util.spec_from_file_location("T", "/b/tests/test_output.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
def dg(files):
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode()); h.update(files[k])
    return h.hexdigest()[:16]
old = T._hidden_files()
new = G.gen_month(T.HIDDEN_SEED, T._hidden_month(), 1600, 1200, True, T.ref_compute)
print("hidden", dg(old), dg(new), dg(old) == dg(new), flush=True)
for k in (1, 2, 3):
    old = T._long_files(k)
    seed = T.HIDDEN_SEED * 31 + k
    import random
    rng = random.Random(seed)
    month = "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))
    rows, accounts, resellers = T.LONG_SHAPES[k - 1]
    new = G.gen_month(seed, month, rows, accounts, True, T.ref_compute, resellers=resellers)
    print("long", k, dg(old), dg(new), dg(old) == dg(new), flush=True)
