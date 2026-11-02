# STACKING_CHECK: tariff-engine-audit-repair, test-hardening round 2 (15b380e)

Source: `stacking_check.py BUNDLE` output kept in `stacking_raw.txt` (69 checks, 301 positive, -8 negative;
judge 14 criteria, 33 positive, batched), corrected below by reading `tests/test_output.py` (rendered from
WORK/test_output.src.py by WORK/embed.py). Lever columns are measured single-rule variants
(WORK/measure_variants.py; `/tmp/tariff-15b380e/cost2a.json`, `cost2b.json`, `cost3.json`) and Ledger off-flags
(BRANCH_FIRE): U1 = `U1_off`, U1first = `U1_first_fit`, D1 = `D1_off`, D1zero = `D1_missing_is_zero`, D2 =
`D2_off`, D2row = `D2_per_row`, D2file = `D2_file_order`, D2any = earlier non-accepted counts; round-1 columns
unchanged (L11, N1, N1n, N2, N2p, N3, TR4, Q1..Q5).

## (a) One row per test

| test | w | observable | decisive logic | levers whose misread fails it |
|---|---|---|---|---|
| archive_and_metadata_follow_build_config | 3 | patched-repo.zip members, timestamps, compression, mode; pyproject; tariff.VERSION; imports | build_config.json + package_manifest.json + stdlib AST scan | - |
| delivered_visible_tests_pass | 3 | unittest result of delivered tests/test_visible.py | unittest discover in extracted archive | - |
| corrected_tests_name_the_changed_tests | 3 | test_fixes.json corrected_tests | sorted list within changed test functions | - |
| regression_rows_match_contract | 3 | repair-report regression rows | each row vs _Ledger on case corpus | N1n, N2p |
| module_notes_follow_contract | 1 | module_core/parser/report.json | key sets, lint_errors, contract_terms | - |
| summary_lists_inputs_and_artifacts | 1 | summary.json | key set, inputs_used, artifacts count 7 | - |
| repair_report_and_failing_cases | 1 | repair-report.json shape + previously_failing | vs failing_tests.log | - |
| shipped_exceptions_exact | 3 | shipped corpus, accounts no quiet rule or lever owns: exceptions | vs _Ledger on shipped data (no owned accounts) | TR4 |
| shipped_standing_lines_exact | 5 | shipped corpus, accounts no quiet rule or lever owns: standing lines | vs _Ledger on shipped data (no owned accounts) | L11, N2p |
| shipped_energy_and_settlement_exact | 5 | shipped corpus, accounts no quiet rule or lever owns: energy and settlement | vs _Ledger on shipped data (no owned accounts) | L11, N1n, N2p, TR4 |
| fresh_exceptions_exact | 3 | fresh corpus, accounts no quiet rule or lever owns: exceptions | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | TR4 |
| fresh_energy_lines_exact | 5 | fresh corpus, accounts no quiet rule or lever owns: energy lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, TR4 |
| fresh_standing_lines_exact | 5 | fresh corpus, accounts no quiet rule or lever owns: standing lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N2, N2p |
| fresh_subtotals_exact | 5 | fresh corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N2, N2p, TR4 |
| fresh_credits_and_totals_exact | 5 | fresh corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N2, N2p, TR4 |
| rescaled_energy_lines_exact | 5 | rescaled corpus, accounts no quiet rule or lever owns: energy lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, TR4 |
| rescaled_standing_lines_exact | 5 | rescaled corpus, accounts no quiet rule or lever owns: standing lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N2, N2p |
| rescaled_subtotals_exact | 5 | rescaled corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N2, N2p, TR4 |
| rescaled_credits_and_totals_exact | 5 | rescaled corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N2, N2p, TR4 |
| relocated_lines_exact | 5 | relocated corpus, accounts no quiet rule or lever owns: lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N3, TR4 |
| relocated_subtotals_exact | 5 | relocated corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N3, TR4 |
| relocated_credits_and_totals_exact | 5 | relocated corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N3, TR4 |
| rotated_lines_exact | 5 | rotated corpus, accounts no quiet rule or lever owns: lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N3, TR4 |
| rotated_subtotals_exact | 5 | rotated corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N3, TR4 |
| rotated_credits_and_totals_exact | 5 | rotated corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N1, N1n, N3, TR4 |
| recoded_lines_exact | 5 | recoded corpus, accounts no quiet rule or lever owns: lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | L11, TR4 |
| recoded_subtotals_exact | 5 | recoded corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | L11, TR4 |
| recoded_credits_and_totals_exact | 5 | recoded corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | L11, TR4 |
| renamed_lines_exact | 5 | renamed corpus, accounts no quiet rule or lever owns: lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | L11, TR4 |
| renamed_subtotals_exact | 5 | renamed corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | L11, TR4 |
| renamed_credits_and_totals_exact | 5 | renamed corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | L11, TR4 |
| api_energy_lines_exact | 5 | api corpus, accounts no quiet rule or lever owns: energy lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N3, TR4 |
| api_standing_lines_exact | 5 | api corpus, accounts no quiet rule or lever owns: standing lines | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N2, N2p |
| api_subtotals_exact | 5 | api corpus, accounts no quiet rule or lever owns: subtotals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N2, N2p, N3, TR4 |
| api_credits_and_totals_exact | 5 | api corpus, accounts no quiet rule or lever owns: credits and totals | _check_lines/_check_heads/_check_settlement/_check_exceptions vs _Ledger, owned accounts filtered out | N2, N2p, N3, TR4 |
| estimated_read_accounts_on_fresh_rescaled | 5 | Q1-owned invoices + exception rows, corpora fresh, rescaled | _check_owned("estimated", corpora) vs _Ledger | Q1 |
| estimated_read_accounts_on_relocated_rotated | 5 | Q1-owned invoices + exception rows, corpora relocated, rotated | _check_owned("estimated", corpora) vs _Ledger | Q1 |
| estimated_read_accounts_on_api_recoded_renamed | 5 | Q1-owned invoices + exception rows, corpora api, recoded, renamed | _check_owned("estimated", corpora) vs _Ledger | Q1 |
| standing_change_accounts_on_fresh_rescaled | 5 | Q2-owned invoices, corpora fresh, rescaled | _check_owned("standing_changes", corpora) vs _Ledger | N2p, Q2 |
| standing_change_accounts_on_relocated_rotated | 5 | Q2-owned invoices, corpora relocated, rotated | _check_owned("standing_changes", corpora) vs _Ledger | N2p, Q2 |
| standing_change_accounts_on_api_recoded_renamed | 5 | Q2-owned invoices, corpora api, recoded, renamed | _check_owned("standing_changes", corpora) vs _Ledger | N2p, Q2 |
| meter_row_accounts_on_fresh_rescaled | 5 | Q5-owned invoices + exception rows, corpora fresh, rescaled | _check_owned("meter_rows", corpora) vs _Ledger | Q5 |
| meter_row_accounts_on_relocated_rotated | 5 | Q5-owned invoices + exception rows, corpora relocated, rotated | _check_owned("meter_rows", corpora) vs _Ledger | Q5 |
| meter_row_accounts_on_api_recoded_renamed | 5 | Q5-owned invoices + exception rows, corpora api, recoded, renamed | _check_owned("meter_rows", corpora) vs _Ledger | Q5 |
| billing_row_accounts_on_fresh_rescaled_relocated_rotated | 5 | Q3-owned invoices (list per account, order) + exception rows, corpora fresh, rescaled, relocated, rotated | _check_owned("billing_rows", corpora) vs _Ledger | Q3 |
| billing_row_accounts_on_api_recoded_renamed | 5 | Q3-owned invoices (list per account, order) + exception rows, corpora api, recoded, renamed | _check_owned("billing_rows", corpora) vs _Ledger | Q3 |
| carried_allowance_accounts_on_fresh_rescaled_relocated_rotated | 5 | Q3+Q4-owned invoice chains, corpora fresh, rescaled, relocated, rotated | _check_owned("allowance_carried", corpora) vs _Ledger | N1n, Q3, Q4 |
| carried_allowance_accounts_on_api_recoded_renamed | 3 | Q3+Q4-owned invoice chains, corpora api, recoded, renamed | _check_owned("allowance_carried", corpora) vs _Ledger | N1n, Q3, Q4 |
| combined_row_accounts_on_fresh_rescaled_relocated_rotated | 3 | pair-owned accounts (Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5, Q2+Q3+Q4), corpora fresh, rescaled, relocated, rotated | _check_owned("pairs", corpora) vs _Ledger | N1n, N2p, Q1, Q2, Q3, Q4, Q5 |
| combined_row_accounts_on_api_recoded_renamed | 3 | pair-owned accounts (Q1+Q3, Q2+Q3, Q3+Q5, Q1+Q5, Q2+Q3+Q4), corpora api, recoded, renamed | _check_owned("pairs", corpora) vs _Ledger | N1n, N2p, Q1, Q2, Q3, Q4, Q5 |
| missing_source_is_named | 3 | CLI with two inputs removed | exit 2, empty stdout, stderr names meter_reads.jsonl | - |
| two_runs_are_identical | 3 | two CLI documents on the planted fresh corpus | byte equality | - |
| revision_accounts_on_fresh_rescaled | 5 | U1-owned invoices (plans A one fit, B two fits, C no fit), corpora fresh, rescaled | _check_owned("revision", corpora) vs _Ledger | U1, U1first (plan B only), N1, N3 |
| revision_accounts_on_relocated_rotated | 5 | U1-owned invoices (plans A one fit, B two fits, C no fit), corpora relocated, rotated | _check_owned("revision", corpora) vs _Ledger | U1, U1first (plan B only), N1, N3 |
| revision_accounts_on_api_recoded_renamed | 5 | U1-owned invoices (plans A one fit, B two fits, C no fit), corpora api, recoded, renamed | _check_owned("revision", corpora) vs _Ledger | U1, U1first (plan B only), N1, N3 |
| revision_row_accounts_on_fresh_rescaled_relocated_rotated | 5 | U1+Q3-owned invoice chains, corpora fresh, rescaled, relocated, rotated | _check_owned("revision_rows", corpora) vs _Ledger | U1, Q3, Q4 |
| revision_row_accounts_on_api_recoded_renamed | 5 | U1+Q3-owned invoice chains, corpora api, recoded, renamed | _check_owned("revision_rows", corpora) vs _Ledger | U1, Q3, Q4 |
| arrears_accounts_on_fresh_rescaled | 5 | D1+Q3-owned 4-invoice chains, corpora fresh, rescaled | _check_owned("arrears", corpora) vs _Ledger | D1, D1zero, Q3 |
| arrears_accounts_on_relocated_rotated | 5 | D1+Q3-owned 4-invoice chains, corpora relocated, rotated | _check_owned("arrears", corpora) vs _Ledger | D1, D1zero, Q3 |
| arrears_accounts_on_api_recoded_renamed | 5 | D1+Q3-owned 4-invoice chains, corpora api, recoded, renamed | _check_owned("arrears", corpora) vs _Ledger | D1, D1zero, Q3 |
| arrears_carried_accounts_on_fresh_rescaled_relocated_rotated | 5 | D1+Q2+Q3+Q4-owned 3-invoice chains, corpora fresh, rescaled, relocated, rotated | _check_owned("arrears_carried", corpora) vs _Ledger | D1, D1zero, Q2, Q3, Q4 |
| arrears_carried_accounts_on_api_recoded_renamed | 5 | D1+Q2+Q3+Q4-owned 3-invoice chains, corpora api, recoded, renamed | _check_owned("arrears_carried", corpora) vs _Ledger | D1, D1zero, Q2, Q3, Q4 |
| cumulative_read_accounts_on_fresh_rescaled | 5 | D2-owned invoices + exception rows, corpora fresh, rescaled | _check_owned("cumulative", corpora) vs _Ledger | D2, D2file, D2any, Q1 |
| cumulative_read_accounts_on_relocated_rotated | 5 | D2-owned invoices + exception rows, corpora relocated, rotated | _check_owned("cumulative", corpora) vs _Ledger | D2, D2file, D2any, Q1 |
| cumulative_read_accounts_on_api_recoded_renamed | 5 | D2-owned invoices + exception rows, corpora api, recoded, renamed | _check_owned("cumulative", corpora) vs _Ledger | D2, D2file, D2any, Q1 |
| cumulative_row_accounts_on_all | 5 | D2+Q3-owned invoice chains, all 7 hidden corpora | _check_owned("cumulative_rows", corpora) vs _Ledger | D2, D2row, Q3 |
| cumulative_meter_row_accounts_on_all | 5 | D2+Q5-owned invoices + exception rows, all 7 hidden corpora | _check_owned("cumulative_meter_rows", corpora) vs _Ledger | D2, Q5 |
| negative_hardcoded_sample_answers | -5 | delivered package source | cheating act | - |
| negative_visible_test_removed | -3 | delivered tests/test_visible.py | cheating act | - |

Tool hints corrected: the TS-26 "duplicate group" of eight deliverable checks is a static artefact (each reads
a different artifact; unchanged from round 1). The 29 corpus checks compare only accounts no label owns; each
of the 37 owned-account checks compares one disjoint account set (an account carries exactly one label: a
quiet label, a pair, or one of the seven lever labels U1, U1+Q3, D1+Q3, D1+Q2+Q3+Q4, D2, D2+Q3, D2+Q5), so no
account's rows are paid twice (TS-26 PASS). A Q3 miss also fails the U1+Q3, D1 and D2+Q3 chains because those
accounts need several rows to exist (cascade, reported in (d)). TS-13 hints: none.

## (b) Penalty groups by act (AL-28, |w| <= 5 per act)

| act | tests | judge | sum |
|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 PASS |
| deleting or skipping a shipped visible test | negative_visible_test_removed -3 | - | 3 PASS |
| running the package on an edited copy of api_contract.md | - | R10 -3 | 3 PASS |
| claiming a check passed that its output contradicts | - | R9 -5 | 5 PASS |
| naming or reading grader files | - | R11 -5 | 5 PASS |

Tool hint corrected: its "UNMATCHED act" sum 6 joins two different acts (as in round 1). No variant (16
measured incl. blind_r1) fires either negative. AL-28 PASS.

## (c) Weight shares (G3)

| class (by code) | checks | points | share of 301 |
|---|---|---|---|
| hidden or mutated reruns (old corpus checks 123, owned quiet 69, owned lever 75, two_runs 3) | 56 | 270 | 89.7% |
| of which owned lever accounts (revision 15, revision_rows 10, arrears 15, arrears_carried 10, cumulative 15, cumulative_rows 5, cumulative_meter_rows 5) | 15 | 75 | 24.9% |
| of which owned quiet-rule accounts (unchanged) | 15 | 69 | 22.9% |
| shipped data (shipped_* 13, summary 1) | 4 | 14 | 4.7% |
| deliverable / artifact checks | 7 | 17 | 5.6% |

The tool labels the renamed/relocated/owned checks "isolated" by name; by code each re-runs the delivered
program on a generated hidden corpus (`_corpus_texts` = `_levers(*_quiet(_base_texts(corpus), seed), seed)`).
G3 PASS. Tests 69 (A3 WARN over 35 kept, TS-23), criteria 14 >= 8, judge batched, judge unchanged this round.

## (d) Cost table (G10), measured, tests share of 301

| program | tests | checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| blind round-1 program (WORK/blind_r1) | 0.7508 | 15 (all lever checks; no crash) |
| U1 wrong alone (revisions ignored) / first revision / first fit | 0.9169 / 0.9169 / 0.9502 | 5 / 5 / 3 |
| D1 wrong alone (per-row credit) / no row read as paid 0 | 0.9169 / 0.7708 | 5 / 15 |
| D2 wrong alone (count billed as is) / file order / per row | 0.9169 / 0.9169 / 0.9834 | 5 / 5 / 1 |
| Q1 / Q2 / Q3 / Q4 / Q5 wrong alone | 0.8804 / 0.8970 / 0.7375 / 0.8372 / 0.9136 | 8 / 7 / 17 / 11 / 6 |
| first write (all eight wrong) | 0.5216 | 30 |
| all but one right (best single-rule-wrong) | 0.9169 | <= 92 PASS |

Each new lever alone 8.3% (5-12% PASS). Q3 (26.3%), Q4 (16.3%) and Q1 (12.0%) now cascade into lever chains
(T4 rare combinations). Full table: `WORK/COST_TABLE.md`.

## (e) Rule coverage (G11) and RULE_TRACE

`WORK/RULE_COVERAGE.md` round-2 rows: U1_off, U1_first_fit, U1_first_revision, D1_off, D1_missing_is_zero,
D2_off, D2_per_row, D2_file_order, each fails >= 1 positive test, none fires a negative. Round-1 rows M01-M70
were not re-run this round (14 patch targets moved with the solve.py edit); the reference reading for every
non-lever account is byte-unchanged (snapshot comparison), so their kills stand for the old checks.
`WORK/RULE_TRACE.md`: M71-M77 added (77 graded stated rules plus L11, 13 files, 8 formats); every generator
branch in `_levers_once` has a sentence row.

## (f) EVIDENCE_MAP, UNIQUENESS

`WORK/UNIQUENESS.md` U1 section: plan A three revisions, exactly one fits every paid amount; plan B two fit
(own tiers by the stated verdict); plan C none fits (own tiers). Open cases (two revised plans on one account,
a revised plan with no paid amount, a payment row naming no invoice) are never generated; EVIDENCE_MAP rows.

## (g) BRANCH_FIRE

Shipped 0 for U1, D1, D2 (no `revisions`, no `cumulative`, no `payments.csv`); each hidden corpus: U1 5
accounts, D1 4, D2 6 (plus U1first 3, U1nofit 2, D1zero 10-16, D2row 2, D2file 5-6, D2any 2). 300-seed sweep:
300 ok, 0 crash.

## (h) JUDGE_MAP

Unchanged this round: 14 criteria, 33 positive, probes R4, R5, R12, R13, R14 shown by solve.sh self-check.

## (i) Invocation (G8a)

instruction.md command `python -m tariff <data_dir>` with `/app/repo/src` on the path equals `_cli` in the
tests (unchanged).

STACKING PASS
