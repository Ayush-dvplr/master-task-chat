# stacking_check: caldermoor-commitment-closure

tests/test_output.py: 38 checks, positive total 133, negatives -21; judge: 11 criteria, positive 19, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| actor_roster_exact | 5 | isolated (default (rule/fixture/case check)) | every principal's roster line is exact. | _passes, test_actor_roster_exact | 0/0 |
| alias_resolution_exact | 5 | isolated (default (rule/fixture/case check)) | what each obligor surface resolved to is exact. | _passes, test_alias_resolution_exact | 0/0 |
| allocation_and_load_exact | 5 | isolated (default (rule/fixture/case check)) | the envelope distribution and the load index are exact. | _passes, test_allocation_and_load_exact | 0/0 |
| allocation_remainder_and_floor_exact | 3 | isolated (default (rule/fixture/case check)) | the envelope split honours largest remainder and the floor. | _passes, test_allocation_remainder_and_floor_exact | 0/0 |
| audit_and_reconciliation_exact | 5 | isolated (default (rule/fixture/case check)) | audit_totals.csv, reconciliation.txt, validation_report.json | _all_same | 0/0 |
| cadence_and_waiver_exact | 3 | isolated (default (rule/fixture/case check)) | cadence debt and the waiver trace are exact. | _passes, test_cadence_and_waiver_exact | 0/0 |
| cadence_streak_and_waiver_semantics_exact | 3 | isolated (default (rule/fixture/case check)) | a waiver suppresses a period and leaves the streak standing. | _passes, test_cadence_streak_and_waiver_semantics_exact | 0/0 |
| class_partition_complete_and_disjoint | 5 | isolated (default (rule/fixture/case check)) | every admitted commitment sits in exactly one class. | _passes, test_class_partition_complete_and_disjoint | 0/0 |
| closure_and_blocked_exact | 5 | isolated (default (rule/fixture/case check)) | the blocking closure and its blocked summary are exact. | _passes, test_closure_and_blocked_exact | 0/0 |
| commitment_ledger_exact | 5 | isolated (default (rule/fixture/case check)) | the ledger is exact in content and in canonical order. | _passes, test_commitment_ledger_exact | 0/0 |
| day_boundary_exact | 3 | isolated (default (rule/fixture/case check)) | the day boundary files pre dawn obligations one day back. | _passes, test_day_boundary_exact | 0/0 |
| declared_artifacts_present_and_parse | 1 | shipped_only (artifact/shipped wording) | every declared artifact exists and parses in its own shape. | _passes, test_declared_artifacts_present_and_parse | 0/0 |
| delivered_program_is_deterministic | 3 | shipped_only (format check, no hidden-input wording) | two runs over one extract produce byte identical output. | _passes, test_delivered_program_is_deterministic | 0/0 |
| documented_boundaries_exact | 3 | whole_doc (whole-document wording) | every documented boundary unit resolves the stated way. | _passes, test_documented_boundaries_exact | 0/0 |
| edge_partition_exact | 5 | isolated (default (rule/fixture/case check)) | live edges and dropped edges are both exact. | _passes, test_edge_partition_exact | 0/0 |
| edge_scope_rule_exact | 3 | isolated (default (rule/fixture/case check)) | edges are dropped at the instant they were asserted. | _passes, test_edge_scope_rule_exact | 0/0 |
| effort_units_and_origins_exact | 3 | isolated (default (rule/fixture/case check)) | unit factors, defaults and declared zeros are all exact. | _passes, test_effort_units_and_origins_exact | 0/0 |
| escalation_queue_exact | 5 | isolated (default (rule/fixture/case check)) | the escalation queue is exact in content and in order. | _passes, test_escalation_queue_exact | 0/0 |
| failed_run_leaves_no_partial_file | 3 | isolated (default (rule/fixture/case check)) | a run that cannot publish leaves no partial file behind. | _passes, test_failed_run_leaves_no_partial_file | 0/0 |
| identity_triangle_recomputed | 3 | shipped_only (artifact/shipped wording) | the three effort identities recompute from the artifacts. | _passes, test_identity_triangle_recomputed | 0/0 |
| negative_directory_iteration_order | -3 | negative (weight < 0 or negative_ name) | fires when input creation order changes the output. | _passes, test_negative_weight_directory_iteration_order | 0/0 |
| negative_filename_dependent_behaviour | -5 | negative (weight < 0 or negative_ name) | commitment_ledger.jsonl | _perturbation_changes_output | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | commitment_ledger.jsonl | _reference, _write_corpus, _run_program | 0/0 |
| negative_environment_dependent_output | -3 | negative (weight < 0 or negative_ name) | fires when harmless process metadata changes the output. | _passes, test_negative_weight_environment_dependent_output | 0/0 |
| negative_mutates_input_extract | -5 | negative (weight < 0 or negative_ name) | fires when a run changes any input name or byte. | _passes, test_negative_weight_mutates_input_extract | 0/0 |
| normalized_and_rejects_exact | 5 | isolated (default (rule/fixture/case check)) | the accepted assertions and every rejected row are exact. | _passes, test_normalized_and_rejects_exact | 0/0 |
| precedence_inversion_exact | 3 | isolated (default (rule/fixture/case check)) | state_resolution.csv, commitment_ledger.jsonl | _probe, _rows, _expect_rows | 0/0 |
| project_lineage_exact | 5 | isolated (default (rule/fixture/case check)) | every resolved project code and its root are exact. | _passes, test_project_lineage_exact | 0/0 |
| queues_and_registers_exact | 5 | isolated (default (rule/fixture/case check)) | every class view is exact and in canonical order. | _passes, test_queues_and_registers_exact | 0/0 |
| reject_precedence_exact | 3 | isolated (default (rule/fixture/case check)) | every rejected row carries the first applicable code. | _passes, test_reject_precedence_exact | 0/0 |
| rollups_and_provenance_exact | 5 | isolated (default (rule/fixture/case check)) | both rollups and the provenance index are exact. | _passes, test_rollups_and_provenance_exact | 0/0 |
| run_manifest_counterfactuals_exact | 3 | isolated (default (rule/fixture/case check)) | the recorded branch figures match the recomputed run. | _passes, test_run_manifest_counterfactuals_exact | 0/0 |
| run_manifest_exact | 5 | shipped_only (artifact/shipped wording) | the decisions recorded for the shipped run are exact. | _passes, test_run_manifest_exact | 0/0 |
| state_resolution_and_contests_exact | 5 | isolated (default (rule/fixture/case check)) | precedence over assertions and over state rows is exact. | _passes, test_state_resolution_and_contests_exact | 0/0 |
| unseen_alpha_full_exact | 5 | whole_doc (whole-document wording) | the program reproduces a whole extract it never saw. | _passes, test_unseen_alpha_full_exact | 0/0 |
| unseen_beta_full_exact | 5 | isolated (default (rule/fixture/case check)) | the program reproduces a second unseen extract. | _passes, test_unseen_beta_full_exact | 0/0 |
| unseen_gamma_full_exact | 5 | isolated (default (rule/fixture/case check)) | every deliverable holds on a third unseen extract. | _passes, test_unseen_gamma_full_exact | 0/0 |
| validation_report_residuals_zero | 3 | isolated (default (rule/fixture/case check)) | the five identities are stated and every residual is zero. | _passes, test_validation_report_residuals_zero | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): none

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

- whole_doc: 8 (6.0%)
- format_hidden: 0 (0.0%)
- isolated: 113 (85.0%)
- mutation: 0 (0.0%)
- shipped_only: 12 (9.0%)
- G3: hidden or mutated reruns 6.0% (>= 30%); isolated+mutation 85.0%, whole-document 6.0%, shipped-only 9.0% (info, no cap)

## 5. Caps and weights

- tests 38, criteria 11 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): declared_artifacts_present_and_parse
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R4, R5

## Verdict hints

- TS-26 duplicate candidates: none
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 6.0% FAIL
- G3 isolated / shipped-only (info, no cap): 85.0% / 9.0%
- tests >= 10 (no cap): 38 PASS
- criteria >= 8 (no cap): 11 PASS
- judge mode batched: batched

## Hand corrections (8826f3a)

- G3 FAIL is the known misclassification. Read from tests/test_output.py: thirteen checks run the program on probe extracts built by seed (`_probe(`): escalation_queue_exact 5, identity_triangle_recomputed 3, class_partition_complete_and_disjoint 5, documented_boundaries_exact 3, edge_scope_rule_exact 3, precedence_inversion_exact 3, effort_units_and_origins_exact 3, day_boundary_exact 3, reject_precedence_exact 3, cadence_streak_and_waiver_semantics_exact 3, allocation_remainder_and_floor_exact 3, run_manifest_counterfactuals_exact 3, validation_report_residuals_zero 3; three run it on unseen extracts: unseen_alpha/beta/gamma_full_exact 15. Hidden reruns = 58 of 133 = 43.6%, >= 30%: PASS. Tests unchanged this round (tests/test_output.py sha 216c24de... same as SOURCE).
- AL-28 "UNMATCHED act" FAIL groups six different acts. By hand, one row per act: input creation order changes output (negative_directory_iteration_order -3), process metadata changes output (negative_environment_dependent_output -3), run changes the input extract (negative_mutates_input_extract -5), closing figure stated with no command computing it (R8 -5), completion claim against a nonzero last run (R9 -3), reruns of one failing command (R10 -1), pass claim with no run after the last edit (R11 -3). Each act <= 5: PASS. Note: R9 and R11 can both fire on one final message that claims success after a failed or missing run (sum 6); kept as master directed, recorded in PL_NOTE.
- J2 conduct criteria: R4, R5 and R6 (R6 runs the program on a second extract it placed outside /app/data; the tool's pattern matches only "constructs its own input").

Corrected verdict: PASS.

## Lessons for the master

- stacking_check counts probe and unseen reruns as isolated and lumps unmatched negatives into one act | template_change: master_chat_tasks/tools/stacking_check.py G3 and AL-28 classifiers
