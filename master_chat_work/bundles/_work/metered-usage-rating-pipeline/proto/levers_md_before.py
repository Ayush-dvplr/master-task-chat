"""Write WORK/LEVERS.md from the real test registrations and cost_table.json failures."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent.parent / "metered-usage-rating-pipeline" / "tests" / "test_output.py"
cost = json.loads((HERE / "cost_table.json").read_text())
weights = dict((m.group(1), int(m.group(2))) for m in
               re.finditer(r"^criteria\.(\w+)\(weight=(-?\d+)\)", TESTS.read_text(), re.M))
levers = ["LV-MU-6", "LV-MU-5", "LV-MU-7"]
noise = ["LV-MU-1", "LV-MU-3"]
failed = {lv: set(cost["alone " + lv]["failed"]) for lv in levers}
failed.update({lv: set(cost["noise alone " + lv]["failed"]) for lv in noise})
where = {"LV-MU-6": "rating_contract.md:162-177 Credit (second pass 174-176), 30-31 credit base, 32-33 credit pool",
         "LV-MU-5": "rating_contract.md:24-26 billing group, 27-29 tier counter, 96-99 parent column, 152-160 Rating",
         "LV-MU-7": "rating_contract.md:34-35 minimum, 113-115 commitments.xml, 179-189 True-up, 191-192 net",
         "LV-MU-1": "rating_contract.md:71-73 north `units` (a JSON integer); 82-84 text collectors (graded noise)",
         "LV-MU-3": "rating_contract.md:22-23 committed account (graded noise)"}
rows = ["# LEVERS: check -> lever map (harden round 2)", "",
        "Lever ids per check are the levers whose wrong reading, injected alone into solve.py, fails that",
        "check against the real tests (`cost_table.json`, `alone` rows). Other ids: COUPLING = region",
        "credit base; MUT = mutation or rejection path; EXIST = existence; NEG = cheating act (hard-coding shipped figures), grades no lever.", "",
        "| check | weight | levers |", "|---|---|---|"]
totals = {lv: 0 for lv in levers}
for name, w in weights.items():
    ids = [lv for lv in levers if name in failed[lv]]
    for lv in ids:
        totals[lv] += w
    ids += [lv + " (noise)" for lv in noise if name in failed[lv]]
    extra = []
    if name.startswith(("credit_", "true_up_", "region_", "segment_", "product_summary", "summary")):
        extra.append("COUPLING")
    if name in ("mutation_tier_scale", "mutation_small_commitment", "mutation_near_base_pool", "missing_collector", "control_mismatch", "determinism"):
        extra.append("MUT")
    if name == "transform_exists":
        extra.append("EXIST")
    if w < 0:
        extra.append("NEG")
    rows.append("| %s | %d | %s |" % (name, w, ", ".join(ids + extra) or "none"))
pos = sum(w for w in weights.values() if w > 0)
rows += ["", "| lever | rule written in | weight carried | share of %d |" % pos, "|---|---|---|---|"]
for lv in levers:
    rows.append("| %s | %s | %d | %.1f%% |" % (lv, where[lv], totals[lv], 100.0 * totals[lv] / pos))
for lv in noise:
    w = sum(weights[n] for n in failed[lv])
    rows.append("| %s (noise) | %s | %d | %.1f%% |" % (lv, where[lv], w, 100.0 * w / pos))
rows += ["", (HERE / "levers_detail.md").read_text().rstrip()]
rows += ["", "Checks: %d, positive weight %d, negative weight %d (test channel; one cheating act)." % (len(weights), pos, sum(w for w in weights.values() if w < 0))]
(HERE / "LEVERS.md").write_text("\n".join(rows) + "\n")
print("\n".join(rows[-8:]))
