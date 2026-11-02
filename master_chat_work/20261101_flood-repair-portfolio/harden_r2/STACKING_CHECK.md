# stacking_check: flood-repair-portfolio

tests/test_output.py: 34 checks, positive total 108, negatives -8; judge: 11 criteria, positive 30, mode batched. Static hints only; confirm by reading the code.

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

## 4. Weight shares (of positive test weight)

- whole_doc: 65 (60.2%)
- format_hidden: 0 (0.0%)
- hidden_rows: 0 (0.0%)
- isolated: 24 (22.2%)
- mutation: 0 (0.0%)
- shipped_only: 19 (17.6%)
- G3: hidden or mutated reruns 60.2% (>= 30%); isolated+mutation 22.2%, whole-document 60.2%, shipped-only 17.6% (info, no cap)

## 5. Caps and weights

- tests 34, criteria 11 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): artifacts_present
- judge J1 hints (criterion quotes a figure): R6, R8
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 7 group(s): CHECK BY HAND
- AL-28 groups <= 5: PASS
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 60.2% PASS
- G3 isolated / shipped-only (info, no cap): 22.2% / 17.6%
- tests >= 10 (no cap): 34 PASS
- criteria >= 8 (no cap): 11 PASS
- judge mode batched: batched

## Hand confirmation (cb8dada, 1 Nov, read tests/test_output.py L1253-1568)

Command: `python3 master_chat_tasks/tools/stacking_check.py <BUNDLE>` (rc 0). The 7 TS-26 groups are static hints from shared helper names; reading the bodies, none pays the same observable twice:

| group | why the observables differ |
|---|---|
| artifacts_present, shipped_regions_match, shipped_segments_match, relocated_copy_matches, missing_input_is_named, reruns_identical | different bodies: presence and JSON parse (L1253); shipped region docs vs expected (L1386, REGION_DOCS); shipped segment docs (L1391, SEGMENT_DOCS); program on moved copy of book M (L1324); exit 1 and ERROR MISSING_FILE line with files removed (L1307); two runs on H1 compared with each other, not with the expected answer (L1332) |
| h1/h2/h3_book_summary, scaled_shuffled_summary_matches, rotated_summary_matches | same document, five different books (H1, H2, H3 seeds 815301/822402/833503; MS, MR variants of M); each book is its own program run |
| h1/h2/h3_book_policy_audit | same document, three different books |
| h1/h2/h3_book_data_quality | same document, three different books |
| hN_book_regions vs hN_book_segments | different documents: four region files (REGION_DOCS) vs two segment files (SEGMENT_DOCS) |

Harden r2 change: only the _BOOKS literal (seeds, rep30 sizes) and _launch/_stop_untrusted changed; no registration, weight or check body changed (digest b1d31eb43bec1684 before and after). TS-26 on reruns_identical: it pays determinism; a program that times out on H1 loses it as well, which is why the lever counts 78 = 75 + 3.

Verdict: TS-26 PASS by hand; AL-28 PASS; G3 60.2% PASS; tests 34; criteria 11.

## Lessons for the master
- The stacking tool groups by helper name; per-book checks always look like duplicates and need the book list to clear.
