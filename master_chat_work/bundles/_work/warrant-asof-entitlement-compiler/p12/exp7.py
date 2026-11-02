import importlib.util, sys, tempfile, json
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", "t4.py"); t = importlib.util.module_from_spec(spec); sys.modules["t"] = t; spec.loader.exec_module(t)
root = Path(tempfile.mkdtemp()) / "tb"
t.build(root, 62029, 0.05, "heldout", None)
cfg, prof, aud, summ, _ = t.everything(root)
alt = dict(cfg)
for k in ("as_of", "recorded_cutoff"):
    alt[k] = t.iso_z(t.stamp(alt[k]) - 2 * t.DAY)
alt["prod.approvals_required"] = 1 if alt["prod.approvals_required"] != 1 else 2
_, prof2, aud2, _, _ = t.everything(root, None, alt)
for k in aud:
    a, b = aud[k], aud2[k]
    print(k, "same" if json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True) else f"differs ({len(a)} vs {len(b)})")
