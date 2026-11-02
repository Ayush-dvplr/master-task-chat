"""Lever table (round 2, extended in harden lp1 r1 and r2 with combined readings) by arithmetic: each check is evaluated with the verifier's own reference playing a program
that has exactly one wrong reading (the flag), through the real check functions. No solver program is written or run.

Usage: python3 lever_table.py WORKSPACE_WITH_ORACLE_OUT [out.json]
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "stub"))
import rewardkit  # noqa: E402

BUNDLE = Path(__file__).parent.parent.parent / "district-heat-flex-procurement"
spec = importlib.util.spec_from_file_location("t", BUNDLE / "tests" / "test_output.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
ws = Path(sys.argv[1])
CHECKS = dict(rewardkit.CHECKS)
WEIGHTS = dict(rewardkit.WEIGHTS)
POS = sum(w for w in WEIGHTS.values() if w > 0)


def play(flags: frozenset):
    def fake(workspace, data):
        if data is None:
            return None
        ref = t.expected(data, flags)
        return {n: json.loads(json.dumps(ref[n])) for n in t.ARTIFACT_JSON}
    t.run_agent = fake
    earned, lost = 0, {}
    for name, (fn, _) in CHECKS.items():
        w = WEIGHTS[name]
        ok = fn(ws) is True
        if w > 0:
            earned += w if ok else 0
            if not ok:
                lost[name] = w
        elif ok:
            earned += w
            lost[name] = w
    return earned, lost


rows = {}
base, lost0 = play(frozenset())
rows["none"] = {"earned": base, "fraction": base / POS, "lost": lost0}
for flag in sorted(t.ALL_FLAGS):
    e, lost = play(frozenset({flag}))
    rows[flag] = {"earned": e, "fraction": round(e / POS, 4), "lost_weight": base - e, "lost": lost}
COMBOS = {"L1_receipt_reading": {"LEDstatic"}, "L3_reflex_id_order": {"LEDid"},
          "L3_text_order": {"LEDstr", "LEDstatic"}, "L4_uplift_and_adder": {"UPL0", "ADD0"},
          "L7_both": {"R7offer", "H5c"}}
for label, flags in COMBOS.items():
    e, lost = play(frozenset(flags))
    rows[label] = {"earned": e, "fraction": round(e / POS, 4), "lost_weight": base - e, "lost": lost}
rows["_meta"] = {"positive_total": POS, "checks": len(CHECKS)}
for k, v in rows.items():
    if k.startswith("_"):
        continue
    print(f"{k:10s} earned {v['earned']:>4} lost {v.get('lost_weight', 0):>3}  {sorted(v['lost'])[:6]}")
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps(rows, indent=1), encoding="utf-8")
