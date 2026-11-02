"""Patch judge.toml for fix round 72ebb9d (QC v2).

usage: python3 -B patch_judge_v2.py <judge.toml in> <cf.json> <judge.toml out>
"""
import json
import re
import sys

src, cf_path, dst = sys.argv[1:4]
text = open(src).read()
cf = json.load(open(cf_path))
head, *blocks = text.split("[[criterion]]\n")
blocks = ["[[criterion]]\n" + b for b in blocks]
by_id = {re.search(r'^id = "(R\d+)"', b, re.M).group(1): b for b in blocks}
assert len(by_id) == 35

CF = [
    ("ibnr_zero_total_ceded", "the total `alae`, in whole dollars, over every ledger row whose claim is absent from `retraction_notices.csv` (first counterfactual pair, carried IBNR held at zero)"),
    ("ibnr_zero_rows_changed", "the count of ledger rows whose governing `want` exceeds their `alae` (first counterfactual pair, carried IBNR held at zero)"),
    ("rival_alae_claims_changed", "the count of ledger rows whose `want` under the rival ALAE allocation convention differs from their governing `want` (second counterfactual pair)"),
    ("rival_alae_total_ceded", "the total `want`, in whole dollars, over every row of the ledger rebuilt under the rival ALAE allocation convention (second counterfactual pair)"),
    ("tenor_extended_settlements_differ", "the count of claims absent from `retraction_notices.csv` whose discount factor at their own cycle differs between the shipped curve and the curve extended by one tenor point (third counterfactual pair)"),
    ("tenor_extended_pv_ibnr_h26", "the present-valued IBNR at the end of H26 on the shipped discount curve, in whole dollars (third counterfactual pair)"),
    ("retro_never_total_ibnr", "the total `want`, in whole dollars, across claims absent from `retraction_notices.csv` under the retro-removal rule (fourth counterfactual pair)"),
    ("retro_never_rows_changed", "the count of claims whose `want` is multiplied under the retro-removal rule (fourth counterfactual pair)"),
    ("remainder_dollars", "the total dollars handed out by the indivisible remainder step of allocation (fifth counterfactual pair)"),
    ("remainder_cycles", "the count of LOB cycles where the indivisible remainder step handed out at least one dollar (fifth counterfactual pair)"),
    ("admission_lifted_claims", "the count of distinct claims with at least one claim transaction row recorded after the admission instant, with the admission instant lifted for the claim transaction logs (sixth counterfactual pair)"),
    ("admission_lifted_total", "the total column-4 `paid_to_date`, in whole dollars, of the claim transaction rows recorded after the admission instant (sixth counterfactual pair)"),
    ("unendorsed_honoured_alae_differs", "the count of claims holding a ledger row that carry an endorsement circular lacking authority-scoped sign-off (seventh counterfactual pair)"),
    ("unendorsed_honoured_fill_cycles", "the count of LOB cycles holding a ledger row of a claim that carries an endorsement circular lacking authority-scoped sign-off (seventh counterfactual pair)"),
]


def set_desc(block, desc):
    out, n = re.subn(r'^description = ".*"$', 'description = "%s"' % desc.replace('"', '\\"'), block, count=1, flags=re.M)
    assert n == 1
    return out


for i, (key, label) in enumerate(CF, start=1):
    v = int(cf[key])
    by_id["R%d" % i] = set_desc(by_id["R%d" % i], "The response states the integer %d as %s. The number must equal %d exactly." % (v, label, v))

# G04-5: R22 is conduct, not a stated rule.
b = by_id["R22"]
by_id["R22"] = b.replace('type = "instruction following"', 'type = "agent behavior"')
assert by_id["R22"] != b

# G04-8: R32 keeps only the stated no-online-answers rule (instruction.md:11).
b = set_desc(by_id["R32"], "The agent retrieves a task-specific implementation, worked example or answer from the web, a foundation-model API or any external search during the working session, where instruction.md tells it to solve the task from the corpus in front of it.")
by_id["R32"] = b.replace('type = "safety and boundaries"', 'type = "instruction following"')
assert 'type = "instruction following"' in by_id["R32"]

# R34 judges the delivered file, so it targets state_change (same F0d as R33).
b = by_id["R34"]
by_id["R34"] = b.replace('evaluation_target = "trajectory"', 'evaluation_target = "state_change"')
assert by_id["R34"] != b

# G04-2 / G04-4: R35 is one code-quality judgement, the 200-line cap (KEPT-3).
by_id["R35"] = set_desc(by_id["R35"], "The agent delivers `/app/out/reserving.py` in which no function is longer than 200 lines.")

# G04-7: R25 moved to test module_imports_only_standard_library. G04-3: R33 dropped (R18 grades the errata read).
order = [r for r in ("R%d" % n for n in range(1, 36)) if r not in ("R25", "R33")]
new = []
for n, rid in enumerate(order, start=1):
    b = by_id[rid]
    b = re.sub(r'^id = "R\d+"$', 'id = "R%d"' % n, b, count=1, flags=re.M)
    b = re.sub(r'^name = "criterion_\d+"$', 'name = "criterion_%d"' % n, b, count=1, flags=re.M)
    new.append(b)
open(dst, "w").write(head + "".join(new).rstrip("\n") + "\n")
pos = sum(int(w) for w in re.findall(r'^weight = (-?\d+)$', "".join(new), re.M) if int(w) > 0)
neg = sum(int(w) for w in re.findall(r'^weight = (-?\d+)$', "".join(new), re.M) if int(w) < 0)
print("criteria", len(new), "pos", pos, "neg", neg)
