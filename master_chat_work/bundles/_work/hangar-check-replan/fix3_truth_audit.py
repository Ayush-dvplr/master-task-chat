import hashlib
import json
import re
import tomllib
from pathlib import Path

bundle = Path(__file__).parent.parent.parent / "hangar-check-replan"
truth = (bundle / "solution/TRUTH.md").read_text()
paths = {
    "fix_patch": "solution/solve.sh",
    "solve_py": "solution/solve.py",
    "test_output": "tests/test_output.py",
    "judge": "tests/judge.toml",
    "reward": "tests/reward.toml",
}
digests = {name: hashlib.sha256((bundle / path).read_bytes()).hexdigest()
           for name, path in paths.items()}
for name, digest in digests.items():
    assert f"{name}_sha256: {digest}" in truth, name
weights = {name: int(weight) for name, weight in re.findall(
    r"criteria\.(\w+)\(weight=(-?\d+)\)", (bundle / "tests/test_output.py").read_text())}
judge = tomllib.loads((bundle / "tests/judge.toml").read_text())["criterion"]
counts = {
    "checks": len(weights),
    "positive_count": sum(w > 0 for w in weights.values()),
    "positive": sum(w for w in weights.values() if w > 0),
    "negative": sum(w for w in weights.values() if w < 0),
    "judge_positive": sum(c["weight"] for c in judge if c["weight"] > 0),
    "judge_negative": sum(c["weight"] for c in judge if c["weight"] < 0),
}
assert counts == {"checks": 75, "positive_count": 74, "positive": 344,
                  "negative": -3, "judge_positive": 39, "judge_negative": -31}
assert "75 checks, positive weight total 344" in truth
print(json.dumps({"counts": counts, "sha": digests}, indent=2))
print("TRUTH_AUDIT_CLEAN")
