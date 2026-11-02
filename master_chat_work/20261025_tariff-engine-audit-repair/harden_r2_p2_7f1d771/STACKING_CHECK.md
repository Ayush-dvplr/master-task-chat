# STACKING_CHECK: tariff-engine-audit-repair, harden round 2 Phase 2 (7f1d771)

Source: `stacking_check.py BUNDLE` output kept in `stacking_raw.txt` (39 checks, 157 positive, -8 negative;
judge 14 criteria, 33 positive, batched), corrected below by reading `tests/test_output.py` (generated from
WORK/test_output.src.py). Lever columns come from the measured single-lever variants (`g10b/g10.json`,
`g10c/g10.json`, WORK/measure_variants.py): L11 = `L11_first_plan` (same rows as `L11_last_plan`),
N1 = `N1_two_passes`, N1n = `N1_no_share`, N2 = `N2_start_month`, N2p = `N2_period_length`,
N3 = `N3_per_meter`, TR4 = `V_qty_coerce`. No reflex column: this round has no reflex gate (the master
issues three blind reads before the next probe, LEVER_RULES section 6).

## (a) One row per test

| test | w | observable | decisive logic | levers whose misread fails it |
|---|---|---|---|---|
| archive_and_metadata_follow_build_config | 3 | patched-repo.zip members, timestamps, compression, mode; pyproject; tariff.VERSION; imports | build_config.json + package_manifest.json + stdlib-only AST scan | - |
| delivered_visible_tests_pass | 3 | unittest result of delivered tests/test_visible.py | unittest discover in extracted archive | - |
| corrected_tests_name_the_changed_tests | 3 | test_fixes.json corrected_tests | sorted list within changed test functions, covers CORRECTED | - |
| regression_rows_match_contract | 3 | repair-report regression rows (2000) | each row actual/expected vs _Ledger on case corpus | N1n, N2p |
| module_notes_follow_contract | 1 | module_core/parser/report.json | key sets, lint_errors vs lint_report.json, contract_terms | - |
| summary_lists_inputs_and_artifacts | 1 | summary.json | key set, inputs_used vs shipped ci names, artifacts count 7 | - |
| repair_report_and_failing_cases | 1 | repair-report.json shape + test_fixes previously_failing | previously_failing vs failing_tests.log FAIL/ERROR names | - |
| shipped_exceptions_exact | 3 | shipped corpus: exception rows | _check_exceptions vs _Ledger | TR4 |
| shipped_standing_lines_exact | 5 | shipped corpus: standing lines | _check_lines vs _Ledger | L11, N2p |
| shipped_energy_and_settlement_exact | 5 | shipped corpus: energy lines + subtotal/credit/total | _check_lines + _check_settlement vs _Ledger | L11, N1n, N2p, TR4 |
| fresh_exceptions_exact | 3 | fresh corpus: exception rows | _check_exceptions vs _Ledger | TR4 |
| fresh_energy_lines_exact | 5 | fresh corpus: energy lines | _check_lines vs _Ledger | N1, N1n, TR4 |
| fresh_standing_lines_exact | 5 | fresh corpus: standing lines | _check_lines vs _Ledger | N2, N2p |
| fresh_subtotals_exact | 5 | fresh corpus: invoice heads (account, period, plan, subtotal) | _check_heads vs _Ledger | N1, N1n, N2, N2p, TR4 |
| fresh_credits_and_totals_exact | 5 | fresh corpus: credit and total | _check_settlement vs _Ledger | N1, N1n, N2, N2p, TR4 |
| rescaled_energy_lines_exact | 5 | rescaled corpus: energy lines | _check_lines vs _Ledger | N1, N1n, TR4 |
| rescaled_standing_lines_exact | 5 | rescaled corpus: standing lines | _check_lines vs _Ledger | N2, N2p |
| rescaled_subtotals_exact | 5 | rescaled corpus: invoice heads | _check_heads vs _Ledger | N1, N1n, N2, N2p, TR4 |
| rescaled_credits_and_totals_exact | 5 | rescaled corpus: credit and total | _check_settlement vs _Ledger | N1, N1n, N2, N2p, TR4 |
| relocated_lines_exact | 5 | relocated corpus: energy + standing lines | _check_lines vs _Ledger | N1, N1n, N3, TR4 |
| relocated_subtotals_exact | 5 | relocated corpus: invoice heads | _check_heads vs _Ledger | N1, N1n, N3, TR4 |
| relocated_credits_and_totals_exact | 5 | relocated corpus: credit and total | _check_settlement vs _Ledger | N1, N1n, N3, TR4 |
| rotated_lines_exact | 5 | rotated corpus: energy + standing lines | _check_lines vs _Ledger | N1, N1n, N3, TR4 |
| rotated_subtotals_exact | 5 | rotated corpus: invoice heads | _check_heads vs _Ledger | N1, N1n, N3, TR4 |
| rotated_credits_and_totals_exact | 5 | rotated corpus: credit and total | _check_settlement vs _Ledger | N1, N1n, N3, TR4 |
| recoded_lines_exact | 5 | recoded corpus (H7, L11 owned): energy + standing lines | _check_lines vs _Ledger (plan resolved by key or trimmed `codes`) | L11, TR4 |
| recoded_subtotals_exact | 5 | recoded corpus: invoice heads (plan = trimmed row value) | _check_heads vs _Ledger | L11, TR4 (and M62 output-plan mutant) |
| recoded_credits_and_totals_exact | 5 | recoded corpus: credit and total | _check_settlement vs _Ledger | L11, TR4 |
| renamed_lines_exact | 5 | renamed corpus (fresh codes in card and rows, plan order rotated, rows rotated): lines | _check_lines vs _Ledger | L11, TR4 |
| renamed_subtotals_exact | 5 | renamed corpus: invoice heads | _check_heads vs _Ledger | L11, TR4 (and M62) |
| renamed_credits_and_totals_exact | 5 | renamed corpus: credit and total | _check_settlement vs _Ledger | L11, TR4 |
| api_energy_lines_exact | 5 | api corpus: energy lines | _check_lines vs _Ledger | N3, TR4 |
| api_standing_lines_exact | 5 | api corpus: standing lines | _check_lines vs _Ledger | N2, N2p |
| api_subtotals_exact | 5 | api corpus: invoice heads | _check_heads vs _Ledger | N2, N2p, N3, TR4 |
| api_credits_and_totals_exact | 5 | api corpus: credit and total | _check_settlement vs _Ledger | N2, N2p, N3, TR4 |
| missing_source_is_named | 3 | CLI on fresh corpus with two inputs removed | exit 2, empty stdout, stderr `missing input: meter_reads.jsonl` | - |
| two_runs_are_identical | 3 | two CLI documents on fresh corpus | byte equality | - |
| negative_hardcoded_sample_answers | -5 | delivered package source | shipped invoice figures copied into the code | none (cheating act; fired only by C_hardcode_shipped) |
| negative_visible_test_removed | -3 | delivered tests/test_visible.py | a shipped visible test function missing | none (cheating act) |

Tool hint corrected: the TS-26 "duplicate group" (eight deliverable checks with no literals) is a static
artefact; each reads a different artifact (zip, unittest run, test_fixes.json, regression rows, module notes,
summary.json, repair-report.json, CLI stderr), so no two rows share observable and logic. Figure checks share
helpers (`_check_lines`, `_check_heads`, `_check_settlement`) but each owns one corpus and one line kind or
head. The six new L11 rows own two corpora (recoded, renamed) that no other row reads. TS-26 PASS, TS-13 PASS.

## (b) Penalty groups by act (AL-28, |w| <= 5 per act)

| act | tests | judge | sum |
|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 PASS |
| deleting or skipping a shipped visible test | negative_visible_test_removed -3 | - | 3 PASS |
| running the package on an edited copy of api_contract.md | - | R10 -3 | 3 PASS |
| claiming a check passed that its output contradicts | - | R9 -5 | 5 PASS |
| naming or reading grader files | - | R11 -5 | 5 PASS |

Tool hint corrected: it grouped negative_visible_test_removed with R10 as one "UNMATCHED act" (sum 6); they are
different acts (editing the delivered tests vs. writing the contract file). No negative grades a lever: no
lever variant and no mutant (mutants2, 61 of 61) fires either negative test. AL-28 PASS.

## (c) Weight shares (G3) and caps

The tool labels rescaled, relocated, rotated, recoded, renamed and api checks "isolated" (19.7% hidden) because
their names lack `fresh`/`_hard`. By code, every one re-runs the delivered program on a hidden generated corpus
(`_corpus_texts`: rescaled, rotated and renamed are mutated copies of fresh, relocated and recoded; relocated
runs `python -I` from a moved copy; api calls `tariff.build_invoices`).

| class (by code) | checks | points | share of 157 |
|---|---|---|---|
| hidden or mutated reruns (fresh 23, rescaled 20, relocated 15, rotated 15, recoded 15, renamed 15, api 20, two_runs 3) | 26 | 126 | 80.3% |
| of which mutated (rescaled, rotated, renamed) | 10 | 50 | 31.8% |
| shipped data (shipped_* 13, summary 1) | 4 | 14 | 8.9% |
| deliverable / artifact checks (archive, visible, corrected, regression, notes, repair, missing) | 7 | 17 | 10.8% |
| whole-corpus exact figure checks (shipped 13, fresh 23, rescaled 20, relocated 15, rotated 15, recoded 15, renamed 15, api 20) | 28 | 136 | 86.6% |

G3 (hidden or mutated reruns >= 30%, one per downstream family): 80.3% PASS; each family (fresh, rescaled,
relocated, rotated, recoded, renamed, api) has its own rows. Weight-1 checks (module notes, summary, repair
report) are not core (TS-20 PASS). Tests 39 >= 10, criteria 14 >= 8, judge mode batched. Judge conduct
criteria R4, R5, R12, R13, R14 (J2; R14 = recompute of a code-named invoice, solve.py prints `check R14 ok`);
R7 is the J4 code-quality criterion. No count caps; kit WARN for more than 35 tests is recorded, not acted on.

## (d) Cost table (G10)

Full table: `WORK/COST_TABLE.md` (bundles/_work/tariff-engine-audit-repair/COST_TABLE.md).

| lever | habit slip | points lost alone | >= 25% | all but one right, overall (rubric 90 / measured 3.33) |
|---|---|---|---|---|
| L11 plan codes | unknown plan value falls back to the first (or last) plan | 40 (25.5%) | PASS | 82.3 FAIL / 38.9 PASS |
| L11 | key-only lookup / untrimmed codes | loud crash (KeyError / ValueError on shipped data) | n/a | the program fails at its first run on shipped data |
| N1 allowance re-share | shared once or twice | 60 (38.2%) | PASS | 75.9 FAIL / 32.6 PASS |
| N1 | no re-share | 68 (43.3%) | PASS | 73.3 FAIL / 30.0 PASS |
| N2 calendar month | days of the start month | 45 (28.7%) | PASS | 80.7 FAIL / 37.3 PASS |
| N2 | billing-period length | 58 (36.9%) | PASS | 76.5 FAIL / 33.2 PASS |
| N3 account tier position | tiers restart per meter | 45 (28.7%) | PASS | 80.7 FAIL / 37.3 PASS |

Every counted lever alone costs >= 25% of test points; L11 sits at 25.5%, inside the master's 25-45% band.
One-fact-wrong (CL-4, FC:491): one code-named recoded invoice one cent off 127/157 (lost 30); one shipped
code-named invoice 152/157; fresh 127/157; api 142/157. The "all but one right < 70" row passes with the
probe-2 measured rubric (3.33) and fails with the default 90; both are reported.

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 61 rows (M01-M60, M62; contract lines of the 194-line api_contract.md and the
rate_card.json witness lines), every row fails at least 1 positive test (raw `mutants2/`), none fires a
negative. L11 rows: M58 first plan 8 tests, M59 last plan 8, M60 untrimmed codes 8, M62 output plan = key 2.
L11 is a lookup, not an ordering or tie-break, so AL-27 needs no planted tie; the separating cases (codes
sharing a stem, a padded code, a code not first or last in its list) are planted per corpus and asserted.
Rows with 0 tests failed: none.

## (f) EVIDENCE_MAP and UNIQUENESS

`WORK/EVIDENCE_MAP.md`: L11 row names the tests (shipped_standing_lines_exact,
shipped_energy_and_settlement_exact, recoded x3, renamed x3), the shipped fact `rate_card.json:7-10, 29-31,
50-53, 72-74, 93, 108-110` (the `codes` lists) governing `billing_periods.csv` (503 of 2000 rows name a plan
by code, for example :2 `T3415`, :159 `T2319`), and the wrong readings it contradicts with counts. N1-N3 rows
point at their sentences (:46-48/:124-130, :43/:51/:115-119, :38-40/:107-113); the invoice `plan` string is
a stated format (:101-103).
`WORK/UNIQUENESS.md`: 18 readings fitted to the shipped witness, the recoded and renamed corpora and 80 extra
generated witness sets: only the R1 class fits all of them (key, else the one entry whose trimmed `codes`
holds the value; the looser variants R1b/R14/R16/R17 choose the same entry on every set and give
byte-identical documents). Verdict ONE. No rule sentence for codes exists in instruction.md, api_contract.md,
README, docstrings or visible tests (grep `codes` over environment/ and instruction.md: rate_card.json only).

STACKING PASS
