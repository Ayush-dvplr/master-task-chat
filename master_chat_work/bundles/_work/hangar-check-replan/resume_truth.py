import hashlib
import re
from pathlib import Path

b = Path(__file__).resolve().parent.parent.parent / "hangar-check-replan"
p = b / "solution/TRUTH.md"
s = p.read_text()
s = s.replace("75 checks, positive weight total 344, one negative\n  `negative_writes_outside_out_dir` (-3).", "76 checks, positive weight total 344, two negatives:\n  `negative_writes_outside_out_dir` (-3) and `negative_hardcoded_sample_answers` (-3).")
s = s.replace("74 positive checks worth 344 weight and 1 negative\n  check worth -3 weight.", "74 positive checks worth 344 weight and 2 negative\n  checks worth -6 weight.")
if "The replay negative requires" not in s:
    s = s.replace("No source-token negative remains.", "The replay negative requires a successful clean held-out run whose nine answers equal shipped ground truth while its own expected answers differ; crashes and stray writes are excluded. No source-token negative remains.")
for key, rel in {"fix_patch": "solution/solve.sh", "solve_py": "solution/solve.py", "test_output": "tests/test_output.py", "judge": "tests/judge.toml", "reward": "tests/reward.toml"}.items():
    digest = hashlib.sha256((b / rel).read_bytes()).hexdigest()
    s = re.sub(rf"(?m)^{key}_sha256: [0-9a-f]{{64}}", f"{key}_sha256: {digest}", s)
p.write_text(s)
print("TRUTH_REGENERATED_LAST")
