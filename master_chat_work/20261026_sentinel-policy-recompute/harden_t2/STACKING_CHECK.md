# STACKING_CHECK sentinel-policy-recompute, test-hardening round t2 (4a82a12)

Source: `stacking_check.py <BUNDLE>` (raw output kept in WORK/t2_stacking_raw.txt), with each hint checked by hand against tests/test_output.py.

## (a) Tests
There are 27 checks. Positive weight totals 98 and negative weight totals -11. The tool's table gives one row per test; the four new rows:

| test | w | observable | corpora | rules whose misread fails it |
|---|---|---|---|---|
| hidden_unique_divisor_fit_hard | 5 | policy_resolved, threshold_curve and graded dependency_trace on its own corpora, whole and exact | utie-a, utie-b, udecoy-a, udecoy-b | U (divisor fixed by standing curve reports; unresolved verdict) |
| hidden_curve_reset_hard | 5 | same three documents | d1-a, d1-b | D1 (a reset withdraws the curve reports at a lower seq) |
| hidden_reinstated_chain_hard | 5 | same three documents | d2-a, d2-b | D2 (a reinstated row adds the deltas of the last earlier active row of its id) |
| hidden_rare_state_pairs_hard | 3 | same three documents | combo2-a, combo2-b | U, D1, D2 and Q1-Q5 on the same records |

TS-26: the tool reports two groups of duplicate candidates: region/cutover/admit/pool, and rare_rule_pairs/unique_divisor_fit/rare_state_pairs. All tests in a group share one helper, but each reads its own corpora, so they are different observables. The same pattern passed QC before (QC_RULINGS district-heat v3:185, cohort v2:183). Each generated corpus family is accepted only when the readings of other rules leave its documents unchanged (G1a ownership, `accepted()`), so no slip is paid twice inside the owned families.

TS-13: each new test asserts one property: its corpora's documents are exact.

## (b) AL-28 groups (corrected by hand)
The tool's UNMATCHED row (sum 14) merges four separate acts. Split by hand, every act sums to 5 or less:

| act | members | sum abs w |
|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 |
| host or credential material in artifacts | negative_url_or_secret_in_artifacts -3 | 3 |
| claiming a check passed with no run | judge r13 -3 | 3 |
| stating a figure that differs from the delivered file | judge r14 -5 | 5 |
| overstating a check's size | judge r15 -3 | 3 |

The negatives are unchanged from t1, and no negative grades a lever reading.

## (c) Shares (G3)
- Hidden or mutated reruns make up 94/98 = 95.9% of positive weight.
- New t2 checks: 18/98 = 18.4%. Q1-Q5 owned checks plus rare_rule_pairs: 28/98. Older N families: 20/98. Coupling whole-document checks: 15/98. Mutation: 9/98. Isolated and rebuild: 6/98. Shipped-only: 1/98.
- Tests 27, judge criteria 15. Weight 1 is used only on the rerun check and the shipped check, neither of which is core.

## (d) Cost table (G10, measured locally on the tests channel; WORK/COST_TABLE.md, WORK/t2_levers3.log)

| program | tests |
|---|---|
| Q1..Q5 wrong alone (each) | 87/98 = 88.78 |
| U: iteration_divisor kept / first fit / first report | 90/98 = 91.84 each |
| D1: every curve counts / only the first reset counts | 90/98 = 91.84 each |
| D2: reinstated not drawn / own deltas / first active | 90/98 = 91.84 each |
| first write (skips every branch the shipped data never fires) | 57/98 = 58.16 |
| blind round-1 program (WORK/blind_r1) | 85/98 = 86.73, no crash |

Each new lever alone loses 8.2% (target 5-12). The best all-but-one score is 91.84 (target 92 or less). The blind round-1 program scores 86.7 (target 70-90).

## (e) Rule coverage and trace
- RULE_COVERAGE: every mutant fails at least one check (t2 rows: 0.9184 each). Rules left uncovered: 0.
- RULE_TRACE rows R38-R43 cover the new sentences. Every generator branch has a sentence.

## (f) Evidence and uniqueness
- EVIDENCE_MAP has t2 rows for the unresolved verdict, the never-generated cases (no fit at all; reinstated with no earlier active row) and the D1/D2 order.
- UNIQUENESS.md lists the exact fit set for every new corpus.

## (g) BRANCH_FIRE
- Shipped data fires U, D1 and D2 0 times. The 28 older corpora fire none of them, and their documents are unchanged.
- Every new owned corpus fires its own rule at least twice, and combo2 fires every rule at least twice (WORK/BRANCH_FIRE.md).

## (h) Judge
The d0f1870 judge is kept exactly: 15 criteria, 9 probes. No probe was added, because solve.sh's self-check runs on shipped copies, where U, D1 and D2 never fire.

## (i) Invocation
Unchanged: the tests run the delivered `cli.py resolve --data-dir <corpus> --out <dir>`, which is the README invocation the instruction points to.

STACKING PASS (the AL-28 and TS-26 hints were corrected by hand as above)

## Lessons for the master
- stacking_check lumps every unnamed negative into one UNMATCHED act and flags shared-helper tests as TS-26 duplicates; both need a hand split every round | template_change: no change: the tool is known to misread gated designs (LEVER_RULES section 5)
