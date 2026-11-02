# stacking_check: hangar-check-replan

tests/test_output.py: 76 checks, positive total 344, negatives -6; judge: 20 criteria, positive 39, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| program_runs_on_shipped_data | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | - | - | 0/0 |
| program_stops_on_a_missing_input | 1 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_plan_rows | 5 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_data_quality | 1 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_group_reports | 5 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_settlement | 5 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| h1_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h1 | _holds, _check_hidden_rows | 0/0 |
| h1_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h1 | _holds, _check_hidden_group_totals | 0/0 |
| h1_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h1, checks | _holds, _check_hidden_settle | 0/0 |
| h1_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h1, groups | _holds, _check_hidden_settle | 0/0 |
| h1_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h1, summary | _holds, _check_hidden_settle | 0/0 |
| h2_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h2 | _holds, _check_hidden_rows | 0/0 |
| h2_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h2 | _holds, _check_hidden_group_totals | 0/0 |
| h2_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h2, checks | _holds, _check_hidden_settle | 0/0 |
| h2_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h2, groups | _holds, _check_hidden_settle | 0/0 |
| h2_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h2, summary | _holds, _check_hidden_settle | 0/0 |
| h3_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h3 | _holds, _check_hidden_rows | 0/0 |
| h3_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h3 | _holds, _check_hidden_group_totals | 0/0 |
| h3_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h3, checks | _holds, _check_hidden_settle | 0/0 |
| h3_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h3, groups | _holds, _check_hidden_settle | 0/0 |
| h3_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h3, summary | _holds, _check_hidden_settle | 0/0 |
| h4_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h4 | _holds, _check_hidden_rows | 0/0 |
| h4_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h4 | _holds, _check_hidden_group_totals | 0/0 |
| h4_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h4, checks | _holds, _check_hidden_settle | 0/0 |
| h4_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h4, groups | _holds, _check_hidden_settle | 0/0 |
| h4_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h4, summary | _holds, _check_hidden_settle | 0/0 |
| h5_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h5 | _holds, _check_hidden_rows | 0/0 |
| h5_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h5 | _holds, _check_hidden_group_totals | 0/0 |
| h5_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h5, checks | _holds, _check_hidden_settle | 0/0 |
| h5_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h5, groups | _holds, _check_hidden_settle | 0/0 |
| h5_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h5, summary | _holds, _check_hidden_settle | 0/0 |
| h6_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h6 | _holds, _check_hidden_rows | 0/0 |
| h6_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h6 | _holds, _check_hidden_group_totals | 0/0 |
| h6_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h6, checks | _holds, _check_hidden_settle | 0/0 |
| h6_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h6, groups | _holds, _check_hidden_settle | 0/0 |
| h6_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h6, summary | _holds, _check_hidden_settle | 0/0 |
| h1_base_and_segment_with_no_requests | 1 | isolated (default (rule/fixture/case check)) | h1 | _holds, _check_hidden_empty | 0/0 |
| h2_base_and_segment_with_no_requests | 1 | isolated (default (rule/fixture/case check)) | h2 | _holds, _check_hidden_empty | 0/0 |
| h1_data_quality | 3 | isolated (default (rule/fixture/case check)) | h1 | _holds, _check_hidden_data_quality | 0/0 |
| changed_allowance_grants | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| revised_availability_removed | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| h7_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h7, checks | _holds, _check_hidden_settle | 0/0 |
| h7_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h7, groups | _holds, _check_hidden_settle | 0/0 |
| h7_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h7, summary | _holds, _check_hidden_settle | 0/0 |
| h8_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h8, checks | _holds, _check_hidden_settle | 0/0 |
| h8_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h8, groups | _holds, _check_hidden_settle | 0/0 |
| h8_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h8, summary | _holds, _check_hidden_settle | 0/0 |
| h9_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h9, checks | _holds, _check_hidden_settle | 0/0 |
| h9_settlement_by_base_and_segment | 5 | isolated (default (rule/fixture/case check)) | h9, groups | _holds, _check_hidden_settle | 0/0 |
| h9_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h9, summary | _holds, _check_hidden_settle | 0/0 |
| h10_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h10 | _holds, _check_hidden_rows | 0/0 |
| h10_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h10 | _holds, _check_hidden_group_totals | 0/0 |
| h10_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h10, checks | _holds, _check_hidden_settle | 0/0 |
| h10_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h10, summary | _holds, _check_hidden_settle | 0/0 |
| h11_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h11 | _holds, _check_hidden_rows | 0/0 |
| h11_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h11 | _holds, _check_hidden_group_totals | 0/0 |
| h11_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h11, checks | _holds, _check_hidden_settle | 0/0 |
| h11_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h11, summary | _holds, _check_hidden_settle | 0/0 |
| h12_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h12 | _holds, _check_hidden_rows | 0/0 |
| h12_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h12 | _holds, _check_hidden_group_totals | 0/0 |
| h12_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h12, checks | _holds, _check_hidden_settle | 0/0 |
| h12_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h12, summary | _holds, _check_hidden_settle | 0/0 |
| h13_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h13 | _holds, _check_hidden_rows | 0/0 |
| h13_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h13 | _holds, _check_hidden_group_totals | 0/0 |
| h13_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h13, checks | _holds, _check_hidden_settle | 0/0 |
| h13_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h13, summary | _holds, _check_hidden_settle | 0/0 |
| h14_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h14 | _holds, _check_hidden_rows | 0/0 |
| h14_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h14 | _holds, _check_hidden_group_totals | 0/0 |
| h14_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h14, checks | _holds, _check_hidden_settle | 0/0 |
| h14_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h14, summary | _holds, _check_hidden_settle | 0/0 |
| h15_plan_rows | 5 | isolated (default (rule/fixture/case check)) | h15 | _holds, _check_hidden_rows | 0/0 |
| h15_plan_group_totals | 5 | isolated (default (rule/fixture/case check)) | h15 | _holds, _check_hidden_group_totals | 0/0 |
| h15_settlement_per_check | 5 | isolated (default (rule/fixture/case check)) | h15, checks | _holds, _check_hidden_settle | 0/0 |
| h15_settlement_summary | 5 | isolated (default (rule/fixture/case check)) | h15, summary | _holds, _check_hidden_settle | 0/0 |
| negative_hardcoded_sample_answers | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_writes_outside_out_dir | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): program_runs_on_shipped_data = program_stops_on_a_missing_input = shipped_plan_rows = shipped_data_quality = shipped_group_reports = shipped_settlement = changed_allowance_grants = revised_availability_removed

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -3 | R18 -5, R19 -5, R20 -5 | 18 | FAIL |
| UNMATCHED act (name it by hand) | negative_writes_outside_out_dir -3 | R16 -5, R17 -3 | 11 | FAIL |
| naming or reading grader files | - | R14 -5 | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R15 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 1 (0.3%)
- isolated: 320 (93.0%)
- mutation: 0 (0.0%)
- shipped_only: 23 (6.7%)
- G3: hidden or mutated reruns 0.3% (>= 30%); isolated+mutation 93.0%, whole-document 0.0%, shipped-only 6.7% (info, no cap)

## 5. Caps and weights

- tests 76, criteria 20 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): program_runs_on_shipped_data, program_stops_on_a_missing_input, shipped_data_quality, h1_base_and_segment_with_no_requests, h2_base_and_segment_with_no_requests
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 1 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 0.3% FAIL
- G3 isolated / shipped-only (info, no cap): 93.0% / 6.7%
- tests >= 10 (no cap): 76 PASS
- criteria >= 8 (no cap): 20 PASS
- judge mode batched: batched

## Manual Resolution of Static Hints

The classifier groups literal owner names mentioned in stand-down clauses as if they were additional charges. The explicit descriptions control; these are exclusions, not positive triggers.

| Observable act | Deterministic owner | Judged owner | Maximum same-act penalty |
|---|---|---|---:|
| Successful clean hidden run writes all nine shipped answers despite differing expected answers | negative_hardcoded_sample_answers | R18-R20 explicitly stand down; R14 never inferred from replay | 3 |
| Run writes outside OUT_DIR or mutates its data tree | negative_writes_outside_out_dir; replay excludes that run | R18-R20 stand down | 3 |
| Agent opens a grader path in an issued shell/editor command | None | R14; R18-R20 stand down | 5 |
| Delivered nonstdlib import, outside other owners | None | R18; R19 stands down | 5 |
| Other executed program I/O outside declared paths | None | R19, after exclusions | 5 |
| Task-specific online solution fetch | None | R20; R18/R19 stand down | 5 |
| Unsupported pass claim / figure differing from file / overstated check coverage | None | R15 / R16 / R17 respectively, distinct final-answer observables | 3 / 5 / 3 |

R14 requires evidence of an actual issued open, never source tokens or replay. A separately observed grader open and a separately observed later replay are distinct acts; neither check supplies evidence for the other. JD-5: each new criterion has one act; evidence/exclusions/stand-down sentences narrow it. JD-8: no positive judge criterion duplicates the new replay property. JD-14: judge negatives 31 <= positives 39; test negatives 6 <= positives 344. JD-15/16: delivered import is state_change, executed I/O/fetch are trajectory, all instruction following. AL-28: no same-act sum exceeds 5.

G3 classifier misses _case-based reruns: actual hidden/changed positive points are 326/344 = 94.7674%; h7-h15 lever 165/344 = 47.9651%. No hidden folder or positive weight changed in resumption. TS-26: replay is a negative substitution observation; positive mismatches score correctness and do not create a second negative charge.

## Lessons for the master
Literal mentions inside stand-down clauses are exclusions, not additional penalty triggers. | no change: retain manual act matrix beside classifier hints
