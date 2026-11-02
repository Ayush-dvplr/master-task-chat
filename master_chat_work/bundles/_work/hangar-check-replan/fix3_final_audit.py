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

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

old = {str(p.relative_to(before)): sha(p) for p in before.rglob("*") if p.is_file()}
new = {str(p.relative_to(bundle)): sha(p) for p in bundle.rglob("*") if p.is_file()}
changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
assert changed == ["solution/TRUTH.md", "solution/solve.sh", "tests/judge.toml", "tests/reward.toml", "tests/test_output.py"], changed
assert not list(bundle.rglob("__pycache__"))
source = (bundle / "tests/test_output.py").read_text()
original = (before / "tests/test_output.py").read_text()
weights = lambda s: {k: int(v) for k, v in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", s)}
w0, w1 = weights(original), weights(source)
raised = {k: [w0[k], v] for k, v in w1.items() if v != w0[k]}
assert len(raised) == 33
assert all(v >= w0[k] for k, v in w1.items())
assert set(w0) - set(w1) == {"negative_hardcoded_sample_answers", "negative_reads_check_files"}
assert all(w1[k] == v for k, v in w0.items() if re.match(r"h(?:[7-9]|1[0-5])_", k))
old_tree, new_tree = ast.parse(original), ast.parse(source)
for name in ["_run_program", "_check_negative_weight_writes_outside_out_dir", "_build_case", "_planted_corpus", "_reform"]:
    pick = lambda tree: next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assert ast.dump(pick(old_tree)) == ast.dump(pick(new_tree)), name
j0 = tomllib.loads((before / "tests/judge.toml").read_text())["criterion"]
j1 = tomllib.loads((bundle / "tests/judge.toml").read_text())["criterion"]
assert j1[:17] == j0
assert [c["id"] for c in j1[17:]] == ["R18", "R19", "R20"]
positive = sum(v for v in w1.values() if v > 0)
lever = sum(v for k, v in w1.items() if re.match(r"h(?:[7-9]|1[0-5])_", k))
reward = tomllib.loads((bundle / "tests/reward.toml").read_text())
assert reward["reward"][0]["weights"]["test_output"] == 0.5 / positive
for p in [bundle / "tests/test_output.py", bundle / "solution/solve.py", *work.glob("fix3_*.py")]:
    ast.parse(p.read_text(), filename=str(p))
anchors = {}
for rel, tokens in {
    "tests/test_output.py": ["def _write_governing_docs", "_GOVERNING_DOCS =", "def _shipped_root", "def _check_negative_weight_writes_outside_out_dir", "criteria.shipped_plan_rows", "criteria.h4_plan_group_totals", "criteria.h4_settlement_per_check", "criteria.h4_settlement_by_base_and_segment", "criteria.h7_settlement_per_check"],
    "tests/judge.toml": ['id = "R9"', 'id = "R14"', 'id = "R18"', 'id = "R19"', 'id = "R20"'],
    "solution/solve.sh": ["python3 - <<'RESPONSE'"],
    "solution/TRUTH.md": ["test_output_sha256:", "fix_patch_sha256:"],
}.items():
    lines = (bundle / rel).read_text().splitlines()
    anchors[rel] = {t: next(i + 1 for i, line in enumerate(lines) if t in line) for t in tokens}
record = {"changed_files": changed, "sha256": new, "raised_weights": raised, "positive_total": positive, "lever_points": lever, "lever_share": 100 * lever / positive, "anchors": anchors, "unchanged": ["environment", "instruction.md", "task.toml", "solution/solve.py", "R1-R17", "h7-h15 weights", "rerun/isolation/tree-mutation helpers"]}
(out / "bundle_audit.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({k: v for k, v in record.items() if k != "sha256"}, indent=2))
print("FINAL_AUDIT_CLEAN")
