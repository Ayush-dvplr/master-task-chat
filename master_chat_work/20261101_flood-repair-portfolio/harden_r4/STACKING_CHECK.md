# stacking_check: flood-repair-portfolio

tests/test_output.py: 34 checks, positive total 108, negatives -8; judge: 12 criteria, positive 32, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| artifacts_present | 1 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_summary_matches | 3 | shipped_only (artifact/shipped wording) | summary.json | _holds, _shipped_documents | 0/0 |
| shipped_policy_audit_matches | 3 | shipped_only (artifact/shipped wording) | policy_audit.json | _holds, _shipped_documents | 0/0 |
| shipped_data_quality_matches | 3 | shipped_only (artifact/shipped wording) | data_quality.json | _holds, _shipped_documents | 0/0 |
| shipped_regions_match | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| shipped_segments_match | 3 | shipped_only (artifact/shipped wording) | - | - | 0/0 |
| h1_book_feasible | 3 | isolated (default (rule/fixture/case check)) | H1 | _holds, _feasible | 0/0 |
| h1_book_optimal | 5 | isolated (default (rule/fixture/case check)) | H1 | _holds, _optimal | 0/0 |
| h1_book_summary | 5 | whole_doc (whole-document wording) | summary.json | _holds, _hidden_documents | 0/0 |
| h1_book_policy_audit | 3 | whole_doc (whole-document wording) | policy_audit.json | _holds, _hidden_documents | 0/0 |
| h1_book_data_quality | 3 | whole_doc (whole-document wording) | data_quality.json | _holds, _hidden_documents | 0/0 |
| h1_book_regions | 3 | whole_doc (whole-document wording) | H1 | _holds, _hidden_documents | 0/0 |
| h1_book_segments | 3 | whole_doc (whole-document wording) | H1 | _holds, _hidden_documents | 0/0 |
| h2_book_feasible | 3 | isolated (default (rule/fixture/case check)) | H2 | _holds, _feasible | 0/0 |
| h2_book_optimal | 5 | isolated (default (rule/fixture/case check)) | H2 | _holds, _optimal | 0/0 |
| h2_book_summary | 5 | whole_doc (whole-document wording) | summary.json | _holds, _hidden_documents | 0/0 |
| h2_book_policy_audit | 3 | whole_doc (whole-document wording) | policy_audit.json | _holds, _hidden_documents | 0/0 |
| h2_book_data_quality | 3 | whole_doc (whole-document wording) | data_quality.json | _holds, _hidden_documents | 0/0 |
| h2_book_regions | 3 | whole_doc (whole-document wording) | H2 | _holds, _hidden_documents | 0/0 |
| h2_book_segments | 3 | whole_doc (whole-document wording) | H2 | _holds, _hidden_documents | 0/0 |
| h3_book_feasible | 3 | isolated (default (rule/fixture/case check)) | H3 | _holds, _feasible | 0/0 |
| h3_book_optimal | 5 | isolated (default (rule/fixture/case check)) | H3 | _holds, _optimal | 0/0 |
| h3_book_summary | 5 | whole_doc (whole-document wording) | summary.json | _holds, _hidden_documents | 0/0 |
| h3_book_policy_audit | 3 | whole_doc (whole-document wording) | policy_audit.json | _holds, _hidden_documents | 0/0 |
| h3_book_data_quality | 3 | whole_doc (whole-document wording) | data_quality.json | _holds, _hidden_documents | 0/0 |
| h3_book_regions | 3 | whole_doc (whole-document wording) | H3 | _holds, _hidden_documents | 0/0 |
| h3_book_segments | 3 | whole_doc (whole-document wording) | H3 | _holds, _hidden_documents | 0/0 |
| scaled_shuffled_summary_matches | 5 | whole_doc (whole-document wording) | summary.json | _holds, _hidden_documents | 0/0 |
| rotated_summary_matches | 3 | whole_doc (whole-document wording) | summary.json | _holds, _hidden_documents | 0/0 |
| relocated_copy_matches | 3 | whole_doc (whole-document wording) | - | - | 0/0 |
| missing_input_is_named | 3 | whole_doc (whole-document wording) | - | - | 0/0 |
| reruns_identical | 3 | shipped_only (format check, no hidden-input wording) | - | - | 0/0 |
| negative_program_reads_verifier_files | -5 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_hardcoded_sample_answers | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): artifacts_present = shipped_regions_match = shipped_segments_match = relocated_copy_matches = missing_input_is_named = reruns_identical; h1_book_summary = h2_book_summary = h3_book_summary = scaled_shuffled_summary_matches = rotated_summary_matches; h1_book_policy_audit = h2_book_policy_audit = h3_book_policy_audit; h1_book_data_quality = h2_book_data_quality = h3_book_data_quality; h1_book_regions = h1_book_segments; h2_book_regions = h2_book_segments; h3_book_regions = h3_book_segments

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| naming or reading grader files | negative_program_reads_verifier_files -5 | - | 5 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -3 | - | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R11 -5 | 5 | PASS |
| UNMATCHED act (name it by hand) | - | R12 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 65 (60.2%)
- format_hidden: 0 (0.0%)
- hidden_rows: 0 (0.0%)
- isolated: 24 (22.2%)
- mutation: 0 (0.0%)
- shipped_only: 19 (17.6%)
- G3: hidden or mutated reruns 60.2% (>= 30%); isolated+mutation 22.2%, whole-document 60.2%, shipped-only 17.6% (info, no cap)

## 5. Caps and weights

- tests 34, criteria 12 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): artifacts_present
- judge J1 hints (criterion quotes a figure): R5
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 7 group(s): CHECK BY HAND
- AL-28 groups <= 5: PASS
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 60.2% PASS
- G3 isolated / shipped-only (info, no cap): 22.2% / 17.6%
- tests >= 10 (no cap): 34 PASS
- criteria >= 8 (no cap): 12 PASS
- judge mode batched: batched
