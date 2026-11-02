"""Build checks for the skdir_csv lever: old vs new generator, shipped data, 300-seed shape.

usage: python3 verify_build.py BUNDLE BEFORE_TESTS_PY OUTJSON
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
import types
from pathlib import Path

rk = types.ModuleType("rewardkit")


class _Crit:
    def __getattr__(self, name):
        return lambda *a, **k: (lambda f: f)


rk.criteria = _Crit()
rk.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = rk

BUNDLE, BEFORE, OUTJSON = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def ref_digest(mod, root):
    ref = mod.solve(root)
    keys = ["vtpv", "sigma0_sq", "dof", "n_obs", "x", "residuals", "weights_final", "flags", "verdict"]
    blob = json.dumps({k: str(ref.get(k)) if isinstance(ref, dict) else str(getattr(ref, k, None))
                       for k in keys}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12], ref


old = load(BEFORE, "old_t")
new = load(BUNDLE / "tests" / "test_output.py", "new_t")
res = {"seeds": {}}
names = {"sample": new.SAMPLE_SEED, "challenge": new.CHALLENGE_SEED,
         "eval": new.EVAL_SEED, "audit": new.AUDIT_SEED}
for label, seed in names.items():
    a = Path(tempfile.mkdtemp()); b = Path(tempfile.mkdtemp())
    old.emit_corpus(a, seed); new.emit_corpus(b, seed)
    ta, tb = tree(a), tree(b)
    diff = sorted(k for k in set(ta) | set(tb) if ta.get(k) != tb.get(k))
    da, ra = ref_digest(old, a)
    db, rb = ref_digest(new, b)
    north = (b / "obs_source_district_north.csv").read_text().splitlines()
    data_lines = [ln for ln in north if not ln.startswith("#")][1:]
    res["seeds"][label] = {"changed_files": diff, "ref_old": da, "ref_new": db,
                           "north_rows": len(data_lines),
                           "north_rows_with_quote": sum('"' in ln for ln in data_lines),
                           "quoted_sigma_kind": sum(',"stddev",' in ln or ',"variance",' in ln for ln in data_lines),
                           "quoted_dir_R": sum(',"R",' in ln for ln in data_lines),
                           "quoted_dir_any": sum(',"R",' in ln or ',"F",' in ln for ln in data_lines)}
    if label == "sample":
        shipped = tree(BUNDLE / "environment" / "data")
        res["shipped_vs_new_sample"] = sorted(k for k in set(shipped) | set(tb)
                                              if shipped.get(k) != tb.get(k))
    print(label, json.dumps(res["seeds"][label]), flush=True)

orig_cfg = new.corpus_config


def quoted_cfg(seed):
    cfg = orig_cfg(seed)
    cfg["csv_quote"] = True
    return cfg


new.corpus_config = quoted_cfg
ok = fail = 0
fails = []
t0 = time.monotonic()
for s in range(1, 301):
    d = Path(tempfile.mkdtemp())
    try:
        new.emit_corpus(d, 1000003 * s + 17)
        ok += 1
    except Exception as e:  # noqa: BLE001 - recorded, not hidden
        fail += 1
        fails.append([s, type(e).__name__, str(e)[:200]])
res["shape_300"] = {"ok": ok, "fail": fail, "fails": fails[:10], "seconds": round(time.monotonic() - t0, 1)}
print("shape_300", json.dumps(res["shape_300"]), flush=True)
OUTJSON.write_text(json.dumps(res, indent=1))
print("ALL_DONE")
