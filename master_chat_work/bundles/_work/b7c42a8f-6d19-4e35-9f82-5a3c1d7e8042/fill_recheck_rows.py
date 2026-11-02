"""Fill the Findings-row placeholders of OUT/RECHECK_FIX.md (dbe00fc)."""
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
t = p.read_text()
rep = {
    "ROW_FIX_AL27": (
        "(gen_extracts.py v5: extract A's claim_adjustment_log.log zeroes alae on every `layer=retention` line "
        "and pins an explicit `layer=retention alae=0` line for each unlogged shared-event claim, so it settles "
        "`excess_only` only; extract B's treasury_curve_observations.log carries pv_factor=(1+curve[10]/100)^-tenor, "
        "so it settles `flat_10y` only; shipped corpus bytes unchanged; unique fit by WORK/unique_fit.py "
        "(runs/unique_fit_v6/out.jsonl); solve.py settle_alae_convention returns fraction None under excess_only and "
        "build_ledger defaults unlogged ALAE to 0 when no fraction; `_EXPECTED_BLOB` and A/B blobs re-sealed "
        "(runs/seal_v5, G7_v6_tests_diff.txt hunks 23c23, 26,27c26,27 only). Bite: hard-coded pro_rata 49/64 "
        "(loses hidden_extract_outcomes_exact 3, methodology_audit_remaining_sections_exact 3, "
        "program_reproduces_unseen_extract_alpha 5, row_order_permutation_changes_nothing 3, "
        "summary_and_treaty_values_exact 1 = 15); hard-coded duration_matched 61/64 (loses "
        "methodology_audit_remaining_sections_exact 3))"
    ),
    "ROW_EFFECT_AL27": "L1 harder (loss 39 -> 42); L2-L7 none (21, 41, 45, 19, 22, 0 unchanged)",
    "ROW_FILES_AL27": (
        "tests/test_output.py (blobs only), solution/solve.py, solution/TRUTH.md (by script); WORK gen_extracts.py, "
        "unique_fit.py, RULE_COVERAGE.md, QC_DEFENCE.md D14/D15, LEVERS.md"
    ),
    "ROW_FIX_JD5": (
        "(R25 now the `settlement.alae_convention` string only, new R36 the `settlement.discount_curve` string; "
        "R34 now `claim_adjustment_log.log` only, new R37 `treasury_curve_observations.log`; all weight 1, "
        "important, user_facing_message; judge positive 66 -> 68; reward.toml judge 0.007575757575757576 -> "
        "0.007352941176470588 = 0.5/68)"
    ),
    "ROW_EFFECT_JD5": "none on L1-L7 (judge only, no lever is judged by these criteria)",
}
for k, v in rep.items():
    assert t.count(k) == 1, k
    t = t.replace(k, v)
p.write_text(t)
print("filled", len(rep))
