"""Score one program output against the reference output on a wide extract (scratch).
Usage: score.py REF_OUT PROG_OUT PROBLEMS.json -> prints feasible selection ties intervals points (3/5/5/3)."""
import json
import sys
from pathlib import Path

REGIONS = ("East", "North", "South", "West")


def load(out):
    try:
        regs = {r: json.loads((Path(out) / f"region_{r}.json").read_text()) for r in REGIONS}
        audit = json.loads((Path(out) / "policy_audit.json").read_text())
        return regs, audit
    except Exception:
        return None, None


def rows(regs, fields):
    return {r: [{k: e.get(k) for k in fields} for e in regs[r]["events"]] for r in REGIONS}


def feasible(regs, problems):
    try:
        by_er = {tuple(p["er"]): p for p in problems}
        for r in REGIONS:
            for e in regs[r]["events"]:
                p = by_er.get((e["event_id"], r))
                ids = e["selected_offer_ids"]
                if p is None:
                    if ids:
                        return False
                    continue
                offers = {o["id"]: (si, o) for si, lane in enumerate(p["lanes"]) for o in lane}
                if any(i not in offers for i in ids) or len({offers[i][0] for i in ids}) != len(ids):
                    return False
                for t in range(p["n"]):
                    if sum(offers[i][1]["rel"][t] for i in ids) > p["limit"][t][0]:
                        return False
                    if sum(offers[i][1]["rec"][t] for i in ids) > p["limit"][t][1]:
                        return False
        return True
    except Exception:
        return False


if __name__ == "__main__":
    ref_regs, ref_audit = load(sys.argv[1])
    regs, audit = load(sys.argv[2])
    problems = json.load(open(sys.argv[3]))
    if regs is None:
        print(0, 0, 0, 0, 0)
        sys.exit()
    f = feasible(regs, problems)
    sel_fields = ("event_id", "candidate_offer_count", "selected_offer_ids")
    s = rows(regs, sel_fields) == rows(ref_regs, sel_fields)
    t = audit.get("tie_decisions") == ref_audit["tie_decisions"]
    i = rows(regs, ("event_id", "intervals")) == rows(ref_regs, ("event_id", "intervals"))
    print(int(f), int(s), int(t), int(i), 3 * f + 5 * s + 5 * t + 3 * i)
