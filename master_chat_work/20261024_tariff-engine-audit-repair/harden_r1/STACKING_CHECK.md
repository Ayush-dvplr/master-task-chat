# STACKING_CHECK: tariff-engine-audit-repair, harden round 1 (d62ffe6)

Source: `stacking_check.py BUNDLE` output kept in `stacking_raw.txt` (33 checks, 127 positive, -8 negative;
judge 13 criteria, 30 positive, batched), corrected below by reading `tests/test_output.py`
(generated from WORK/test_output.src.py). Lever columns come from the measured single-lever variants
(`mutants/variants.json`): N1 = `N1_two_passes`, N2 = `N2_start_month`, N2p = `N2_period_length`
(probe-1 reading), N3 = `N3_per_meter`, TR4 = `V_qty_coerce`, TR2 = `V_half_up`, cred = `V_credit_rounded`.
Reflex = probe-1 agent program (`agent_program/`) on the round-1 tests (`reflex_agent_checks.json`).

## (a) One row per test

| test | w | observable | decisive logic | levers whose misread fails it | reflex |
|---|---|---|---|---|---|
| archive_and_metadata_follow_build_config | 3 | patched-repo.zip members, timestamps, compression, mode; pyproject; tariff.VERSION; imports | build_config.json + package_manifest.json + stdlib-only AST scan | - | pass |
| delivered_visible_tests_pass | 3 | unittest result of delivered tests/test_visible.py | unittest discover in extracted archive | - | pass |
| corrected_tests_name_the_changed_tests | 3 | test_fixes.json corrected_tests | sorted list within changed test functions, covers CORRECTED | - | pass |
| regression_rows_match_contract | 3 | repair-report regression rows (2000) | each row actual/expected vs _Ledger on case corpus | N2p | FAIL |
| module_notes_follow_contract | 1 | module_core/parser/report.json | key sets, lint_errors vs lint_report.json, contract_terms | - | pass |
| summary_lists_inputs_and_artifacts | 1 | summary.json | key set, inputs_used vs shipped ci names, artifacts list, count 7 | - | pass |
| repair_report_and_failing_cases | 1 | repair-report.json shape + test_fixes previously_failing | previously_failing vs failing_tests.log FAIL/ERROR names | - | FAIL |
| shipped_exceptions_exact | 3 | shipped corpus: exception rows | _check_exceptions vs _Ledger | TR4 | pass |
| shipped_standing_lines_exact | 5 | shipped corpus: standing lines | _check_lines vs _Ledger | N2p | FAIL |
| shipped_energy_and_settlement_exact | 5 | shipped corpus: energy lines + subtotal/credit/total | _check_lines + _check_settlement vs _Ledger | N2p, TR4 | FAIL |
| fresh_exceptions_exact | 3 | fresh corpus: exception rows | _check_exceptions vs _Ledger | TR4 | pass |
| fresh_energy_lines_exact | 5 | fresh corpus: energy lines | _check_lines vs _Ledger | N1, TR4, TR2 | FAIL |
| fresh_standing_lines_exact | 5 | fresh corpus: standing lines | _check_lines vs _Ledger | N2, N2p | FAIL |
| fresh_subtotals_exact | 5 | fresh corpus: invoice heads (account, period, plan, subtotal) | _check_heads vs _Ledger | N1, N2, N2p, TR4, TR2 | FAIL |
| fresh_credits_and_totals_exact | 5 | fresh corpus: credit and total | _check_settlement vs _Ledger | N1, N2, N2p, TR4, TR2, cred | FAIL |
| rescaled_energy_lines_exact | 5 | rescaled corpus: energy lines | _check_lines vs _Ledger | N1, TR4, TR2 | FAIL |
| rescaled_standing_lines_exact | 5 | rescaled corpus: standing lines | _check_lines vs _Ledger | N2, N2p | FAIL |
| rescaled_subtotals_exact | 5 | rescaled corpus: invoice heads (account, period, plan, subtotal) | _check_heads vs _Ledger | N1, N2, N2p, TR4, TR2 | FAIL |
| rescaled_credits_and_totals_exact | 5 | rescaled corpus: credit and total | _check_settlement vs _Ledger | N1, N2, N2p, TR4, TR2, cred | FAIL |
| relocated_lines_exact | 5 | relocated corpus: energy + standing lines | _check_lines vs _Ledger | N1, N3, TR4, TR2 | FAIL |
| relocated_subtotals_exact | 5 | relocated corpus: invoice heads (account, period, plan, subtotal) | _check_heads vs _Ledger | N1, N3, TR4, TR2 | FAIL |
| relocated_credits_and_totals_exact | 5 | relocated corpus: credit and total | _check_settlement vs _Ledger | N1, N3, TR4, TR2, cred | FAIL |
| rotated_lines_exact | 5 | rotated corpus: energy + standing lines | _check_lines vs _Ledger | N1, N3, TR4, TR2 | FAIL |
| rotated_subtotals_exact | 5 | rotated corpus: invoice heads (account, period, plan, subtotal) | _check_heads vs _Ledger | N1, N3, TR4, TR2 | FAIL |
| rotated_credits_and_totals_exact | 5 | rotated corpus: credit and total | _check_settlement vs _Ledger | N1, N3, TR4, TR2, cred | FAIL |
| api_energy_lines_exact | 5 | api corpus: energy lines | _check_lines vs _Ledger | N3, TR4, TR2 | FAIL |
| api_standing_lines_exact | 5 | api corpus: standing lines | _check_lines vs _Ledger | N2, N2p | FAIL |
| api_subtotals_exact | 5 | api corpus: invoice heads (account, period, plan, subtotal) | _check_heads vs _Ledger | N2, N2p, N3, TR4, TR2 | FAIL |
| api_credits_and_totals_exact | 5 | api corpus: credit and total | _check_settlement vs _Ledger | N2, N2p, N3, TR4, TR2, cred | FAIL |
| missing_source_is_named | 3 | CLI on fresh corpus with two inputs removed | exit 2, empty stdout, stderr `missing input: meter_reads.jsonl` | - | pass |
| two_runs_are_identical | 3 | two CLI documents on fresh corpus | byte equality | - | pass |
| negative_hardcoded_sample_answers | -5 | delivered package source | shipped invoice figures copied into the code | none (cheating act) | not fired |
| negative_visible_test_removed | -3 | delivered tests/test_visible.py | a shipped visible test function missing | none (cheating act) | not fired |

Tool hint corrected: the TS-26 "duplicate group" (eight deliverable checks with no literals) is a static
artefact; each reads a different artifact (zip, unittest run, test_fixes.json, regression rows, module
notes, summary.json, repair-report.json, CLI stderr), so no two rows share observable and logic. Figure
checks share helpers (`_check_lines`, `_check_heads`, `_check_settlement`) but each owns one corpus and one
line kind or head. TS-13: one property per test; `shipped_energy_and_settlement_exact` asserts the energy
lines and the settlement of the same shipped invoices (kept unchanged from the QC-passed build), every other
figure check asserts one line kind or one head field. TS-26 PASS, TS-13 PASS.

## (b) Penalty groups by act (AL-28, |w| <= 5 per act)

| act | tests | judge | sum |
|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 PASS |
| deleting or skipping a shipped visible test | negative_visible_test_removed -3 | - | 3 PASS |
| running the package on an edited copy of api_contract.md | - | R10 -3 | 3 PASS |
| claiming a check passed that its output contradicts | - | R9 -5 | 5 PASS |
| naming or reading grader files | - | R11 -5 | 5 PASS |

Tool hint corrected: it grouped negative_visible_test_removed with R10 as one "UNMATCHED act" (sum 6); they
are different acts (editing the delivered tests vs. writing the contract file). No negative grades a lever:
the lever columns of both negative tests are empty (not fired by any variant or by the reflex program).
AL-28 PASS.

## (c) Weight shares (G3) and caps

Tool classes are heuristic: it labels the rescaled (except energy), relocated, rotated and api checks
"isolated" because their names lack `fresh`/`_hard`. By code, every one of them re-runs the delivered
program on a hidden generated corpus (`_corpus_texts`: rescaled and rotated are mutated copies of fresh and
relocated; relocated runs `python -I` from a moved copy; api calls `tariff.build_invoices`).

| class (by code) | checks | points | share of 127 |
|---|---|---|---|
| hidden or mutated reruns (fresh 23, rescaled 20, relocated 15, rotated 15, api 20, two_runs 3) | 20 | 96 | 75.6% |
| of which mutated (rescaled, rotated) | 7 | 35 | 27.6% |
| shipped data (shipped_* 13, summary 1) | 4 | 14 | 11.0% |
| deliverable / artifact checks (archive, visible, corrected, regression, notes, repair, missing) | 7 | 17 | 13.4% |

G3 (hidden or mutated reruns >= 30%, one per downstream family): 75.6% PASS; every corpus family (fresh,
rescaled, relocated, rotated, api) has its own energy/standing/subtotal/credit rows. Weight-1 checks
(module notes, summary, repair report) are not core (TS-20 PASS). Tests 33 >= 10, criteria 13 >= 8,
judge mode batched. Judge conduct criteria R4, R5, R12, R13 (J2); R7 quotes a size figure (J4 code quality,
kept from build).

## (d) Cost table (G10)

Full table: `WORK/COST_TABLE.md` (bundles/_work/tariff-engine-audit-repair/COST_TABLE.md).

| lever | habit slip | points lost alone | >= 25% | all but one right, overall (rubric 90 / measured 62.5) |
|---|---|---|---|---|
| N1 allowance re-share (H7) | shared once or twice | 60 (47.2%) | PASS | 71.4 FAIL / 57.6 PASS |
| N2 calendar month (H3) | days of the start month | 45 (35.4%) | PASS | 77.3 FAIL / 63.5 PASS |
| N2 | billing-period length (probe-1 program) | 58 (45.7%) | PASS | 72.2 FAIL / 58.4 PASS |
| N3 account tier position (H6) | tiers restart per meter (probe-1 program) | 45 (35.4%) | PASS | 77.3 FAIL / 63.5 PASS |

Every counted lever alone costs >= 25% of test points. The "all but one right < 70" row passes with the
rubric measured on probe 1 (62.5, old 24-point rubric) and fails with the default 90; both are reported.
Differential fuzz on the probe-1 program (fuzz_r1/fuzz_r1.json): differs on N1 74/74, N2 74/74, N3 79/79
corpora, 0/79 lever-free; no counted lever is REVEALING. Uncounted gates: TR4 86, TR2 75, credit 25 points.

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 57 rows (M01-M57, contract lines of the 194-line api_contract.md), every row
fails at least 1 positive test, none fires a negative. Rows with 0 tests failed: none.

STACKING PASS
