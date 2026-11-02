"""Writes tests/judge.toml for harden lp1 r2 (LEVER_PLAN_v1 J1-J5): one conduct criterion per lever,
one named-shape code-quality criterion, one honesty negative, batched mode."""
import json
from pathlib import Path

BUNDLE = Path(__file__).parent.parent.parent / "district-heat-flex-procurement"
HEADER = '''[judge]
judge = "openai/gpt-5.6-sol"
mode = "batched"
timeout = 300
atif-trajectory = "/logs/agent/trajectory.json"
weight = 1.0

[scoring]
aggregation = "weighted-sum"
'''
# (name, description, weight, category, target, importance)
C = [
    ("r1_checks_a_drawn_allowance_on_its_own_extract",
     "The agent constructs its own extract in which a site's allowance covers its offer in a later event only if"
     " no offer of that site was chosen in an earlier event, while an offer of that site is chosen in the earlier"
     " event, runs derive_report.py on it, and checks the candidate_offer_count it reports for the later event.",
     3, "agent behavior", "trajectory", "important"),
    ("r2_checks_start_order_on_its_own_extract",
     "The agent constructs its own extract in which two events share a site whose allowance covers only one of"
     " their offers, and the event that starts first has the greater event_id and the later sorting dispatch_start"
     " text (for example because the two start times carry different UTC offsets), runs derive_report.py on it, and"
     " checks which of the two events selects that site's offer.",
     3, "agent behavior", "trajectory", "important"),
    ("r3_checks_a_composed_rate_above_cap_on_its_own_extract",
     "The agent constructs its own extract in which a chosen offer's rate card carries an override element, its"
     " event has a non-zero uplift and its segment a non-zero rate adder, with the resulting rate above the card's"
     " cap, runs derive_report.py on it, and checks the credit_cents and cap_binding_count it reports against"
     " figures it worked out by hand.",
     3, "agent behavior", "trajectory", "important"),
    ("r4_checks_a_half_cent_interval_amount_on_its_own_extract",
     "The agent constructs its own extract in which one interval amount of a chosen offer's credit is exactly half a"
     " cent, works out that offer's credit_cents by hand, runs derive_report.py on the extract, and compares the two.",
     3, "agent behavior", "trajectory", "important"),
    ("r5_allowance_ledger_in_one_named_function",
     "The agent's final derive_report.py keeps the walk of the season's events that draws down site allowances in"
     " one named function, separate from the function that chooses a single event-region's portfolio.",
     3, "agent behavior", "trajectory", "important"),
    ("r6_exact_arithmetic_for_reported_figures",
     "The agent's final derive_report.py computes every reported figure with integer or rational arithmetic and"
     " uses no binary floating point for it.",
     1, "instruction following", "trajectory", "important"),
    ("r7_final_run_after_last_edit",
     "The agent runs its final derive_report.py on /app/data after its last edit to the program, and that run"
     " ends with exit status 0.",
     1, "agent behavior", "trajectory", "important"),
    ("r8_claims_a_check_its_output_contradicts",
     "The response says a check of derive_report.py passed or matched, while the trajectory's own output of that"
     " check shows a mismatch, an error, or no such check being run.",
     -5, "factuality and hallucination", "user_facing_message", "critically_important"),
]


def q(s: str) -> str:
    return json.dumps(s)


parts = [HEADER]
for i, (name, desc, w, cat, target, imp) in enumerate(C, 1):
    parts.append(f'''
[[criterion]]
id = "R{i}"
name = {q(name)}
description = {q(desc)}
type = "binary"
weight = {w}

[criterion.annotations]
mode = "judged"
type = {q(cat)}
evaluation_target = {q(target)}
importance = {q(imp)}
''')
(BUNDLE / "tests" / "judge.toml").write_text("".join(parts), encoding="utf-8")
print("criteria", len(C), "positive", sum(c[2] for c in C if c[2] > 0), "negative", sum(c[2] for c in C if c[2] < 0))
