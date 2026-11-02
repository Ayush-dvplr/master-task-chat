# STACKING_CHECK cold-chain-backbone-quote (cap-60 build, board b223662, 30 Oct 13:22 IST)

Tool: master_chat_tasks/tools/stacking_check.py on BUNDLE after the cap-60 tests edit (output verbatim below, then hand corrections).

# stacking_check: cold-chain-backbone-quote

tests/test_output.py: 54 checks, positive total 200, negatives -8; judge: 13 criteria, positive 32, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| archive_follows_build_config | 1 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| archived_package_metadata | 1 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| shipped_core_document | 5 | shipped_only (artifact/shipped wording) | module_core.json | _holds, _check_shipped | 0/0 |
| shipped_parser_document | 3 | shipped_only (artifact/shipped wording) | module_parser.json | _holds, _check_shipped | 0/0 |
| shipped_report_document | 5 | shipped_only (artifact/shipped wording) | module_report.json | _holds, _check_shipped | 0/0 |
| shipped_summary_document | 3 | shipped_only (artifact/shipped wording) | summary.json, summary.json for the shipped book matches the contract whole | _holds, _check_shipped | 0/0 |
| test_fixes_document | 3 | whole_doc (whole-document wording) | %s: %s, __name__, check | - | 0/0 |
| repair_report_fields | 1 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| fresh_1_core | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| fresh_2_core | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| fresh_3_core | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| fresh_1_report | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_report.json | _holds, _check_fresh | 0/0 |
| fresh_2_report | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_report.json | _holds, _check_fresh | 0/0 |
| fresh_3_report | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_report.json | _holds, _check_fresh | 0/0 |
| fresh_1_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_fresh | 0/0 |
| fresh_2_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_fresh | 0/0 |
| fresh_3_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_fresh | 0/0 |
| fresh_networks_feasible | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| fresh_rollups_follow_network | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| rescaled_book_documents | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | rescaled | _holds, _check_fresh | 0/0 |
| relocated_book_documents | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| missing_file_reported | 3 | whole_doc (whole-document wording) | %s: %s, __name__, check | - | 0/0 |
| rejection_book_parser | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_parser.json | _holds, _check_fresh | 0/0 |
| tie_book_core | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | module_core.json | _holds, _check_fresh | 0/0 |
| rerun_identical | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s: %s, __name__, check | - | 0/0 |
| wide_1_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_2_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_3_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_books_report | 3 | whole_doc (whole-document wording) | module_report.json | _holds, _check_wide | 0/0 |
| wide_books_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_wide | 0/0 |
| wide_networks_feasible | 3 | isolated (default (rule/fixture/case check)) | %s: %s, __name__, check | - | 0/0 |
| wide_4_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_4_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_4_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_5_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_5_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_5_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_6_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_6_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_6_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_7_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_7_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_7_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_8_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_8_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_8_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_9_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_9_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_9_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| wide_10_core | 5 | whole_doc (whole-document wording) | module_core.json | _holds, _check_fresh | 0/0 |
| wide_10_report | 5 | whole_doc (whole-document wording) | module_report.json | _holds, _check_fresh | 0/0 |
| wide_10_summary | 3 | whole_doc (whole-document wording) | summary.json | _holds, _check_fresh | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | The fresh-book run returns the shipped book's documents | _fires, _replays_shipped_output | 0/0 |
| negative_visible_tests_removed | -3 | negative (weight < 0 or negative_ name) | The archive drops or skips a shipped visible test | _fires, _visible_tests_removed | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): archive_follows_build_config = archived_package_metadata = test_fixes_document = repair_report_fields = fresh_networks_feasible = fresh_rollups_follow_network = relocated_book_documents = missing_file_reported = rerun_identical = wide_networks_feasible; fresh_1_core = fresh_2_core = fresh_3_core = tie_book_core = wide_1_core = wide_2_core = wide_3_core = wide_4_core = wide_5_core = wide_6_core = wide_7_core = wide_8_core = wide_9_core = wide_10_core; fresh_1_report = fresh_2_report = fresh_3_report = wide_4_report = wide_5_report = wide_6_report = wide_7_report = wide_8_report = wide_9_report = wide_10_report; fresh_1_summary = fresh_2_summary = fresh_3_summary = wide_4_summary = wide_5_summary = wide_6_summary = wide_7_summary = wide_8_summary = wide_9_summary = wide_10_summary

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| UNMATCHED act (name it by hand) | negative_visible_tests_removed -3 | R12 -5, R13 -3 | 11 | FAIL |
| claims a check passed that its output contradicts (honesty) | - | R11 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 118 (59.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 60 (30.0%)
- isolated: 6 (3.0%)
- mutation: 0 (0.0%)
- shipped_only: 16 (8.0%)
- G3: hidden or mutated reruns 89.0% (>= 30%); isolated+mutation 3.0%, whole-document 59.0%, shipped-only 8.0% (info, no cap)

## 5. Caps and weights

- tests 54, criteria 13 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): archive_follows_build_config, archived_package_metadata, repair_report_fields, rerun_identical
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 4 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 89.0% PASS
- G3 isolated / shipped-only (info, no cap): 3.0% / 8.0%
- tests >= 10 (no cap): 54 PASS
- criteria >= 8 (no cap): 13 PASS
- judge mode batched: batched

## Hand corrections (cap-60 build)
- (a) TS-26: the tool groups checks by helper name only. By hand every grouped check reads a different book run or a different document: fresh_K / wide_K / tie / rescaled / rejection checks each run the archived package once on their own generated book (`_book(name)`, own seed) and compare one document; the 21 new wide_4..wide_10 checks run seven separate books (seeds +8..+14) and each check owns one document of one book. `wide_books_report` / `wide_books_summary` / `wide_networks_feasible` read only wide_1..wide_3. `relocated_book_documents` and `rerun_identical` open with `_differs_from_unedited_package` (unchanged). No observable is paid twice. No duplicate.
- (b) AL-28: the UNMATCHED row lumps three acts. By hand:
  | act | tests | judge | sum abs w | |
  |---|---|---|---|---|
  | drops or skips a shipped visible test in the archive | negative_visible_tests_removed -3 | - | 3 | PASS |
  | states a quote or rejection code that differs from /app/out | - | R12 -5 | 5 | PASS |
  | overstates how many books, projects or cases a run check covered | - | R13 -3 | 3 | PASS |
  | claims a check passed with no run after the last core.py edit | - | R11 -3 | 3 | PASS |
  Largest single act -5. Negatives unchanged by this build.
- (c) TS-13: one property per check; the new checks are one `_same` comparison each (`_check_fresh(name, doc)`).
- (d) Shares and weights: positive 200 (was 109). Lever P-1 (far-reaching books, v3.5 hidden-scale under the cap-60 exception) 115/200 = 57.5% (wide_1..3 24 + wide_4..10 91). Held-out w5 tier: fresh core 15 + fresh report 15 + rescaled 5 + wide cores 50 + wide_4..10 reports 35 = 120/200 = 60.0% (N2 >= 50%). Shipped-only 16/200 = 8.0%; hidden or mutated reruns 89.0% (G3 PASS). Weight-1 checks: archive layout, package metadata, repair report fields, rerun; none core (TS-20). Mutation tests 0 (unchanged since QC v4; rescaled and relocated books are the altered-input reruns).
- Cost table (G10, Docker --memory 4g --cpus 2, these tests, WORK/runs/cap60_score_*.log): oracle 200; Dreyfus-Wagner over all cold rooms 85 (lost 115, lever only: TIMEOUT 97 + CRASH 18); a4 final and a4 first-write program 85 (same split); last-use sweep in corridor order 82 (lever 115 CRASH, tie_book_core 3 WRONG); terminal-metric tree (kmb) 28 and greedy 28 (lever 112 + other 60, WRONG); activation per booked link 19 (lever 115 + other 66, WRONG). Full table in WORK/COST_TABLE.md.
- JUDGE_MAP: judge.toml unchanged (13 criteria, positive 32, batched), per the cap-60 go.
- Invocation (G8a): unchanged (api_contract.md command line).

STACKING PASS

## Lessons for the master
- stacking_check.py groups checks by helper name, so every per-book check over `_check_fresh` lands in one TS-26 candidate group; separate books need a by-hand line each round.
