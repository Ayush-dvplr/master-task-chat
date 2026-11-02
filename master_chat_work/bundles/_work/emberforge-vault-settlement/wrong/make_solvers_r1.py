"""Write the P3 wrong solvers (round 1) as small edits of solution/solve.py.

Usage: python3 make_solvers_r1.py <solve.py> <round0_solve.py> <out_dir>
Every edit is an exact replacement that must hit once.
"""
from __future__ import annotations

import sys
from pathlib import Path

TRUE_DRAW = 'Draw("RS-C", "half-even", "GFS", "opening-plus-acquired")'

FORGE_RIGHT = '''        bars: list[tuple[str, str]] = []
        cost = 0
        if workshop_id in walk.closed:
            bars.append(("CAP_REACHED", workshop_id))
        else:
            cost = self._charge(entry, lines, indices)
            cap = self.charge_cap[corpus.workshops[workshop_id]["charter_tier"]]
            if walk.accrued[workshop_id] + cost > cap:
                walk.closed.add(workshop_id)
                bars.append(("CAP_REACHED", workshop_id))
        short = [reagent_id for reagent_id in sorted(draw) if walk.balance[reagent_id] < draw[reagent_id]]
        if short:
            bars.append(("STOCK_FLOOR", short[0]))
'''

EDITS: dict[str, list[tuple[str, str]]] = {
    # LV-EF-1 (the run's reading): a closed workshop gives CAP only; at an open
    # workshop the floor is tested first and short-circuits the cap (no closure).
    "LV1": [(FORGE_RIGHT, '''        bars: list[tuple[str, str]] = []
        cost = 0
        short = [reagent_id for reagent_id in sorted(draw) if walk.balance[reagent_id] < draw[reagent_id]]
        if workshop_id in walk.closed:
            bars.append(("CAP_REACHED", workshop_id))
        elif short:
            bars.append(("STOCK_FLOOR", short[0]))
        else:
            cost = self._charge(entry, lines, indices)
            cap = self.charge_cap[corpus.workshops[workshop_id]["charter_tier"]]
            if walk.accrued[workshop_id] + cost > cap:
                walk.closed.add(workshop_id)
                bars.append(("CAP_REACHED", workshop_id))
''')],
    # LV-EF-2: a retired reagent refuses the forge before anything else is tested.
    "LV2": [(
        '        bars: list[tuple[str, str]] = []\n        cost = 0\n',
        '        bars: list[tuple[str, str]] = []\n        cost = 0\n'
        '        gone = [r for r in sorted(draw) if entry["day"] >= corpus.retired_from.get(r, entry["day"] + 1)]\n'
        '        if gone:\n'
        '            return [("RETIRED_REAGENT", gone[0])]\n',
    )],
    # LV-EF-3 (the run's reading): the consumed reference counts every forge
    # that resolves an edition, statically refused or not.
    "LV3": [(
        '            if lines is None or entry["entry_id"] in self.barred:\n                continue\n',
        '            if lines is not None and entry["op"] == "forge" and entry["entry_id"] in self.barred:\n'
        '                for line in lines:\n'
        '                    walk.called_for[line["reagent_id"]] += line["units_per_craft"] * entry["units"]\n'
        '            if lines is None or entry["entry_id"] in self.barred:\n                continue\n',
    )],
    # LV-EF-4: exhaustive search over every plan (the round-0 fund), set in by main().
    "LV4": [],
    # L1 scarcity fixed point: one forward pass.
    "L1": [(
        '        from_above = self._climb(self.ceiling)\n',
        '        return self._sweep(self._sweep({r: 0 for r in self.corpus.scarce}).indices)\n'
        '        from_above = self._climb(self.ceiling)\n',
    )],
    # L2 draw recovery: hardcoded.
    "L2": [(
        '    data_dir = Path(data_dir)\n    slice_corpus = Corpus(data_dir, "calibration_")\n',
        '    return %s\n    data_dir = Path(data_dir)\n    slice_corpus = Corpus(data_dir, "calibration_")\n' % TRUE_DRAW,
    )],
    # L4 identity: renames and merges applied whatever their day.
    "L4": [('                if moved_on <= day and moved_on > latest:', '                if moved_on > latest:')],
    # L5 E3: salvage governed by its own filing day.
    "L5": [('        return None if source is None else source["day"]', '        return None if source is None else entry["day"]')],
    # L6 S6 removed.
    "L6": [('        if source_id in walk.redeemed:\n            return [("SALVAGE_ALREADY_CREDITED", source_id)]\n', '')],
    # L7s static refusals: first condition only.
    "L7s": [('        return lines, bars\n\n    # -- H1 through H5', '        return lines, bars[:1]\n\n    # -- H1 through H5')],
    # L8 N1: file order.
    "L8": [('            ),\n            key=lambda entry: (entry["day"], entry["entry_id"]),\n        )\n', '            ),\n            key=lambda entry: 0,\n        )\n')],
    # L9 no trailing newline.
    "L9": [('            json.dumps(records[name], **CANONICAL) + "\\n", encoding="utf-8"', '            json.dumps(records[name], **CANONICAL), encoding="utf-8"')],
}

NEW = ["LV1", "LV2", "LV3", "LV4"]
OLD = ["L1", "L2", "L4", "L5", "L6", "L8", "L9"]
SOLVERS = {
    "S2": ["LV1", "LV2", "LV3", "LV4", "L1", "L2", "L4", "L5", "L6", "L7s", "L8", "L9"],
    "S4": NEW,
    **{"S3_" + k: [k] for k in NEW + OLD},
    "PAIR_LV1_LV2": ["LV1", "LV2"],
    "PAIR_LV3_LV4": ["LV3", "LV4"],
    "SHORTCUT_draw": ["L2"],
}


EXHAUSTIVE_FUND = '''def fund(corpus: Corpus, closing: dict[str, int]) -> tuple[dict[str, int], int]:
    """Q1 to Q8 by exhaustive search over every grant of every requisition."""
    charter = corpus.charter
    pool = int(charter["season_pool_units"])
    guild_cap = {name: int(cap) for name, cap in charter["guild_cap_units"].items()}
    tier_cap = {int(tier): int(cap) for tier, cap in charter["tier_unit_cap"].items()}
    eligible = [req for req in corpus.requisitions if req["workshop_id"] in corpus.in_scope]
    items = sorted(eligible, key=lambda req: (int(req["priority"]), req["req_id"]))
    choices = []
    for req in items:
        workshop = corpus.workshops[req["workshop_id"]]
        high = min(int(req["units_requested"]), tier_cap[workshop["charter_tier"]])
        choices.append([0] + list(range(int(req["min_units"]), high + 1)))

    def step(i, units, state):
        used, guilds, reagents, charters = state
        if units == 0:
            return state
        req = items[i]
        workshop = corpus.workshops[req["workshop_id"]]
        if workshop["charter_id"] in charters or used + units > pool:
            return None
        if guilds.get(workshop["guild_id"], 0) + units > guild_cap.get(workshop["guild_id"], 0):
            return None
        rid = req["reagent_id"]
        if rid in corpus.scarce and reagents.get(rid, 0) + units > closing.get(rid, 0):
            return None
        g = dict(guilds); g[workshop["guild_id"]] = g.get(workshop["guild_id"], 0) + units
        r = dict(reagents); r[rid] = r.get(rid, 0) + units
        return used + units, g, r, charters | {workshop["charter_id"]}

    def best_from(i, state):
        if i == len(items):
            return 0
        best = 0
        for units in choices[i]:
            moved = step(i, units, state)
            if moved is not None:
                best = max(best, units + best_from(i + 1, moved))
        return best

    state = (0, {}, {}, frozenset())
    remaining = best_from(0, state)
    total = remaining
    grants = {}
    for i in range(len(items)):
        for units in sorted(choices[i], reverse=True):
            moved = step(i, units, state)
            if moved is not None and units + best_from(i + 1, moved) == remaining:
                grants[items[i]["req_id"]] = units
                state, remaining = moved, remaining - units
                break
    return grants, total


'''


def build(src: str, levers: list[str], round0: str) -> str:
    out = src
    for lever in levers:
        if lever == "LV4":
            start = out.index("class Requests:")
            end = out.index("# ---------------------------------------------------------------------------\n# the delivered records")
            out = out[:start] + EXHAUSTIVE_FUND + out[end:]
            continue
        for old, new in EDITS[lever]:
            if out.count(old) != 1:
                raise SystemExit("edit %s does not hit exactly once" % lever)
            out = out.replace(old, new)
    return out


def main() -> None:
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    round0 = Path(sys.argv[2]).read_text(encoding="utf-8")
    dest = Path(sys.argv[3])
    dest.mkdir(parents=True, exist_ok=True)
    for sid, levers in SOLVERS.items():
        (dest / ("%s.py" % sid)).write_text(build(src, levers, round0), encoding="utf-8")
        print(sid, "+".join(levers))


if __name__ == "__main__":
    main()
