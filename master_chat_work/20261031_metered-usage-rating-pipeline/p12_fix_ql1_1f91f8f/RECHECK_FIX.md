# P12 fix QL1 - metered-usage-rating-pipeline (board 1f91f8f)

No fix lets the a4 program pass a long or ladder month: a4 keeps 262/422 test points before and after (all 44 long/ladder checks still time out at 20 s), so a4 stays 62.09 tests / 44.05 final. Counts: REAL 2, PARTLY 2 (fixed), FALSE_POSITIVE 5 (kept), UNSURE 0; status DONE.

- Inputs: QL report `_ql/metered-usage-rating-pipeline/20261031T1040_report/QL_REPORT.md`, triage `20261031_metered-usage-rating-pipeline/ql1_triage_fc64da5/TRIAGE.md`, last QC v4 (copy 145bdba, PASS 0/0/0).
- Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Session rename: `name_session.py 1f91f8f` printed `codex: no match` / `opencode: ['ses_e6f3f3374ffe0iszwmMlAhIPvp']` (list does not show 1f91f8f; not retried).
- BUNDLE backed up to WORK/ql1_bbc865f36130 (tree bbc865f36130); task.toml copied from Tasks_INPUT (only task.toml:9 authors differ, now Shubhi Goyal); BUNDLE tree 88bd0a39d67b == Tasks_INPUT before any fix.
- Lever list (LEVERS.md): LV-MU-5, LV-MU-6, LV-MU-7, LV-MU-8, LV-MU-9; graded noise LV-MU-1, LV-MU-3 (reported too).

## Findings

| ID | label | rule quote (live kit file:line) | evidence quote (bundle file:line) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| F-1 | REAL | AL-17 05_Alignment_Integrity_QC.md:74 "verifier timeout plausible for what test.sh does"; Final_checklist.md:390 "Every one of the five oracle runs must read exactly `1.000`"; :400 "An errored trial is not a score." | before: tests/test_output.py:1041-1045 `if "hidden" not in _CACHE:` (same check-then-set at :1048-1096, :1120-1133, :1243-1246 `_cached_run`, :1258-1261 `_expected`), only lock :1209 `_RUN_LOCK` used at :1195; test.sh:10 `exec rewardkit /tests ...` (no concurrency flag), tests/Dockerfile:5 rewardkit 0.2.1 (8 threads default); triage measured hidden built 8x, long months 4x, ladder months up to 8x, oracle verifier 1819.6 s of task.toml:21 2700 s; QL Step 10 five trials errored | FIX: one RLock per cache key (`_key_lock`, tests/test_output.py:1027-1036) wraps all nine builders (:1039 shipped, :1052 hidden, :1061 long, :1074 ladder, :1087 scaled, :1134 small, :1143 near, :1259 run, :1275 expected); `_RUN_LOCK` (:1224) stays innermost; TRUTH.md Verification paragraph records the lock and the measured fix-gate verifier wall | AL-17 FIX (guard each cache key) | LV-MU-5..9 none; noise LV-MU-1/3 none (trap losses identical) | not needed | WORK/tests_template.py -> tests/test_output.py; truth_template.md, write_truth.py -> solution/TRUTH.md |
| F-2 | PARTLY (REAL part fixed) | TS-11 03_Tests_QC.md:41 "Deterministic: the same submission must earn the same score every run"; _COMMON_RULES_v5.md:58 limit "at least 3x the oracle's measured time on the hidden inputs" | before: tests/test_output.py:29 `RUN_LIMIT_SEC = 15`; environment/data/rating_contract.md:48-49 "Every run of the program finishes / within 15 seconds."; triage: oracle worst 6.35 s (ladder_3, two generators busy) x 3 = 19.05 s > 15 | FIX option (a): RUN_LIMIT_SEC 20 (:29), seven long/ladder descriptions (:1894, :1914, :1934, :1954, :1994, :2034, :2074 "exits 0 within 20 seconds"), rating_contract.md:49 "within 20 seconds.", TRUTH.md :48, :154, :160, :272 | TS-11 FIX | LV-MU-8 160 -> 160, LV-MU-9 112 -> 112 (stated "easier only for programs between 15 and 20 s"; measured none); LV-MU-5/6/7 none | not needed (no loss shrank) | WORK/tests_template.py, assemble_tests.py -> tests/test_output.py; environment/data/rating_contract.md (and WORK copy); truth_template.md -> TRUTH.md; XREF.md "run limit" (retired "within 15 seconds"); LEVERS.md, RULE_COVERAGE.md text |
| M-1 | REAL | DS-22 02_Data_Solution_QC.md:78 "TRUTH.md describes the bundle that actually shipped"; AL-18 05:75 "nothing mentions files, paths, counts, or numbers that do not match the actual bundle" | before: solution/TRUTH.md:198 `task.toml: bd6b83a7...` vs actual task.toml sha 4ac8cf6b95666e39... (authors line changed after v4) | FIX: all nine digests rewritten by write_truth.py after every other edit (last run after the fix gate) | DS-22 FIX (TRUTH by script, last) | all none | not needed | solution/TRUTH.md |
| M-2 | PARTLY (REAL part fixed) | TS-19 03_Tests_QC.md:50 "every promise the instruction makes must be graded by something" | before: instruction.md:28 "your program is run again on this month's files and on fresh extracts of other months"; tests grade this month from `/app/out` (`return _expected("shipped", _shipped_files), OUT_DIR`, before :1299) and never rerun the program on the shipped files | FIX: instruction.md:28 now "this month's documents are graded as they stand in `/app/out` when you finish, and your program is run again on fresh extracts of other months laid out like this one, from a different input folder and a different working directory." (no new rule, no hint) | TS-19 FIX (reword promise to what is graded) | all none (wording of grading channel only; no rule text changed) | not needed | instruction.md; XREF.md "whole-document sentence" (retired "graded whole on fresh inputs") |
| W-1 | FALSE_POSITIVE (carry-over KEEP) | TS-23 03:62 "at least 10 checks (fail), at most 35 (warn)"; Final_checklist.md:204 "A real file carries 10 to 35 checks" | 113 checks; KEPT.md row G03-2 (rests on FC:204 and 03:62); QC_RULINGS.md:137-138 TS-23 warn KEEP; playbook row TS-23 | KEEP, no change | KEEP (KEPT G03-2) | all none | n/a | none |
| W-2 | FALSE_POSITIVE (carry-over) | TS-20 03:51 "Weights map to importance semantically" | v4:204 TS-20 PASS, v4:255 CL-5 PASS on the same weights (unchanged this round); QC_RULINGS.md:66 | KEEP, no change | REBUT (QC_RULINGS:66) | all none | n/a | none |
| W-3 | FALSE_POSITIVE (carry-over) | JD-6 04_Judge_QC.md:72 "Self-contained: the judge sees the trajectory and artifacts" | tests/judge.toml:5 `atif-trajectory = "/logs/agent/trajectory.json"`; :155 R12 `n2_states_document_figure_other_than_delivered` reads the trajectory the judge is given; a4 judge_response.txt:46-49 judge applied it | KEEP, no change | REBUT | all none | n/a | none |
| W-4 | FALSE_POSITIVE (carry-over) | JD-9 04:86 "Process focus is the judged channel's value-add" | tests/judge.toml:13 `b1_times_last_program_on_app_data` ... :208 `b11_times_run_on_long_rate_card` (process criteria :13-120, :208-289); test.sh:8 `chmod -R go-rwx /tests` | KEEP, no change | REBUT | all none | n/a | none |
| W-5 | FALSE_POSITIVE (carry-over) | JD-11 04:88 "Negative-weight criteria should cover the real cheat surface of THIS task" | tests/judge.toml:181 R14 `n4_opens_verifier_paths` (:180-192); task.toml:23 `environment_mode = "separate"` | KEEP, no change | REBUT | all none | n/a | none |

## Noise keeps

Noise diff vs previous QC copy `QC/copies/145bdba` (`diff -rq`): only task.toml differs (authors line :9). Every line cited by F-1, F-2 and M-2 is byte-identical to the copy that passed v4 (AL-17 PASS v4:279, TS-11 PASS v4:195, TS-19 PASS v4:203). These are NOT kept as noise: the triage brings new measured evidence the v4 reviewer did not have (duplicate builds counted per key, oracle verifier 1819.6 s, oracle run 6.35 s with both cores busy, QL Step 10 errored trials), and the master ruled them FIX. M-1 is new since v4 (task.toml authors changed the digest). W-1..W-5 are carry-over KEEPs resting on KEPT.md rows / QC_RULINGS, not noise rows. Noise keeps: 0.

## Side effects

Always 14: `20261024_process/qc_reverse/B/FIX_SIDE_EFFECTS.md` lists for the fixed ids: TS-19 -> TS-23 warn, TS-26 fail (FIX_SIDE_EFFECTS.md:12); DS-22 is the common follow-on of any regeneration (FIX_SIDE_EFFECTS.md:7, :36 stale-generator chain). AL-17 and TS-11 have no row. Re-checked:

| side-effect id | from fix | check | verdict |
|---|---|---|---|
| TS-23 | M-2 (TS-19) | check count 113, positives 422, negative -5; G7 diff has no check added or removed | no new finding (count unchanged; carry-over warn KEEP G03-2) |
| TS-26 | M-2 (TS-19) | M-2 changed instruction.md:28 only; no test or criterion added; G7 diff names every hunk (limit, locks, seven descriptions) | no new finding |
| DS-22 | M-1 and every edit | write_truth.py run after the last edit; the nine digests in solution/TRUTH.md equal `shasum -a 256` of the files; precheck DS-22 sha check clean | no new finding |
| AL-18 | F-2 text | `grep -rIn 'within 15\|15 second\|15-second'` over BUNDLE: 0 hits; every "20 seconds" (TRUTH.md:48, :154, :160, :192, :272, rating_contract.md:49, test_output.py:29 and descriptions) matches RUN_LIMIT_SEC = 20 | no new finding |
| stale generator (FIX_SIDE_EFFECTS.md:36) | all test edits | edits made in WORK/tests_template.py and assemble_tests.py, tests regenerated by script; G7 diff of tests/ before/after saved WORK/ql1/G7_diff.txt, 13 hunks all named | no new finding |

Side-effect findings: 0.

## Trap survival

Fixed tests (test_output.py sha 79e405be...) scored in Docker by WORK/ql1/ql1_runner.py (log `_runs/20261031/metered-usage-rating-pipeline/fixscore-20261031T124007-d421/logs/trap.log`, json WORK/ql1/trap_ql1.json); baseline = WORK/d215/trap_d215.json on the shipped tests (sha a8f5f94e..., identical to the pre-fix bundle). Points lost of 422:

| lever | before | after | kept |
|---|---|---|---|
| LV-MU-5 | 335 | 335 | 100% |
| LV-MU-6 | 204 | 204 | 100% |
| LV-MU-7 | 204 | 204 | 100% |
| LV-MU-8 | 160 | 160 | 100% |
| LV-MU-9 | 112 | 112 | 100% |
| noise LV-MU-1 | 351 | 351 | 100% |
| noise LV-MU-3 | 257 | 257 | 100% |
| QC variant A | 249 | 249 | 100% |

Oracle 422/422, no program 0/422, empty program 0/422, constant documents 22/422, detach forge 106/422 (all as before). The 20-second limit moved no lever: the LV-MU-8 walk and the LV-MU-9 scan still overrun 20 s on every long and ladder month. Trap survival PASS.

## QC_RULINGS rows

- TS-19 (M-2): promise reworded to what is graded (this month from `/app/out`, other months by rerun); no test change. Ruling: an instruction promise of a rerun that no test performs is fixed in the instruction, not by adding a test.
- TS-20 (W-2): weights unchanged this round; v4:204 PASS stands (QC_RULINGS.md:66).
- TS-13, TS-26: no check body or weight changed (G7 diff); no finding.
- AL-28: stacking_check output identical before/after (OUT/STACKING_CHECK.md); hand PASS on R12/R13/R15 unchanged.
- JD-7, JD-15: judge.toml untouched; no criterion cites the run limit or instruction.md:28 wording (`grep -n 'second\|fresh\|this month\|again' tests/judge.toml`: only :14, :209, :222 elapsed-seconds wording, no limit value).
- IN-15, IN-16: instruction.md:28 now has one reading (this month graded as delivered, other months by rerun); no graded rule of engagement added or removed.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| F-1 | per-key lock in tests/test_output.py:1027-1036, nine `with _key_lock(...)` blocks :1039-:1275 | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: no check body, name, description or weight changed by F-1 (`diff -w` of G7 hunks: indentation only plus lock lines); CL-2 constant 22/422 and detach 106/422 unchanged; CL-4 per-document checks unchanged |
| F-2 | RUN_LIMIT_SEC 20 test_output.py:29; descriptions :1894, :1914, :1934, :1954, :1994, :2034, :2074; rating_contract.md:49 | TS-14, TS-20, TS-25, TS-26, CL-2, CL-4; JD-7, JD-15 | PASS: description "exits 0 within 20 seconds" matches body `timeout=RUN_LIMIT_SEC` (test_output.py:29); weights unchanged; judge has no limit value (judge.toml:14, :209, :222 ask for elapsed seconds only) |
| M-1 | solution/TRUTH.md digests and prose by write_truth.py | DS-22, DS-27, AL-18 | PASS: digests equal files; added paragraph TRUTH.md:188-193 describes the verifier (no production narrative) |
| M-2 | instruction.md:28 | TS-19, TS-26, AL-1, AL-2, IN-15, IN-16; JD-2, JD-5, JD-6, JD-9, JD-13, JD-15, AL-28 | PASS: visible tier graded from `/app/out` (test_output.py `_source`, `return _expected("shipped", _shipped_files), OUT_DIR`), hidden/long/ladder by rerun from other dirs; judge.toml untouched, stacking unchanged |

Touched rows: 4.

## Vacuity probe

- Tests: the unedited shipped environment has no program (`environment/` holds only Dockerfile and data/). Run through every positive check by WORK/ql1/ql1_runner.py: no program 0/422, empty program 0/422 (trap_ql1.json rows 'vacuity no program', 'nop empty program').
- Judge: 18 positive criteria b1..b18 read; each requires an agent act on `/app/out/transform.py` or a reply (b1-b5, b7-b9, b11-b17 a command output in the trajectory; b6 a delivered program's handlers; b10/b18 the reply). The unedited container has no program and no trajectory, so none passes.
- Vacuity PASS.

## Gate results

Fix gate `_runs/20261031/metered-usage-rating-pipeline/fixgate-20261031T130146-6ce7/` (copies by live kit `exe_copy.py`, plain and `--owner-only`; warm image built first; bundle lock taken and released; each lane started on dockfree START=yes):

| trial | reward | verifier phase (s) | exception |
|---|---|---|---|
| oracle-1 | 1.0 | 262.3 | none |
| oracle-2 | 1.0 | 296.3 | none |
| oracle-3 | 1.0 | 284.1 | none |
| owner-1 (owner-only copy) | 1.0 | 298.7 | none |
| nop-1 | 0.0 | 210.4 | none |

Verifier wall: worst 298.7 s of 2700 s (11.1 percent; oracle worst 296.3 s, 11.0 percent), down from 1819.6 s (67.4 percent) before the per-key lock. Recorded in solution/TRUTH.md:192-193.

Kit scripts after the last edit: structure_qc 17 pass / 1 warn (X1 collector_south.txt, KEPT X1 REBUT) / 0 fail; instruction_qc 5/0/0; tests_qc 36 pass / 1 warn (A3 113 checks, KEPT G03-2) / 0 fail; judge_qc 19/0/0. xref_check 24 entries, 0 findings. precheck last line `PRECHECK CLEAN`. stacking_check unchanged (OUT/STACKING_CHECK.md).

## Fix receipt

- (a) Tree sha (method `find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`): QC copy 145bdba bbc865f36130; BUNDLE before fix (Tasks_INPUT task.toml) 88bd0a39d67b; after 23342018274a. Tasks_INPUT/metered-usage-rating-pipeline synced by `rsync -a --delete` 88bd0a39d67b -> 23342018274a (`diff -rq` empty). Output_RFP untouched.
- (b) Test checks: no check added, removed or reweighted; 113 checks, positive total 422 -> 422, negative -5 -> -5; reward.toml 0.5/422 unchanged (sha 99b3e771). Changed text only: seven long/ladder `finishes` descriptions "exits 0 within 15 seconds" -> "within 20 seconds" (test_output.py:1894, :1914, :1934, :1954, :1994, :2034, :2074). Judge criteria: none changed (23 criteria, positive 50 unchanged).
- (c) Oracle/owner/nop: before (v4 / QC copy 145bdba) oracle 1.000 x5, owner 1.000, nop 0.000 (QL Step 10: five oracle trials errored on the QL machine); after 1.0 x3, owner 1.0, nop 0.0, no errored trial.
- (d) a4 program (`gate_run_a4/.../app/out/transform.py`, saved copy sha 489ea8a1): before 262/422 (paid-run verifier); after 262/422 on the fixed tests (Docker, WORK/ql1/trap_ql1.json row 'a4 program'). Lever checks moved: none; the same 44 long_1..3 and ladder_1..4 checks fail ("no result within 20 seconds").
- (e) Rescan after last edit:
  - AL-18 / DS-22 / DS-27: PASS. Nine digests in solution/TRUTH.md:197-205 equal `shasum -a 256` of the files; `grep -rIn 'within 15\|15 second\|15-second'` BUNDLE 0 hits; TRUTH.md:188-193 describes the verifier, no production narrative.
  - JD-14 / AL-28: PASS. judge.toml untouched (sha ff83d309); stacking_check output identical to before; hand PASS on R12/R13/R15 stands.
  - AL-1 / AL-2: PASS. instruction.md:28 promise (this month graded as it stands in `/app/out`, other months by rerun from other dirs) matches test_output.py `_source` (visible tier `_expected("shipped", _shipped_files), OUT_DIR`; hidden/long/ladder by `_cached_run`).
  - AL-27: PASS. Long and ladder fixtures still trigger LV-MU-8/9 (losses 160 and 112, unchanged).

## Deviations from master directions

- Verifier wall measured as Harbor's verifier phase (`result.json` verifier started_at/finished_at, container start to finish) because the verifier containers are removed when the trial ends; the triage figure 1819.6 s was the same kind of span.

## Lessons for the master

- Per-key cache locks cut the oracle verifier from 1819.6 s to under 300 s; duplicate builds, not slow code, were the cost | template_change: _COMMON_RULES_v5.md:58 add "test caches built once per key (per-key lock) since rewardkit runs 8 checks at once"
- Raising a run limit 15 -> 20 s moved no lever because the walk/scan variants overrun by 5x+ | no change: LEVER_RULES_v3.md 1C already asks for the trap re-measure
- Harbor result.json verifier phase is the practical verifier-wall source after containers are removed | template_change: _COMMON_RULES_v5.md:49 (d) name "result.json verifier started_at/finished_at"
