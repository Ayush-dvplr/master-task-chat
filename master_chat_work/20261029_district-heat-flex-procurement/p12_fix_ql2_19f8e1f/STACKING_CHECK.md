# stacking_check: district-heat-flex-procurement

tests/test_output.py: 78 checks, positive total 261, negatives -13; judge: 12 criteria, positive 27, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped_only (artifact/shipped wording) | out, derive_report.py | produced | 0/0 |
| canonical_serialization_and_integer_units | 1 | shipped_only (format check, no hidden-input wording) | utf-8, out, int | expected, visible_root, _strict_load | 0/0 |
| report_keys_match_schema | 1 | shipped_only (artifact/shipped wording) | summary.json | expected, visible_root, _key_paths | 0/0 |
| report_arrays_in_schema_order | 1 | shipped_only (artifact/shipped wording) | policy_audit.json, summary.json, .json | expected, mine, _sorted_strictly | 0/0 |
| selection_match | 3 | shipped_only (artifact/shipped wording) | selection | _graded, family_passes | 0/0 |
| selection_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | selection | _graded, family_passes | 0/0 |
| intervals_match | 3 | shipped_only (artifact/shipped wording) | intervals | _graded, family_passes | 0/0 |
| intervals_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | intervals | _graded, family_passes | 0/0 |
| tie_decisions_match | 3 | isolated (default (rule/fixture/case check)) | passed, check raised, : | _note | 0/0 |
| tie_decisions_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | tie_decisions | _graded, family_passes | 0/0 |
| segment_rows_match | 3 | shipped_only (artifact/shipped wording) | segment_rows | _graded, family_passes | 0/0 |
| segment_rows_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_rows | _graded, family_passes | 0/0 |
| ledger_quality_match | 3 | shipped_only (artifact/shipped wording) | ledger_quality | _graded, family_passes | 0/0 |
| ledger_quality_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | ledger_quality | _graded, family_passes | 0/0 |
| region_totals_North_match | 3 | shipped_only (artifact/shipped wording) | region_totals_North | _graded, family_passes | 0/0 |
| region_totals_North_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_totals_North | _graded, family_passes | 0/0 |
| region_totals_South_match | 3 | shipped_only (artifact/shipped wording) | region_totals_South | _graded, family_passes | 0/0 |
| region_totals_South_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_totals_South | _graded, family_passes | 0/0 |
| region_totals_West_match | 3 | shipped_only (artifact/shipped wording) | region_totals_West | _graded, family_passes | 0/0 |
| region_totals_West_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_totals_West | _graded, family_passes | 0/0 |
| region_totals_East_match | 3 | shipped_only (artifact/shipped wording) | region_totals_East | _graded, family_passes | 0/0 |
| region_totals_East_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_totals_East | _graded, family_passes | 0/0 |
| segment_totals_match | 3 | shipped_only (artifact/shipped wording) | segment_totals | _graded, family_passes | 0/0 |
| segment_totals_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_totals | _graded, family_passes | 0/0 |
| summary_match | 3 | shipped_only (artifact/shipped wording) | summary | _graded, family_passes | 0/0 |
| summary_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary | _graded, family_passes | 0/0 |
| labels_match | 3 | shipped_only (artifact/shipped wording) | labels | _graded, family_passes | 0/0 |
| labels_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | labels | _graded, family_passes | 0/0 |
| quality_counts_match | 3 | shipped_only (artifact/shipped wording) | quality_counts | _graded, family_passes | 0/0 |
| quality_counts_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | quality_counts | _graded, family_passes | 0/0 |
| credit_rows_match | 3 | shipped_only (artifact/shipped wording) | credit_rows | _graded, family_passes | 0/0 |
| credit_rows_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | credit_rows | _graded, family_passes | 0/0 |
| segment_credit_rows_match | 3 | shipped_only (artifact/shipped wording) | segment_credit_rows | _graded, family_passes | 0/0 |
| segment_credit_rows_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_credit_rows | _graded, family_passes | 0/0 |
| funded_pool_match | 3 | shipped_only (artifact/shipped wording) | funded_pool | _graded, family_passes | 0/0 |
| funded_pool_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | funded_pool | _graded, family_passes | 0/0 |
| grants_match | 3 | shipped_only (artifact/shipped wording) | grants | _graded, family_passes | 0/0 |
| grants_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | grants | _graded, family_passes | 0/0 |
| grant_allocation_match | 3 | shipped_only (artifact/shipped wording) | grant_allocation | _graded, family_passes | 0/0 |
| grant_allocation_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | grant_allocation | _graded, family_passes | 0/0 |
| residual_match | 3 | shipped_only (artifact/shipped wording) | residual | _graded, family_passes | 0/0 |
| residual_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | residual | _graded, family_passes | 0/0 |
| cap_binding_match | 3 | shipped_only (artifact/shipped wording) | cap_binding | _graded, family_passes | 0/0 |
| cap_binding_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | cap_binding | _graded, family_passes | 0/0 |
| bid_cost_rows_match | 3 | shipped_only (artifact/shipped wording) | bid_cost_rows | _graded, family_passes | 0/0 |
| bid_cost_rows_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | bid_cost_rows | _graded, family_passes | 0/0 |
| compliance_rows_match | 3 | shipped_only (artifact/shipped wording) | compliance_rows | _graded, family_passes | 0/0 |
| compliance_rows_match_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | compliance_rows | _graded, family_passes | 0/0 |
| wide_0_portfolios_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | passed, check raised, : | _note | 0/0 |
| wide_0_selection_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | selection | _graded, wide_passes | 0/0 |
| wide_0_tie_decisions_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | tie_decisions | _graded, wide_passes | 0/0 |
| wide_0_intervals_match | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | intervals | _graded, wide_passes | 0/0 |
| wide_1_portfolios_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | passed, check raised, : | _note | 0/0 |
| wide_1_selection_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | selection | _graded, wide_passes | 0/0 |
| wide_1_tie_decisions_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | tie_decisions | _graded, wide_passes | 0/0 |
| wide_1_intervals_match | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | intervals | _graded, wide_passes | 0/0 |
| wide_2_portfolios_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | passed, check raised, : | _note | 0/0 |
| wide_2_selection_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | selection | _graded, wide_passes | 0/0 |
| wide_2_tie_decisions_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | tie_decisions | _graded, wide_passes | 0/0 |
| wide_2_intervals_match | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | intervals | _graded, wide_passes | 0/0 |
| wide_3_portfolios_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | passed, check raised, : | _note | 0/0 |
| wide_3_selection_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | selection | _graded, wide_passes | 0/0 |
| wide_3_tie_decisions_match | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | tie_decisions | _graded, wide_passes | 0/0 |
| wide_3_intervals_match | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | intervals | _graded, wide_passes | 0/0 |
| wide_0_bid_cost_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | bid_cost_rows | _graded, wide_passes | 0/0 |
| wide_0_compliance_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | compliance_rows | _graded, wide_passes | 0/0 |
| wide_1_bid_cost_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | bid_cost_rows | _graded, wide_passes | 0/0 |
| wide_1_compliance_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | compliance_rows | _graded, wide_passes | 0/0 |
| wide_2_bid_cost_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | bid_cost_rows | _graded, wide_passes | 0/0 |
| wide_2_compliance_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | compliance_rows | _graded, wide_passes | 0/0 |
| wide_3_bid_cost_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | bid_cost_rows | _graded, wide_passes | 0/0 |
| wide_3_compliance_rows_match | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | compliance_rows | _graded, wide_passes | 0/0 |
| segment_rate_adder_mutation | 3 | mutation (mutation in name or description lead) | mut_adder, mut_adder_moved | _graded, mutation_passes, _credit_family | 0/0 |
| allowance_ticks_mutation | 3 | mutation (mutation in name or description lead) | policy_audit.json | _graded, mutation_passes, _ledger_view | 0/0 |
| minimum_grant_mutation | 3 | mutation (mutation in name or description lead) | mut_grant, mut_grant_moved | _graded, mutation_passes, _grant_rows | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | summary.json | hidden_root, run_agent, expected | 0/2 |
| negative_reads_tests_or_reward_files | -5 | negative (weight < 0 or negative_ name) | /tests, /tests/, /logs/, judge.toml ... | _program_tree, _ran_cleanly | 0/1 |
| negative_external_dependency_or_network | -3 | negative (weight < 0 or negative_ name) | . | _program_tree | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): selection_match = selection_match_hard; intervals_match = intervals_match_hard; tie_decisions_match = wide_0_portfolios_feasible = wide_1_portfolios_feasible = wide_2_portfolios_feasible = wide_3_portfolios_feasible; segment_rows_match = segment_rows_match_hard; ledger_quality_match = ledger_quality_match_hard; region_totals_North_match = region_totals_North_match_hard; region_totals_South_match = region_totals_South_match_hard; region_totals_West_match = region_totals_West_match_hard; region_totals_East_match = region_totals_East_match_hard; segment_totals_match = segment_totals_match_hard; summary_match = summary_match_hard; labels_match = labels_match_hard; quality_counts_match = quality_counts_match_hard; credit_rows_match = credit_rows_match_hard; segment_credit_rows_match = segment_credit_rows_match_hard; funded_pool_match = funded_pool_match_hard; grants_match = grants_match_hard; grant_allocation_match = grant_allocation_match_hard; residual_match = residual_match_hard; cap_binding_match = cap_binding_match_hard; bid_cost_rows_match = bid_cost_rows_match_hard; compliance_rows_match = compliance_rows_match_hard; wide_0_selection_match = wide_1_selection_match = wide_2_selection_match = wide_3_selection_match; wide_0_tie_decisions_match = wide_1_tie_decisions_match = wide_2_tie_decisions_match = wide_3_tie_decisions_match; wide_0_intervals_match = wide_1_intervals_match = wide_2_intervals_match = wide_3_intervals_match; wide_0_bid_cost_rows_match = wide_1_bid_cost_rows_match = wide_2_bid_cost_rows_match = wide_3_bid_cost_rows_match; wide_0_compliance_rows_match = wide_1_compliance_rows_match = wide_2_compliance_rows_match = wide_3_compliance_rows_match

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| naming or reading grader files | negative_reads_tests_or_reward_files -5 | - | 5 | PASS |
| third-party or network import | negative_external_dependency_or_network -3 | - | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R7 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 182 (69.7%)
- isolated: 3 (1.1%)
- mutation: 9 (3.4%)
- shipped_only: 67 (25.7%)
- G3: hidden or mutated reruns 73.2% (>= 30%); isolated+mutation 4.6%, whole-document 0.0%, shipped-only 25.7% (info, no cap)

## 5. Caps and weights

- tests 78, criteria 12 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): artifact_set_exists_and_parses, canonical_serialization_and_integer_units, report_keys_match_schema, report_arrays_in_schema_order, wide_0_bid_cost_rows_match, wide_0_compliance_rows_match, wide_1_bid_cost_rows_match, wide_1_compliance_rows_match, wide_2_bid_cost_rows_match, wide_2_compliance_rows_match, wide_3_bid_cost_rows_match, wide_3_compliance_rows_match
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R1, R2, R3, R4, R12

## Verdict hints

- TS-26 duplicate candidates: 27 group(s): CHECK BY HAND
- AL-28 groups <= 5: PASS
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 73.2% PASS
- G3 isolated / shipped-only (info, no cap): 4.6% / 25.7%
- tests >= 10 (no cap): 78 PASS
- criteria >= 8 (no cap): 12 PASS
- judge mode batched: batched

## By-hand verdict (P12 fix ql2, session 19f8e1f, 29 Oct 2026)

- Changed since the last check (ql1, 66 checks, +237): 12 new checks, 24 points (master direction F4 / AL-2): `bid_cost_rows_match` and `compliance_rows_match` on the shipped extract (w3 each), their `_hard` twins on H1 (w5 each), and `wide_k_bid_cost_rows_match` / `wide_k_compliance_rows_match` on each of the four wide extracts (w1 each). Now 78 checks, +261 / -13. Judge unchanged (12 criteria, 27).
- `quality_counts_match` (shipped) no longer projects `unallocated_pool_count`; `residual_match` stays its only shipped owner (F3 / TS-26). Hard checks unchanged.
- TS-26 (27 candidate groups): each group is a `<family>_match` (shipped extract) and `<family>_match_hard` (hidden extract) pair, or a wide_k quartet on four different wide extracts. Each check reads a different extract, so one wrong figure is never paid twice for one input. The two new families project keys no other family projects (`bid_cost_cents`, `compliance_counts` of the event entries; checked against FAMILIES in tests/test_output.py). PASS.
- TS-20: the eight new weight-1 checks are value cross-checks the master set at w1 (TRIAGE `## Directions for P12`, F4); the core observable of each wide extract (selection) stays w5. Recorded, not changed.
- AL-28 penalty groups all <= 5 (unchanged). PASS.
- G3 hidden or mutated reruns 73.2% (>= 30%). PASS.
- Verdict: STACKING PASS.
