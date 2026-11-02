"""Build the single-rule AL-27 mutants of solution/solve.py (QC v8, board 391ff22).

usage: python3 make_al27_mutants.py <solve.py> <out_dir>
Each mutant changes exactly one rule; every replaced string must occur exactly once.
"""
import pathlib
import sys

src = pathlib.Path(sys.argv[1]).read_text()
out = pathlib.Path(sys.argv[2])

MUTANTS = {
    # finding_codes.md STOCK_FLOOR: detail names the LAST short reagent instead of the first.
    "al27_stock_floor_last": [('bars.append(("STOCK_FLOOR", short[0]))', 'bars.append(("STOCK_FLOOR", short[-1]))')],
    # rulebook_admission.md A2: both edges exclusive (opened on first day / closed on last day drop out).
    "al27_a2_edges": [
        ('if workshop["opened_day"] > self.calendar.first_day:', 'if workshop["opened_day"] >= self.calendar.first_day:'),
        ('and workshop["closed_day"] < self.calendar.last_day', 'and workshop["closed_day"] <= self.calendar.last_day'),
    ],
    # rulebook_requisitions.md Q1: every requisition is considered, in scope or not.
    "al27_q1_all": [('eligible = [req for req in corpus.requisitions if req["workshop_id"] in corpus.in_scope]',
                     'eligible = list(corpus.requisitions)')],
    # rulebook_scarcity.md V2: units serve only entries of LATER days.
    "al27_v2_strict": [('while arrivals and arrivals[0]["day"] <= entry["day"]:',
                        'while arrivals and arrivals[0]["day"] < entry["day"]:')],
}

for name, edits in MUTANTS.items():
    text = src
    for old, new in edits:
        assert text.count(old) == 1, (name, old, text.count(old))
        text = text.replace(old, new)
    (out / (name + ".py")).write_text(text)
    print(name, "built,", len(edits), "edit(s)")
