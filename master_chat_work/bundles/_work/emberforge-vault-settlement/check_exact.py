"""Independent exact check of the Q1 to Q8 requisition plan, and a count of feasible plans.

Usage: python3 check_exact.py <corpus_dir> <settled_out_dir> [<another_out_dir> ...]

Method (shares nothing with solve.py or test_output.py): dynamic programming over
charter groups, with the state set to the units already granted per guild and per
scarce reagent. Two partial plans that reach the same state accept exactly the same
completions, so keeping, per state, the partial plan that is greatest in Q8 order
loses nothing (the first Q8 position where two full plans differ lies in the part
they do not share). The final answer is the greatest total, then the greatest plan
in Q8 order among those. The same pass counts every feasible plan, which is the
least number of complete plans an exhaustive search has to visit.

The pool limit is read off the state, because every eligible requisition belongs to
a guild: units granted = sum of the guild coordinates.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    corpus = Path(sys.argv[1])
    outs = [Path(p) for p in sys.argv[2:]]
    charter = json.loads((corpus / "season_charter.json").read_text())
    reqs = json.loads((corpus / "requisitions.json").read_text())["requisitions"]
    calendar = rows(corpus / "patch_calendar.csv")
    first = min(int(p["opens_day"]) for p in calendar)
    last = max(int(p["closes_day"]) for p in calendar)
    shops = {}
    for w in rows(corpus / "workshop_registry.csv"):
        closed = w["closed_day"]
        shops[w["workshop_id"]] = dict(
            w, tier=int(w["charter_tier"]),
            live=int(w["opened_day"]) <= first and (closed == "" or int(closed) >= last) and int(w["charter_tier"]) >= 2,
        )
    scarce = sorted(r["reagent_id"] for r in rows(corpus / "reagent_registry.csv") if r["scarce"] == "1")
    vault = json.loads((outs[0] / "vault_audit.json").read_text())["reagents"]
    closing = {r["reagent_id"]: r["closing_units"] for r in vault}

    guilds = sorted(charter["guild_cap_units"])
    cap = [int(charter["guild_cap_units"][g]) for g in guilds]
    lim = [closing[r] for r in scarce]
    pool = int(charter["season_pool_units"])
    unit_cap = {int(k): int(v) for k, v in charter["tier_unit_cap"].items()}

    live = [r for r in reqs if shops[r["workshop_id"]]["live"]]
    pref = sorted(live, key=lambda r: (int(r["priority"]), r["req_id"]))
    pos = {r["req_id"]: i for i, r in enumerate(pref)}
    groups: dict[str, list[dict]] = {}
    for r in live:
        groups.setdefault(shops[r["workshop_id"]]["charter_id"], []).append(r)

    start = time.time()
    width = len(pref)
    zero = (0,) * (len(guilds) + len(scarce))
    best = {zero: (0,) * width}
    count = {zero: 1}
    for name in sorted(groups):
        moves = []
        for r in groups[name]:
            hi = min(int(r["units_requested"]), unit_cap[shops[r["workshop_id"]]["tier"]])
            gi = guilds.index(shops[r["workshop_id"]]["guild_id"])
            si = scarce.index(r["reagent_id"]) if r["reagent_id"] in scarce else None
            for v in range(int(r["min_units"]), hi + 1):
                moves.append((pos[r["req_id"]], gi, si, v))
        nbest = dict(best)
        ncount = dict(count)
        for state, plan in best.items():
            n = count[state]
            for p, gi, si, v in moves:
                s = list(state)
                s[gi] += v
                if s[gi] > cap[gi]:
                    continue
                if si is not None:
                    s[len(guilds) + si] += v
                    if s[len(guilds) + si] > lim[si]:
                        continue
                if sum(s[: len(guilds)]) > pool:
                    continue
                t = tuple(s)
                q = plan[:p] + (v,) + plan[p + 1:]
                ncount[t] = ncount.get(t, 0) + n
                old = nbest.get(t)
                if old is None or q > old:
                    nbest[t] = q
        best, count = nbest, ncount
    total = max(sum(s[: len(guilds)]) for s in best)
    plan = max(best[s] for s in best if sum(s[: len(guilds)]) == total)
    feasible = sum(count.values())
    want = {r["req_id"]: plan[pos[r["req_id"]]] if r["req_id"] in pos else 0 for r in reqs}
    print(json.dumps({"corpus": str(corpus), "requisitions": len(reqs), "eligible": len(live),
                      "states": len(best), "optimum_total": total, "feasible_plans": feasible,
                      "seconds": round(time.time() - start, 1)}))
    for out in outs:
        got = json.loads((out / "allocation.json").read_text())
        grants = {a["req_id"]: a["allocated_units"] for a in got["assignments"]}
        verdict = "AGREES" if grants == want and got["allocated_total"] == total else "DIFFERS"
        print(out, verdict)


if __name__ == "__main__":
    main()
