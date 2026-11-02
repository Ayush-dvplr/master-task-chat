import ast
import hashlib
import json
import re
import tomllib
from pathlib import Path

work = Path(__file__).parent
bundle = work.parent.parent / "hangar-check-replan"
before = work / "fix3_pre"
out = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_hangar-check-replan/fix_qcv4")
old = {str(p.relative_to(before)): hashlib.sha256(p.read_bytes()).hexdigest() for p in before.rglob("*") if p.is_file()}
new = {str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob("*") if p.is_file()}
changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
assert changed == ["solution/TRUTH.md", "solution/solve.sh", "tests/judge.toml", "tests/reward.toml", "tests/test_output.py"]
assert not list(bundle.rglob("__pycache__"))
source = (bundle / "tests/test_output.py").read_text()
original = (before / "tests/test_output.py").read_text()
w0 = {k: int(v) for k, v in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", original)}
w1 = {k: int(v) for k, v in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", source)}
raised = {k: [w0[k], v] for k, v in w1.items() if v > 0 and v != w0[k]}
assert len(raised) == 33
assert all(v >= w0[k] for k, v in w1.items() if v > 0)
assert len(w1) == 76 and sum(v for v in w1.values() if v > 0) == 344
assert {k: v for k, v in w1.items() if v < 0} == {"negative_hardcoded_sample_answers": -3, "negative_writes_outside_out_dir": -3}
assert set(w0) - set(w1) == {"negative_reads_check_files"}
assert all(w1[k] == v for k, v in w0.items() if re.match(r"h(?:[7-9]|1[0-5])_", k))
old_tree, new_tree = ast.parse(original), ast.parse(source)
for name in ["_run_program", "_check_negative_weight_writes_outside_out_dir", "_build_case", "_planted_corpus", "_reform"]:
    a = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    b = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert ast.dump(a) == ast.dump(b), name
j0 = tomllib.loads((before / "tests/judge.toml").read_text())["criterion"]
j1 = tomllib.loads((bundle / "tests/judge.toml").read_text())["criterion"]
assert j1[:17] == j0
assert [c["id"] for c in j1[17:]] == ["R18", "R19", "R20"]
assert all("negative_hardcoded_sample_answers" in c["description"] for c in j1[17:])
reward = tomllib.loads((bundle / "tests/reward.toml").read_text())
assert reward["reward"][0]["weights"]["test_output"] == 0.5 / 344
truth = (bundle / "solution/TRUTH.md").read_text()
for key, rel in {"fix_patch": "solution/solve.sh", "solve_py": "solution/solve.py", "test_output": "tests/test_output.py", "judge": "tests/judge.toml", "reward": "tests/reward.toml"}.items():
    assert f"{key}_sha256: {new[rel]}" in truth
for p in [bundle / "solution/solve.py", *work.glob("resume_*.py")]:
    ast.parse(p.read_text(), filename=str(p))
record = {"changed_files": changed, "sha256": new, "raised_weights": raised, "checks": 76, "positive_total": 344, "negative_total": -6, "lever_points": 165, "lever_share": 100 * 165 / 344, "unchanged": ["environment", "instruction.md", "task.toml", "solution/solve.py", "R1-R17", "h7-h15 weights", "rerun/isolation/tree-mutation helpers"]}
(out / "bundle_audit_resume.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({k: v for k, v in record.items() if k != "sha256"}, indent=2))
print("FINAL_RESUME_AUDIT_CLEAN")
