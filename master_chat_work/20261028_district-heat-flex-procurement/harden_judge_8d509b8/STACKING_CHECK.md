# STACKING_CHECK - district-heat-flex-procurement, gate v3.6 judge harden (board 8d509b8)

Tool output (stacking_check.py, unedited) follows the hand corrections.

## Hand corrections (read from tests/test_output.py)
- (a) TS-26: the tool lists 24 candidate groups by name pattern. None is a duplicate. Each shipped check and its `_hard` partner
  read different extracts (shipped vs H1/H2 seeded extract; family_passes(workspace, family, False|True)). The four wide groups
  (wide_0..wide_3 x feasible/selection/tie_decisions/intervals) each read a different seeded extract (`wide_root(k)`, seeds
  75775, 84071, 7120, 24943, test_output.py:1404) through their own program run. QC v6 and v7 passed TS-26 on the same
  pattern (v6.md:300). TS-13: one observable per check (tool: none flagged).
- (a) wide_k_portfolios_feasible: the tool's observable column ("passed, check raised") is a parse artefact of `_graded`; the
  real observable is admissibility plus non-empty of `selected_offer_ids` per event entry (wide_feasible :2101-2135).
- (b) AL-28: every act <= 5 (PASS, tool table). No negative grades a lever.
- (c) G3 shares through the call graph: hidden_rows 164 of 237 (69.2%: 20 `_hard` x 5 = 100 + 16 wide x 3/5 = 64), mutations
  9 (3.8%), shipped-only 64 (27.0%: 20 shipped w3 = 60 + 4 format w1). Hidden or mutated 173/237 = 73.0%. Lever (wide)
  64/237 = 27.0% (25-40% band).
- (d) Cost table: WORK/COST_TABLE.md gate36 section (Docker, 237-point tests); tests unchanged this round (G7).
- (e) Rule coverage / RULE_TRACE: unchanged rules; the new corpora fire the same stated optimum and tie rules (AL-27).
- (f) EVIDENCE_MAP unchanged (no new rule).
- (g) BRANCH_FIRE: the wide branch (20-26 sites per event-region) fires 0 times on shipped data (max sites per event-region
  on shipped data is below that; the shipped run takes 1.1-2.4 s for every program) and on every wide corpus.
- (h) JUDGE_MAP: WORK/JUDGE_MAP.md (8d509b8). 11 criteria, positive 24, R7 -5; R4, R8, R9, R10 re-targeted (two half-cent
  amounts; reruns on altered copies of /app/data), still w3 probes, R1-R4, R8-R10 = 21 of 24 positive. Tool "J2 conduct" lists
  R1-R4 (own-extract wording); R8-R10 are the same probe kind (altered-copy rerun, P-d), each shown by solve.sh's own-extract
  stage (JD-7). J1 hints none: no criterion quotes a figure.
- (i) Invocation: `python3 /app/out/derive_report.py DATA_DIR OUT_DIR` in instruction.md equals run_agent's command (unchanged).
- Counts: 66 checks (63 positive = 237, 3 negatives = -13); TS-23 warn above 35 recorded (option A), nothing merged.

STACKING PASS

## Tool output

# stacking_check: district-heat-flex-procurement

tests/test_output.py: 66 checks, positive total 237, negatives -13; judge: 11 criteria, positive 24, mode batched. Static hints only; confirm by reading the code.

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
| tie_decisions_match | 3 | shipped_only (artifact/shipped wording) | tie_decisions | _graded, family_passes | 0/0 |
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
| segment_rate_adder_mutation | 3 | mutation (mutation in name or description lead) | mut_adder, mut_adder_moved | _graded, mutation_passes, _credit_family | 0/0 |
| allowance_ticks_mutation | 3 | mutation (mutation in name or description lead) | policy_audit.json | _graded, mutation_passes, _ledger_view | 0/0 |
| minimum_grant_mutation | 3 | mutation (mutation in name or description lead) | mut_grant, mut_grant_moved | _graded, mutation_passes, _grant_rows | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | summary.json | hidden_root, run_agent, expected | 0/2 |
| negative_reads_tests_or_reward_files | -5 | negative (weight < 0 or negative_ name) | /tests, /tests/, /logs/, judge.toml ... | _program_tree, _ran_cleanly | 0/1 |
| negative_external_dependency_or_network | -3 | negative (weight < 0 or negative_ name) | socket, urllib, http, ftplib ... | _program_tree | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): selection_match = selection_match_hard; intervals_match = intervals_match_hard; tie_decisions_match = tie_decisions_match_hard; segment_rows_match = segment_rows_match_hard; ledger_quality_match = ledger_quality_match_hard; region_totals_North_match = region_totals_North_match_hard; region_totals_South_match = region_totals_South_match_hard; region_totals_West_match = region_totals_West_match_hard; region_totals_East_match = region_totals_East_match_hard; segment_totals_match = segment_totals_match_hard; summary_match = summary_match_hard; labels_match = labels_match_hard; quality_counts_match = quality_counts_match_hard; credit_rows_match = credit_rows_match_hard; segment_credit_rows_match = segment_credit_rows_match_hard; funded_pool_match = funded_pool_match_hard; grants_match = grants_match_hard; grant_allocation_match = grant_allocation_match_hard; residual_match = residual_match_hard; cap_binding_match = cap_binding_match_hard; wide_0_portfolios_feasible = wide_1_portfolios_feasible = wide_2_portfolios_feasible = wide_3_portfolios_feasible; wide_0_selection_match = wide_1_selection_match = wide_2_selection_match = wide_3_selection_match; wide_0_tie_decisions_match = wide_1_tie_decisions_match = wide_2_tie_decisions_match = wide_3_tie_decisions_match; wide_0_intervals_match = wide_1_intervals_match = wide_2_intervals_match = wide_3_intervals_match

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
- hidden_rows: 164 (69.2%)
- isolated: 0 (0.0%)
- mutation: 9 (3.8%)
- shipped_only: 64 (27.0%)
- G3: hidden or mutated reruns 73.0% (>= 30%); isolated+mutation 3.8%, whole-document 0.0%, shipped-only 27.0% (info, no cap)

## 5. Caps and weights

- tests 66, criteria 11 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): artifact_set_exists_and_parses, canonical_serialization_and_integer_units, report_keys_match_schema, report_arrays_in_schema_order
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R1, R2, R3, R4

## Verdict hints

- TS-26 duplicate candidates: 24 group(s): CHECK BY HAND
- AL-28 groups <= 5: PASS
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 73.0% PASS
- G3 isolated / shipped-only (info, no cap): 3.8% / 27.0%
- tests >= 10 (no cap): 66 PASS
- criteria >= 8 (no cap): 11 PASS
- judge mode batched: batched
