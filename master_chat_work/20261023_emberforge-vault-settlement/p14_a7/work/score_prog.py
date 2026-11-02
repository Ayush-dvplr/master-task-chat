"""Score a program with the grader's own value checks (local, no setpriv). Usage: python3 score_prog.py <program.py>"""
import sys, types
from pathlib import Path
HERE = Path(__file__).resolve().parent
rk = types.ModuleType("rewardkit")
def _deco(*a, **k):
    if a and callable(a[0]) and not k: return a[0]
    return lambda f: f
class _C:
    def __getattr__(self, n): return _deco
rk.criteria = _C(); rk.criterion = _deco
sys.modules["rewardkit"] = rk
sys.path.insert(0, str(HERE))
import grader as G
G.PROGRAM = (HERE / sys.argv[1]).resolve()
G._drop_privileges = lambda cmd: cmd
G._open_to_sandbox = lambda *a, **k: None
W = {"whole_summary":5,"whole_vault_audit":5,"whole_reconciliation":5,"whole_data_quality":5,"whole_allocation":5,
     "whole_workshop_reports":5,"whole_guild_reports":5,"unit_charge_season_total":3,"cap_release_closures":3,
     "live_window_refusals":3,"mutation_family_multiplier":3,"mutation_grade_step":3}
tot = 0
for n, w in W.items():
    try:
        r = getattr(G, "test_" + n)(); ok = (r is None) or bool(r)
    except AssertionError as e:
        ok = False
    tot += w if ok else 0
    print("%-28s w%d %s" % (n, w, "PASS" if ok else "FAIL"))
print("value points %d of 50 (+4 structure)" % tot)
