# stacking_check: cohort-retention-reconciliation

tests/test_output.py: 24 checks, positive total 71, negatives -23; judge: 8 criteria, positive 19, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped_only (artifact/shipped wording) | /app/out/derive_report.py is missing, /app/out/ | - | 3/0 |
| hidden_cohorts | 5 | whole_doc (whole-document wording) | cohorts.json | _hidden_share | 0/0 |
| hidden_retention | 5 | whole_doc (whole-document wording) | retention.json | _hidden_share | 0/0 |
| hidden_survival | 5 | whole_doc (whole-document wording) | survival.json | _hidden_share | 0/0 |
| hidden_revenue | 5 | whole_doc (whole-document wording) | revenue.json | _hidden_share | 0/0 |
| hidden_segments | 5 | whole_doc (whole-document wording) | segments.json | _hidden_share | 0/0 |
| hidden_data_quality | 5 | whole_doc (whole-document wording) | data_quality.json | _hidden_share | 0/0 |
| hidden_reconciliation | 3 | whole_doc (whole-document wording) | reconciliation.json | _hidden_share | 0/0 |
| hidden_study_audit | 5 | whole_doc (whole-document wording) | study_audit.json | _hidden_share | 0/0 |
| hidden_per_cohort_documents | 5 | whole_doc (whole-document wording) | cohort_*.json | _note, _hidden_case, _emitted | 2/0 |
| hidden_serialization_is_canonical | 3 | format_hidden (format/determinism check on hidden inputs) | lacks a trailing newline, :, utf-8 | _hidden_case, _written_study, _format_faults | 2/0 |
| deterministic_rerun | 3 | format_hidden (format/determinism check on hidden inputs) | two runs wrote different file sets, differs between two runs | _study_files, _run_on, _written_study | 2/0 |
| spaced_values_and_dates_are_malformed | 3 | isolated (default (rule/fixture/case check)) | data_quality.json, events.csv | _fixture, _same_figure, _append_rows | 0/0 |
| identifiers_match_across_files | 3 | isolated (default (rule/fixture/case check)) | cohorts.json, accounts.csv, exclusions.csv, events.csv | _fixture, _same_figure, _append_rows | 0/0 |
| manifest_figures_follow_its_note | 3 | isolated (default (rule/fixture/case check)) | data_quality.json, events.csv, extract_manifest.json, accounts.csv | _fixture, _same_figure, _append_rows | 0/0 |
| balance_belongs_to_the_resolved_account | 3 | isolated (default (rule/fixture/case check)) | revenue.json, accounts.csv, account_merges.csv, events.csv | _fixture, _same_figure, _append_rows | 0/0 |
| segment_override_follows_the_resolved_account | 3 | isolated (default (rule/fixture/case check)) | revenue.json, accounts.csv, account_merges.csv, events.csv | _fixture, _same_figure, _append_rows | 0/0 |
| mutation_override_moves_only_weighted_revenue | 3 | mutation (mutation in name or description lead) | revenue.json | _fixture, _with_override, _same_figure | 2/0 |
| mutation_minimum_moves_cohort_sizes | 3 | mutation (mutation in name or description lead) | cohorts.json | _fixture, _with_minimum, _same_figure | 1/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | no hard-coded shipped answers detected | _hardcoded_shipped_answers | 1/0 |
| negative_reads_tests_or_reward_files | -5 | negative (weight < 0 or negative_ name) | no verifier paths referenced, /tests, test_output, /logs/ | _delivered_sources, _string_constants | 1/0 |
| negative_external_dependency_or_network | -3 | negative (weight < 0 or negative_ name) | only standard-library, non-network imports, . | _delivered_sources | 1/1 |
| negative_filename_dependent_behaviour | -5 | negative (weight < 0 or negative_ name) | cohorts.json | _study_files, _run_on, _hardcoded_shipped_answers | 1/2 |
| negative_reads_training_corpus_at_runtime | -5 | negative (weight < 0 or negative_ name) | cohorts.json | _study_files, _hardcoded_shipped_answers, _write_dir | 1/2 |

TS-26 duplicate candidates (same observable AND same logic): none

## 2. TS-13 multi-assert hints

- artifact_set_exists_and_parses: 3 asserts, 0 and-chained comparisons

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| naming or reading grader files | negative_reads_tests_or_reward_files -5 | - | 5 | PASS |
| third-party or network import | negative_external_dependency_or_network -3 | - | 3 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -5 | - | 5 | PASS |
| reads data beyond its argument | negative_reads_training_corpus_at_runtime -5 | - | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R8 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 43 (60.6%)
- format_hidden: 6 (8.5%)
- isolated: 15 (21.1%)
- mutation: 6 (8.5%)
- shipped_only: 1 (1.4%)
- G3: isolated+mutation 29.6% (<= 30%), whole-document 60.6% (>= 50%), shipped-only 1.4% (<= 5%)

## 5. Caps and weights

- tests 24, criteria 8 (cap 70 each; QC WARN above 35)
- weight-1 checks (TS-20: never on a core check): artifact_set_exists_and_parses
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: R1, R2, R3, R4, R5

## Verdict hints

- TS-26 duplicate candidates: none
- AL-28 groups <= 5: PASS
- G3 isolated+mutation <= 30%: 29.6% PASS
- G3 whole-document >= 50%: 60.6% PASS
- G3 shipped-only <= 5%: 1.4% PASS
- caps tests <= 70: 24 PASS
- caps criteria <= 70: 8 PASS
- judge mode batched: batched

## Lessons for the master
- New hidden-study rows moved no G3 share; the AL-27 fix is stacking-neutral.
