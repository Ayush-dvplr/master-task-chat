# stacking_check: slipway-overhaul-replan-repair

tests/test_output.py: 49 checks, positive total 112, negatives -63; judge: 16 criteria, positive 36, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| delivered_documents_present_and_parse | 1 | whole_doc (whole-document wording) | .json, .jsonl, .csv, .tsv ... | _delivered | 5/0 |
| delivered_package_layout | 1 | isolated (default (rule/fixture/case check)) | the archive carries no pyproject, the archive carries no module, pyproject.toml, .py ... | _engine_root | 2/0 |
| delivered_shipped_suite_unedited | 1 | shipped_only (artifact/shipped wording) | project.zip | _engine_root, _scratch, _corpus | 2/0 |
| delivered_engine_stdlib_only | 1 | isolated (default (rule/fixture/case check)) | the archive carries no module under src, *.py, src, utf-8 ... | _engine_root | 3/1 |
| shipped_identifier_layer_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_graph_layer_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_closure_and_demand_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_rule_and_charge_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_baseline_optimum_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_amendment_classification_exact | 3 | shipped_only (override) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_invalidation_sets_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_work_ledger_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_store_summary_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_final_optimum_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| shipped_audit_documents_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _echoes_shipped, _reference, _compare | 0/0 |
| package_eval_state_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_eval_cascade_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_challenge_state_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_challenge_cascade_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_probe_publication_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_crosswalk_groups_state_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_rules_state_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_amendments_cascade_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_amendments_state_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_every_state_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_every_publication_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_groups_cascade_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_groups_publication_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_rules_cascade_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_rules_publication_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_amendments_publication_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| package_crosswalk_every_cascade_exact | 5 | hidden_rows (override) | the held-out round, name:, carries documents the contract does not, , | _held_case, _compare, _held_reference | 0/0 |
| negative_shift_length_taken_flat | -5 | negative (weight < 0 or negative_ name) | R_FLAT_SHIFT | _detector | 0/0 |
| negative_pool_weights_taken_flat | -5 | negative (weight < 0 or negative_ name) | R_LEGACY_WEIGHTS | _detector | 0/0 |
| negative_deferral_rate_from_the_rescinded_sitting | -5 | negative (weight < 0 or negative_ name) | R_RESCINDED_MEMO | _detector | 0/0 |
| negative_drafting_register_read | -3 | negative (weight < 0 or negative_ name) | R_CURRENT_REGISTER | _detector | 0/0 |
| negative_capacity_boundary_read_as_strict | -3 | negative (weight < 0 or negative_ name) | R_STRICT_CAPACITY | _detector | 0/0 |
| negative_set_ranked_on_charge_alone | -5 | negative (weight < 0 or negative_ name) | R_COST_ONLY | _detector | 0/0 |
| negative_rebate_taken_before_the_surcharges | -3 | negative (weight < 0 or negative_ name) | R_REBATE_BEFORE | _detector | 0/0 |
| negative_penalty_charged_on_every_job | -3 | negative (weight < 0 or negative_ name) | R_PENALTY_ALL | _detector | 0/0 |
| negative_cascade_stopped_at_the_first_hop | -5 | negative (weight < 0 or negative_ name) | R_SHALLOW_CASCADE | _detector | 0/0 |
| negative_cascade_never_stopped | -3 | negative (weight < 0 or negative_ name) | R_NO_CUTOFF | _detector | 0/0 |
| negative_withdrawal_treated_as_inert | -3 | negative (weight < 0 or negative_ name) | R_REMOVAL_INERT | _detector | 0/0 |
| negative_rebinds_verifier_dependencies | -3 | negative (weight < 0 or negative_ name) | the archive shadows no verifier dependency, sitecustomize, usercustomize, conftest ... | _engine_root | 1/2 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | the shipped record is wrong; this detector stays silent | _echoes_shipped, _reference, _case | 1/0 |
| negative_package_ignores_its_input | -3 | negative (weight < 0 or negative_ name) | 18_final_selection.json | _echoes_shipped, _reference, _case | 1/0 |
| negative_nondeterministic_output | -3 | negative (weight < 0 or negative_ name) | repeat | _case, _drive, _corpus | 1/0 |
| negative_filename_dependent_behaviour | -3 | negative (weight < 0 or negative_ name) | repeat, papers_under_another_name, renamed-run, renamed | _case, _drive, _seal | 1/0 |
| negative_reads_training_corpus_at_runtime | -3 | negative (weight < 0 or negative_ name) | 18_final_selection.json | _scratch, _seal, _drive | 1/0 |

TS-26 duplicate candidates (same observable AND same logic): shipped_identifier_layer_exact = shipped_graph_layer_exact = shipped_closure_and_demand_exact = shipped_rule_and_charge_exact = shipped_baseline_optimum_exact = shipped_amendment_classification_exact = shipped_invalidation_sets_exact = shipped_work_ledger_exact = shipped_store_summary_exact = shipped_final_optimum_exact = shipped_audit_documents_exact; package_eval_state_exact = package_eval_cascade_exact = package_challenge_state_exact = package_challenge_cascade_exact = package_probe_publication_exact; package_crosswalk_groups_state_exact = package_crosswalk_rules_state_exact = package_crosswalk_amendments_cascade_exact = package_crosswalk_amendments_state_exact = package_crosswalk_every_state_exact = package_crosswalk_every_publication_exact = package_crosswalk_groups_cascade_exact = package_crosswalk_groups_publication_exact = package_crosswalk_rules_cascade_exact = package_crosswalk_rules_publication_exact = package_crosswalk_amendments_publication_exact = package_crosswalk_every_cascade_exact

## 2. TS-13 multi-assert hints

- delivered_documents_present_and_parse: 5 asserts, 0 and-chained comparisons
- delivered_engine_stdlib_only: 3 asserts, 1 and-chained comparisons

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| UNMATCHED act (name it by hand) | negative_shift_length_taken_flat -5, negative_pool_weights_taken_flat -5, negative_deferral_rate_from_the_rescinded_sitting -5, negative_drafting_register_read -3, negative_capacity_boundary_read_as_strict -3, negative_set_ranked_on_charge_alone -5, negative_rebate_taken_before_the_surcharges -3, negative_penalty_charged_on_every_job -3, negative_cascade_stopped_at_the_first_hop -5, negative_cascade_never_stopped -3, negative_withdrawal_treated_as_inert -3, negative_package_ignores_its_input -3 | R14 -5, R15 -3, R16 -3 | 57 | FAIL |
| rebinds verifier dependencies | negative_rebinds_verifier_dependencies -3 | - | 3 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| nondeterministic output | negative_nondeterministic_output -3 | - | 3 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -3 | - | 3 | PASS |
| reads data beyond its argument | negative_reads_training_corpus_at_runtime -3 | - | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R13 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 16 (14.3%)
- format_hidden: 0 (0.0%)
- hidden_rows: 60 (53.6%)
- isolated: 2 (1.8%)
- mutation: 0 (0.0%)
- shipped_only: 34 (30.4%)
- G3: hidden or mutated reruns 67.9% (>= 30%); isolated+mutation 1.8%, whole-document 14.3%, shipped-only 30.4% (info, no cap)

## 5. Caps and weights

- tests 49, criteria 16 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): delivered_documents_present_and_parse, delivered_package_layout, delivered_shipped_suite_unedited, delivered_engine_stdlib_only
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 3 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 67.9% PASS
- G3 isolated / shipped-only (info, no cap): 1.8% / 30.4%
- tests >= 10 (no cap): 49 PASS
- criteria >= 8 (no cap): 16 PASS
- judge mode batched: batched
