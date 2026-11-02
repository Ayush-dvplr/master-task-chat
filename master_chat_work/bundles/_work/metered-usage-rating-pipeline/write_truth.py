"""Fill truth_template.md with current weights and sha256 values -> BUNDLE/solution/TRUTH.md."""
import hashlib
import re
import tomllib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "metered-usage-rating-pipeline"


def sha(rel):
    return hashlib.sha256((BUNDLE / rel).read_bytes()).hexdigest()


tests = (BUNDLE / "tests/test_output.py").read_text()
weights = [int(w) for w in re.findall(r"^criteria\.\w+\(weight=(-?\d+)\)", tests, re.M)]
judge = tomllib.loads((BUNDLE / "tests/judge.toml").read_text())
jw = [c["weight"] for c in judge[next(k for k in judge if isinstance(judge[k], list))]]
hashed = ["solution/solve.sh", "solution/solve.py", "tests/test_output.py", "tests/judge.toml",
          "tests/reward.toml", "tests/test.sh", "instruction.md", "task.toml",
          "environment/data/rating_contract.md"]
hashes = "\n".join(f"{Path(r).name}: {sha(r)}" for r in hashed)
values = {
    "n_pos": sum(1 for w in weights if w > 0), "pos": sum(w for w in weights if w > 0),
    "n_neg": sum(1 for w in weights if w < 0), "neg": sum(w for w in weights if w < 0),
    "n_judge": len(jw), "jpos": sum(w for w in jw if w > 0), "hashes": hashes,
    "solve_sh": sha("solution/solve.sh"), "solve_py": sha("solution/solve.py"),
    "solve_lines": len((BUNDLE / "solution/solve.py").read_text().splitlines()),
    "verifier_wall": (WORK / "ql1/verifier_wall.txt").read_text().strip(),
}
text = (WORK / "truth_template.md").read_text() % values
(BUNDLE / "solution/TRUTH.md").write_text(text)
print(values["n_pos"], values["pos"], values["n_neg"], values["neg"], values["n_judge"], values["jpos"])
print(hashes)
