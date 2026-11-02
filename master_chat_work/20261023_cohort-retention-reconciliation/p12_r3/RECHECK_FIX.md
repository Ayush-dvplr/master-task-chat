# P12 r3 recheck and fix: cohort-retention-reconciliation (board cac63fd)

QC report: QC_2026-10-22/qc_report/cohort-retention-reconciliation/v4.md (FAIL, 2 fails, 3 minors). Live kit Input_Bundle_QC HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e (same kit as v4).
Levers (WORK/LEVERS.md): CR2-L1 green control wrong answer, CR2-L2 identifiers vs strict fields, CR2-L3 refundable balance ledger, CR2-L4 segment weight override.
Test count 24 checks (positive 71, negatives -23) and judge 8 criteria unchanged; reward.toml unchanged (0.5/71).

## Findings

| ID | Label | Rule quote (live kit) | Evidence quote (bundle) | Decision | Effect per lever (L1/L2/L3/L4) | Compensation | Files changed |
|---|---|---|---|---|---|---|---|
| DS-22 | REAL (fail) | 02_Data_Solution_QC.md:78 "a digest comparison proves `solve.py` was not edited after the fact" | TRUTH.md:231 (before) `solve_py_sha256: f1506cbf...  # sha256 of solution/solve.py, 551 lines`; `shasum -a 256 solution/solve.py` -> `bf91bc6f53941b282e4c208d227d5884b7ae0bc8d877a120c9778ea658cbdf13`; `wc -l` -> `552 solution/solve.py` | FIX: digest and line count recomputed LAST (solve.py not edited this round); TRUTH.md:242 now `bf91bc6f...cbdf13  # sha256 of solution/solve.py, 552 lines` | none/none/none/none | none | solution/TRUTH.md |
| AL-27 (a) cleaned order type tie-break | REAL (fail) | 05_Alignment_Integrity_QC.md:27 "which graded input would come out differently if the solver broke exactly this rule? - no such input means the rule is ungraded" | schema.md:88 "ordered by date, then resolved account, then event type."; only same-day pair was drained later (test_output.py:572-576) | FIX: side account with an undrained same-day purchase then refund, purchase first in file; refund must meet an empty balance | L1 compensated (see trap), L2/L3/L4 none (measured) | L1, see (d) | tests/test_output.py |
| AL-27 (b) zero-revenue cohort | REAL (fail) | same | schema.md:123-124 "Every cohort appears in every revenue map, with 0 when it has no revenue events." | FIX: side account qualifying in the last period, no revenue rows | same | same | tests/test_output.py |
| AL-27 (c) offset_zero_is_full false | REAL (fail) | same | schema.md:132-134; all hidden studies drew true | FIX: `flag = rng.between(0, 3) != 0 and seed != HIDDEN_SEEDS[0]` (draw kept) | same | same | tests/test_output.py |
| AL-27 (d) control value residual | REAL (fail) | same | schema.md:134-137; residual 0 in every hidden study | FIX: every hidden manifest records events value_cents_sum as the strictly parsed sum, so the note's definition gives residual minus the padded values | L1: first try easier (L1a 11 -> 6), compensated in L1 family -> 11 | value-sum fault equals strict-parse sum, so the unstripped reading stays green and wrong | tests/test_output.py |
| AL-27 (e) zero-denominator rate "0" | UNSURE | same | schema.md:15-16 "A rate whose denominator would be zero is written as `\"0\"`."; only weighted_share can reach 0 (retention/survival divide by cohort size, never 0 by schema.md:96) | UNSURE, PL question: triggering needs a study with zero weighted revenue, which removes weighted grading (L4) from that study; no change made | none | n/a | none |
| AL-27 (f) calendar order vs name order | REAL (fail) | same | schema.md:100-102, :190-193; names `f"{year}-{tag}{k+1}"` sort like the calendar | FIX: period numbers start at 7..9 (side stream) so names cross 9 -> 10 | same as (a) | same | tests/test_output.py |
| AL-27 (g) control_mismatches sort | REAL (fail) | same | schema.md:168 "the sorted list"; manifest written with sort_keys | FIX: three faulty figures in three files, manifest written mid, low, high order without sort_keys | same | same | tests/test_output.py |
| IN-16 | REAL (minor, hidden rule) | 01_Instruction_QC.md:46 "Third, nothing in any file the agent can read picks between them" | schema.md:40-41 merge tie on equal effective_from open; reference `_in_force` takes the later file row | FIX (hidden rule, suggestion test NO): schema.md:41 now "; when two such rows share that `effective_from`, the later row in the file wins." (same words as audit_policy.md:13-14); hidden tie row placed before the winning ghost row | none/none/none/none | none | environment/data/schema.md, tests/test_output.py (re-embedded `_SHIPPED_DATA`) |
| TS-29 | REAL (minor) | 03_Tests_QC.md:55 "Each check returns a bool, never a number, None or a string."; fail list :135 only raising checks | test_output.py:979 `return hits / len(HIDDEN_SEEDS)` | KEEP: suggestion test NO (not easier) but not cheap: one bool per seed adds 18 checks (24 -> 42, over the 35 WARN line) and an all-seeds bool changes the grading; deviation already stated in TRUTH.md Verification | none | n/a | none |
| TS-13 | REAL (minor) | 03_Tests_QC.md:44 "A test asserting two unrelated properties hides which one failed and skews the weight" | test_output.py:1032-1036 `_written_study` asserts cohorts.json equality | KEEP: suggestion test YES: replacing the gate with a key-set check pays 6/71 for format and rerun to programs with no cohort right (lowers the floor of every lever reading); QC_RULINGS TS-13 lesson | none | n/a | none |

AL-27 measurement: wrong-reading flags are named mutants of the reference `derive()` in OUT gates/al27/mut.py (bundle has no `reference()` function; no wrong-reading code ships in tests). Score of 71, before -> after:

| Rule | Mutant | Before | After | Checks lost after |
|---|---|---|---|---|
| (a) | clean_order_date_only | 71 | 56 | hidden_revenue, hidden_segments, hidden_per_cohort_documents |
| (a) | clean_order_type_desc | 71 | 56 | same |
| (b) | zero_revenue_cohort_dropped | 71 | 66 | hidden_revenue |
| (c) | offset_zero_always | 71 | 70 | hidden_reconciliation (1 of 3 seeds) |
| (c) | offset_zero_flag_ignored | 68 | 69 | hidden_reconciliation |
| (d) | control_zero | 71 | 68 | hidden_reconciliation |
| (d) | control_sign_flipped | 71 | 68 | hidden_reconciliation |
| (e) | rate_zero_denominator_text | 71 | 71 | none (UNSURE) |
| (f) | calendar_lexical_order | 71 | 45 | retention, survival, data_quality, per_cohort, serialization, rerun |
| (f) | per_cohort_lexical | n/a | 60 | hidden_per_cohort_documents |
| (g) | mismatches_manifest_order | 71 | 66 | hidden_data_quality |
| (g) | mismatches_unsorted_reversed | 66 | 66 | hidden_data_quality |
| IN-16 | merge_tie_earlier_row | 71 | 36.667 | cohorts, retention, survival, revenue, segments, data_quality, per_cohort, serialization, rerun |
| control | baseline (reference) | 71 | 71 | none |

All new rows come from a second seeded stream (`side = Rng(seed ^ 0x6A09E667F3BCC908)`) added after the main draws, so every earlier fixture and the trap separation stay as they were.

## Gates

- xref_check before: 33 entries, 0 findings; after: 33 entries, 0 findings.
- QC scripts (live kit 71a653b): structure_qc 17 pass 0 warn 0 fail; instruction_qc 5/0/0; tests_qc 37/0/0; judge_qc 19/0/0. Manual: no TODO/FIXME/XXX/PLACEHOLDER, no CR, test_output.py parses. 0 FAIL.
- Common rule 6 after the schema.md edit: `_SHIPPED_DATA` re-embedded (14 files); reward.toml test weight 0.5/71 unchanged; TRUTH.md has no data digests, only solve.sh and solve.py digests.
- Stacking: PASS (OUT/STACKING_CHECK.md): whole-doc 60.6%, isolated+mutation 29.6%, shipped-only 1.4%, caps PASS.
- Reflex (a2 derive_report.py, tests channel, local scorer): before 0.0563, after 0.0563.
- Docker (tests only, exe_copy plain and --owner-only): oracle x3 = 1.000, 1.000, 1.000; owner-only x1 = 1.000; nop x1 = 0.000 (warm image, one nohup chain ending ALL_DONE, logs /tmp/opencode-logs/crr-r3-20261023T123628-d88e/chain.log, jobs /tmp/harbor-jobs-r3/crr-20261023T123628-d88e).

## Trap survival

Loss of the 71 positive points, current tests before any fix (WORK/trap) vs fixed tests and data. Separating cases kept = no check that failed a reading before passes it after.

| Reading | Before loss | After loss | Ratio | Separating cases kept | Verdict |
|---|---|---|---|---|---|
| L1a | 11 | 11 | 1.000 | y | PASS |
| L1b | 8 | 8 | 1.000 | y | PASS |
| L2none | 55 | 54 | 0.982 | y | PASS |
| L2a | 53 | 53 | 1.000 | y | PASS |
| L2b | 38 | 38 | 1.000 | y | PASS |
| L2c | 53 | 52 | 0.981 | y | PASS |
| L3a | 18 | 18 | 1.000 | y | PASS |
| L3b | 18 | 18 | 1.000 | y | PASS |
| L4a | 21 | 21 | 1.000 | y | PASS |
| L4b | 16.333 | 16.333 | 1.000 | y | PASS |
| reflex a2 | score 0.0563 | score 0.0563 | n/a | n/a | PASS (<= 0.20, <= before + 0.05) |

First try failed L1a (11 -> 6, ratio 0.55): the forced value-sum fault turned the unstripped reading's control red too. Compensation in the L1 family (try 1 of 2): the recorded value sum equals the strictly parsed sum. L2none and L2c each regained 1 of hidden_reconciliation's 3 seed shares in the study where offset_zero_is_full is now false; their other failing checks still fail.

## QC_RULINGS rows

- IN-15: rule = every graded rule of engagement is stated; our design = stdlib, no network, DATA_DIR only at instruction.md:5; QC verdict PASS (v4:109); our label agree; reason: no rule of engagement changed.
- IN-16: rule = no significant ambiguity in anything graded; our design = merge tie now stated in schema.md:41 and graded by a hidden tie row; QC verdict MINOR (v4:113, earlier PASS v2:120 "REUSE with care"); our label REAL, fixed; reason: the tie was open in schema.md and only safe while ungraded, now settled in the same words as the plan tie.
- TS-13: rule = one property per test; our design = cohorts gate shared by serialization and rerun; QC verdict MINOR (v4:166, still open since v3); our label REAL, KEEP; reason: removing the gate pays 6/71 to programs with no cohort right.
- TS-19: rule = every promise graded and every graded behaviour learnable; our design = reference derive follows schema.md rule for rule; QC verdict PASS (v4:190); our label agree; reason: the six newly triggered rules were already stated, and the merge tie is now stated before it is graded.
- TS-20: rule = weights map to importance; our design = 5 core, 3 sub-goal, 1 presence; QC verdict PASS (v4:191); our label agree; reason: no weight changed.
- TS-26: rule = no intra-test double payment; our design = fixture pairs read different inputs; QC verdict PASS (v4:193); our label agree; reason: new rows feed existing hidden checks only.
- AL-28: rule = no penalty stacking; our design = negatives on distinct acts; QC verdict PASS (v4:275); our label agree; reason: negatives unchanged.
- JD-7: rule = the oracle satisfies every criterion; our design = solve.py without except clauses; QC verdict FIXED (v4:444); our label agree; reason: solve.py not edited this round.
- JD-15: rule = what a criterion may require; our design = R1-R5 conduct, R6 code shape, R7 verify, R8 honesty; QC verdict PASS (v4:225); our label agree; reason: no criterion changed.

## Lessons for the master

- New hidden rows drawn from a second seeded stream keep every earlier fixture and trap separation unchanged; recommend it for any AL-27 fix.
- Forcing a fault can make a wrong reading's control red too, so it stops being separated (L1a 11 -> 6). Set the fault so it disagrees only under the correct definition.
- A "reversed" mutant passes against a reverse-sorted manifest; to test a sort rule, write the input in an order that is neither sorted nor reverse-sorted.
- Fingerprint files in knowledge/fingerprints were made at kit 3fb1650b, but the live kit is at 71a653b; refresh them.
- Zero-denominator sentences that only one figure can reach (weighted share) cannot be graded without removing that figure's grading; avoid writing them.
