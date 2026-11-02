"""Time the reference, the prototype Dreyfus-Wagner and a tuned Dreyfus-Wagner per cold-room count.

Run inside the harness image: python3 -B dwbench.py <mount dir>
The mount holds test_output.py (hidden project generator), src/ (repaired package),
proto.py (prototype dw) and variants.py (TUNED_DW text).  Prints one line per run, then ALL_DONE.
"""
import importlib.util
import random
import sys
import time
import types
from pathlib import Path

base = Path(sys.argv[1])
sys.path.insert(0, str(base / "src"))
sys.path.insert(0, str(base))

stub = types.ModuleType("rewardkit")
stub.criteria = types.SimpleNamespace(__getattr__=None)


class _Criteria:
    def __getattr__(self, name):
        return lambda **kw: None


stub.criteria = _Criteria()
stub.criterion = lambda **kw: (lambda f: f)
sys.modules["rewardkit"] = stub
spec = importlib.util.spec_from_file_location("hidden", base / "test_output.py")
hidden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hidden)

from task import core, parser  # noqa: E402
import proto  # noqa: E402

namespace: dict = {}
variants_text = (base / "variants.py").read_text()
start = variants_text.index("TUNED_DW = '''") + len("TUNED_DW = '''")
exec(variants_text[start:variants_text.index("'''", start)], namespace)
tuned_dw = namespace["_dw_quote"]


def as_package_project(P):
    sites = [("S%03d" % q, "depot" if q == 0 else ("cold_room" if q in P["terms"] else "relay"),
              None if q == 0 else "mill", P["act"][q]) for q in range(P["n"] + 1)]
    links = [("L%03d%03d" % (a, b), "S%03d" % a, "S%03d" % b, c) for (a, b), c in sorted(P["edges"].items())]
    return parser.assemble("P0001", sites, links, len(links))


plan = [(12, 2), (13, 2), (14, 2), (15, 2), (16, 1), (17, 1)]
rng = random.Random(174241)
for k, repeats in plan:
    made = 0
    while made < repeats:
        n = rng.randint(46, 51)
        P = hidden._hub_project(rng, n, k, rng.randint(82, 92), rng.randint(3, 6))
        project = as_package_project(P)
        t0 = time.time()
        net = core.best_network(project)
        t_ref = time.time() - t0
        if net is None:
            continue
        made += 1
        t0 = time.time()
        q_tuned = tuned_dw(project)
        t_tuned = time.time() - t0
        t0 = time.time()
        q_proto = proto.dw(P)
        t_proto = time.time() - t0
        q_proto = q_proto[0] if isinstance(q_proto, (list, tuple)) else q_proto
        print("cold %2d sites %2d links %2d | reference %.3f s | prototype_dw %.1f s | tuned_dw %.1f s | quotes %s %s %s"
              % (k, n + 1, len(P["edges"]), t_ref, t_proto, t_tuned, net.quote, q_tuned, q_proto), flush=True)
print("ALL_DONE", flush=True)
