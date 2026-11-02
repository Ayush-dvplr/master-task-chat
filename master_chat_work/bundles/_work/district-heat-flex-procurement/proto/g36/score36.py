"""g36 scratch: score.py plus the QC v6 TS-25 non-empty rule of wide_feasible. Usage: score36.py REF_OUT PROG_OUT PROBLEMS.json"""
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score as S
ref_regs, ref_audit = S.load(sys.argv[1]); regs, audit = S.load(sys.argv[2]); problems = json.load(open(sys.argv[3]))
if regs is None:
    print(0, 0, 0, 0, 0); sys.exit()
f = S.feasible(regs, problems)
try:
    for r in S.REGIONS:
        mine = {e["event_id"]: e["selected_offer_ids"] for e in regs[r]["events"]}
        for e in ref_regs[r]["events"]:
            if e["selected_offer_ids"] and not mine.get(e["event_id"]):
                f = False
except Exception:
    f = False
sel = ("event_id", "candidate_offer_count", "selected_offer_ids")
s = S.rows(regs, sel) == S.rows(ref_regs, sel)
t = audit.get("tie_decisions") == ref_audit["tie_decisions"]
i = S.rows(regs, ("event_id", "intervals")) == S.rows(ref_regs, ("event_id", "intervals"))
print(int(f), int(s), int(t), int(i), 3 * f + 5 * s + 5 * t + 3 * i)
