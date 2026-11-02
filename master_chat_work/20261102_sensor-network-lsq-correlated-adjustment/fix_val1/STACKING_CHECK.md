# stacking_check: sensor-network-lsq-correlated-adjustment

tests/test_output.py: 34 checks, positive total 86, negatives -12; judge: 17 criteria, positive 39, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped_only (artifact/shipped wording) | missing /app/out/derive_report.py, missing /app/out/, .json | _jload | 3/0 |
| challenge_model_test_document | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge | _check_model_test | 0/0 |
| challenge_unknowns_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge | _check_unknowns | 0/0 |
| challenge_residual_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge | _check_residuals | 0/0 |
| challenge_observation_sets | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge | _check_sets | 0/0 |
| challenge_rollup_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge | _check_rollups | 0/0 |
| challenge_summary_reports | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge | _check_reports | 0/0 |
| eval_model_test_document | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval | _check_model_test | 0/0 |
| eval_unknowns_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval | _check_unknowns | 0/0 |
| eval_residual_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval | _check_residuals | 0/0 |
| eval_observation_sets | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval | _check_sets | 0/0 |
| eval_rollup_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval | _check_rollups | 0/0 |
| eval_summary_reports | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval | _check_reports | 0/0 |
| audit_model_test_document | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit | _check_model_test | 0/0 |
| audit_unknowns_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit | _check_unknowns | 0/0 |
| audit_residual_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit | _check_residuals | 0/0 |
| audit_observation_sets | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit | _check_sets | 0/0 |
| audit_rollup_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit | _check_rollups | 0/0 |
| audit_summary_reports | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit | _check_reports | 0/0 |
| control_values_on_hidden_extracts | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | adjusted_state.json, datum_transformation.json, provenance_summary.json, removed_blunders.json | _hidden, frac_to_str, _jload | 14/2 |
| superseded_records_on_hidden_extracts | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | provenance_summary.json | _hidden, _jload | 2/0 |
| canonical_serialization_on_hidden_extracts | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | observation_stream.jsonl, .json | _hidden, _keys_sorted | 4/0 |
| traverse_closure_rows_shipped | 3 | shipped_only (artifact/shipped wording) | absorbed | _owned_rows | 0/0 |
| eval_traverse_closure_rows_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | eval, program exit status, code, ref ... | _hidden, _closure_rows | 1/0 |
| centring_chain_rows_shipped | 3 | shipped_only (artifact/shipped wording) | linked, obs, length | _owned_rows | 0/1 |
| challenge_centring_chain_rows_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | challenge, program exit status, code, ref ... | _hidden, _chain_rows | 1/0 |
| district_rollups_shipped | 3 | shipped_only (artifact/shipped wording) | shipped run: the four district rollups match. | _passes, test_district_rollups_shipped | 0/0 |
| audit_district_rows_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | audit, program exit status, code, ref ... | _hidden, _district_rollups, _owned_rows | 1/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | catches a program that embeds the shipped extract's answers. | _passes, test_negative_weight_hardcoded_sample_answers | 0/0 |
| negative_external_dependency | -3 | negative (weight < 0 or negative_ name) | program did not run; detector stands down, no external numeric-library dependency detected, numpy, scipy ... | _ran_cleanly | 2/0 |
| negative_filename_dependent_behaviour | -1 | negative (weight < 0 or negative_ name) | no filename-dependent documents observed, filename_dependent_behaviour | _new_negative_owner | 1/0 |
| negative_reads_training_corpus_at_runtime | -1 | negative (weight < 0 or negative_ name) | no shipped-tree-dependent documents observed, reads_training_corpus_at_runtime | _new_negative_owner | 1/0 |
| negative_nondeterministic_output | -1 | negative (weight < 0 or negative_ name) | no nondeterministic documents observed, nondeterministic_output | _new_negative_owner | 1/0 |
| negative_rebinds_verifier_dependencies | -1 | negative (weight < 0 or negative_ name) | no delivered shadow module or startup hook, rebinds_verifier_dependencies | _new_negative_owner | 1/0 |

TS-26 duplicate candidates (same observable AND same logic): none

## 2. TS-13 multi-assert hints

- artifact_set_exists_and_parses: 3 asserts, 0 and-chained comparisons
- control_values_on_hidden_extracts: 14 asserts, 2 and-chained comparisons
- canonical_serialization_on_hidden_extracts: 4 asserts, 0 and-chained comparisons

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5, negative_reads_training_corpus_at_runtime -1 | - | 6 | FAIL |
| third-party or network import | negative_external_dependency -3 | - | 3 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -1 | - | 1 | PASS |
| nondeterministic output | negative_nondeterministic_output -1 | - | 1 | PASS |
| rebinds verifier dependencies | negative_rebinds_verifier_dependencies -1 | - | 1 | PASS |
| UNMATCHED act (name it by hand) | - | R6 -5, R8 -3 | 8 | FAIL |
| claims a check passed that its output contradicts (honesty) | - | R7 -5 | 5 | PASS |
| naming or reading grader files | - | R17 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 76 (88.4%)
- isolated: 0 (0.0%)
- mutation: 0 (0.0%)
- shipped_only: 10 (11.6%)
- G3: hidden or mutated reruns 88.4% (>= 30%); isolated+mutation 0.0%, whole-document 0.0%, shipped-only 11.6% (info, no cap)

## 5. Caps and weights

- tests 34, criteria 17 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): artifact_set_exists_and_parses, canonical_serialization_on_hidden_extracts
- judge J1 hints (criterion quotes a figure): R1, R2, R3, R4, R13
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: none
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 88.4% PASS
- G3 isolated / shipped-only (info, no cap): 0.0% / 11.6%
- tests >= 10 (no cap): 34 PASS
- criteria >= 8 (no cap): 17 PASS
- judge mode batched: batched

## Hand recheck - 3302dbb

The raw AL-28 hints above are retained, not suppressed. The hardcoding/runtime sum of 6 is unreachable: test_output.py:3432-3437 gives existing hardcoding (-5) and external-dependency (-3) owners priority and returns before any new negative can fire. Then at most one new -1 owner is selected. The unmatched R6/R8 sum of 8 groups different acts: judge.toml:79 is a final-reply figure disagreeing with an artifact (-5), while :105 is the program opening outside its supplied directories (-3). No same-act sum of 8 follows. Runtime -1 plus applicable outside-directory R8 -3 is at most -4. R17 alone owns grader reads; these probes do not read or hide grader paths. All eight fresh lanes show all six negatives silent; each planted witness fires only its intended new owner. No judge or existing penalty was edited.

## Lessons for the master
Static name buckets do not model stand-down control flow | no change: retain the raw hints and record the executable ownership recheck.
