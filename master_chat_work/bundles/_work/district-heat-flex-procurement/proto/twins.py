"""Count candidate lanes holding identical offers (same relief, recovery, cost) in shipped and existing hidden corpora."""
import importlib.util, sys
from pathlib import Path
sys.dont_write_bytecode = True
import gen
T = gen.T
SOLVE = Path("/b/solution/solve.py")
spec = importlib.util.spec_from_file_location("solve", SOLVE)
S = importlib.util.module_from_spec(spec); sys.modules["solve"] = S; spec.loader.exec_module(S)
orig = S.choose_portfolio
stat = {}
def wrap(ex, event, region, candidates):
    by = {}
    for o in candidates:
        by.setdefault(o.site.site_id, []).append((tuple(o.relief), tuple(o.recovery), o.cost))
    stat["ers"] += 1; stat["lanes"] += len(by)
    tw = sum(1 for v in by.values() if len(set(v)) < len(v))
    stat["twin_lanes"] += tw; stat["ers_with_twin"] += 1 if tw else 0
    chosen, ways = orig(ex, event, region, candidates)
    if tw and any(len(set(v)) < len(v) and any(o.site.site_id == s for o in chosen) for s, v in by.items()):
        stat["ers_twin_chosen"] += 1
    return chosen, ways
S.choose_portfolio = wrap
for name, root in (("shipped", Path("/b/environment/data")), ("H1", T.hidden_root("H1")), ("H2", T.hidden_root("H2"))):
    stat.clear(); stat.update(ers=0, lanes=0, twin_lanes=0, ers_with_twin=0, ers_twin_chosen=0)
    S.build(Path(root))
    print(name, stat, flush=True)
