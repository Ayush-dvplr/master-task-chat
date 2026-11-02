"""Stage hidden corpora from a tests dir and run a program on them with a long limit.
Usage: python3 -B diag.py <tests_dir> <program.py> <seconds> <test_name>..."""
import importlib.util, sys, time, types
from pathlib import Path
tests_dir, program, limit = Path(sys.argv[1]), Path(sys.argv[2]).resolve(), int(sys.argv[3])
fake = types.ModuleType("rewardkit")
class _C:
    def __getattr__(self, n): return lambda **k: None
fake.criteria = _C(); fake.criterion = lambda description="": (lambda f: f)
sys.modules["rewardkit"] = fake
spec = importlib.util.spec_from_file_location("t", tests_dir / "test_output.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._delivered_program = lambda: program
m.LAUNCH_SECONDS = limit
import json as _j, os as _o
if _o.environ.get("TRUTHQ"):
    _emit = m._emit_corpus
    def _emit2(root, plan, specs):
        _emit(root, plan, specs)
        (Path(root).parent / "truth_q.json").write_text(_j.dumps(plan["values"]))
        _o.chmod(Path(root).parent / "truth_q.json", 0o644)
    m._emit_corpus = _emit2
for name in sys.argv[4:]:
    t0 = time.time()
    try:
        getattr(m, name)(); verdict = "PASS"
    except BaseException as e:
        verdict = "FAIL " + str(e).replace("\n", " ")[:400]
    rooms = [b["room"] for b in m._STAGE_CACHE.values()]
    print("%s %.1fs %s ROOM %s" % (name, time.time() - t0, verdict, rooms[-1] if rooms else "-"), flush=True)
    m._STAGE_CACHE.clear()
