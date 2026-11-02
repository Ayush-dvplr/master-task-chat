"""Local tests-only scorer: run the real tests/test_output.py checks against <root>/app/out.

Usage: local_score.py <root> [tests_file]   (root holds app/out; tests_file defaults to BUNDLE tests/test_output.py,
or env SPR_TESTS; prints per-check result and the tests-channel score)
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute")
root = Path(sys.argv[1]).resolve()
tests_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ.get("SPR_TESTS", BUNDLE / "tests" / "test_output.py"))
source = tests_file.read_text()
patched = source.replace('OUT = Path("/app/out")', f'OUT = Path({str(root / "app" / "out")!r})', 1)
assert patched != source
staged = root / "_test_output_local.py"
staged.write_text(patched)
spec = importlib.util.spec_from_file_location("local_test_output", staged)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
weights = {name: int(w) for name, w in re.findall(r"^criteria\.(\w+)\(weight=(-?\d+)\)$", source, re.M)}
positive = sum(w for w in weights.values() if w > 0)
earned = 0
for name, weight in weights.items():
    test_name = "test_" + (name.replace("negative_", "negative_weight_", 1) if name.startswith("negative_") else name)
    result = module._passes(name, getattr(module, test_name))
    if weight > 0 and result:
        earned += weight
    if weight < 0 and result:
        earned += weight
    print(f"{name:60s} w={weight:4d} {'PASS' if result else 'fail'}")
score = max(0.0, earned / positive)
print(f"SCORE {score:.4f} ({earned}/{positive})")
staged.unlink()
