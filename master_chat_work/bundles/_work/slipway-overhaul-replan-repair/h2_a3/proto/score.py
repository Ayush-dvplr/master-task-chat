"""Score diag2 logs against the positive checks of a test_output.py.

usage: python3 -B score.py <test_output.py> <diag2 log>...
Each shipped_* check reads the SAMPLE_SEED run, package_* checks read their
own seed run, crosswalk checks read the held-out spec runs. Negatives are
not modelled (reported separately).
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("T", sys.argv[1])
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
text = Path(sys.argv[1]).read_text()
weights = {m.group(1): int(m.group(2)) for m in
           re.finditer(r"^criteria\.(\w+)\(weight=(-?\d+)\)", text, re.M)}

SHIPPED = {
    "shipped_identifier_layer_exact": T.IDENTIFIER_GROUP,
    "shipped_graph_layer_exact": T.GRAPH_GROUP,
    "shipped_closure_and_demand_exact": T.CLOSURE_GROUP,
    "shipped_rule_and_charge_exact": T.CHARGE_GROUP,
    "shipped_baseline_optimum_exact": T.BASELINE_GROUP,
    "shipped_amendment_classification_exact": T.CLASSIFICATION_GROUP,
    "shipped_invalidation_sets_exact": T.INVALIDATION_GROUP,
    "shipped_work_ledger_exact": T.LEDGER_GROUP,
    "shipped_store_summary_exact": T.STORE_GROUP,
    "shipped_final_optimum_exact": T.FINAL_GROUP,
    "shipped_audit_documents_exact": T.AUDIT_GROUP,
}
PACKAGE = {
    "package_eval_state_exact": ("EVAL_SEED", T.STATE_FAMILY),
    "package_eval_cascade_exact": ("EVAL_SEED", T.CASCADE_FAMILY),
    "package_challenge_state_exact": ("CHALLENGE_SEED", T.STATE_FAMILY),
    "package_challenge_cascade_exact": ("CHALLENGE_SEED", T.CASCADE_FAMILY),
    "package_probe_publication_exact": ("PROBE_SEED", T.PUBLICATION_FAMILY),
}


def spec_of(round_):
    return "%d:%s" % (round_[0], ",".join(round_[1]))


if hasattr(T, "HELD_GROUPS"):
    PACKAGE.update({
        "package_crosswalk_groups_state_exact": (spec_of(T.HELD_GROUPS), T.STATE_FAMILY),
        "package_crosswalk_rules_state_exact": (spec_of(T.HELD_RULES), T.STATE_FAMILY),
        "package_crosswalk_amendments_cascade_exact": (spec_of(T.HELD_AMENDMENTS), T.CASCADE_FAMILY),
        "package_crosswalk_amendments_state_exact": (spec_of(T.HELD_AMENDMENTS), T.STATE_FAMILY),
        "package_crosswalk_every_state_exact": (spec_of(T.HELD_EVERY), T.STATE_FAMILY + T.CASCADE_FAMILY),
        "package_crosswalk_every_publication_exact": (spec_of(getattr(T, "HELD_PUBLISHED", T.HELD_EVERY)), T.PUBLICATION_FAMILY),
    })
if hasattr(T, "HELD_EVERY_CASCADE"):
    PACKAGE["package_crosswalk_every_state_exact"] = (spec_of(T.HELD_EVERY), T.STATE_FAMILY)
    PACKAGE.update({
        "package_crosswalk_groups_cascade_exact": (spec_of(T.HELD_GROUPS_CASCADE), T.CASCADE_FAMILY),
        "package_crosswalk_groups_publication_exact": (spec_of(T.HELD_GROUPS_PUBLISHED), T.PUBLICATION_FAMILY),
        "package_crosswalk_rules_cascade_exact": (spec_of(T.HELD_RULES_CASCADE), T.CASCADE_FAMILY),
        "package_crosswalk_rules_publication_exact": (spec_of(T.HELD_RULES_PUBLISHED), T.PUBLICATION_FAMILY),
        "package_crosswalk_amendments_publication_exact": (spec_of(T.HELD_AMENDMENTS_PUBLISHED), T.PUBLICATION_FAMILY),
        "package_crosswalk_every_cascade_exact": (spec_of(T.HELD_EVERY_CASCADE), T.CASCADE_FAMILY),
    })
LEVER = {k for k in PACKAGE if "crosswalk" in k}

for log in sys.argv[2:]:
    runs = {}
    for line in Path(log).read_text().splitlines():
        key, _, body = line.partition(" ")
        if body.startswith("{"):
            runs[key] = json.loads(body)

    def ok(seed, family):
        rec = runs.get(seed)
        if rec is None or rec["rc"] != 0:
            return False
        return not (set(rec["wrong"]) & set(family))

    earned = total = lever = lever_total = 0
    lost = []
    for name, w in weights.items():
        if w <= 0:
            continue
        total += w
        if name in SHIPPED:
            good = ok("SAMPLE_SEED", SHIPPED[name])
        elif name in PACKAGE:
            good = ok(*PACKAGE[name])
        else:
            good = runs.get("SAMPLE_SEED", {}).get("rc") == 0
        if name in LEVER:
            lever_total += w
            lever += w if good else 0
        if good:
            earned += w
        else:
            lost.append("%s(%d)" % (name, w))
    print("%s tests %d/%d = %.2f%% lever %d/%d share %.1f%% lost %s" % (
        Path(log).stem, earned, total, 100.0 * earned / total, lever,
        lever_total, 100.0 * lever_total / total, " ".join(lost) or "none"))
print("ALL_DONE")
