"""Scratch: digests of hidden + mutation corpora and expected docs for a given tests module."""
import hashlib, importlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
mod = sys.argv[1]
if mod.endswith(".py"):
    import importlib.util
    spec = importlib.util.spec_from_file_location("T", mod); T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
else:
    T = importlib.import_module(mod)
def dg(files):
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode()); h.update(files[k])
    return h.hexdigest()[:16]
def dd(docs):
    return {k: hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:16] for k, v in sorted(docs.items())}
out = {}
for key, fn in (("hidden", T._hidden_files), ("scaled", T._tier_scaled_files), ("small", T._small_commitment_files), ("near", T._near_base_files)):
    f = fn(); out[key] = {"files": dg(f), "docs": dd(T._expected(key, fn))}
f = T._shipped_files(); out["shipped"] = {"files": dg(f), "docs": dd(T._expected("shipped", T._shipped_files))}
print(json.dumps(out, indent=1, sort_keys=True))
