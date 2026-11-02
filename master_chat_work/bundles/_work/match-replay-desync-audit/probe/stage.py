"""Write a hidden corpus to a folder without running anything. Usage: python3 -B stage.py <tests_dir> <dest> <tag> <only-bit-name or ->"""
import importlib.util, sys, types
from pathlib import Path
tests_dir, dest, tag, bit = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
fake = types.ModuleType("rewardkit")
class _C:
    def __getattr__(self, n): return lambda **k: None
fake.criteria = _C(); fake.criterion = lambda description="": (lambda f: f)
sys.modules["rewardkit"] = fake
spec = importlib.util.spec_from_file_location("t", tests_dir / "test_output.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tweak = ("only", getattr(m, bit)) if bit != "-" else None
plan = m.replay_plan(m.corpus_seed(tag), tweak)
m._emit_corpus(dest / "data", plan, m._spec_notes())
(dest / "out").mkdir(parents=True, exist_ok=True)
import json
(dest / "expect.json").write_text(json.dumps(m.expected_reports(plan), indent=1))
