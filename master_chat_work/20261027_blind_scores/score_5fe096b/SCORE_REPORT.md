# SCORE_REPORT 5fe096b - cold-chain-backbone-quote blind scoring

Bundle: `master_chat_work/bundles/cold-chain-backbone-quote` (after Law-1 fix 25c745d), read-only. Copies built with `exe_copy.py` into `/tmp/score_5fe096b/` (judge.toml removed, reward.toml test_output weight 1/108, network public, openhands venv dropped). Each run: `harbor run ... -y --agent oracle` (chain `logs/run_chain.sh`, log `logs/chain.log`); job dirs kept under `logs/jobs_<label>/`.

Session rename: `name_session.py 5fe096b` printed `codex: no match / opencode: ['ses_e81a9150dffel81ZhdpJ41VMXX']`, so the output does not literally show 5fe096b.

## Oracle sanity
Oracle copy: reward **1.0** (108/108); all 30 positive checks pass and neither negative fires (`jobs_oracle/2026-10-27__22-41-23/cold-chain-backbone-quote__XD9JAP3/verifier/reward-details.json`).

## Lever checks (from HARDEN_REPORT 678c839 / FIX_REPORT 25c745d)
wide_1_core 5, wide_2_core 5, wide_3_core 5, wide_books_report 3, wide_books_summary 3, wide_networks_feasible 3 = **24 of 108 positive points (22.2%)**. These are the 10-project wide books (96-127 sites, 30-41 cold rooms each); the CLI limit is 4 s/project + 10 s = 50 s.

## Measurement method
`logs/measure_chain.sh` + `logs/measure_wide.py`: each blind's delivered `out/` mounted at /app/out in `warm-cold-chain-backbone-quote:l1` with `--memory 4g --cpus 2` (task.toml limits). The script reuses the test module's own helpers (archive extract, book build, `_untrusted_command` setpriv to nobody, `_env`) and runs `python -B -m task --book B --out O` with a 200 s cap instead of 50 s, logging wall seconds, return code and peak child RSS. fresh_1 serves as a control. Logs: `logs/measure_a.log`, `logs/measure_b.log`.


## Blind 2cbd32a  (`/tmp/blind/cold-chain-backbone-quote-20261027T214454-0adb`)

**Install map** (blind path -> /app path): `app/repo` -> `/app/repo`; `app/build_outputs.py` -> `/app/build_outputs.py`; `out/*` -> `/app/out/*`. The bundle's `solve.sh` was replaced by a copy-only installer; the blind files sit in `solution/blind/`.

**Diff proof**: host `diff -r` blind app/out vs copy `solution/blind/{app,out}` gave identical. In the container (`agent/oracle.txt`): `INSTALL-DIFF app/repo vs /app/repo: identical`, `INSTALL-DIFF out vs /app/out: identical`, `INSTALL-DIFF app/build_outputs.py vs /app/build_outputs.py: identical`. `diff -r` oracle copy vs blind copy: only `solution/solve.sh` differs, plus `Only in solution: blind`. No `/tmp/blind` absolute paths in any blind file or zip.

**Tests**: reward 0.7778 = **77.78%** (84/108).

| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| archive_follows_build_config | 1 | pass | - | - |
| shipped_core_document | 5 | pass | - | - |
| shipped_parser_document | 3 | pass | - | - |
| shipped_report_document | 5 | pass | - | - |
| shipped_summary_document | 3 | pass | - | - |
| test_fixes_document | 3 | pass | - | - |
| repair_report_fields | 1 | pass | - | - |
| fresh_1_core | 5 | pass | - | - |
| fresh_2_core | 5 | pass | - | - |
| fresh_3_core | 5 | pass | - | - |
| fresh_1_report | 5 | pass | - | - |
| fresh_2_report | 5 | pass | - | - |
| fresh_3_report | 5 | pass | - | - |
| fresh_1_summary | 3 | pass | - | - |
| fresh_2_summary | 3 | pass | - | - |
| fresh_3_summary | 3 | pass | - | - |
| fresh_networks_feasible | 3 | pass | - | - |
| fresh_rollups_follow_network | 3 | pass | - | - |
| rescaled_book_documents | 5 | pass | - | - |
| relocated_book_documents | 3 | pass | - | - |
| missing_file_reported | 3 | pass | - | - |
| rejection_book_parser | 3 | pass | - | - |
| tie_book_core | 3 | pass | - | - |
| rerun_identical | 1 | pass | - | - |
| wide_1_core | 5 | **FAIL** | CRASH | `_check_fresh: exit -9: (empty stderr)` |
| wide_2_core | 5 | **FAIL** | CRASH | `_check_fresh: exit -9: (empty stderr)` |
| wide_3_core | 5 | **FAIL** | CRASH | `_check_fresh: exit -9: (empty stderr)` |
| wide_books_report | 3 | **FAIL** | CRASH | `_check_wide: exit -9: (empty stderr)` |
| wide_books_summary | 3 | **FAIL** | CRASH | `_check_wide: exit -9: (empty stderr)` |
| wide_networks_feasible | 3 | **FAIL** | CRASH | `_check_wide_feasible: exit -9: (empty stderr)` |
| negative_hardcoded_sample_answers | -5 | not fired | - | - |
| negative_visible_tests_removed | -3 | not fired | - | - |

Measured runs (4 GB / 2 CPU, cap 200 s, limit 50 s):

| book | rc | seconds | peak child RSS MB | outputs match |
|---|---|---|---|---|
| fresh_1 | 0 | 0.55 | 186.0 | True |
| wide_1 | -9 | 1.13 | 4091.9 | None |
| wide_2 | -9 | 0.95 | 4091.9 | None |
| wide_3 | -9 | 0.94 | 4091.9 | None |

Each wide book dies with SIGKILL (rc -9) after about 0.8-1.5 s with peak RSS 4091-4092 MB, which is the 4 GB container cap. The cause is an out-of-memory kill, not the 50 s timeout: stderr is empty, whereas a timeout would read 'timed out after 50 s'. The core is an exact Dreyfus-Wagner Steiner DP (`full = (1 << len(terminals)) - 1`, with per-subset tables) that tries to allocate exponential state for 30-41 terminals. Every lost lever check is a **CRASH** (OOM) at about 1 s, and it would also be infeasible in time.

**Lever checks lost**: 6/6, 24/24 pts. **Loses >=10% of positive points**: yes, 24/108 = 22.2%. **Non-lever checks lost**: 0 (none); all 24 non-lever positive checks pass, including fresh_1-3 (8-10 cold rooms), rescaled, relocated, tie, rejection and rerun. Under Law-1 v3.5 the CRASH loss is confined to lever checks, so it counts.


## Blind 23bef90  (`/tmp/blind/cold-chain-backbone-quote-20261027T214455-a9f0`)

**Install map** (blind path -> /app path): `app/repo` -> `/app/repo`; `app/make_deliverables.py` -> `/app/make_deliverables.py`; `out/*` -> `/app/out/*`. The bundle's `solve.sh` was replaced by a copy-only installer; the blind files sit in `solution/blind/`.

**Diff proof**: host `diff -r` blind app/out vs copy `solution/blind/{app,out}` gave identical. In the container (`agent/oracle.txt`): `INSTALL-DIFF app/repo vs /app/repo: identical`, `INSTALL-DIFF out vs /app/out: identical`, `INSTALL-DIFF app/make_deliverables.py vs /app/make_deliverables.py: identical`. `diff -r` oracle copy vs blind copy: only `solution/solve.sh` differs, plus `Only in solution: blind`. No `/tmp/blind` absolute paths in any blind file or zip.

**Tests**: reward 0.7778 = **77.78%** (84/108).

| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| archive_follows_build_config | 1 | pass | - | - |
| shipped_core_document | 5 | pass | - | - |
| shipped_parser_document | 3 | pass | - | - |
| shipped_report_document | 5 | pass | - | - |
| shipped_summary_document | 3 | pass | - | - |
| test_fixes_document | 3 | pass | - | - |
| repair_report_fields | 1 | pass | - | - |
| fresh_1_core | 5 | pass | - | - |
| fresh_2_core | 5 | pass | - | - |
| fresh_3_core | 5 | pass | - | - |
| fresh_1_report | 5 | pass | - | - |
| fresh_2_report | 5 | pass | - | - |
| fresh_3_report | 5 | pass | - | - |
| fresh_1_summary | 3 | pass | - | - |
| fresh_2_summary | 3 | pass | - | - |
| fresh_3_summary | 3 | pass | - | - |
| fresh_networks_feasible | 3 | pass | - | - |
| fresh_rollups_follow_network | 3 | pass | - | - |
| rescaled_book_documents | 5 | pass | - | - |
| relocated_book_documents | 3 | pass | - | - |
| missing_file_reported | 3 | pass | - | - |
| rejection_book_parser | 3 | pass | - | - |
| tie_book_core | 3 | pass | - | - |
| rerun_identical | 1 | pass | - | - |
| wide_1_core | 5 | **FAIL** | CRASH | `_check_fresh: exit -9: (empty stderr)` |
| wide_2_core | 5 | **FAIL** | CRASH | `_check_fresh: exit -9: (empty stderr)` |
| wide_3_core | 5 | **FAIL** | CRASH | `_check_fresh: exit -9: (empty stderr)` |
| wide_books_report | 3 | **FAIL** | CRASH | `_check_wide: exit -9: (empty stderr)` |
| wide_books_summary | 3 | **FAIL** | CRASH | `_check_wide: exit -9: (empty stderr)` |
| wide_networks_feasible | 3 | **FAIL** | CRASH | `_check_wide_feasible: exit -9: (empty stderr)` |
| negative_hardcoded_sample_answers | -5 | not fired | - | - |
| negative_visible_tests_removed | -3 | not fired | - | - |

Measured runs (4 GB / 2 CPU, cap 200 s, limit 50 s):

| book | rc | seconds | peak child RSS MB | outputs match |
|---|---|---|---|---|
| fresh_1 | 0 | 0.57 | 186.1 | True |
| wide_1 | -9 | 1.51 | 4091.4 | None |
| wide_2 | -9 | 0.83 | 4092.0 | None |
| wide_3 | -9 | 0.88 | 4092.0 | None |

Each wide book dies with SIGKILL (rc -9) after about 0.8-1.5 s with peak RSS 4091-4092 MB, which is the 4 GB container cap. The cause is an out-of-memory kill, not the 50 s timeout: stderr is empty, whereas a timeout would read 'timed out after 50 s'. The core is an exact Dreyfus-Wagner Steiner DP (`full = (1 << len(terminals)) - 1`, with per-subset tables) that tries to allocate exponential state for 30-41 terminals. Every lost lever check is a **CRASH** (OOM) at about 1 s, and it would also be infeasible in time.

**Lever checks lost**: 6/6, 24/24 pts. **Loses >=10% of positive points**: yes, 24/108 = 22.2%. **Non-lever checks lost**: 0 (none); all 24 non-lever positive checks pass, including fresh_1-3 (8-10 cold rooms), rescaled, relocated, tie, rejection and rerun. Under Law-1 v3.5 the CRASH loss is confined to lever checks, so it counts.


## Blind 9387727  (`/tmp/blind/cold-chain-backbone-quote-20261027T214456-130c`)

**Install map** (blind path -> /app path): `app/repo` -> `/app/repo`; `out/*` -> `/app/out/*`. The bundle's `solve.sh` was replaced by a copy-only installer; the blind files sit in `solution/blind/`.

**Diff proof**: host `diff -r` blind app/out vs copy `solution/blind/{app,out}` gave identical. In the container (`agent/oracle.txt`): `INSTALL-DIFF app/repo vs /app/repo: identical`, `INSTALL-DIFF out vs /app/out: identical`. `diff -r` oracle copy vs blind copy: only `solution/solve.sh` differs, plus `Only in solution: blind`. No `/tmp/blind` absolute paths in any blind file or zip.

**Tests**: reward 0.7778 = **77.78%** (84/108).

| check | weight | result | failure kind | first assertion line |
|---|---|---|---|---|
| archive_follows_build_config | 1 | pass | - | - |
| shipped_core_document | 5 | pass | - | - |
| shipped_parser_document | 3 | pass | - | - |
| shipped_report_document | 5 | pass | - | - |
| shipped_summary_document | 3 | pass | - | - |
| test_fixes_document | 3 | pass | - | - |
| repair_report_fields | 1 | pass | - | - |
| fresh_1_core | 5 | pass | - | - |
| fresh_2_core | 5 | pass | - | - |
| fresh_3_core | 5 | pass | - | - |
| fresh_1_report | 5 | pass | - | - |
| fresh_2_report | 5 | pass | - | - |
| fresh_3_report | 5 | pass | - | - |
| fresh_1_summary | 3 | pass | - | - |
| fresh_2_summary | 3 | pass | - | - |
| fresh_3_summary | 3 | pass | - | - |
| fresh_networks_feasible | 3 | pass | - | - |
| fresh_rollups_follow_network | 3 | pass | - | - |
| rescaled_book_documents | 5 | pass | - | - |
| relocated_book_documents | 3 | pass | - | - |
| missing_file_reported | 3 | pass | - | - |
| rejection_book_parser | 3 | pass | - | - |
| tie_book_core | 3 | pass | - | - |
| rerun_identical | 1 | pass | - | - |
| wide_1_core | 5 | **FAIL** | TIMEOUT | `_check_fresh: exit -9: timed out after 50 s` |
| wide_2_core | 5 | **FAIL** | TIMEOUT | `_check_fresh: exit -9: timed out after 50 s` |
| wide_3_core | 5 | **FAIL** | TIMEOUT | `_check_fresh: exit -9: timed out after 50 s` |
| wide_books_report | 3 | **FAIL** | TIMEOUT | `_check_wide: exit -9: timed out after 50 s` |
| wide_books_summary | 3 | **FAIL** | TIMEOUT | `_check_wide: exit -9: timed out after 50 s` |
| wide_networks_feasible | 3 | **FAIL** | TIMEOUT | `_check_wide_feasible: exit -9: timed out after 50 s` |
| negative_hardcoded_sample_answers | -5 | not fired | - | - |
| negative_visible_tests_removed | -3 | not fired | - | - |

Measured runs (4 GB / 2 CPU, cap 200 s, limit 50 s):

| book | rc | seconds | peak child RSS MB | outputs match |
|---|---|---|---|---|
| fresh_1 | 0 | 0.6 | 186.4 | True |
| wide_1 | capped | 200.18 | 1053.2 | None |
| wide_2 | capped | 200.17 | 1053.2 | None |
| wide_3 | capped | 200.17 | 1053.2 | None |

All three wide books were still running at 200 s, which is 4x the 50 s limit, at about 1.05 GB RSS. This is an exact Dreyfus-Wagner subset DP (`_steiner_tables` loops `range(1, 1 << len(terminals))`) and is exponential in 30-41 cold rooms. Every lost lever check is a **TIMEOUT**; the verifier's subprocess timeout fired at 50 s.

**Lever checks lost**: 6/6, 24/24 pts. **Loses >=10% of positive points**: yes, 24/108 = 22.2%. **Non-lever checks lost**: 0 (none); all 24 non-lever positive checks pass, including fresh_1-3 (8-10 cold rooms), rescaled, relocated, tie, rejection and rerun. Under Law-1 v3.5 the TIMEOUT loss is confined to lever checks, so it counts.


## Summary
| blind | tests % | lever lost | kind | non-lever lost |
|---|---|---|---|---|
| 2cbd32a | 77.78 | 24/24 | CRASH | 0 |
| 23bef90 | 77.78 | 24/24 | CRASH | 0 |
| 9387727 | 77.78 | 24/24 | TIMEOUT | 0 |

Oracle 1.0. All three blinds lose exactly the 24 lever points and nothing else, which matches the FIX_REPORT 25c745d prediction for exact DW solvers. 2cbd32a and 23bef90 die by OOM-kill (CRASH) at about 1 s; 9387727 dies by TIMEOUT (>200 s measured against a 50 s limit).
