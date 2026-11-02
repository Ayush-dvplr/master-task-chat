# Blind score report — board 185c588

Session rename: `name_session.py 185c588` printed `codex: no match / opencode: ['ses_e833517f7ffeawalVHQ9O3O274']`; it did not show 185c588 (not retried).

Method: `exe_copy.py <bundle> <dest>` (judge off: judge.toml removed, reward = test_output only; network public) into `/tmp/score_185c588/<slug>-{oracle,blind}`. In the blind copy only, `solution/solve.sh` was replaced and the blind's `app/` and `out/` trees were added as `solution/blind_app` and `solution/blind_out`. Each copy was run once with `yes | harbor run --agent oracle --env docker` (harbor 0.24.0, OPENAI_API_KEY=unused), sequentially, max 2 Docker jobs at once, with locks. Both blind instruction.md files are byte-identical to the bundle instruction.md. The tests (rewardkit, verifier environment_mode=separate) read only `/app/out/*`. The tariff test rebuilds the repo from `/app/out/patched-repo.zip`. Neither blind wrote `/tmp/blind`, `/Users/` or `environment/` paths into a delivered file.

Replacement solve.sh (same in both blind copies):
```bash
#!/bin/bash
# Score-only: installs the blind solution's delivered files byte for byte. No program is run.
set -euo pipefail
S="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp -R "$S/blind_app/." /app/
cp -R "$S/blind_out/." /app/out/
echo "INSTALLED_SHA256_BEGIN"
cd "$S/blind_app" && find . -type f | sort | while read -r f; do sha256sum "/app/${f#./}"; done
cd "$S/blind_out" && find . -type f | sort | while read -r f; do sha256sum "/app/out/${f#./}"; done
echo "INSTALLED_SHA256_END"
```

## 1. tariff-engine-audit-repair (bundle after harden d11904c, blind caf075b)

**Install map**: blind `app/build_deliverables.py` -> `/app/build_deliverables.py`; blind `app/repo/**` (README.md, pyproject.toml, src/tariff/{__init__,__main__,core,parser,report}.py, tests/test_visible.py) -> `/app/repo/**`; blind `out/{module_core,module_parser,module_report,repair-report,summary,test_fixes}.json, out/patched-repo.zip` -> `/app/out/`.

**Diff proof**: `diff -r /tmp/blind/tariff-engine-audit-repair-20261027T144736-0293/app <copy>/solution/blind_app` and the same for `out` were both empty. `diff -rq oracle-copy blind-copy` showed only `blind_app`, `blind_out` added and `solve.sh` changed. sha256 values printed inside the container after install (agent/oracle.txt) equal the host sha256 values of the blind files (16 files, `diff` empty):
```
827b27985f770501e9365662b7eeb92ce861d4191a9aa49a67c5cf17f97dda88  app/build_deliverables.py
1f58bb1f132e2fc0d4fce6d58d1f83a5e74cdf619def9052475733af3b8ef5a0  app/repo/README.md
7effde929aad9a57496c1aa1bd139f56c3661ff2eaf07059c54327b5c4efd4cf  app/repo/pyproject.toml
45777f71838e8724b125f0fe24993aead8e35638b659094227b24a0b578e1495  app/repo/src/tariff/__init__.py
2012b09940bddeebb7e68d13024ac58cc84bbefbd6e3375ce6ffa1b509f53cb3  app/repo/src/tariff/__main__.py
bbef6e84bfb35abe685aba5d6ceb1bb8cf8e69ce5b5546a883dde9fdc19dcd63  app/repo/src/tariff/core.py
561f253f9b0a68b2dae4392bc7924b08888df7377338922a559cbe2ff3178ea2  app/repo/src/tariff/parser.py
a8c154261e7afdeabc041429fefd01578eba44e8a3a1d9cc5bcec3064f7244e6  app/repo/src/tariff/report.py
68a5c15e2484353d3d8b86aa66f300910bbbd75a04628f60d0e18abc54d03d59  app/repo/tests/test_visible.py
1dbdd262653cbb7a4996866b5ebb27da43fe0a1298dd9ce4d103a1446df1e2cc  out/module_core.json
b4aa7ee6436440abddd25847d8d5beed65ceaf9498a30b82c2c04a2c3d4c6a7d  out/module_parser.json
ff4c400443c0134162d847fadaa3ae328b2bee298937c4541f71ffd843ac1bb0  out/module_report.json
0c155ad5c3c6069c24a6034a470bc6bf13e0438ed0992c88812873d1fc0ca16f  out/patched-repo.zip
c57bd168691510ccdbfcedb0278dd95d9a0a6de1fd44fd5a243f5a53d920f3c5  out/repair-report.json
984ee0838208781b67b1c7883fb28469ec35a9157762633c81a3fc1d2c2fa879  out/summary.json
10225bb16931ef6ce0a9c411227b569f5077aff84d7faf124d79f1e000505bb5  out/test_fixes.json
```

**Oracle sanity** (same copy recipe, unchanged solve.sh): reward **1.0** (488/488).

**Blind**: reward 0.8135 -> **tests% = 81.35%** (397/488 positive points, both negatives not fired: (397 − 0)/488). It loses 91/488 = **18.6%** of the positive test points, which is **≥ 10%: yes**.

**Lever checks lost (P-1 ledger-scale statements, from harden_w1_d11904c/HARDEN_REPORT.md)**: **21/21 checks, 91/91 points**. That is `<corpus>_ledger_statements_feasible` (w3), `_ledger_statement_due_exact` (w5) and `_ledger_statement_redeemed_exact` (w5) for fresh, rescaled, relocated, rotated, api, recoded and renamed. Every non-lever positive check passes (89/89).

**Failure kind**: crash. The delivered `python -m tariff --statements` exits with **-9 (SIGKILL) and empty stderr** about 5–8 s into the first statement run of each corpus. That is inside the test's 10 s STATEMENT_SECONDS limit, so this is not the test's timeout path (which would say "no statements within 10 seconds"), and the output was not a wrong document. The tests set no rlimits (setpriv only). The likely cause is the container's OOM killer under the task's 4 GB limit. I did not confirm this with a memory trace. The harbor verifier stdout prints only the reward because the test's `_holds` swallows exceptions. The first assertion lines come from a diagnostic re-run of the same criteria bodies in Docker (tests image, --cpus 2 --memory 4g, the blind out/ mounted at /app/out).

| check | weight | result | lever | failure kind | first assertion line |
|---|---|---|---|---|---|
| archive_and_metadata_follow_build_config | 3 | pass |  |  |  |
| delivered_visible_tests_pass | 3 | pass |  |  |  |
| corrected_tests_name_the_changed_tests | 3 | pass |  |  |  |
| regression_rows_match_contract | 3 | pass |  |  |  |
| module_notes_follow_contract | 1 | pass |  |  |  |
| summary_lists_inputs_and_artifacts | 1 | pass |  |  |  |
| repair_report_and_failing_cases | 1 | pass |  |  |  |
| shipped_exceptions_exact | 3 | pass |  |  |  |
| shipped_standing_lines_exact | 5 | pass |  |  |  |
| shipped_energy_and_settlement_exact | 5 | pass |  |  |  |
| fresh_exceptions_exact | 3 | pass |  |  |  |
| fresh_energy_lines_exact | 5 | pass |  |  |  |
| fresh_standing_lines_exact | 5 | pass |  |  |  |
| fresh_subtotals_exact | 5 | pass |  |  |  |
| fresh_credits_and_totals_exact | 5 | pass |  |  |  |
| rescaled_energy_lines_exact | 5 | pass |  |  |  |
| rescaled_standing_lines_exact | 5 | pass |  |  |  |
| rescaled_subtotals_exact | 5 | pass |  |  |  |
| rescaled_credits_and_totals_exact | 5 | pass |  |  |  |
| relocated_lines_exact | 5 | pass |  |  |  |
| relocated_subtotals_exact | 5 | pass |  |  |  |
| relocated_credits_and_totals_exact | 5 | pass |  |  |  |
| rotated_lines_exact | 5 | pass |  |  |  |
| rotated_subtotals_exact | 5 | pass |  |  |  |
| rotated_credits_and_totals_exact | 5 | pass |  |  |  |
| recoded_lines_exact | 5 | pass |  |  |  |
| recoded_subtotals_exact | 5 | pass |  |  |  |
| recoded_credits_and_totals_exact | 5 | pass |  |  |  |
| renamed_lines_exact | 5 | pass |  |  |  |
| renamed_subtotals_exact | 5 | pass |  |  |  |
| renamed_credits_and_totals_exact | 5 | pass |  |  |  |
| api_energy_lines_exact | 5 | pass |  |  |  |
| api_standing_lines_exact | 5 | pass |  |  |  |
| api_subtotals_exact | 5 | pass |  |  |  |
| api_credits_and_totals_exact | 5 | pass |  |  |  |
| estimated_read_accounts_on_fresh_rescaled | 5 | pass |  |  |  |
| estimated_read_accounts_on_relocated_rotated | 5 | pass |  |  |  |
| estimated_read_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| standing_change_accounts_on_fresh_rescaled | 5 | pass |  |  |  |
| standing_change_accounts_on_relocated_rotated | 5 | pass |  |  |  |
| standing_change_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| meter_row_accounts_on_fresh_rescaled | 5 | pass |  |  |  |
| meter_row_accounts_on_relocated_rotated | 5 | pass |  |  |  |
| meter_row_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| billing_row_accounts_on_fresh_rescaled_relocated_rotated | 5 | pass |  |  |  |
| billing_row_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| carried_allowance_accounts_on_fresh_rescaled_relocated_rotated | 5 | pass |  |  |  |
| carried_allowance_accounts_on_api_recoded_renamed | 3 | pass |  |  |  |
| combined_row_accounts_on_fresh_rescaled_relocated_rotated | 3 | pass |  |  |  |
| combined_row_accounts_on_api_recoded_renamed | 3 | pass |  |  |  |
| revision_accounts_on_fresh_rescaled | 5 | pass |  |  |  |
| revision_accounts_on_relocated_rotated | 5 | pass |  |  |  |
| revision_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| revision_row_accounts_on_fresh_rescaled_relocated_rotated | 5 | pass |  |  |  |
| revision_row_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| arrears_accounts_on_fresh_rescaled | 5 | pass |  |  |  |
| arrears_accounts_on_relocated_rotated | 5 | pass |  |  |  |
| arrears_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| arrears_carried_accounts_on_fresh_rescaled_relocated_rotated | 5 | pass |  |  |  |
| arrears_carried_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| cumulative_read_accounts_on_fresh_rescaled | 5 | pass |  |  |  |
| cumulative_read_accounts_on_relocated_rotated | 5 | pass |  |  |  |
| cumulative_read_accounts_on_api_recoded_renamed | 5 | pass |  |  |  |
| cumulative_row_accounts_on_all | 5 | pass |  |  |  |
| cumulative_meter_row_accounts_on_all | 5 | pass |  |  |  |
| missing_source_is_named | 3 | pass |  |  |  |
| two_runs_are_identical | 3 | pass |  |  |  |
| shipped_statements_exact | 5 | pass |  |  |  |
| fresh_statements_feasible | 3 | pass |  |  |  |
| fresh_statement_due_exact | 5 | pass |  |  |  |
| fresh_statement_redeemed_exact | 5 | pass |  |  |  |
| rescaled_statements_feasible | 3 | pass |  |  |  |
| rescaled_statement_due_exact | 5 | pass |  |  |  |
| rescaled_statement_redeemed_exact | 5 | pass |  |  |  |
| relocated_statements_feasible | 3 | pass |  |  |  |
| relocated_statement_due_exact | 5 | pass |  |  |  |
| relocated_statement_redeemed_exact | 5 | pass |  |  |  |
| rotated_statements_feasible | 3 | pass |  |  |  |
| rotated_statement_due_exact | 5 | pass |  |  |  |
| rotated_statement_redeemed_exact | 5 | pass |  |  |  |
| api_statements_feasible | 3 | pass |  |  |  |
| api_statement_due_exact | 5 | pass |  |  |  |
| api_statement_redeemed_exact | 5 | pass |  |  |  |
| recoded_statements_feasible | 3 | pass |  |  |  |
| recoded_statement_due_exact | 5 | pass |  |  |  |
| recoded_statement_redeemed_exact | 5 | pass |  |  |  |
| renamed_statements_feasible | 3 | pass |  |  |  |
| renamed_statement_due_exact | 5 | pass |  |  |  |
| renamed_statement_redeemed_exact | 5 | pass |  |  |  |
| fresh_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: fresh: exit -9:` |
| fresh_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: fresh: exit -9:` |
| fresh_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: fresh: exit -9:` |
| rescaled_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: rescaled: exit -9:` |
| rescaled_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: rescaled: exit -9:` |
| rescaled_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: rescaled: exit -9:` |
| relocated_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: relocated: exit -9:` |
| relocated_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: relocated: exit -9:` |
| relocated_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: relocated: exit -9:` |
| rotated_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: rotated: exit -9:` |
| rotated_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: rotated: exit -9:` |
| rotated_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: rotated: exit -9:` |
| api_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: api: exit -9:` |
| api_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: api: exit -9:` |
| api_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: api: exit -9:` |
| recoded_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: recoded: exit -9:` |
| recoded_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: recoded: exit -9:` |
| recoded_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: recoded: exit -9:` |
| renamed_ledger_statements_feasible | 3 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: renamed: exit -9:` |
| renamed_ledger_statement_due_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: renamed: exit -9:` |
| renamed_ledger_statement_redeemed_exact | 5 | FAIL | yes | crash (SIGKILL exit -9 at ~5-8 s, before the 10 s limit) | `AssertionError: renamed: exit -9:` |
| negative_hardcoded_sample_answers | -5 | not fired |  |  |  |
| negative_visible_test_removed | -3 | not fired |  |  |  |

## 2. cold-chain-backbone-quote (bundle after harden 678c839, blind eac8712)

**Install map**: blind `app/make_outputs.py` -> `/app/make_outputs.py`; blind `app/repo/**` (incl. `src/task/core.py`) -> `/app/repo/**`; blind `out/*` (7 files) -> `/app/out/`.

**Diff proof**: `diff -r /tmp/blind/cold-chain-backbone-quote-20261027T144736-9cb7/app <copy>/solution/blind_app` and the same for `out` were both empty. `diff -rq oracle-copy blind-copy` showed only `blind_app`, `blind_out` added and `solve.sh` changed. In-container sha256 values equal the host values (16 files):
```
649cbbdb3390c075876e8a69be0ac26102487adcc5c9e8d217732814c36c9ef9  app/make_outputs.py
47df3e022a13112e8abee07a7ed63f12870fac8d25351fb48dbebb1a06a8c88f  app/repo/README.md
875ac1bc2fd65466b2c930550ef4f8117e0405cc5bb8cd5ce581c7206cbd0069  app/repo/pyproject.toml
e57d81ea6a8e555d56aa742a18c6debf5845d79854fa10fb569fcef8b2f597a5  app/repo/src/task/__init__.py
e1acb21985c20e20623621ebb768649ac85c4923fe61182bbe357938cc895324  app/repo/src/task/__main__.py
5404bef9af3387188785a6170084c53f3d81c87e0ffc5f94c07678f6050e4226  app/repo/src/task/core.py
47d2e5869a03b5e696459868b0a90fea90c4d7be24e1227fbbd00297f6b2c1b7  app/repo/src/task/parser.py
d85d50deca774115d65caf75d5386df64a3bcada2c25eb26573b4a968d0a6e70  app/repo/src/task/report.py
95e231e6957e93e9f6822845aec4a332687874733b04f18cf39888f1fa3d9cc0  app/repo/tests/test_visible.py
b73192ea3e5b42acbe94430fe2d76848e4252c4fce2658c1afdc2ae482bb1f56  out/module_core.json
2f1c9d739862d98efba9faa0ad3904d4e4fa144f6ebe5a5feebccdc5d72f7cc3  out/module_parser.json
503058dd3d08f55be88e3b8bcffae6a4727cbebd57dafa0d59868b2a7497b43e  out/module_report.json
73e439622ae2c418e2e1ad158712938805a140afd88a14a572db1e10e4b5b29c  out/patched-repo.zip
911bfd8e8e360b723ded8866be0ee841e67a8f891506689555b565f0dafc01af  out/repair-report.json
138d0e5241f32f44e0082c15125df87b6ee67c1755f554e2fb63a033e030040d  out/summary.json
09442bac31659a5eb0eb421136262d45bf9cddd8d78e7559fd5f9eac566ca370  out/test_fixes.json
```

**Oracle sanity**: reward **1.0** (108/108).

**Blind**: reward 0.2778 -> **tests% = 27.78%** (30/108, both negatives not fired). It loses 78/108 = **72.2%** of the positive test points, which is **≥ 10%: yes**.

**Lever checks lost (P-1 span hint removed, from harden_w1_678c839/HARDEN_REPORT.md)**: **6/6 checks, 24/24 points** (wide_1_core 5, wide_2_core 5, wide_3_core 5, wide_books_report 3, wide_books_summary 3, wide_networks_feasible 3). The blind also loses 54 non-lever points: all fresh_*, rescaled/relocated book documents and rerun_identical.

**Failure kind**: timeout, for all 20 failing checks. The delivered CLI is killed at the test's limit (4 s/project × 10 projects + 10 s = 50 s), giving `exit -9: timed out after 50 s`. The verifier stdout shows the same lines. In the diagnostic re-run each uncached CLI call took about 51–53 s before it was killed. The 10 passing checks are static checks of the delivered out/ and repo.

| check | weight | result | lever | failure kind | first assertion line |
|---|---|---|---|---|---|
| archive_follows_build_config | 1 | pass |  |  |  |
| shipped_core_document | 5 | pass |  |  |  |
| shipped_parser_document | 3 | pass |  |  |  |
| shipped_report_document | 5 | pass |  |  |  |
| shipped_summary_document | 3 | pass |  |  |  |
| test_fixes_document | 3 | pass |  |  |  |
| repair_report_fields | 1 | pass |  |  |  |
| fresh_1_core | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_2_core | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_3_core | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_1_report | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_2_report | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_3_report | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_1_summary | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_2_summary | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_3_summary | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_networks_feasible | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| fresh_rollups_follow_network | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| rescaled_book_documents | 5 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| relocated_book_documents | 3 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| missing_file_reported | 3 | pass |  |  |  |
| rejection_book_parser | 3 | pass |  |  |  |
| tie_book_core | 3 | pass |  |  |  |
| rerun_identical | 1 | FAIL |  | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_1_core | 5 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_2_core | 5 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_3_core | 5 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_books_report | 3 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_books_summary | 3 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| wide_networks_feasible | 3 | FAIL | yes | timeout (50 s CLI limit) | `AssertionError: exit -9: timed out after 50 s` |
| negative_hardcoded_sample_answers | -5 | not fired |  |  |  |
| negative_visible_tests_removed | -3 | not fired |  |  |  |

## Housekeeping
Work dir `/tmp/score_185c588/` (copies, jobs, diagnostic images s185-*-tests) is removed after this report. The harbor logs, chain logs, reward-details and diagnostic outputs are kept under `OUT/logs/`. No bundle, blind folder, Tasks_INPUT, harness clone or QC kit was edited. Nothing from the blind ran on the host.
