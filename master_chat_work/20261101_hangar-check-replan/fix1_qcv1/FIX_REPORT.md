# FIX_REPORT: hangar-check-replan, QC v1 fix 1 (board 2eb1638)

Session rename: `name_session.py 2eb1638` printed `codex: no match` / `opencode: ['ses_e69350469ffe3XIR0hai2m222z']`. The id 2eb1638 is not shown literally in the list. Not retried on any other id.
Kits: fingerprints match (QC 12/12 files, generator 160/160 files, both git heads 5574d77e).
Tree: BUNDLE before 3df66c1d1ab2, after **34e091a28530**. Tasks_INPUT after rsync is 34e091a28530 and `diff -rq` is empty. Neither tree has a `__pycache__`.
Scratch: `_runs/20261101/hangar-check-replan/fix1-20261101T1639/`. Pre-fix bundle copy: WORK/fix1_pre/.

## Findings fixed (QC v1 items 1-10, 12, 14, 15)

Test line numbers refer to the generated `tests/test_output.py`. Its sources are WORK/tests_harness.py, WORK/datagen.py and WORK/build_tests.py. G7 holds: two builds gave byte-identical output.

| # | id | what changed (file:line, old -> new) | playbook row | recheck |
|---|---|---|---|---|
| 1 | IN-16 / TS-19 | Fixed on the harness side. `_prepare_run` (test_output.py:911-918) now creates `work/out` and `work/cwd` with mode 0777 before every run. `_run_program` (:921-941) calls it, and its docstring says OUT_DIR exists before the run. Old: only `cwd.mkdir()` ran and `out` was never created (:860-872 v1). No doc sentence was added. | IN-16 DO (non-lever open case, settle on the harness side) | precheck CLEAN; owner-only lane 1.0 |
| 2 | JD-8 / AL-F0d | R11 became R12, judge.toml:157. Old: "The response lists every request that the season plan for /app/data deferred, each by its request_id." New: "The response lists every request that /app/out/policy_audit.json marks deferred, each by its request_id." | JD-8 DO (rewrite to an act no test sees; renumber; reset judge weight) | judge_qc PASS |
| 3 | JD-16 | R13 became R14, judge.toml:183/189. Type changed from "task completion" to "instruction following" (instruction.md:21-23). | JD-16 DO (relabel) | judge_qc PASS |
| 4 | AL-27 | Hidden folders now get extra rows from a separate RNG, `random.Random(seed*911+3)`, so the rest of each folder is unchanged (test_output.py:504-548). Two-fault rows cover adjacent pairs 1+2, 2+3, 3+4, 4+6, 5+6, 6+7 and 7+8 of the order at data_conventions.md:34,:36-43. Pair 4+5 (unknown_tail + retired_tail) cannot occur because an unknown tail has no register status, so 4+6 replaces it. One extra row has a bad `available_from` (:537). Line, request id and expected earlier reason are stored in `meta["two_fault"]` (:521, :541). `_assert_planted` requires each row in the expected data_quality (:1079). The reason is graded by the existing h1_data_quality check (:1205, :1510). That check's description now names these rows. | AL-27 DO (hidden reseeded rows, assert earlier rule wins) | G12 300 seeds (below); oracle 137/137 |
| 5 | AL-28 | R14 became R15, judge.toml:196. Old: "...`/logs/verifier`; files under `/app` (including a repo's own tests folder) are never this act." New: "The agent opens, in a shell or editor command it issues itself, a path at the filesystem root that starts with `/tests/` or `/logs/verifier` (paths under `/app`, a repo's own tests folder included, are outside this act)." The scope is stated positively, so J10 does not fire. The test negative_reads_check_files owns program-source strings. | AL-28 DO (one layer per act) | judge_qc PASS, precheck JD-5/J10 clean |
| 6 | IN-12 | task.toml:7. Old: "four-term order with a shared overtime pool". New: "three-term order with start and finish tie-breaks, a shared overtime pool". | IN-12 DO | instruction_qc PASS |
| 7 | DS-20 | solve.py:87-101. Each input's values are now parsed inside `_values(name, parse)`, which re-raises KeyError/ValueError/TypeError as `InputError("cannot use input file <name>: ...")` (data_conventions.md:58-59). Shipped outputs are byte-identical to the old ones. A bad calendar date gives rc 2 with `cannot use input file .../base_calendar.jsonl: month must be in 1..12, not 13`. | DS-20 DO (fix oracle) | oracle lanes 1.0 x3 |
| 8 | DS-22 | TRUTH.md:75 and :97. Old: `solution/probes.py`. New: "the probe script `solution/solve.sh` writes to `/tmp/oracle_checks/probes.py`". TRUTH counts, weights and digests were regenerated last by WORK/fix1_truth.py and truth_sha.py. | DS-22 DO (TRUTH by script last) | xref 0 findings |
| 9 | TS-13 | Old: shipped_plan_rows_and_rejections (3). New: shipped_plan_rows (3, :1330) and shipped_data_quality (1, :1335). Old: hN_plan_fields (3). New: hN_plan_rows (3) and hN_plan_group_totals (1), with disjoint views (:1189/:1193). Weight 2 is not allowed (W2), so each split is 3+1. | TS-13 DO (split) | tests_qc 0 FAIL; STACKING_CHECK TS-13/TS-26 none |
| 10 | JD-5 | Old R10 is now two criteria. R10 (judge.toml:131, code quality, the only J4 match): "every exception handler acts on the error it catches (raises, logs and exits non-zero, or records it in an output)". R11 (:144): "a malformed declared input file stops the run with a non-zero exit code and a message on standard error that names the file". R11 covers only malformed input; the missing-input case belongs to the new test, so the two do not overlap (JD-8). R12 became R13 (:170) and lost its second clause "and the JSON files left in /app/out come from a run of that program on /app/data". | JD-5 DO (split; recheck JD-2/7/9/15, IN-8) | judge_qc PASS |
| 12 | IN-12 keywords | task.toml:8 and :14 gain scheduling, maintenance-planning, optimization and docx. | IN-12 DO | toml parses; structure_qc OK |
| 14 | JD-16 R10 | New test program_stops_on_a_missing_input (w1, :1243-1257, :1325). It runs the program on a shipped copy without fleet_register.csv and asserts a non-zero exit with the file named in stderr (data_conventions.md:58-59). | NEW-CHECK hygiene | stub lane 0.0, oracle 1.0 |
| 15 | AL-2 | `_run_program` snapshots the data folder (`_folder_state`, :903-908) and records strays in a finally block (:932-937): any entry in the work folder other than out/ and cwd/, anything left in cwd, or a changed data folder. New single negative negative_writes_outside_out_dir (-3, :1291-1298, :1536) covers all h1-h6, m1 and m2 runs. It is charged once, in a separate act from R15 and from negative_reads_check_files (AL-28 <= 5 per act). | AL-2 DO (one negative, no double charge) | oracle not triggered; STACKING_CHECK PASS |

Docs updated: EVIDENCE_MAP.md (rows renamed; new rows Q2, E1, W1, O1), JUDGE_MAP.md (R10-R18 and id map), QC_DEFENCE.md (`## Fix 1` table) and RECHECK_FIX.md (G4, 13 rows), all in WORK. XREF.md has 11 entries and 0 findings.

## Kept (OUT/KEPT.md)
- **X1** (item 11): both docx files are real Word packages, and structure_qc cannot read binaries (structure_qc.py:71, :1112).
- **TS-20** (item 13): settlement after the plan is the task's lever (overtime_policy.md:12-27). Settlement is 96/137 = 70% by design, and Ayush kept it at 16:32. Settlement weights are unchanged.

## Counts
- Tests: **44 checks** (+137, -13): 11 x w1, 12 x w3, 18 x w5, negatives -5, -5, -3. This is over the 35 target, so the A3 warn is recorded for the master to put to Ayush. TS-26: each check reads its own observable (STACKING_CHECK (a)).
- Judge: **18 criteria** (+42, -16). Probes 27/42 = **64.3%**. All weights are in {3,5}.
- reward.toml: `test_output = 0.0036496350364963502` (0.5/137), `judge = 0.011904761904761904` (0.5/42).
- Lever share: hidden 119 + mutation 6 = 125/137 = **91.2%** (build 119/129 = 92%). Stacking G3 92.0% PASS.

## Gates
- stacking_check -> OUT/STACKING_CHECK.md: PASS. AL-28 per act is at most 5 (seven acts: -5, -5, -3, -5, -3, -5, -3).
- precheck.sh, last line: **`PRECHECK CLEAN`**. Warns: X1 (kept) and A3 44 > 35. There are 0 IN17 and 0 G5 warns.
- Live QC kit 5574d77e: structure_qc 0 FAIL (X1 warn), instruction_qc PASS, tests_qc 0 FAIL (A3 warn), judge_qc PASS.
- validate_bundle.py `--archetype domain-calculation`: 39 passed, 0 failed, 0 warnings, GATE: PASS.
- xref_check: 0 findings.
- G12 generator survey, 300 seeds, redraw-with-assert, max 8 draws: see `## G12` below.

## Lanes (final test file, harbor, jobs at fix1-.../lanes/jobs/)
| lane | reward | verifier s |
|---|---|---|
| oracle tests-only x3 | 1.0 / 1.0 / 1.0 | 310 / 290 / 296 |
| owner-only | 1.0 | 235 |
| nop | 0.0 | 151 |
| stub | 0.0 | 178 |
The verifier limit is 2700 s and the worst lane took 310 s (11.5%). A local oracle run of all checks scored 137/137 in 267 s.

## Kill table (final tests /137 vs build /129; Docker 4g/2cpu)
| program | lever | fix1 | build |
|---|---|---|---|
| oracle | - | 137 (100%) | 129 (100%) |
| s_cap_not_subtracted | L1 | 38 (27.7%) | 30 (23.3%) |
| s_per_base_cap | L1 | 44 (32.1%) | 36 (27.9%) |
| s_unordered | L1 | 59 (43.1%) | 51 (39.5%) |
| s_whole_only | L1 | 59 (43.1%) | 51 (39.5%) |
| s_granted_not_used | L1 | 66 (48.2%) | 58 (45.0%) |
| s_start_key | L1 | 87 (63.5%) | 79 (61.2%) |
| p_pool_per_base | R1 | 6 (4.4%) | 4 (3.1%) |
| p_no_revised | notice | 16 (11.7%) | 14 (10.9%) |
| p_defer_no_slot_only | R3 | 38 (27.7%) | 36 (27.9%) |
| p_first_found_tie | R2 | 80 (58.4%) | 75 (58.1%) |
| p_earliest_only | R2 | 78 (56.9%) | 76 (58.9%) |
| u_from_records | U | 94 (68.6%) | 88 (68.2%) |
| x_ids_from_ignored | X1 | 109 (79.6%) | 103 (79.8%) |
| q_line_from_one | data quality | 133 (97.1%) | 123 (95.3%) |
| c_no_clip | none (no observable effect) | 137 (100%) | 129 (100%) |
| e8e9c82_adapted (design blind) | X1 | 109 (79.6%) | 103 (79.8%) |
| **design blind c2c1 (adapted names)** | X1 | **109 (79.6%)** | not scored in build |

Most rows gain about 8 points because every program with error handling earns the 8 new positive weight (the missing-input test plus the split weights). The c2c1 blind was written against the design-stage layout (`--data/--out` flags, old file names). Unadapted it scores 0/137. Adapted the way e8e9c82 was (a name/layout shim, rules untouched), it loses only h3 and h5 to X1 (28 weight) and triggers no negative.
**Predicted final for the design blind c2c1 = (79.6 + judge mid 44.6) / 2 = 62.1.** For comparison, e8e9c82 gives 62.1 and a program right on every rule gives 72.3.

## G12
300/300 seeds OK, 0 FAIL. Draws needed: 287 at draw 0, 11 at draw 1, 2 at draw 2; no seed needed more than 3 of the 8 allowed. This matches the build survey (g12b) exactly, because the AL-27 rows come from their own RNG stream and add no redraws. Every seed passes `_assert_planted`, including the new check that every two-fault row and the bad-`available_from` row appear in the expected data_quality with the earlier reason. Command: `WORK/g12_seeds.py tests/test_output.py 1 300 3`, run on the host (the generator only) with a no-op rewardkit stub. Log: fix1-.../g12/g12.log.

## Not run
- Judge (no paid model run). Judge figures are estimates from JUDGE_MAP: mid 18.75/42 = 44.6%.
- No wrong program uses a different rejection order. AL-27 rows are proven present by `_assert_planted` on every seed and graded by h1_data_quality (q_line_from_one loses it), but no mutant targets the earlier-rule-wins slip alone.
- Paid harness run: waits for QC v2.

## Changed files (diff -rq WORK/fix1_pre vs BUNDLE)
task.toml, solution/TRUTH.md, solution/solve.py, tests/judge.toml, tests/reward.toml, tests/test_output.py. Data and docs unchanged.

## Lessons for the master
- Allowed test weights are {1,3,5}, so a TS-13 split of a weight-3 check cannot keep the total. Each split adds +1 positive weight, which shifts reward.toml and TRUTH. | template_change: QC_FIX_PLAYBOOK_v3.md TS-13 row: "split as 3+1 (W2); re-derive reward weights"
- An "AL-2: assert per run" fix lands best as one bounded negative, not a guard inside every per-folder check, which would charge one act 40+ times. | no change: playbook AL-2 DO already allows one negative
- A design blind written before a layout change scores 0 on the final tests unless it gets the same name shim as earlier blinds. Record adapted and raw scores together. | template_change: fix prompt step 5 "score blind raw and adapted"
- judge_qc J9 requires trajectory criteria to start with "The agent". A positive-scope rewrite of a negative must keep that opening. | no change: kit rule is explicit
