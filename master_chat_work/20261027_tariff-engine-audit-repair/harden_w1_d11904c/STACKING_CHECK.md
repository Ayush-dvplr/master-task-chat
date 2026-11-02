# STACKING_CHECK: tariff-engine-audit-repair, wave 1 hardening (d11904c)

Source: `stacking_check.py BUNDLE` output kept in `stacking_raw.txt` (112 checks, 488 positive, -8 negative;
judge 14 criteria, 33 positive, batched), corrected below by reading `tests/test_output.py` (rendered from
WORK/test_output.src.py by WORK/embed.py). Rows 1-91 are the round-3 rows, unchanged apart from the shipped
statement count; the 21 ledger rows are new. Lever columns as in round 3; S1L = the wave-1 ledger-scale optimum
(any one-sum table, halves, Pareto list or bounded search runs past 10 s; greedy is feasible but not optimal).

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
| shipped_statements_exact | 5 | shipped `--statements` document (61 statements, incl. A1643 in two-unit shape) | whole document vs `_statements` on shipped ci + vouchers.csv | S1 greedy (15 shipped rows), S2, S3 |
| fresh_statements_feasible | 3 | fresh statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| fresh_statement_due_exact | 5 | fresh statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| fresh_statement_redeemed_exact | 5 | fresh statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| rescaled_statements_feasible | 3 | rescaled statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| rescaled_statement_due_exact | 5 | rescaled statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| rescaled_statement_redeemed_exact | 5 | rescaled statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| relocated_statements_feasible | 3 | relocated statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| relocated_statement_due_exact | 5 | relocated statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| relocated_statement_redeemed_exact | 5 | relocated statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| rotated_statements_feasible | 3 | rotated statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| rotated_statement_due_exact | 5 | rotated statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| rotated_statement_redeemed_exact | 5 | rotated statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| api_statements_feasible | 3 | api statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| api_statement_due_exact | 5 | api statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| api_statement_redeemed_exact | 5 | api statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| recoded_statements_feasible | 3 | recoded statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| recoded_statement_due_exact | 5 | recoded statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| recoded_statement_redeemed_exact | 5 | recoded statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| renamed_statements_feasible | 3 | renamed statement corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_statement_feasible` vs `_statements`; 10 s run | S3 (no_paid, no_clamp), corpus lever per `_STATEMENT_LEVER`, S1 slow (timeout) |
| renamed_statement_due_exact | 5 | renamed statement corpus: (account, due) list | `_check_statement_field(due)` | S1 greedy/slow, S3, corpus lever |
| renamed_statement_redeemed_exact | 5 | renamed statement corpus: (account, redeemed) list | `_check_statement_field(redeemed)` | S1 greedy/slow, S2 tie_any/numeric ids, S3, corpus lever |
| fresh_ledger_statements_feasible | 3 | fresh ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| fresh_ledger_statement_due_exact | 5 | fresh ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| fresh_ledger_statement_redeemed_exact | 5 | fresh ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| rescaled_ledger_statements_feasible | 3 | rescaled ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| rescaled_ledger_statement_due_exact | 5 | rescaled ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| rescaled_ledger_statement_redeemed_exact | 5 | rescaled ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| relocated_ledger_statements_feasible | 3 | relocated ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| relocated_ledger_statement_due_exact | 5 | relocated ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| relocated_ledger_statement_redeemed_exact | 5 | relocated ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| rotated_ledger_statements_feasible | 3 | rotated ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| rotated_ledger_statement_due_exact | 5 | rotated ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| rotated_ledger_statement_redeemed_exact | 5 | rotated ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| api_ledger_statements_feasible | 3 | api ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| api_ledger_statement_due_exact | 5 | api ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| api_ledger_statement_redeemed_exact | 5 | api ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| recoded_ledger_statements_feasible | 3 | recoded ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| recoded_ledger_statement_due_exact | 5 | recoded ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| recoded_ledger_statement_redeemed_exact | 5 | recoded ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| renamed_ledger_statements_feasible | 3 | renamed ledger corpus: accounts, order, balance, redeemed ids own and distinct, sum <= balance, due = balance - sum | `_check_ledger_feasible` vs `_ledger_statements`; 10 s run | S1L timeout (table, halves, Pareto, bounded search), S3, corpus lever per `_LEDGER_LEVER` |
| renamed_ledger_statement_due_exact | 5 | renamed ledger corpus: (account, due) list | `_check_ledger_field(due)` vs `_redeem_split` | S1L greedy/timeout, S3, corpus lever |
| renamed_ledger_statement_redeemed_exact | 5 | renamed ledger corpus: (account, redeemed) list | `_check_ledger_field(redeemed)` vs `_redeem_split` | S1L greedy/timeout, S2 ties in both voucher groups, S3, corpus lever |
| negative_hardcoded_sample_answers | -5 | delivered package source | cheating act | - |
| negative_visible_test_removed | -3 | delivered tests/test_visible.py | cheating act | - |

Tool hints corrected: the TS-26 "duplicate group" of eight deliverable checks is a static artefact (each reads
a different artifact; unchanged from round 1). The 29 corpus checks compare only accounts no label owns; each
of the 37 owned-account checks compares one disjoint account set (an account carries exactly one label: a
quiet label, a pair, or one of the seven lever labels U1, U1+Q3, D1+Q3, D1+Q2+Q3+Q4, D2, D2+Q3, D2+Q5), so no
account's rows are paid twice (TS-26 PASS). A Q3 miss also fails the U1+Q3, D1 and D2+Q3 chains because those
accounts need several rows to exist (cascade, reported in (d)). TS-13 hints: none.

Round 3: the 22 statement checks read the `--statements` document only (new observable); feasibility reads the
balance and the set's admissibility, due and redeemed are separate fields with separate logic, so no observable is
paid twice (TS-26 PASS). Statement corpora are separate texts; the invoice checks and expectations are unchanged.

Wave 1: the 21 ledger checks read the `--statements` document on seven new texts (own RNG, balances 3e10-1e11
cents); feasibility, due and redeemed are separate fields with separate logic, as in round 3, so no observable is
paid twice (TS-26 PASS). The round-3 statement corpora, checks and r3 `_redeem` are byte-unchanged.

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

## (c) Weight shares (G3), by code

| class | points | share of 488 |
|---|---|---|
| hidden or mutated reruns (round-3 total 361 + ledger hidden 7 x 13 = 91) | 452 | 92.6% |
| of which statement checks on hidden corpora (r3 91 + ledger 91) | 182 | 37.3% |
| of which the wave-1 lever (ledger checks) | 91 | 18.6% |
| shipped data (shipped_* 13, summary 1, shipped_statements_exact 5) | 19 | 3.9% |
| deliverable / artifact checks | 17 | 3.5% |

The tool's 24.6% hidden figure classes checks by name; by code every corpus check reruns the delivered program on a
generated hidden corpus. G3 PASS. Tests 112 (A3 WARN over 35 kept, TS-23), criteria 14 >= 8, judge unchanged.

## (d) Cost table (G10), measured in Docker, tests share of 488 (WORK/t4_results/cost_docker.json)

| program | tests | positive checks failed |
|---|---|---|
| oracle | 1.0000 | 0 |
| blind round-3 program (WORK/blind_r3, 397/397 last round) | 0.8135 | 21 |
| blind round-3 program with the reference optimum | 1.0000 | 0 |
| big-int bitset over cents (blind r3 `_redeem` / gcd-reduced rebuild / sum only) | 0.8135 / 0.8135 / 0.6598 | 21 / 21 / 36 |
| dict table of sums | 0.6270 | 42 |
| Pareto list | 0.6270 | 42 |
| halves (raw / deduped id split / deduped amount split) | 0.6270 / 0.6270 / 0.6270 | 42 / 42 / 42 |
| branch and bound, fractional bound | 0.6270 | 42 |
| largest voucher first (greedy) | 0.7029 | 29 |
| naive combinations | 0.6270 | 42 |
| Q1 / Q2 / Q3 / Q4 / Q5 wrong alone | 0.8197 / 0.8299 / 0.6885 / 0.7500 / 0.8934 | 20 / 19 / 34 / 28 / 12 |
| U1 / D1 / D2 wrong alone | 0.9057 / 0.8955 / 0.8955 | 10 / 11 / 11 |
| first write (Q1-Q5, U1, D1, D2 wrong) / plus cents bitset / plus greedy | 0.3422 / 0.3422 / 0.3217 | 71 / 71 / 73 |
| all but one right (best single-rule-wrong: U1_off) | 0.9057 | 10; <= 92 PASS |

Lever alone: 91 of 488 points in 21 checks (18.6%, 10-30 PASS);
every generic solver keeps at most the feasibility points of the ledger corpora (>= 15% lost PASS).

## (e) Rule coverage (G11) and RULE_TRACE

RULE_COVERAGE round-3 rows S_off, S_greedy, S_setdp, S_naive, S_tie_any, S_numeric_ids, S_no_paid, S_no_clamp each
fail 8-22 positive checks; none fires a negative. RULE_TRACE M78-M86 added (86 graded stated rules, 14 files, 8
formats); every branch of `_statements_once` has a sentence row. Earlier rows unchanged.

## (f) EVIDENCE_MAP, UNIQUENESS

`WORK/UNIQUENESS.md` U1 section: plan A three revisions, exactly one fits every paid amount; plan B two fit
(own tiers by the stated verdict); plan C none fits (own tiers). Open cases (two revised plans on one account,
a revised plan with no paid amount, a payment row naming no invoice) are never generated; EVIDENCE_MAP rows.

## (g) BRANCH_FIRE

Round 2 levers: shipped 0, each hidden corpus 4-6 accounts (unchanged). Round 3 statements: shipped 60 statements
(0 big, 9 no-fit, 1 tie, 15 where greedy differs); each hidden corpus 12 statements, 3 big (balance 50,000-90,000),
2-4 ties, 1-2 at balance 0.00, 9-11 where greedy differs (WORK/BRANCH_FIRE.md round 3).

Wave 1 ledger corpora: 7 statements each, 3 big (balance 3e10-1e11 cents, 55-66 vouchers, both voucher groups
used, ties planted in each group), 1 overpaid at 0.00, greedy differs on 4-6 of 7 (WORK/BRANCH_FIRE.md wave 1);
shipped now 61 statements (A1643 added).

## (h) JUDGE_MAP

Unchanged this round: 14 criteria, 33 positive, probes R4, R5, R12, R13, R14 shown by solve.sh self-check.

## (i) Invocation (G8a)

`python -m tariff <data_dir>` equals `_cli`; `python -m tariff --statements <data_dir>` (contract :25-28) equals
`_statement_run` and `_ledger_run` (`[sys.executable, "-B", "-m", "tariff", "--statements", data]`, timeout 10 s).

STACKING PASS
