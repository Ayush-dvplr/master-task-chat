"""Half-window tiers and the shipped corpus: corpus bytes and expected outputs must be identical
between the pre-fix verifier (t_before.py) and the fixed one (argv[1])."""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


old = load(os.path.join(HERE, "t_before.py"), "t_old")
new = load(sys.argv[1], "t_new")


def digest(root):
    h = hashlib.sha256()
    for dp, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            h.update(os.path.relpath(p, root).encode() + b"\0" + open(p, "rb").read())
    return h.hexdigest()[:16]


def canon(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:16]


specs = [("tier_a", 51017, 0.05, "heldout", None), ("tier_b", 62029, 0.05, "heldout", None),
         ("tier_c", 73031, 0.04, "boundary", None)]
for name, seed, zone, window in new.CONV_TIERS:
    if window == "half":
        specs.append((name, seed, 0.05, "conv", {"hr": "zone:" + zone, "start": "requested"}))
bad = 0
for name, seed, scale, variant, conv in specs:
    t0 = time.time()
    ra, rb = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    old.build(ra, seed, scale, variant, conv)
    new.build(rb, seed, scale, variant, dict(conv, window="half") if conv else conv)
    da, db = digest(ra), digest(rb)
    ea = canon(old.everything(ra, conv)[:4])
    eb = canon(new.everything(rb, dict(conv, window="half") if conv else conv)[:4])
    same = da == db and ea == eb
    bad += not same
    print(f"{name} {time.time() - t0:.0f}s corpus {da}/{db} expected {ea}/{eb} {'SAME' if same else 'CHANGED'}", flush=True)
print("IDENTITY", "OK" if not bad else f"{bad} CHANGED", flush=True)
