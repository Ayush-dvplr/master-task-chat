"""Write the single-lever variants of the oracle program.

Usage: python3 single_lever.py <solve.py> <out_dir>
Each variant is the oracle with one reading changed; every edit must apply once.
"""

import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text(encoding="utf-8")
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

DRAW = '        left[charter] = (renewal, left[charter][1] - amount)\n'
SKIP = '        if entry["kept"] is None:\n            continue\n'
RENEW = '        renewal = max(first for first in openings if first <= entry["tick"])\n'
CHARTER = '        charter = entry["charter"]\n        if left.get'
RUN = '    def run(self):\n'
TIE = '                  key=lambda item: item[:3])\n'
POP = '            queue.pop(0)["kept"] = None\n'
RETIRED = '''        if owner is None:
            out["dropped_retired"] += 1
            out["dropped"] += entry["amount"]
'''
OFFWINDOW = '''        elif not any(first <= entry["tick"] <= last for first, last in spans):
            out["dropped_offwindow"] += 1
            out["dropped"] += entry["amount"]
'''
SWAPPED = '''        if not any(first <= entry["tick"] <= last for first, last in spans):
            out["dropped_offwindow"] += 1
            out["dropped"] += entry["amount"]
        elif owner is None:
            out["dropped_retired"] += 1
            out["dropped"] += entry["amount"]
'''

CARRY = '''    def run(self):
        carried = {"frame_bias_limit": 9, "weave_seed_offset": 23, "sentinel_code_value": 214,
                   "drift_modulus": 11, "seal_label_index": 5, "spin_modulus": 13,
                   "shadow_pad_base": 7, "alias_donor_shift": 3, "echo_window_span": 6,
                   "cadence_modulus": 4, "upkeep_target_scale": 17}
        figures = self.inputs["slice"]["figures"]
        table = []
        for name, candidates, control in self.inputs["slice"]["quantities"]:
            self.quantities.append({"name": name, "value": carried[name], "control": control,
                                    "rejected": [{"candidate": c, "falsifier": control}
                                                 for c in candidates if c != carried[name]]})
            table.append({"control": control, "published": figures[control],
                          "produced": figures[control]})
        self.values = dict(carried)
        return table

    def run_recovered(self):
'''

DIVTICK = '    out["divergence_tick"] = live[out["divergence"]]["tick"] if out["divergence"] >= 0 else 0\n'
LIVEONLY = '''    for entry in live:
        if entry["kept"] is None:
            out["entry_total"] -= 1
            out["decoded"] -= entry["amount"]
'''

VARIANTS = {
    # L3 reflex: each entry capped by the allowance, nothing drawn down.
    "var_perentry": [(DRAW, '        left[charter] = (renewal, left[charter][1])\n')],
    # L4 reflex: one allowance for the whole walk, never renewed.
    "var_norenew": [(RENEW, '        renewal = 0\n')],
    # L3 variant: the allowance drawn is the opening charter's.
    "var_opening": [(CHARTER, '        charter = entry["opening"]\n        if left.get')],
    # L3 ordering variant: cancelled entries draw before they are skipped.
    "var_cancelled_draw": [(SKIP, ''), (DRAW, DRAW + SKIP)],
    # F-03: the eleven quantities carried in source as the shipped values.
    "var_carry_eleven": [(RUN, CARRY)],
    # Engine rules: retired and off-window checked in the other order.
    "var_precedence": [(RETIRED + OFFWINDOW, SWAPPED)],
    # L4 variant: renewal only at openings strictly before the entry's tick.
    "var_renew_strict": [(RENEW, '        renewal = max((first for first in openings '
                                 'if first < entry["tick"]), default=0)\n')],
    # Walk order: ordinal before capture number on a tick tie.
    "var_tiebreak": [(TIE, '                  key=lambda item: (item[0], item[2], item[1]))\n')],
    # Reversal order: latest-uncancelled (LIFO) instead of earliest.
    "var_lifo": [(POP, '            queue.pop()["kept"] = None\n')],
    # CL-4 reading B: decoded totals leave out cancelled entries and the reversals that cancel them.
    "var_decoded_live": [(DIVTICK, DIVTICK + LIVEONLY)],
}

for name, edits in VARIANTS.items():
    text = source
    for old, new in edits:
        if text.count(old) != 1:
            raise SystemExit("%s: edit anchor found %d times" % (name, text.count(old)))
        text = text.replace(old, new)
    (out / (name + ".py")).write_text(text, encoding="utf-8")
    print("wrote", name)
