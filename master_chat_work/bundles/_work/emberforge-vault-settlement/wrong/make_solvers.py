"""Write the P3 wrong solvers as small edits of the bundle's solution/solve.py.

Usage: python3 make_solvers.py <solve.py> <out_dir>
Every edit is an exact string replacement that must hit once, so a drift in
solve.py fails loudly instead of producing a silently-correct solver.
"""
from __future__ import annotations

import sys
from pathlib import Path

TRUE_DRAW = 'Draw("RS-C", "half-even", "GFS", "opening-plus-acquired")'

EDITS: dict[str, list[tuple[str, str]]] = {
    # L1 scarcity fixpoint: one forward pass from zero indices, charged once.
    "L1": [(
        '        from_above = self._climb(self.ceiling)\n'
        '        from_below = self._climb(0)\n',
        '        first = self._sweep({r: 0 for r in self.corpus.scarce}).indices\n'
        '        return self._sweep(first)\n'
        '        from_above = self._climb(self.ceiling)\n'
        '        from_below = self._climb(0)\n',
    )],
    # L2 draw recovery: the draw found on the visible slice is hardcoded.
    "L2": [(
        '    data_dir = Path(data_dir)\n    slice_corpus = Corpus(data_dir, "calibration_")\n',
        '    return %s\n    data_dir = Path(data_dir)\n    slice_corpus = Corpus(data_dir, "calibration_")\n' % TRUE_DRAW,
    )],
    # L3 requisition plan: greedy by requested size instead of the Q7/Q8 optimum.
    "L3": [(
        '    seats = range(len(eligible))\n    charters = ',
        '    grants_g, total_g, used, gused, rused = {}, 0, set(), {}, {}\n'
        '    for req in sorted(eligible, key=lambda r: (-int(r["units_requested"]), r["req_id"])):\n'
        '        w = corpus.workshops[req["workshop_id"]]\n'
        '        grants_g[req["req_id"]] = 0\n'
        '        if w["charter_id"] in used:\n'
        '            continue\n'
        '        hi = min(int(req["units_requested"]), tier_cap[w["charter_tier"]], pool - total_g,\n'
        '                 guild_cap.get(w["guild_id"], 0) - gused.get(w["guild_id"], 0))\n'
        '        if req["reagent_id"] in corpus.scarce:\n'
        '            hi = min(hi, closing.get(req["reagent_id"], 0) - rused.get(req["reagent_id"], 0))\n'
        '        if hi >= int(req["min_units"]) and hi > 0:\n'
        '            grants_g[req["req_id"]] = hi\n'
        '            total_g += hi\n'
        '            used.add(w["charter_id"])\n'
        '            gused[w["guild_id"]] = gused.get(w["guild_id"], 0) + hi\n'
        '            rused[req["reagent_id"]] = rused.get(req["reagent_id"], 0) + hi\n'
        '    return grants_g, total_g\n'
        '    seats = range(len(eligible))\n    charters = ',
    )],
    # L4 identity: renames and merges applied whatever their effective day.
    "L4": [(
        '                if moved_on <= day and moved_on > latest:',
        '                if moved_on > latest:',
    )],
    # L5 E3: a salvage governed by the edition in force on its own filing day.
    "L5": [(
        '        return None if source is None else source["day"]',
        '        return None if source is None else entry["day"]',
    )],
    # L6 S6: every salvage the window admits is credited, redeemed or not.
    "L6": [(
        '        if source_id in walk.redeemed:\n            return [("SALVAGE_ALREADY_CREDITED", source_id)]\n',
        '',
    )],
    # L7 N3 composition at the forge (the run's own reading): closed -> CAP only;
    # floor tested before the cap and short-circuits it (no CAP, no closure).
    "L7": [(
        '        if workshop_id in walk.closed:\n'
        '            bars.append(("CAP_REACHED", workshop_id))\n'
        '        else:\n'
        '            cost = self._charge(entry, lines, indices)\n'
        '            cap = self.charge_cap[corpus.workshops[workshop_id]["charter_tier"]]\n'
        '            if walk.accrued[workshop_id] + cost > cap:\n'
        '                walk.closed.add(workshop_id)\n'
        '                bars.append(("CAP_REACHED", workshop_id))\n'
        '        short = [reagent_id for reagent_id in sorted(draw) if walk.balance[reagent_id] < draw[reagent_id]]\n'
        '        if short:\n'
        '            bars.append(("STOCK_FLOOR", short[0]))\n',
        '        short = [reagent_id for reagent_id in sorted(draw) if walk.balance[reagent_id] < draw[reagent_id]]\n'
        '        if workshop_id in walk.closed:\n'
        '            bars.append(("CAP_REACHED", workshop_id))\n'
        '        elif short:\n'
        '            bars.append(("STOCK_FLOOR", short[0]))\n'
        '        else:\n'
        '            cost = self._charge(entry, lines, indices)\n'
        '            cap = self.charge_cap[corpus.workshops[workshop_id]["charter_tier"]]\n'
        '            if walk.accrued[workshop_id] + cost > cap:\n'
        '                walk.closed.add(workshop_id)\n'
        '                bars.append(("CAP_REACHED", workshop_id))\n',
    )],
    # L7s (lazy only) N3 static refusals: only the first condition found.
    "L7s": [(
        '        return lines, bars\n\n    # -- H1 through H5',
        '        return lines, bars[:1]\n\n    # -- H1 through H5',
    )],
    # L8 N1: ledger settled in file order.
    "L8": [(
        '            ),\n            key=lambda entry: (entry["day"], entry["entry_id"]),\n        )\n',
        '            ),\n            key=lambda entry: 0,\n        )\n',
    )],
    # L9 canonical form: records written without the trailing newline.
    "L9": [(
        '            json.dumps(records[name], **CANONICAL) + "\\n", encoding="utf-8"',
        '            json.dumps(records[name], **CANONICAL), encoding="utf-8"',
    )],
}

SOLVERS = {
    "S2": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L7s", "L8", "L9"],
    "S4": ["L7"],
    **{"S3_" + k: [k] for k in ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9")},
    # L5 and L6 with the draw hardcoded: the lever's own weight once the failed
    # search no longer zeroes the run.
    "S3_L5h": ["L5", "L2"],
    "S3_L6h": ["L6", "L2"],
}


def build(src: str, levers: list[str]) -> str:
    out = src
    for lever in levers:
        for old, new in EDITS[lever]:
            if out.count(old) != 1:
                raise SystemExit("edit %s does not hit exactly once" % lever)
            out = out.replace(old, new)
    return out


def main() -> None:
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    dest = Path(sys.argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    for sid, levers in SOLVERS.items():
        (dest / ("%s.py" % sid)).write_text(build(src, levers), encoding="utf-8")
        print(sid, "+".join(levers))


if __name__ == "__main__":
    main()
