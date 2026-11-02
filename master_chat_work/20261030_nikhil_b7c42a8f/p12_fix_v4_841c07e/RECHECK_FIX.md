# RECHECK_FIX b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 (P12 fix v4, board 841c07e)

Replayed prediction is 18.35, below 35, so no warning is needed here. The gate v3.7 holds.

- Session rename: `name_session.py 841c07e` listed opencode `ses_e6f592113ffe51Ki2XyYEVeDQK` (codex: no match).
- QC report: QC/reports/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/v4.md (FAIL: 2 fails with one root, 1 minor, 1 warn, 6 acknowledged). Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271.
- BUNDLE before = QC copy faeab3c = Tasks_INPUT, tree b5dd7c985e44 (`diff -rq` identical). Backup at WORK/qc4_b5dd7c985e44. BUNDLE after: 7e457f09086a. Tasks_INPUT after: 7e457f09086a.
- Noise check (Always 13): all cited lines are byte-identical to faeab3c, but none of them passed in that round. G03-1/G05-1 is the v3 G05-2 fix misfiring (a test negative that was new in 2990713). The G04-1 clause was appended to R25 in 2990713. G04-2 is a new warn on the R25 artifact half. So none of these findings is NOISE.

## Recheck table

| ID | label | rule quote (live kit) | evidence quote | decision | playbook row | effect per lever (L1-L6) | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G03-1 TS-12 / TS-16 (fail) | REAL | 03_Tests_QC.md:42 "In separate mode the verifier sees only the declared artifacts, so a test can grade scope or another effect only when the affected paths are declared artifacts; otherwise the judged channel owns it." Also :47 "Anti-cheat negatives must fire on the cheat and ONLY on the cheat." (ID and wording unchanged) | task.toml: `environment_mode = "separate"`, artifacts = 10 `"type": "file"` paths. The old test_output.py:1023-1036 `negative_output_directory_holds_extra_files` iterated `/app/out`, which arrives holding only those 10 files, so the check could never fire | fix (one root with G05-1): deleted the function and its registration; the negatives comment now reads `sum of absolute values = 23` (test_output.py:1049). The act moves to judge R35 | TS-16 (delete a dead negative only if the act is covered elsewhere: R35); G3 (R35 names the new grader) | none x6 | - | tests/test_output.py, tests/judge.toml, solution/TRUTH.md |
| G05-1 AL-2 / CL-1 (fail) | REAL | 05_Alignment_Integrity_QC.md:33 "Everything promised is graded ... Strict fail" | instruction.md:7 "Treat the corpus as read only, add nothing to the output directory beyond the nine documents and the program, and make a second run over the same input produce the same bytes."; no live grader once the test negative was found dead | fix: judge.toml:454 R35 (weight -1, type "instruction following", evaluation_target "trajectory", importance important): "The agent leaves any file in `/app/out` other than the nine documents and `reserving.py` when its run ends, where instruction.md says to \"add nothing to the output directory beyond the nine documents and the program\"." The J2b guard holds because reserving.py and the nine documents are exempt | AL-2 (grade it through the judged channel, which owns undeclared paths); LEVER_RULES J10 (scope rule w -1, quotes the sentence) | none x6 | - | tests/judge.toml, solution/TRUTH.md |
| G04-1 JD-5 (minor) | REAL | 04_Judge_QC.md:71 "Clearly compound criteria are a fail; a borderline case (two facets of one act) is a minor." | old judge.toml:326 R25 "... states those same two strings in its methodology recap. The recap and the artifact agree on both strings, and the recap names `claim_adjustment_log.log` and `treasury_curve_observations.log` as the logs that settled them." | fix: moved the log-name clause to judge.toml:441 R34 (weight 1, factuality and hallucination, user_facing_message, important), worded as QC wrote it. reward.toml judge = 0.5/66 = 0.007575757575757576, my own computation after G04-2, equal to QC's value | JD-5 (split; each half is shown by the oracle-side reference and the saved run) | none x6 | - | tests/judge.toml, tests/reward.toml, solution/TRUTH.md |
| G04-2 JD-9 / JD-16 item 4 (warn) | REAL | 04_Judge_QC.md:97 "... A deterministic assertion returns the same verdict every run and a judge does not ... Warn rather than fail" | output_contract.md:19 fixes settlement as two strings from closed sets; old test_output.py:579 "(settlement values are graded by judge R25)"; old loop at :618 omitted settlement | fix: `settlement` added first to the `methodology_audit_remaining_sections_exact` loop over shipped, A and B (test_output.py:630). Description updated at :618; the R25 note was dropped from :579. R25 is cut to the recap: "The response states, in its methodology recap, the same `settlement.alae_convention` and `settlement.discount_curve` strings that the agent wrote to `/app/out/methodology_audit.json`." (target user_facing_message). No reseal was needed because the sealed blob already holds settlement {pro_rata, duration_matched} for all three corpora. Lever condition met: every lever keeps 100% (trap table) | JD-9 (deterministic artifact property becomes a test; LEVER_RULES J7) | none x6 | - | tests/test_output.py, tests/judge.toml, solution/TRUTH.md |
| KEPT 1-6 (acknowledged) | carry-over | as in KEPT.md | unchanged lines | keep, untouched (master direction) | - | none | - | - |

No FAIL rows in the QL coverage table beyond the four findings above.

## Gate results

- Kit scripts on BUNDLE after edits: tests_qc 37 pass / 0 warn / 0 fail; judge_qc 19 pass; structure_qc 17 pass; instruction_qc 5 pass.
- Docker block `_runs/20261031/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/fixgate-20261031T121029-8810/`: built with the live exe_copy.py (plain and `--owner-only`). The warm build ran first (WARM_EXIT=0, WARMENV_EXIT=0), then three lanes each started after dockfree START=yes. Results: oracle-1/2/3 = 1.0 / 1.0 / 1.0, owner-1 = 1.0, nop-1 = 0.0, no exceptions, ALL_DONE. The copies were built before the final TRUTH.md rewrite and differ from BUNDLE only in solution/TRUTH.md (a doc).
- precheck.sh BUNDLE, last line: `PRECHECK CLEAN`. It also printed 27 heuristic WARNs, all present before this round; the qc4 backup gave 28, and the R25 JD-5 heuristic warn is now gone.
- xref_check: 45 entries, 0 findings (also 0 before edits, on 44 entries).
- STACKING_CHECK: OUT/STACKING_CHECK.md, verdict `STACKING PASS`. The tool's UNMATCHED-act lump is the same tool artefact as in 72ebb9d and 2990713; R35 joins it.

## Deviations from master directions

None. The master's reward value 0.5/66 equals my computation: 28 judge positives sum to 66 after R25 is cut (still w1) and R34 is added (w1). R35 is a negative and is not counted.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| test negative_output_directory_holds_extra_files | deleted (-1 -> -) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: the act is graded by judge R35 (judge.toml:454) (G3); the other 7 negatives are unchanged; tests_qc 37 pass |
| test methodology_audit_remaining_sections_exact | widened to settlement (3 -> 3) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: the description at test_output.py:618 names settlement (TS-13). The settlement mutants hyg_alae and hyg_curve each score 61/64 and lose only this check (TS-25); the oracle passes. Empty out scores 0 (TS-14). Not a duplicate of attachment_exact (TS-26). CL-2/CL-4: exact whole-section compare, as before |
| test methodology_audit_attachment_exact | description re-worded (3 -> 3) | TS-13 | PASS: test_output.py:579 no longer points at a judge criterion |
| judge R25 | cut to the recap; target state_change -> user_facing_message (1 -> 1) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: one act (recap states the two strings), judge.toml:326. The artifact half now belongs to the test (JD-9). The saved run's closing message states both strings, so JD-7 holds. Its JD-14 neighbours R28/R29 grade a contradiction with the log, a different claim |
| judge R34 | added (- -> 1) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: one act (names two logs), judge.toml:443. The promise is at instruction.md:9; alae_rules.md:3 and discounting_rules.md:3 name these logs; the saved run names both (JD-7). Message only (JD-9). Label factuality and hallucination (JD-15). No other criterion pays for log names |
| judge R35 | added (- -> -1) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: quotes instruction.md:7 (judge.toml:456). Undeclared-path scope belongs to the judged channel (kit 04_Judge_QC.md:97, 03_Tests_QC.md:42). AL-28: the test negative was deleted, so R35 shadows nothing. J2b: reserving.py exempt. Label instruction following, trajectory (J10) |
| tests/reward.toml judge | 0.007692307692307693 -> 0.007575757575757576 | JD-13 | PASS: 0.5/66 with 66 = sum of positive judge weights (tomllib) |

## Vacuity probe

The environment ships no tool (environment/ = Dockerfile + data/ only), so the unedited shipped state is an empty /app/out. Graded on the AFTER tests (WORK/runs/vacuity_v4/grade.json): 0/64 positive, no negative fired: PASS. Judge positives: R1-R14 need stated integers; R15-R24 need the agent's own work; R25 needs strings the agent wrote to methodology_audit.json; R34 needs the log names in the response; R33 needs a delivered module. An agent that changes nothing earns 0: PASS.

## Side effects

| FIX id | ids re-checked (FIX_SIDE_EFFECTS) | result |
|---|---|---|
| G03-1 (TS-16) | TS-14, TS-15 | PASS: 7 remaining negatives are unchanged and fire only on their cheats (tests_qc 37 pass, W5 negatives count fine) |
| G05-1 (AL-2) | TS-25 | PASS: R35 grades the promise; no presence-only test was added |
| G04-1 (JD-5) | JD-15, JD-2, JD-9, JD-7, IN-8 | PASS: labels valid (judge_qc 19 pass); R34 message-only; the saved run shows the act; IN-8: the instruction.md:9 log-name promise now maps to R34 |
| G04-2 (JD-9) | TS-13, TS-25, CL-2 | PASS: see Touched rules |

## Noise keeps

None. No finding is NOISE (see the noise check at the top).

## Trap survival

Before = WORK/runs/trap_v3_after (the current tests at faeab3c); after = WORK/runs/trap_v4_after (BUNDLE tests). P = 64, oracle 64/64 both times.

| lever | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| L1 paid col 4 vs 7 | 39 | 39 | 1.00 | yes | PASS |
| L2 clash cover vs per-claim retention | 21 | 21 | 1.00 | yes | PASS |
| L3 admission instant | 41 | 41 | 1.00 | yes (still loses methodology_audit_remaining_sections_exact) | PASS |
| L4 cutover precedence | 45 | 45 | 1.00 | yes (same) | PASS |
| L5 RE-0412 epochs | 19 | 19 | 1.00 | yes | PASS |
| L6 chain-ladder clip | 22 | 22 | 1.00 | yes | PASS |
| L7 remainder tiebreak (not a lever) | 0 | 0 | - | - | - |

No data, input or hidden case was removed. No negative fired on any variant.

## Score band

Replay of the saved teammate run (original_backup/trajectories/claude-opus-5/run_1, artifacts app/out), graded by grade.py in warm-b7c-tests2 (WORK/runs/replay_v4/grades.jsonl). Predicted final = mean(tests %, judge reading %).

| bundle | tests | judge (reading) | predicted final |
|---|---|---|---|
| BEFORE (b5dd7c985e44) | 7/64 = 10.94 | 16/65 = 24.62 | 17.78 |
| AFTER (7e457f09086a) | 7/64 = 10.94 | 17/66 = 25.76 | 18.35 |

Moved +0.57, by G04-1 alone. The closing message names `claim_adjustment_log.log` for pro_rata and `treasury_curve_observations.log` for duration_matched. Before, that paid 1 point inside R25; now R25 (recap strings) and R34 (log names) pay 1 each. G04-2 moved nothing: the saved settlement is correct, but methodology_audit_remaining_sections_exact already failed on the other sections and hidden runs. G03-1/G05-1 moved nothing: the saved out/ holds only the 10 declared files (the agent removed `__pycache__` at trajectory step 41), so R35 does not fire. Gate v3.7: tests 10.94 < 85, rubric 25.76 < 85, final 18.35 < 40.

## Fix receipt

(a) Tree sha (`find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`): before (QC copy faeab3c) b5dd7c985e44; after 7e457f09086a (BUNDLE = Tasks_INPUT).
(b) Tests: negative_output_directory_holds_extra_files -1 -> -; methodology_audit_remaining_sections_exact 3 -> 3 (now also compares settlement). Positive total 64 -> 64; negatives 24 -> 23 (8 -> 7 checks). Judge: R25 1 -> 1 (cut to the recap); R34 - -> 1; R35 - -> -1. Positive total 65 -> 66; negatives 24 -> 25; 33 -> 35 criteria. reward.toml: test_output 0.0078125 (unchanged), judge 0.007692307692307693 -> 0.007575757575757576.
(c) Oracle 1.0 x3 -> 1.0 x3; owner 1.0 -> 1.0; nop 0.0 -> 0.0.
(d) Saved teammate run re-scored: tests 7/64 before and after, and the same 19 checks lost. No lever check moved; methodology_audit_remaining_sections_exact was lost both times.
(e) Rescan after the last edit:
- AL-18 / DS-22 / DS-27: PASS: TRUTH.md was regenerated by WORK/write_truth.py as the last edit. Counts (24/64, 7/23, 28/66, 7/25, 0.5/64 and 0.5/66) match test_output.py:1049 and judge.toml. The sha256 lines match (precheck CLEAN, xref 0).
- JD-14 / AL-28: PASS: settlement artifact = test only; recap strings = R25; log names = R34; contradiction with a log = R28/R29; extra files in out/ = R35 only.
- AL-1 / AL-2: PASS: instruction.md:7 scope promise is graded by R35; instruction.md:9 log names by R34; settlement strings by the test plus R25. Nothing is graded that is not promised.
- AL-27: PASS: no stated rule changed. RULE_COVERAGE.md has no 0 row; the scope sentence is a process rule graded by R35.

## QC_RULINGS rows

- TS-16 / TS-12 | our design: test negative over /app/out in separate mode | QC verdict: fail (dead, verifier sees only declared artifacts) | label REAL | reason: kit 03_Tests_QC.md:42; scope over undeclared paths belongs to the judged channel (R35). A QC Fix line asking for a test negative over undeclared paths in separate mode should be refused.
- AL-28 | our design: R35 judge negative for extra files in out/ after deleting the test negative | QC verdict: fix direction | label REAL | reason: one grader per act, so no shadowing.
- JD-7 | R34 split from R25 | QC verdict: minor (compound) | label REAL | reason: each half is shown by the saved run's closing message.

## Lessons for the master

- In separate mode a Fix line that asks for a test over a non-artifact path (here /app/out listing) is dead on arrival; check task.toml artifacts before applying | template_change: QC_FIX_PLAYBOOK_v3.md row TS-16 (add: "separate mode: undeclared-path scope goes to a judge negative, never a test").
- Moving a judged artifact property into an existing exact-section test needed no reseal because the sealed blob already carried the section; check the blob before planning a reseal | no change: bundle-specific.
