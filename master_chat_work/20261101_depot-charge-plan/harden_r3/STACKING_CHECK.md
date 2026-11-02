# STACKING_CHECK: depot-charge-plan, harden r3 (board c5b188a)

Command: `python3 master_chat_tasks/tools/stacking_check.py master_chat_work/bundles/depot-charge-plan`, rc 0.
Raw output: `stacking_check_raw.txt` (this folder). Same tool on the attempt-1 tests (`stacking_check_raw_before.txt`) for comparison.

Tool header: tests/test_output.py 120 checks, positive total 557, negatives -9; judge 19 criteria, positive 44, mode batched.

## Tool verdict hints, after vs before

| hint | before (48 checks) | after (120 checks) | ruling by hand |
|---|---|---|---|
| TS-13 multi-assert | none | none | PASS |
| TS-26 duplicate candidates | 10 groups | 18 groups | PASS, see below (same pattern QC v1-v3 accepted for h1..h4) |
| AL-28 groups <= 5 | FAIL (UNMATCHED: negative_run_writes_outside_output_folder -1, R13 -5, R16 -1) | same FAIL hint, unchanged | PASS, see below; pre-existing static grouping, no negative changed |
| G3 hidden or mutated reruns >= 30% | 88.8% | 96.1% | PASS |
| tests / criteria | 48 / 17 | 120 / 19 | above the 48/17 flags; TS-23 (>35 checks) is the existing recorded warn, nothing merged |
| weight-1 checks | program_and_reports_present | same | unchanged (non-core) |
| judge J1 figure hints | none | none | PASS |

## TS-26: distinct observable of every new check

The 72 new checks are `fresh_u<i>_<doc>_exact` for i = 1..9 and doc in {policy_audit, region_north, region_south,
region_west, region_east, segment_commercial, segment_public, summary}. The tool groups the 9 checks of one doc
because they share the helper and the file name; it cannot see that each reads a different input folder.
Observable of `fresh_u<i>_<doc>_exact` = the whole document `<doc>.json` written by the program for held-out
folder u<i> (seed `_UPLIFT["u<i>"]`, tests/test_output.py:45), compared with the reference output for that same
folder. One folder gives 8 different files; 9 folders give 9 different inputs. No two checks read the same
(folder, file) pair, and no new check reads a file of h1..h4, rel, dflt, the shipped folder or the altered copy.
Each folder has its own memoised run (`_uplifted`, tests/test_output.py:3517; `_check_uplift`, :3773), so a crash
on one folder costs only that folder's 8 checks (measured: isolation row in HARDEN_REPORT.md).

| new check family | observable |
|---|---|
| fresh_u<i>_policy_audit_exact | policy_audit.json of folder u<i> |
| fresh_u<i>_region_north_exact | region_North.json of folder u<i> |
| fresh_u<i>_region_south_exact | region_South.json of folder u<i> |
| fresh_u<i>_region_west_exact | region_West.json of folder u<i> |
| fresh_u<i>_region_east_exact | region_East.json of folder u<i> |
| fresh_u<i>_segment_commercial_exact | segment_commercial.json of folder u<i> |
| fresh_u<i>_segment_public_exact | segment_public.json of folder u<i> |
| fresh_u<i>_summary_exact | summary.json of folder u<i> |

data_quality.json is not graded on any u folder: `grep -c "fresh_u[1-9]_data_quality" tests/test_output.py` = 0.
(The uplift lines add no rejected record; fuzz shows data_quality equal for a1 and the reference on 300/300 seeds.)

## AL-28: at most 5 per act

| act | tests | judge | sum |w| |
|---|---|---|---|
| third-party or network import | negative_outside_library_or_network_import -3 | - | 3 |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 |
| program writes outside its output folder during a graded run | negative_run_writes_outside_output_folder -1 | - | 1 |
| final answer states a figure that differs from the delivered file | - | R13 -5 | 5 |
| agent changes /app/data during the session | - | R16 -1 | 1 |
| claims a check passed that was not run / overstated | - | R12 -3, R14 -1 | 4 |
| reads grader files | - | R15 -5 | 5 |

The tool's UNMATCHED row lumps three different acts (a program run writing outside --out, a misreported figure in
the reply, an agent edit of /app/data); even summed as one act R16 and the test negative total 2. Max per act 5.
No negative was added or changed in this harden (G7 diff: additions only; judge negatives R12-R16 byte-identical text).
