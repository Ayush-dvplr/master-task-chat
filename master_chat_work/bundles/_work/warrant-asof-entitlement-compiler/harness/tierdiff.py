import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/h")
import load_t

t = load_t.load(os.environ.get("TESTS", "/tests/test_output.py"))
SPECS = [
    ("c_51017_0.05_heldout_site_decided", 51017, 0.05, "heldout", None),
    ("c_62029_0.05_heldout_site_decided", 62029, 0.05, "heldout", None),
    ("c_73031_0.04_boundary_site_decided", 73031, 0.04, "boundary", None),
] + [
    (f"c_{s}_0.05_conv_zone={z}_requested", s, 0.05, "conv", {"hr": "zone:" + z, "start": "requested"})
    for _, s, z in t.CONV_TIERS
]


def digest(root):
    h = hashlib.sha256()
    for dp, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            h.update(os.path.relpath(p, root).encode() + b"\0" + open(p, "rb").read())
    return h.hexdigest()[:16]


bad = 0
for name, seed, scale, variant, conv in SPECS:
    root = Path(tempfile.mkdtemp())
    t0 = time.time()
    t.build(root, seed, scale, variant, conv)
    a, b = digest(root), digest(os.path.join("/c", name))
    bad += a != b
    print(f"{name} {time.time() - t0:.1f}s new {a} old {b} {'SAME' if a == b else 'CHANGED'}", flush=True)
print("TIERDIFF", "OK" if not bad else f"{bad} CHANGED")
