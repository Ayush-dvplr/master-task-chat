TRIAGE (read only, triage_tasks.py 1.0)

Tasks folders: mix
Gate: tests under 85, rubric under 85, final under 40; slip cap 50 percent; paid model claude-opus-5; settings from settings.json.
Kit ids: located in the given kit folder.
Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.
Every QC risk and family line is a hint with its file and line, never a verdict.

RANKED TABLE

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | assay-plate-triage | 91.3 | FIX AND PUSH | 3.3 / 7.7 / 5.5 | 3.3 / 7.7 / 5.5 | 1 0 0 | none | -34.5 | D1 D2 D4 D8 | 44.4 | 1 | trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 2 | cohort-retention-reconciliation | 46.0 | RE RUN FIRST | none | none | 0 0 0 | none | unknown | D1 D4 |  | 0 | no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score |

Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).

TASK 1. assay-plate-triage

Recommendation: FIX AND PUSH. trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 91.3 = gate 40.0 + levers 27.3 + QC 17.0 + effort 7.0. Distance to gate: -34.5.
Real score (trusted claude-opus-5 runs): 3.3 / 7.7 / 5.5. Recorded score (every paid run): 3.3 / 7.7 / 5.5.
Inventory: bundle at mix/assay-plate-triage; present 10 of 10 kit files; data 166 KB in 32 files, 4 formats (.csv:16 .json:8 .jsonl:6 .md:2).
Tests now: 33 checks, positive weight 90.0; judge now: 15 criteria.
Structure problems: none found.
Runs:
1. TRUSTED, model claude-opus-5: tests 3.3, rubric 7.7, final 5.5 (from pass_summary.json)
   folder mix/assay_runs_only/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:862) and make agent files readable (tests/test_output.py:847): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:442 hidden data generator or held out inputs (18 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/reports.md:81 Both digests are lowercase hex sha256 over UTF-8 text built from the three
3. D4 a stated runtime on a large hidden input: instruction.md:15 The program takes two command line arguments, the input directory first and the output directory second, and i
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/engine.md` and `/app/data/reports.md` give the file shapes, the carried plate state, t | environment/data/engine.md:55 ## Carried plate state
Checks the paid model lost (trusted runs, positive test weight 90.0):
1. every_bit_except_chain_blank lost 5.00 (5.6 percent)
2. every_bit_except_role_lookback lost 5.00 (5.6 percent)
3. every_bit_except_exposure_floor lost 5.00 (5.6 percent)
4. every_bit_except_baseline_delta lost 5.00 (5.6 percent)
5. every_bit_except_mask_absolves lost 5.00 (5.6 percent)
6. every_bit_except_matrix_alias lost 5.00 (5.6 percent)
7. full_mode_run_alpha lost 5.00 (5.6 percent)
8. full_mode_run_beta lost 5.00 (5.6 percent)
9. and 19 more
Largest share one slip took: 44.4 percent (full_mode_run_alpha and 7 similar) against the cap 50 percent; all hidden input checks lost together 96.7 percent.
QC risk hints:
1. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 2. cohort-retention-reconciliation

Recommendation: RE RUN FIRST. no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score.
Score 46.0 = gate 15.0 + levers 4.0 + QC 20.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): none.
Inventory: bundle at mix/cohort-retention-reconciliation; present 10 of 10 kit files; data 14 KB in 14 files, 3 formats (.csv:8 .json:4 .md:2).
Tests now: 24 checks, positive weight 71.0; judge now: 8 criteria.
Structure problems: none found.
Runs:
1. BROKEN (grader timeout), model oracle (not the paid model, shown only): tests , rubric , final  (from none); evidence: mix/cohort_gates/errored_build_timeout/crr-oracle-1/crr_run__oNBzNnQ/result.json exception_info: EnvironmentStartTimeoutError: Verifier environment start timed out after 900.0 seconds
   folder mix/cohort_gates/errored_build_timeout/crr-oracle-1/crr_run__oNBzNnQ
   also BROKEN grader timeout: mix/cohort_gates/errored_build_timeout/crr-oracle-1/crr_run__oNBzNnQ/exception.txt:37 raise TimeoutError from exc_val
   also BROKEN grader crash: mix/cohort_gates/errored_build_timeout/crr-oracle-1/crr_run__oNBzNnQ/exception.txt:1 Traceback (most recent call last):
2. BROKEN (grader timeout), model oracle (not the paid model, shown only): tests , rubric , final  (from none); evidence: mix/cohort_gates/errored_build_timeout/crr-oracle-2/crr_run__qVuGMyN/result.json exception_info: EnvironmentStartTimeoutError: Verifier environment start timed out after 900.0 seconds
   folder mix/cohort_gates/errored_build_timeout/crr-oracle-2/crr_run__qVuGMyN
   also BROKEN grader timeout: mix/cohort_gates/errored_build_timeout/crr-oracle-2/crr_run__qVuGMyN/exception.txt:37 raise TimeoutError from exc_val
   also BROKEN grader crash: mix/cohort_gates/errored_build_timeout/crr-oracle-2/crr_run__qVuGMyN/exception.txt:1 Traceback (most recent call last):
3. BROKEN (grader crash), model oracle (not the paid model, shown only): tests , rubric , final  (from none); evidence: mix/cohort_gates/errored_build_timeout/crr-owner-only-1/crr_owner__LthD5aM/result.json exception_info: CancelledError: 
   folder mix/cohort_gates/errored_build_timeout/crr-owner-only-1/crr_owner__LthD5aM
   also BROKEN grader crash: mix/cohort_gates/errored_build_timeout/crr-owner-only-1/crr_owner__LthD5aM/exception.txt:1 Traceback (most recent call last):
   also BROKEN missing outputs: mix/cohort_gates/errored_build_timeout/crr-owner-only-1/crr_owner__LthD5aM: no verifier score file (reward-details, ctrf, reward, test-stdout)
4. TRUSTED, model oracle (not the paid model, shown only): tests 0.0, rubric , final 0.0 (from checks)
   folder mix/cohort_gates/jobs/crr2-forgery-1/crr_forge__NRYPNwB
   note: tests drop the uid (tests/test_output.py:61) and make agent files readable (tests/test_output.py:779): permission ruled out
5. TRUSTED, model nop (not the paid model, shown only): tests 0.0, rubric , final 0.0 (from checks)
   folder mix/cohort_gates/jobs/crr2-nop-1/crr_run__GNXjn8o
   note: tests drop the uid (tests/test_output.py:61) and make agent files readable (tests/test_output.py:779): permission ruled out
6. TRUSTED, model oracle (not the paid model, shown only): tests 100.0, rubric , final 100.0 (from checks)
   folder mix/cohort_gates/jobs/crr2-oracle-0600/crr_0600__enGv3Nj
7. TRUSTED, model oracle (not the paid model, shown only): tests 100.0, rubric , final 100.0 (from checks)
   folder mix/cohort_gates/jobs/crr2-oracle-1/crr_run__F7iC8YU
8. TRUSTED, model oracle (not the paid model, shown only): tests 100.0, rubric , final 100.0 (from checks)
   folder mix/cohort_gates/jobs/crr2-oracle-2/crr_run__sAWs4GB
9. TRUSTED, model oracle (not the paid model, shown only): tests 100.0, rubric , final 100.0 (from checks)
   folder mix/cohort_gates/jobs/crr2-owner-only-1/crr_owner__AmZHzvB
10. UNSURE (permission risk), model oracle (not the paid model, shown only): tests 3.3, rubric , final 3.3 (from checks); evidence: tests drop the uid at tests/test_output.py:61; a read grant exists (tests/test_output.py:779) but the score shows the split; 2 shipped or interface checks passed while all 18 other positive checks failed
   folder mix/cohort_gates/jobs/crr2-stub-1/crr_stub__U64NSWd
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:42 hidden data generator or held out inputs (73 lines)
2. D4 a stated runtime on a large hidden input: tests/test_output.py:831 _, stderr = process.communicate(timeout=60)
QC risk hints:
1. none found
Next: ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice.

