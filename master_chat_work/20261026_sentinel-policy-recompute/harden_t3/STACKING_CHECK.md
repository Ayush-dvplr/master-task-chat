# STACKING_CHECK sentinel-policy-recompute, test-hardening round t3 (3022cae)

Source: `stacking_check.py <BUNDLE>` (raw output in harden_t3/stacking_raw.txt), with each hint checked by hand against tests/test_output.py.

## (a) Tests
There are 34 checks. Positive weight totals 131 and negative weight totals -11. The seven new rows:

| test | w | observable | corpora | rules whose misread fails it |
|---|---|---|---|---|
| hidden_ledger_repair_reconciles_hard | 5 | ledger_repair.json feasibility: keys = mismatched tenants, null exactly where no repair, each list distinct spare seqs whose removal reconciles rows, max_records sum and ms timeout sum | rbig-a/b, runit-a/b | R45, R48, R49 (missing file, infeasible set, wrong null) |
| hidden_ledger_repair_cheapest_hard | 5 | whole ledger_repair.json | rbig-a/b | R46 cheapest total, R47 tie, R46 ms unit |
| hidden_ledger_repair_tie_hard | 5 | whole ledger_repair.json | rtie-a/b | R47 tie-break, R44 spare (Q2/Q5/D2) |
| hidden_ledger_repair_unit_hard | 5 | whole ledger_repair.json | runit-a/b | R46 cost in ms under the cutover |
| hidden_ledger_repair_spare_hard | 5 | whole ledger_repair.json | rspare-a/b | R44 spare rows (reissue, carry, reinstated source) |
| hidden_rare_repair_pairs_hard | 3 | whole ledger_repair.json | rall-a/b | R44, R46, R47 on the same tenants |
| hidden_fresh_state_corpora_hard | 5 | policy, curve and graded trace, whole and exact | fresh-q1..q5, fresh-utie, fresh-udecoy, fresh-d1, fresh-d2 | Q1-Q5, U, D1, D2 |

Feasibility (reconciles) is checked apart from optimality (cheapest/tie/unit/spare/rare); every R check reads its own corpora.

TS-26: the tool reports the same two groups as in t2 (region/cutover/admit/pool; rare_rule_pairs/unique_divisor_fit/rare_state_pairs). Each test in a group shares one helper but reads its own corpora, so the observables differ (same ruling as t2). None of the new tests is listed.

TS-13: hidden_ledger_repair_reconciles_hard has 6 asserts; they are the parts of one property (the written set is a valid repair, or null where none exists). The other new tests assert one property each: the corpora's documents are exact.

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

Negatives unchanged from t1; no negative grades a lever reading.

## (c) Weight shares
hidden_rows 118 (90.1%), mutation 9 (6.9%), isolated 3 (2.3%), shipped_only 1 (0.8%). G3 hidden or mutated reruns 96.9% (>= 30%). New R checks 28/131 = 21.4%; fresh check 5/131 = 3.8%. No weight-1 core check (weight-1: rerun and shipped artifacts, unchanged).

## (d) Measured cost (WORK/COST_TABLE.md t3)
All-but-one 90.08 (<= 92); blind r2 78.63; greedy, every k-subset, exact table and halves each 78.63 (lose 21.4%).

STACKING PASS (the AL-28 and TS-26 hints were corrected by hand as above)
