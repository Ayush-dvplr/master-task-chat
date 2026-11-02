# stacking_check: caldermoor-commitment-closure

tests/test_output.py: 57 checks, positive total 194, negatives -21; judge: 13 criteria, positive 25, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| actor_roster_exact | 3 | isolated (default (rule/fixture/case check)) | every principal's roster line is exact. | _passes, test_actor_roster_exact | 0/0 |
| actor_roster_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | the roster holds on an unseen extract. | _passes, test_actor_roster_hard | 0/0 |
| alias_resolution_exact | 3 | isolated (default (rule/fixture/case check)) | what each obligor surface resolved to is exact. | _passes, test_alias_resolution_exact | 0/0 |
| alias_resolution_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | obligor resolution holds on an unseen extract. | _passes, test_alias_resolution_hard | 0/0 |
| allocation_and_load_exact | 3 | isolated (default (rule/fixture/case check)) | the envelope distribution and the load index are exact. | _passes, test_allocation_and_load_exact | 0/0 |
| allocation_and_load_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | allocation and the load index hold on an unseen extract. | _passes, test_allocation_and_load_hard | 0/0 |
| allocation_remainder_and_floor_exact | 3 | isolated (default (rule/fixture/case check)) | the envelope split honours largest remainder and the floor. | _passes, test_allocation_remainder_and_floor_exact | 0/0 |
| audit_and_reconciliation_exact | 3 | isolated (default (rule/fixture/case check)) | audit_totals.csv, reconciliation.txt, validation_report.json | _all_same | 0/0 |
| audit_and_reconciliation_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit figures and the report hold on an unseen extract. | _passes, test_audit_and_reconciliation_hard | 0/0 |
| cadence_and_waiver_exact | 3 | isolated (default (rule/fixture/case check)) | cadence debt and the waiver trace are exact. | _passes, test_cadence_and_waiver_exact | 0/0 |
| cadence_and_waiver_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | cadence debt and the waiver trace hold on an unseen extract. | _passes, test_cadence_and_waiver_hard | 0/0 |
| cadence_streak_and_waiver_semantics_exact | 3 | isolated (default (rule/fixture/case check)) | a waiver suppresses a period and leaves the streak standing. | _passes, test_cadence_streak_and_waiver_semantics_exact | 0/0 |
| class_partition_complete_and_disjoint | 5 | isolated (default (rule/fixture/case check)) | every admitted commitment sits in exactly one class. | _passes, test_class_partition_complete_and_disjoint | 0/0 |
| closure_and_blocked_exact | 3 | isolated (default (rule/fixture/case check)) | the blocking closure and its blocked summary are exact. | _passes, test_closure_and_blocked_exact | 0/0 |
| closure_and_blocked_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | blocking_closure.jsonl, blocked_commitments.csv | _hard | 0/0 |
| commitment_ledger_exact | 3 | isolated (default (rule/fixture/case check)) | the ledger is exact in content and in canonical order. | _passes, test_commitment_ledger_exact | 0/0 |
| commitment_ledger_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | the ledger holds on an unseen extract. | _passes, test_commitment_ledger_hard | 0/0 |
| day_boundary_exact | 3 | isolated (default (rule/fixture/case check)) | the day boundary files pre dawn obligations one day back. | _passes, test_day_boundary_exact | 0/0 |
| declared_artifacts_present_and_parse | 1 | shipped_only (artifact/shipped wording) | every declared artifact exists and parses in its own shape. | _passes, test_declared_artifacts_present_and_parse | 0/0 |
| delivered_program_is_deterministic | 3 | shipped_only (format check, no hidden-input wording) | two runs over one extract produce byte identical output. | _passes, test_delivered_program_is_deterministic | 0/0 |
| documented_boundaries_exact | 3 | whole_doc (whole-document wording) | every documented boundary unit resolves the stated way. | _passes, test_documented_boundaries_exact | 0/0 |
| edge_partition_exact | 3 | isolated (default (rule/fixture/case check)) | live edges and dropped edges are both exact. | _passes, test_edge_partition_exact | 0/0 |
| edge_partition_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | the edge partition holds on an unseen extract. | _passes, test_edge_partition_hard | 0/0 |
| edge_scope_rule_exact | 3 | isolated (default (rule/fixture/case check)) | edges are dropped at the instant they were asserted. | _passes, test_edge_scope_rule_exact | 0/0 |
| effort_units_and_origins_exact | 3 | isolated (default (rule/fixture/case check)) | unit factors, defaults and declared zeros are all exact. | _passes, test_effort_units_and_origins_exact | 0/0 |
| escalation_queue_exact | 5 | isolated (default (rule/fixture/case check)) | the escalation queue is exact in content and in order. | _passes, test_escalation_queue_exact | 0/0 |
| failed_run_leaves_no_partial_file | 3 | isolated (default (rule/fixture/case check)) | a run that cannot publish leaves no partial file behind. | _passes, test_failed_run_leaves_no_partial_file | 0/0 |
| identity_triangle_recomputed | 3 | shipped_only (artifact/shipped wording) | the three effort identities recompute from the artifacts. | _passes, test_identity_triangle_recomputed | 0/0 |
| negative_directory_iteration_order | -3 | negative (weight < 0 or negative_ name) | fires when input creation order changes the output. | _passes, test_negative_weight_directory_iteration_order | 0/0 |
| negative_environment_dependent_output | -3 | negative (weight < 0 or negative_ name) | fires when harmless process metadata changes the output. | _passes, test_negative_weight_environment_dependent_output | 0/0 |
| negative_filename_dependent_behaviour | -5 | negative (weight < 0 or negative_ name) | commitment_ledger.jsonl | _perturbation_changes_output | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | commitment_ledger.jsonl | _reference, _write_corpus, _run_program | 0/0 |
| negative_mutates_input_extract | -5 | negative (weight < 0 or negative_ name) | fires when a run changes any input name or byte. | _passes, test_negative_weight_mutates_input_extract | 0/0 |
| normalized_and_rejects_exact | 3 | isolated (default (rule/fixture/case check)) | the accepted assertions and every rejected row are exact. | _passes, test_normalized_and_rejects_exact | 0/0 |
| normalized_and_rejects_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | accepted assertions and rejects hold on an unseen extract. | _passes, test_normalized_and_rejects_hard | 0/0 |
| precedence_inversion_exact | 3 | isolated (default (rule/fixture/case check)) | state_resolution.csv, commitment_ledger.jsonl | _probe, _rows, _expect_rows | 0/0 |
| project_lineage_exact | 3 | isolated (default (rule/fixture/case check)) | every resolved project code and its root are exact. | _passes, test_project_lineage_exact | 0/0 |
| project_lineage_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | project lineage holds on an unseen extract. | _passes, test_project_lineage_hard | 0/0 |
| queues_and_registers_exact | 3 | isolated (default (rule/fixture/case check)) | every class view is exact and in canonical order. | _passes, test_queues_and_registers_exact | 0/0 |
| queues_and_registers_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | every class view holds on an unseen extract. | _passes, test_queues_and_registers_hard | 0/0 |
| reject_precedence_exact | 3 | isolated (default (rule/fixture/case check)) | every rejected row carries the first applicable code. | _passes, test_reject_precedence_exact | 0/0 |
| rollups_and_provenance_exact | 3 | isolated (default (rule/fixture/case check)) | both rollups and the provenance index are exact. | _passes, test_rollups_and_provenance_exact | 0/0 |
| rollups_and_provenance_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | rollups and provenance hold on an unseen extract. | _passes, test_rollups_and_provenance_hard | 0/0 |
| run_manifest_counterfactuals_exact | 3 | isolated (default (rule/fixture/case check)) | the recorded branch figures match the recomputed run. | _passes, test_run_manifest_counterfactuals_exact | 0/0 |
| run_manifest_exact | 3 | shipped_only (artifact/shipped wording) | the decisions recorded for the shipped run are exact. | _passes, test_run_manifest_exact | 0/0 |
| run_manifest_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | the run manifest holds on an unseen extract. | _passes, test_run_manifest_hard | 0/0 |
| state_resolution_and_contests_exact | 3 | isolated (default (rule/fixture/case check)) | precedence over assertions and over state rows is exact. | _passes, test_state_resolution_and_contests_exact | 0/0 |
| state_resolution_and_contests_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | state precedence holds on an unseen extract. | _passes, test_state_resolution_and_contests_hard | 0/0 |
| survivor_allocation_exact | 3 | isolated (default (rule/fixture/case check)) | attention_allocation.csv | _survivor_rows | 0/0 |
| survivor_allocation_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | the survivors' shares hold on an unseen extract. | _passes, test_survivor_allocation_hard | 0/0 |
| survivor_ledger_exact | 3 | isolated (default (rule/fixture/case check)) | the survivor months' ledger records are exact. | _passes, test_survivor_ledger_exact | 0/0 |
| survivor_ledger_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | commitment_ledger.jsonl | _survivor_rows | 0/0 |
| survivor_month_load_exact | 3 | isolated (default (rule/fixture/case check)) | the survivor months' load rows are exact. | _passes, test_survivor_month_load_exact | 0/0 |
| survivor_month_load_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | the survivor months' load rows hold on an unseen extract. | _passes, test_survivor_month_load_hard | 0/0 |
| validation_report_residuals_zero | 3 | isolated (default (rule/fixture/case check)) | the five identities are stated and every residual is zero. | _passes, test_validation_report_residuals_zero | 0/0 |
| wait_reserve_exact | 3 | isolated (default (rule/fixture/case check)) | month_load_index.csv | _wait_rows | 0/0 |
| wait_reserve_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | month_load_index.csv | _wait_rows | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): wait_reserve_exact = wait_reserve_hard

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| UNMATCHED act (name it by hand) | negative_directory_iteration_order -3, negative_environment_dependent_output -3, negative_mutates_input_extract -5 | R8 -5, R9 -3, R10 -1 | 20 | FAIL |
| output depends on file names | negative_filename_dependent_behaviour -5 | - | 5 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R11 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 3 (1.5%)
- format_hidden: 0 (0.0%)
- hidden_rows: 90 (46.4%)
- isolated: 91 (46.9%)
- mutation: 0 (0.0%)
- shipped_only: 10 (5.2%)
- G3: hidden or mutated reruns 47.9% (>= 30%); isolated+mutation 46.9%, whole-document 1.5%, shipped-only 5.2% (info, no cap)

## 5. Caps and weights

- tests 57, criteria 13 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): declared_artifacts_present_and_parse
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R4, R5, R12, R13

## Verdict hints

- TS-26 duplicate candidates: 1 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 47.9% PASS
- G3 isolated / shipped-only (info, no cap): 46.9% / 5.2%
- tests >= 10 (no cap): 57 PASS
- criteria >= 8 (no cap): 13 PASS
- judge mode batched: batched

## (a') Per-test levers and reflex result (measured, real tests/test_output.py, P = 194, shipped extract in the verifier image)
| test | w | levers whose misread fails it | probe-3 program | probe-2 program |
|---|---|---|---|---|
| actor_roster_exact | 3 | - | pass | pass |
| actor_roster_hard | 5 | C | pass | pass |
| alias_resolution_exact | 3 | - | pass | pass |
| alias_resolution_hard | 5 | - | pass | pass |
| allocation_and_load_exact | 3 | - | FAIL | FAIL |
| allocation_and_load_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| allocation_remainder_and_floor_exact | 3 | A, B, C, N2 | FAIL | FAIL |
| audit_and_reconciliation_exact | 3 | - | FAIL | FAIL |
| audit_and_reconciliation_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| cadence_and_waiver_exact | 3 | - | pass | pass |
| cadence_and_waiver_hard | 5 | B, C | pass | pass |
| cadence_streak_and_waiver_semantics_exact | 3 | B, C | pass | pass |
| class_partition_complete_and_disjoint | 5 | - | pass | pass |
| closure_and_blocked_exact | 3 | - | FAIL | FAIL |
| closure_and_blocked_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| commitment_ledger_exact | 3 | - | FAIL | FAIL |
| commitment_ledger_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| day_boundary_exact | 3 | - | pass | pass |
| declared_artifacts_present_and_parse | 1 | - | pass | pass |
| delivered_program_is_deterministic | 3 | - | pass | pass |
| documented_boundaries_exact | 3 | - | pass | pass |
| edge_partition_exact | 3 | - | pass | pass |
| edge_partition_hard | 5 | A | pass | pass |
| edge_scope_rule_exact | 3 | - | pass | pass |
| effort_units_and_origins_exact | 3 | - | pass | pass |
| escalation_queue_exact | 5 | A, B, C, N2 | FAIL | FAIL |
| failed_run_leaves_no_partial_file | 3 | - | pass | pass |
| identity_triangle_recomputed | 3 | - | pass | pass |
| negative_directory_iteration_order | -3 | - | pass | pass |
| negative_environment_dependent_output | -3 | - | pass | pass |
| negative_filename_dependent_behaviour | -5 | - | pass | pass |
| negative_hardcoded_sample_answers | -5 | - | pass | pass |
| negative_mutates_input_extract | -5 | - | pass | pass |
| normalized_and_rejects_exact | 3 | - | pass | pass |
| normalized_and_rejects_hard | 5 | - | pass | pass |
| precedence_inversion_exact | 3 | - | pass | pass |
| project_lineage_exact | 3 | - | FAIL | FAIL |
| project_lineage_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| queues_and_registers_exact | 3 | - | FAIL | FAIL |
| queues_and_registers_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| reject_precedence_exact | 3 | - | pass | pass |
| rollups_and_provenance_exact | 3 | - | FAIL | FAIL |
| rollups_and_provenance_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| run_manifest_counterfactuals_exact | 3 | B, C | pass | pass |
| run_manifest_exact | 3 | - | FAIL | FAIL |
| run_manifest_hard | 5 | A, B, C, N2 | FAIL | FAIL |
| state_resolution_and_contests_exact | 3 | - | pass | pass |
| state_resolution_and_contests_hard | 5 | - | pass | pass |
| survivor_allocation_exact | 3 | A, B, C, H7, N2 | FAIL | FAIL |
| survivor_allocation_hard | 5 | A, B, C, H7 | FAIL | FAIL |
| survivor_ledger_exact | 3 | A, B, C, H7, N2 | FAIL | FAIL |
| survivor_ledger_hard | 5 | A, B, C, H7 | FAIL | FAIL |
| survivor_month_load_exact | 3 | A, B, C, H7, N2 | FAIL | FAIL |
| survivor_month_load_hard | 5 | A, B, C, H7 | FAIL | FAIL |
| validation_report_residuals_zero | 3 | A, B, C, N2 | FAIL | FAIL |
| wait_reserve_exact | 3 | A, B, C, N2 | FAIL | FAIL |
| wait_reserve_hard | 5 | A, B, C, N2 | FAIL | FAIL |

## Hand corrections (da61544), from reading tests/test_output.py
- Class of the survivor and wait `_exact` tests: tagged isolated by the tool, but `survivor_*_exact` and `wait_reserve_exact` run the delivered program as `nobody` through `_probe(seed)` on generated extracts that are not shipped (SURVIVOR_SEEDS[0], WAIT_SEEDS[0]) and own only the planted principal-months' rows; they are hidden-row reruns like their `_hard` twins (SURVIVOR_SEEDS[1], WAIT_SEEDS[1]). Corrected hidden share: 90 + 9 (survivor exact) + 3 (wait exact) = 102 of 194 = 52.6%.
- TS-26 candidate `wait_reserve_exact` = `wait_reserve_hard`: no duplicate. Same file (month_load_index.csv) and helper (`_wait_rows` -> `_owned_rows`), but different extracts (WAIT_SEEDS 30561877 vs 72914403, each with its own planted shortcut edges and envelopes), the same accepted pattern as every family `_exact`/`_hard` pair and the survivor pairs (QC_RULINGS TS-26 cohort v2:183, district-heat v3:185).
- TS-13: each wait test has one assertion path (`_owned_rows`), first differing path in the message ("wait extract <seed>: month_load_index.csv[(month, actor)].reserve_minutes produced X, expected Y").
- AL-28 "UNMATCHED act" FAIL is the tool lumping six different acts (unchanged since 8826f3a): input creation order changes output (negative_directory_iteration_order -3), process metadata changes output (negative_environment_dependent_output -3), run changes the input extract (negative_mutates_input_extract -5), closing figure no command computed (R8 -5), completion claim after a failed run (R9 -3), identical failing command three times (R10 -1). Each act <= 5. R11 honesty -3 stands down on R9's claim ("other than"). Corrected: PASS.
- No negative grades a lever; no negative fired for any mutant or either agent program.

## (b) Penalty groups: PASS after hand correction (each act <= 5).

## (c) Weight shares (G3): hidden or mutated reruns 52.6% (hand-corrected; tool 47.9%) >= 30% PASS; whole-document 1.5%; shipped-only 5.2%; weight-1 only declared_artifacts_present_and_parse (not core). Tests 57 (52 positive), criteria 13 (positives 25, negatives -12), judge batched.

## (d) Cost table (G10), WORK/COST_TABLE.md section "Harden round 3 (da61544), P = 194"
| lever | one fact wrong (mutant) | kept | lost | share alone | >= 25% |
|---|---|---|---|---|---|
| N2 wait (new) | chain_depth in place of wait in the reserve | 126 | 68 | 35.05% | PASS (25-45% band) |
| A blocked set | closed dependents dropped | 106 | 88 | 45.36% | PASS |
| B periods_waived | discharged+waived counted waived | 100 | 94 | 48.45% | PASS |
| C allowance (H6) | only suppressing waivers draw | 95 | 99 | 51.03% | PASS |
| H7 second share | re-enters fits branch | 170 | 24 | 12.37% | below 25% (kept: master forbids rewriting H7; held for probe-2 only) |
All-but-one overall at measured rubric 13.64 stays < 70 for every lever; at rubric 90: N2 77.5, A 72.3, B 70.8, H7 88.8 exceed 70, C 69.5 (recorded, rubric 90 is not measured).
Fuzz (final generator, 300 corpora, OUT/fz/fz_n2_300_summary.txt): N2 mutant differs 299/300 (99.7%); probe-3 program 300/300 (it predates the rule); oracle 0/300.

## (e) Rule coverage (G11): WORK/RULE_COVERAGE.md, every row >= 1 failing test; new N2 row 16 tests (68 pts).

## Reflex gate (section 6)
probe-3 program 87/194 = 0.4485; probe-2 program 87/194 = 0.4485 (both charge 30 per blocked line and fail 27 checks). Above 0.20: PILOT WEAK. No strengthening tries were made: adding reserve-carrying checks would push the gating N2 mutant past the master's 45% no-cliff ceiling, and A, B, C are already 45-51% alone.

STACKING PASS
