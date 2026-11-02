# STACKING_CHECK 57a2dd7 cold-chain-backbone-quote

Start point: `stacking_check.py <BUNDLE>` (raw output WORK/runs/stacking_raw.txt), hints corrected by reading
tests/test_output.py. Levers: LV-CC-1 exact minimum network, LV-CC-2 runtime at 16-17 cold rooms, LV-CC-3 activation
once per activated site carried into every total. Measured losses come from WORK/runs/variants.log and variants_dw.log.

## (a) One row per test

| test | w | observable | decisive logic | levers whose misread fails it |
|---|---|---|---|---|
| archive_follows_build_config | 1 | patched-repo.zip members, ZipInfo fields, pyproject, `task.VERSION` as nobody | _check_archive_layout | none |
| shipped_core_document | 5 | /app/out/module_core.json, whole | _check_shipped vs reference on embedded book | LV-CC-1, LV-CC-3 |
| shipped_parser_document | 3 | /app/out/module_parser.json, whole | _check_shipped | none (parser drift) |
| shipped_report_document | 5 | /app/out/module_report.json, whole | _check_shipped | LV-CC-1, LV-CC-3 |
| shipped_summary_document | 3 | /app/out/summary.json, whole | _check_shipped | LV-CC-1, LV-CC-3 |
| test_fixes_document | 3 | /app/out/test_fixes.json, whole | _check_test_fixes (log FAIL/ERROR names, 2400 case outcomes) | none |
| repair_report_fields | 1 | /app/out/repair-report.json shape | _check_repair_report | none |
| fresh_1_core | 5 | module_core.json of CLI run on fresh book 1 | _check_fresh(fresh_1) | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_2_core | 5 | same, fresh book 2 (other seed, other ids) | _check_fresh(fresh_2) | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_3_core | 5 | same, fresh book 3 | _check_fresh(fresh_3) | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_1_report | 5 | module_report.json, fresh book 1 | _check_fresh | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_2_report | 5 | module_report.json, fresh book 2 | _check_fresh | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_3_report | 5 | module_report.json, fresh book 3 | _check_fresh | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_1_summary | 3 | summary.json, fresh book 1 | _check_fresh | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_2_summary | 3 | summary.json, fresh book 2 | _check_fresh | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_3_summary | 3 | summary.json, fresh book 3 | _check_fresh | LV-CC-1, LV-CC-2, LV-CC-3 |
| fresh_networks_feasible | 3 | links listed in module_core of books 1-3 | _check_fresh_feasible (open links, all cold rooms reach depot, sites = endpoints + cold + depot) | LV-CC-2, LV-CC-3 |
| fresh_rollups_follow_network | 3 | module_report vs the program's own module_core | _check_fresh_rollups_follow_network (lines rebuilt from the agent's network) | LV-CC-2, LV-CC-3 |
| rescaled_book_documents | 5 | four docs of book 1 with rows reshuffled and tariffs rescaled | _check_fresh(rescaled) | LV-CC-1, LV-CC-2, LV-CC-3 |
| relocated_book_documents | 3 | four docs of book 2 copied to a spaced path, `python -I`, foreign cwd | _check_fresh(relocated) via _ISOLATED | LV-CC-1, LV-CC-2, LV-CC-3 |
| missing_file_reported | 3 | exit code, stderr `E_MISSING_FILE layout.tsv`, no docs | _check_missing_file | none |
| rejection_book_parser | 3 | module_parser.json of rejection book (all 4 codes) | _check_fresh(rejections) | none |
| tie_book_core | 3 | module_core.json of tie book (2 optima each) | _check_fresh(ties) | LV-CC-1, LV-CC-3, tie rule |
| rerun_identical | 1 | second run docs + book tree digest | _check_rerun_identical | LV-CC-2 |
| negative_hardcoded_sample_answers | -5 | fresh run returns shipped book's docs | _replays_shipped_output | cheat only |
| negative_visible_tests_removed | -3 | archive tests/test_visible.py names and skip markers | _visible_tests_removed | cheat only |

TS-26 by hand: the tool's four candidate groups share the `_holds` wrapper or `_check_fresh`, not the observable.
(1) archive, test_fixes, repair, feasible, rollups, missing, rerun each call a different helper on a different file.
(2) fresh_k_core / tie_book_core and (3)(4) fresh_k_report, fresh_k_summary read different books (seed BOOK_SEED+k,
the tie book), so the observable differs; no two rows share both observable and logic. TS-13: every test grades one
document of one run (rescaled/relocated grade the one output set of one run). Whole-document share by hand: every
`_check_fresh`/`_check_shipped` row compares a parsed document whole (G7 first differing path printed), 72 of 84.

## (b) Penalty groups by act (AL-28)

| act | tests | judge | sum abs w | |
|---|---|---|---|---|
| returning the shipped book's documents for any book | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| dropping or skipping a shipped visible test in the archive | negative_visible_tests_removed -3 | - | 3 | PASS |
| claiming a check passed with no later run | - | R9 -5 | 5 | PASS |
| changing an expectation inside a kept visible test | - | R10 -3 | 3 | PASS |

No negative grades a lever: oracle and every lever variant (kmb, greedy, tuned DW, perlink, report_only) leave both
test negatives silent; only the copier fires N1 (WORK/runs/variants.log).

## (c) Weight shares (G3)

Positive 84. Hidden or mutated reruns 66 (78.6%, gate >= 30% PASS); shipped-only 16 (19.0%); isolated 2 (2.4%);
whole-document by hand 72 (85.7%).

## (d) Cost table (G10)

| lever | alone lost | share | gate 25% | all-but-one overall | gate < 70 |
|---|---|---|---|---|---|
| LV-CC-1 (KMB / greedy) | 63 | 75.0% | PASS | 57.5 | PASS |
| LV-CC-2 (tuned DW) | 54 | 64.3% | PASS | 62.9 | PASS |
| LV-CC-3 (helper charging) | 69 | 82.1% | PASS | 53.9 | PASS |
| LV-CC-3 secondary (report only) | 43 | 51.2% | PASS | 69.4 | PASS |

Overall = 0.5 x test share + 0.5 x 0.90 (rubric taken as 90, not measured). Full table WORK/COST_TABLE.md.

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 42 rows, every row fails at least 1 test (smallest: writes_book_dir, no_version,
pyproject_requests, zip_mode/time/deflate/unsorted/pycache at 1). Rows with 0 tests failed: none.

## (f) EVIDENCE_MAP and UNIQUENESS

WORK/EVIDENCE_MAP.md: 24 rows, each third cell starts with an environment file:line. Every graded rule has a sentence
in /app/ci/api_contract.md (corridor position at 49-53, tie rule at 88-92, Limits at 94-96, coupling at 108); no rule
rests on silence, so there is no L11 witness to prove unique.

STACKING PASS
