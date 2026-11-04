TRIAGE (read only, triage_tasks.py 1.0)

Tasks folders: synthetic
Gate: tests under 85, rubric under 85, final under 40; slip cap 50 percent; paid model claude-opus-5; settings from settings.json.
Kit ids: located in the given kit folder.
Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.
Every QC risk and family line is a hint with its file and line, never a verdict.

RANKED TABLE

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | syn_regrade | 84.4 | REGRADE | 23.1 / 10.7 / 16.9 | 23.1 / 10.7 / 16.9 | 1 0 0 | none | -23.1 | D2 D4 | 19.2 | 1 | tests or judge changed after the trusted run (tests: 1 added, 1 removed, 0 reweighted since the run); K2: regrade the last valid run |
| 2 | syn_grader_crash | 43.0 | RE RUN FIRST | none | 23.1 / 10.7 / 16.9 | 0 1 0 | grader crash | unknown | D2 D4 |  | 1 | no trusted claude-opus-5 run: BROKEN grader crash |
| 3 | syn_grader_timeout | 43.0 | RE RUN FIRST | none | 23.1 / 10.7 / 16.9 | 0 1 0 | grader timeout | unknown | D2 D4 | 19.2 | 1 | no trusted claude-opus-5 run: BROKEN grader timeout |
| 4 | syn_judge_api | 43.0 | RE RUN FIRST | none | 23.1 / 10.7 / 16.9 | 0 1 0 | judge or API error | unknown | D2 D4 | 19.2 | 1 | no trusted claude-opus-5 run: BROKEN judge or API error |
| 5 | syn_missing_outputs | 43.0 | RE RUN FIRST | none | 23.1 / 10.7 / 16.9 | 0 1 0 | missing outputs | unknown | D2 D4 |  | 1 | no trusted claude-opus-5 run: BROKEN missing outputs |
| 6 | syn_perm_text | 43.0 | RE RUN FIRST | none | 23.1 / 10.7 / 16.9 | 0 1 0 | permission denied | unknown | D2 D4 | 19.2 | 1 | no trusted claude-opus-5 run: BROKEN permission denied |

Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).

TASK 1. syn_regrade

Recommendation: REGRADE. tests or judge changed after the trusted run (tests: 1 added, 1 removed, 0 reweighted since the run); K2: regrade the last valid run.
Score 84.4 = gate 40.0 + levers 19.4 + QC 17.0 + effort 8.0. Distance to gate: -23.1.
Real score (trusted claude-opus-5 runs): 23.1 / 10.7 / 16.9. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at synthetic/syn_regrade; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json)
   folder synthetic/syn_regrade/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:13) and make agent files readable (tests/test_output.py:51): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder synthetic/syn_regrade/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D2 carrier or encoding variation inside a named standard: environment/data/schema.md:3 All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose | environment/data/schema.md:53 `audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output ord
2. D4 a stated runtime on a large hidden input: tests/test_output.py:65 try:stdout,stderr=p.communicate(timeout=120)
Checks the paid model lost (trusted runs, positive test weight 52.0):
1. scenario_revision_tie lost 5.00 (9.6 percent)
2. scenario_fx_half_up lost 5.00 (9.6 percent)
3. scenario_withholding_half_up lost 5.00 (9.6 percent)
4. scenario_pool_priority lost 5.00 (9.6 percent)
5. scenario_largest_remainder lost 5.00 (9.6 percent)
6. scenario_advance_priority lost 5.00 (9.6 percent)
7. scenario_period_carry lost 5.00 (9.6 percent)
8. scenario_signed_adjustment lost 5.00 (9.6 percent)
Largest share one slip took: 19.2 percent (scenario_fx_half_up and 1 similar) against the cap 50 percent; all hidden input checks lost together 76.9 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: ask Ayush: regrade the last valid run with the current tests and judge (K2), then triage again.

TASK 2. syn_grader_crash

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN grader crash.
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at synthetic/syn_grader_crash; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (grader crash), model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json); evidence: synthetic/syn_grader_crash/trajectories/claude-opus-5/run_1/verifier/ctrf.json: summary tests 0 (no check ran)
   folder synthetic/syn_grader_crash/trajectories/claude-opus-5/run_1
   also BROKEN grader crash: synthetic/syn_grader_crash/trajectories/claude-opus-5/run_1/verifier/test-stdout.txt:1 ImportError while loading conftest '/tests/conftest.py'.
   note: tests drop the uid (tests/test_output.py:13) and make agent files readable (tests/test_output.py:51): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder synthetic/syn_grader_crash/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D2 carrier or encoding variation inside a named standard: environment/data/schema.md:3 All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose | environment/data/schema.md:53 `audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output ord
2. D4 a stated runtime on a large hidden input: tests/test_output.py:65 try:stdout,stderr=p.communicate(timeout=120)
Checks the paid model lost: none.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice.

TASK 3. syn_grader_timeout

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN grader timeout.
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at synthetic/syn_grader_timeout; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (grader timeout), model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json); evidence: synthetic/syn_grader_timeout/trajectories/claude-opus-5/run_1/result.json exception_info: VerifierTimeoutError: Verifier execution timed out after 900.0 seconds
   folder synthetic/syn_grader_timeout/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:13) and make agent files readable (tests/test_output.py:51): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder synthetic/syn_grader_timeout/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D2 carrier or encoding variation inside a named standard: environment/data/schema.md:3 All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose | environment/data/schema.md:53 `audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output ord
2. D4 a stated runtime on a large hidden input: tests/test_output.py:65 try:stdout,stderr=p.communicate(timeout=120)
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 52.0):
1. scenario_revision_tie lost 5.00 (9.6 percent)
2. scenario_fx_half_up lost 5.00 (9.6 percent)
3. scenario_withholding_half_up lost 5.00 (9.6 percent)
4. scenario_pool_priority lost 5.00 (9.6 percent)
5. scenario_largest_remainder lost 5.00 (9.6 percent)
6. scenario_advance_priority lost 5.00 (9.6 percent)
7. scenario_period_carry lost 5.00 (9.6 percent)
8. scenario_signed_adjustment lost 5.00 (9.6 percent)
Largest share one slip took: 19.2 percent (scenario_fx_half_up and 1 similar) against the cap 50 percent; all hidden input checks lost together 76.9 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice.

TASK 4. syn_judge_api

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN judge or API error.
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at synthetic/syn_judge_api; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (judge or API error), model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json); evidence: synthetic/syn_judge_api/trajectories/claude-opus-5/run_1/verifier/reward-details.json judge R1: Judge call failed: litellm.RateLimitError: Error code: 429 rate limit reached
   folder synthetic/syn_judge_api/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:13) and make agent files readable (tests/test_output.py:51): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder synthetic/syn_judge_api/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D2 carrier or encoding variation inside a named standard: environment/data/schema.md:3 All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose | environment/data/schema.md:53 `audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output ord
2. D4 a stated runtime on a large hidden input: tests/test_output.py:65 try:stdout,stderr=p.communicate(timeout=120)
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 52.0):
1. scenario_revision_tie lost 5.00 (9.6 percent)
2. scenario_fx_half_up lost 5.00 (9.6 percent)
3. scenario_withholding_half_up lost 5.00 (9.6 percent)
4. scenario_pool_priority lost 5.00 (9.6 percent)
5. scenario_largest_remainder lost 5.00 (9.6 percent)
6. scenario_advance_priority lost 5.00 (9.6 percent)
7. scenario_period_carry lost 5.00 (9.6 percent)
8. scenario_signed_adjustment lost 5.00 (9.6 percent)
Largest share one slip took: 19.2 percent (scenario_fx_half_up and 1 similar) against the cap 50 percent; all hidden input checks lost together 76.9 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: ask Ayush: regrade the run (judge only) or one new paid run.

TASK 5. syn_missing_outputs

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN missing outputs.
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at synthetic/syn_missing_outputs; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (missing outputs), model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json); evidence: synthetic/syn_missing_outputs/trajectories/claude-opus-5/run_1: no verifier score file (reward-details, ctrf, reward, test-stdout)
   folder synthetic/syn_missing_outputs/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:13) and make agent files readable (tests/test_output.py:51): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder synthetic/syn_missing_outputs/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D2 carrier or encoding variation inside a named standard: environment/data/schema.md:3 All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose | environment/data/schema.md:53 `audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output ord
2. D4 a stated runtime on a large hidden input: tests/test_output.py:65 try:stdout,stderr=p.communicate(timeout=120)
Checks the paid model lost: none.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice.

TASK 6. syn_perm_text

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN permission denied.
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at synthetic/syn_perm_text; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (permission denied), model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json); evidence: synthetic/syn_perm_text/trajectories/claude-opus-5/run_1/verifier/test-stdout.txt:1 [check] scenario_fx_half_up: python3: can't open file '/app/out/settle.py': [Errno 13] Permission denied
   folder synthetic/syn_perm_text/trajectories/claude-opus-5/run_1
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder synthetic/syn_perm_text/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D2 carrier or encoding variation inside a named standard: environment/data/schema.md:3 All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose | environment/data/schema.md:53 `audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output ord
2. D4 a stated runtime on a large hidden input: tests/test_output.py:65 try:stdout,stderr=p.communicate(timeout=120)
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 52.0):
1. scenario_revision_tie lost 5.00 (9.6 percent)
2. scenario_fx_half_up lost 5.00 (9.6 percent)
3. scenario_withholding_half_up lost 5.00 (9.6 percent)
4. scenario_pool_priority lost 5.00 (9.6 percent)
5. scenario_largest_remainder lost 5.00 (9.6 percent)
6. scenario_advance_priority lost 5.00 (9.6 percent)
7. scenario_period_carry lost 5.00 (9.6 percent)
8. scenario_signed_adjustment lost 5.00 (9.6 percent)
Largest share one slip took: 19.2 percent (scenario_fx_half_up and 1 similar) against the cap 50 percent; all hidden input checks lost together 76.9 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

