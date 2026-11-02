"""Load <tests_dir>/test_output.py with a stand-in rewardkit and run one helper.

Usage:
  python3 -B tk.py <tests_dir> emit <dest>                 shipped corpus into <dest>/data
  python3 -B tk.py <tests_dir> heldout <tag> <dest>         held-out corpus for tag into <dest>/data
  python3 -B tk.py <tests_dir> notes                        embedded notes match shipped
  python3 -B tk.py <tests_dir> figures <tag|shipped>        control figures of that plan
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
tests_dir = Path(sys.argv[1])
fake = types.ModuleType("rewardkit")


class _Criteria:
    def __getattr__(self, name):
        return lambda weight: None


fake.criteria = _Criteria()
fake.criterion = lambda description="": (lambda f: f)
sys.modules["rewardkit"] = fake
spec = importlib.util.spec_from_file_location("t_o", tests_dir / "test_output.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

cmd = sys.argv[2]
if cmd == "emit":
    t._write_corpus(Path(sys.argv[3]))
elif cmd == "heldout":
    tag = sys.argv[3]
    t._write_corpus(Path(sys.argv[4]), seed=t.corpus_seed(tag), tweak=("class", tag.split("-")[1]))
elif cmd == "notes":
    print("notes match:", t._notes_match_shipped())
elif cmd == "figures":
    tag = sys.argv[3]
    plan = t.replay_plan(t.CHALLENGE_SEED) if tag == "shipped" else t.replay_plan(t.corpus_seed(tag), ("class", tag.split("-")[1]))
    print(json.dumps(t.control_figures(plan), indent=1))
