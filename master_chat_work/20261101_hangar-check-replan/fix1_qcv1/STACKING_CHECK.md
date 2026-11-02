# STACKING_CHECK, hangar-check-replan (fix1, after QC v1 fixes)

Tool: `master_chat_tasks/tools/stacking_check.py BUNDLE --classes <hidden checks = hidden_rows; changed_allowance_grants, revised_availability_removed, program_stops_on_a_missing_input = mutation; program_runs_on_shipped_data = shipped_only>` (raw output appended below). Each hint row was confirmed by reading `tests/test_output.py`.

## (a) TS-26 duplicates (same observable and same logic): none
The tool groups `program_runs_on_shipped_data`, `program_stops_on_a_missing_input`, `shipped_plan_rows`, `shipped_data_quality`, `shipped_group_reports`, `shipped_settlement`, `changed_allowance_grants`, `revised_availability_removed` only because none has a literal in its call. By hand they read different observables:
| check | observable (tests/test_output.py) |
|---|---|
| program_runs_on_shipped_data | run exit 0 and the nine files parse (:1225-1230) |
| program_stops_on_a_missing_input | exit code and stderr of a run with fleet_register.csv removed (:1243-1257) |
| shipped_plan_rows | policy_audit.json plan fields of every request (:1233-1235) |
| shipped_data_quality | data_quality.json rejected rows and counts (:1238-1240) |
| shipped_group_reports | region/segment/summary plan fields |
| shipped_settlement | settlement fields of all files |
| changed_allowance_grants | settlement fields on the grant-rewritten copy |
| revised_availability_removed | every field on the copy with the revised availability table emptied |
Likewise `hN_plan_rows` (`_view_plan(c, s, False, True)`, policy_audit rows) and `hN_plan_group_totals` (`_view_plan(c, s, True, False)`, region/segment/summary non-settlement fields) read disjoint views (:1189, :1193).

## (b) TS-13 multi-assert: none
Each check is one comparison of one field view (first differing path reported). The two v1 TS-13 hits are split (shipped rows vs data_quality; hidden rows vs group totals).

## (c) AL-28 per act (tests + judge, limit 5): PASS by hand
| act | tests | judge | sum |
|---|---|---|---|
| hardcoding the shipped answers into the program | negative_hardcoded_sample_answers -5 | none | 5 |
| program source names check files (`/tests/`, test_output, judge.toml, rewardkit) | negative_reads_check_files -5 | none | 5 |
| program run leaves files outside OUT_DIR or changes the data folder | negative_writes_outside_out_dir -3 | none | 3 |
| agent opens `/tests/` or `/logs/verifier` in its own shell or editor command | none | R15 -5 | 5 |
| claims a pass with no run after the last edit | none | R16 -3 | 3 |
| states a figure unlike the delivered file | none | R17 -5 | 5 |
| overstates check coverage | none | R18 -3 | 3 |
The tool put negative_reads_check_files, negative_writes_outside_out_dir, R17 and R18 in one UNMATCHED group; they are four different acts (source strings; run-time writes; a figure in the reply; a coverage claim in the reply). Source strings (test) and the agent opening `/tests` (judge R15, now scoped to the agent's own commands so reads made by derive_report.py are left to the test) are different acts: QC_RULINGS AL-28 district-heat v3:251 PASS.

## (d) Weight shares (positive tests 137)
hidden reruns 119 (86.9%), mutation reruns 7 (5.1%), shipped-only 11 (8.0%), whole-document 0. G3 hidden or mutated 92.0% PASS. Tests 44 (over the 35 cap: A3/TS-23 warn, count reported to the master), judge criteria 18 (positive 42, probes 27 = 64.3%). Weight-1 checks: program run, missing-input stop, shipped data_quality, the six group-total halves of the TS-13 split and the two empty-axis checks; the core lever views (plan rows w3, settlement w5) keep their weights. Settlement weights unchanged (TS-20 kept).

Verdict: PASS.

## Raw tool output (with classes)
# stacking_check: hangar-check-replan

tests/test_output.py: 44 checks, positive total 137, negatives -13; judge: 18 criteria, positive 42, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| program_runs_on_shipped_data | 1 | shipped_only (override) | - | - | 0/0 |
| program_stops_on_a_missing_input | 1 | mutation (override) | - | - | 0/0 |
| shipped_plan_rows | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_data_quality | 1 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_group_reports | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_settlement | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| h1_plan_rows | 3 | hidden_rows (override) | h1 | _holds, _check_hidden_rows | 0/0 |
| h1_plan_group_totals | 1 | hidden_rows (override) | h1 | _holds, _check_hidden_group_totals | 0/0 |
| h1_settlement_per_check | 5 | hidden_rows (override) | h1, checks | _holds, _check_hidden_settle | 0/0 |
| h1_settlement_by_base_and_segment | 5 | hidden_rows (override) | h1, groups | _holds, _check_hidden_settle | 0/0 |
| h1_settlement_summary | 5 | hidden_rows (override) | h1, summary | _holds, _check_hidden_settle | 0/0 |
| h2_plan_rows | 3 | hidden_rows (override) | h2 | _holds, _check_hidden_rows | 0/0 |
| h2_plan_group_totals | 1 | hidden_rows (override) | h2 | _holds, _check_hidden_group_totals | 0/0 |
| h2_settlement_per_check | 5 | hidden_rows (override) | h2, checks | _holds, _check_hidden_settle | 0/0 |
| h2_settlement_by_base_and_segment | 5 | hidden_rows (override) | h2, groups | _holds, _check_hidden_settle | 0/0 |
| h2_settlement_summary | 5 | hidden_rows (override) | h2, summary | _holds, _check_hidden_settle | 0/0 |
| h3_plan_rows | 3 | hidden_rows (override) | h3 | _holds, _check_hidden_rows | 0/0 |
| h3_plan_group_totals | 1 | hidden_rows (override) | h3 | _holds, _check_hidden_group_totals | 0/0 |
| h3_settlement_per_check | 5 | hidden_rows (override) | h3, checks | _holds, _check_hidden_settle | 0/0 |
| h3_settlement_by_base_and_segment | 5 | hidden_rows (override) | h3, groups | _holds, _check_hidden_settle | 0/0 |
| h3_settlement_summary | 5 | hidden_rows (override) | h3, summary | _holds, _check_hidden_settle | 0/0 |
| h4_plan_rows | 3 | hidden_rows (override) | h4 | _holds, _check_hidden_rows | 0/0 |
| h4_plan_group_totals | 1 | hidden_rows (override) | h4 | _holds, _check_hidden_group_totals | 0/0 |
| h4_settlement_per_check | 5 | hidden_rows (override) | h4, checks | _holds, _check_hidden_settle | 0/0 |
| h4_settlement_by_base_and_segment | 5 | hidden_rows (override) | h4, groups | _holds, _check_hidden_settle | 0/0 |
| h4_settlement_summary | 5 | hidden_rows (override) | h4, summary | _holds, _check_hidden_settle | 0/0 |
| h5_plan_rows | 3 | hidden_rows (override) | h5 | _holds, _check_hidden_rows | 0/0 |
| h5_plan_group_totals | 1 | hidden_rows (override) | h5 | _holds, _check_hidden_group_totals | 0/0 |
| h5_settlement_per_check | 5 | hidden_rows (override) | h5, checks | _holds, _check_hidden_settle | 0/0 |
| h5_settlement_by_base_and_segment | 5 | hidden_rows (override) | h5, groups | _holds, _check_hidden_settle | 0/0 |
| h5_settlement_summary | 5 | hidden_rows (override) | h5, summary | _holds, _check_hidden_settle | 0/0 |
| h6_plan_rows | 3 | hidden_rows (override) | h6 | _holds, _check_hidden_rows | 0/0 |
| h6_plan_group_totals | 1 | hidden_rows (override) | h6 | _holds, _check_hidden_group_totals | 0/0 |
| h6_settlement_per_check | 5 | hidden_rows (override) | h6, checks | _holds, _check_hidden_settle | 0/0 |
| h6_settlement_by_base_and_segment | 5 | hidden_rows (override) | h6, groups | _holds, _check_hidden_settle | 0/0 |
| h6_settlement_summary | 5 | hidden_rows (override) | h6, summary | _holds, _check_hidden_settle | 0/0 |
| h1_base_and_segment_with_no_requests | 1 | hidden_rows (override) | h1 | _holds, _check_hidden_empty | 0/0 |
| h2_base_and_segment_with_no_requests | 1 | hidden_rows (override) | h2 | _holds, _check_hidden_empty | 0/0 |
| h1_data_quality | 3 | hidden_rows (override) | h1 | _holds, _check_hidden_data_quality | 0/0 |
| changed_allowance_grants | 3 | mutation (override) | - | - | 0/0 |
| revised_availability_removed | 3 | mutation (override) | - | - | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_reads_check_files | -5 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_writes_outside_out_dir | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): program_runs_on_shipped_data = program_stops_on_a_missing_input = shipped_plan_rows = shipped_data_quality = shipped_group_reports = shipped_settlement = changed_allowance_grants = revised_availability_removed

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| UNMATCHED act (name it by hand) | negative_reads_check_files -5, negative_writes_outside_out_dir -3 | R17 -5, R18 -3 | 16 | FAIL |
| naming or reading grader files | - | R15 -5 | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R16 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 119 (86.9%)
- isolated: 0 (0.0%)
- mutation: 7 (5.1%)
- shipped_only: 11 (8.0%)
- G3: hidden or mutated reruns 92.0% (>= 30%); isolated+mutation 5.1%, whole-document 0.0%, shipped-only 8.0% (info, no cap)

## 5. Caps and weights

- tests 44, criteria 18 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): program_runs_on_shipped_data, program_stops_on_a_missing_input, shipped_data_quality, h1_plan_group_totals, h2_plan_group_totals, h3_plan_group_totals, h4_plan_group_totals, h5_plan_group_totals, h6_plan_group_totals, h1_base_and_segment_with_no_requests, h2_base_and_segment_with_no_requests
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 1 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 92.0% PASS
- G3 isolated / shipped-only (info, no cap): 5.1% / 8.0%
- tests >= 10 (no cap): 44 PASS
- criteria >= 8 (no cap): 18 PASS
- judge mode batched: batched
