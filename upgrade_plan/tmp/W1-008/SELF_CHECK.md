W1-008 SELF CHECK

CONFIRMED
1. Score arithmetic, from reward-details.json. Tests: 80 of 85, the only loss is program_lead_drop_exact (weight 5), and all 8 negatives are at 0. Rubric: 34 of 103. Lost positive weight is 65. R2 (-1) and R31 (-3) fired.
2. The lost rubric ids and weights listed in CARD section 2 match the judge reasoning text.
3. The lead drop divergence was reproduced. I stubbed rewardkit, imported tests/test_output.py, minted LEAD_DROP_SEED 20302207, and ran the agent's conform.py from artifacts/app/out. slot_placement, conform_trace, playout_schedule, day_report and manifest differ. The other 20 artifacts are byte equal. In the diff, sl_02's trim is 0 for Opus and 558 in the reference, and sl_03's correction is CR_TRIM_SHORTFALL for Opus and CR_TRIM_FLEX in the reference.
4. Agent conform.py line 615 is: low = previous_fixed if previous_fixed is not None else index.
5. test_output.py line 4848 is: lo = prev_fixed if prev_fixed >= 0 else 0.
6. test_output.py line 1108 contains "every kind of correction happen on every instance".
7. spec_stage_v8_drift_correction.md lines 11-14 contain the backwards walk text. spec_stage_v7 line 24 contains "occupies no time and the slots after it move up". spec_stage_v7 line 32 contains "The first slot of the day is a fixed junction".
8. instruction.md lines 48, 53 and 76 contain the quoted phrases.
9. A local generate(SAMPLE_SEED) equals the shipped environment/data for every file except the two sqlite files (diff -rq). Every doc file is identical between the SAMPLE and EVAL seeds. Only data files differ.
10. junction_policy.yaml line 6 says "to the previous fixed junction inclusive". No shipped doc covers the case with no previous fixed junction (grep over md, txt, yaml and json).

UNCONFIRMED
1. I did not inspect the contents of the sqlite byte difference. It may be file metadata or real content.
2. I did not run the other graded seeds myself. Their pass status is taken from reward-details.json.
3. I did not open trajectory.json. The rubric evidence (counts but no instances) is taken from the judge reasoning text only.
4. Docs size of about 78 KB is from wc -c over md, txt and yaml files only.
