TRIAGE (read only, triage_tasks.py 1.0)

Tasks folders: teammates
Gate: tests under 85, rubric under 85, final under 40; slip cap 50 percent; paid model claude-opus-5; settings from settings.json.
Kit ids: located in the given kit folder.
Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.
Every QC risk and family line is a hint with its file and line, never a verdict.

RANKED TABLE

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 05550e00-2e66-4fab-8bce-727bfbbce24c | 91.0 | FIX AND PUSH | 5.2 / 4.7 / 4.9 | 5.2 / 4.7 / 4.9 | 1 0 0 | none | -35.1 | D1 D2 D4 D8 | 8.6 | 1 | trusted run under the gate (final 4.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 2 | 28a29cf0-a25e-5de2-a8b9-140b24175727 | 90.5 | FIX AND PUSH | 7.5 / 4.7 / 6.1 | 7.5 / 4.7 / 6.1 | 1 0 0 | none | -33.9 | D1 D2 D4 D8 | 43.0 | 1 | trusted run under the gate (final 6.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 3 | f348165e-f7f6-5e73-b82d-b84ee751f3b0 | 89.8 | FIX AND PUSH | 6.2 / 42.5 / 24.4 | 6.2 / 42.5 / 24.4 | 1 0 0 | none | -15.6 | D1 D2 D3 D4 D8 | 25.6 | 2 | trusted run under the gate (final 24.4); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 4 | 75407a55-6665-505e-95d8-5ff9bdb3384f | 86.4 | FIX AND PUSH | 23.1 / 10.7 / 16.9 | 23.1 / 10.7 / 16.9 | 1 0 0 | none | -23.1 | D2 D4 | 19.2 | 1 | trusted run under the gate (final 16.9); QC with the fix map, keep the design |
| 5 | 8defd7be-eb46-5779-a556-aec18521635e | 82.5 | FIX AND PUSH | 2.4 / 15.7 / 9.1 | 2.4 / 15.7 / 9.1 | 1 0 0 | none | -30.9 | D1 D4 D8 decoy | 66.3 | 3 | trusted run under the gate (final 9.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 6 | f357cd96-1afe-50bc-b553-a1be78c907e3 | 61.4 | HARDEN WITH OWNER | 70.7 / 70.6 / 70.7 | 70.7 / 70.6 / 70.7 | 1 0 0 | none | 30.6 | D1 D2 D3 D4 D8 | 5.0 | 0 | trusted run 30.6 points over the gate; hardening changes the design, so the owner agrees first |
| 7 | 65ba10c2-1913-5076-94a6-d8763828cf25 | 46.4 | DROP | 69.1 / 87.9 / 78.5 | 69.1 / 87.9 / 78.5 | 1 0 0 | none | 38.5 | D1 D2 D3 D4 D6 D8 D9 decoy | 22.1 | 3 | trusted run 38.5 points over the gate; levers would need a redesign |

Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).

TASK 1. 05550e00-2e66-4fab-8bce-727bfbbce24c

Recommendation: FIX AND PUSH. trusted run under the gate (final 4.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 91.0 = gate 40.0 + levers 27.0 + QC 17.0 + effort 7.0. Distance to gate: -35.1.
Real score (trusted claude-opus-5 runs): 5.2 / 4.7 / 4.9. Recorded score (every paid run): 5.2 / 4.7 / 4.9.
Inventory: bundle at teammates/anubis-stage-2/05550e00-2e66-4fab-8bce-727bfbbce24c; present 10 of 10 kit files; data 92 KB in 14 files, 4 formats (.csv:8 .jsonl:3 .md:2 .json:1).
Tests now: 28 checks, positive weight 58.0; judge now: 16 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 5.2, rubric 4.7, final 4.9 (from pass_summary.json)
   folder teammates/anubis-stage-2/05550e00-2e66-4fab-8bce-727bfbbce24c/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1089) and make agent files readable (tests/test_output.py:1073): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 37.9, rubric 7.0, final 22.4 (from pass_summary.json)
   folder teammates/anubis-stage-2/05550e00-2e66-4fab-8bce-727bfbbce24c/trajectories/glm-5.3/run_1
   note: tests drop the uid (tests/test_output.py:1089) and make agent files readable (tests/test_output.py:1073): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:607 hidden data generator or held out inputs (16 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/reports.md:102 Every digest is the lowercase hexadecimal sha256 of a run of UTF-8 bytes, taken
3. D4 a stated runtime on a large hidden input: instruction.md:15 The program takes two command line arguments, the input directory first and the output directory second, and w
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/gate.md` and `/app/data/reports.md` describe the gate and its four reports: the input  | instruction.md:7 The second part is thinner. `/app/data/probes.jsonl` and the four lookup tables beside it are the recorded shi
Checks the paid model lost (trusted runs, positive test weight 58.0):
1. full_ledger_on_unseen_shift_alpha lost 5.00 (8.6 percent)
2. meter_accumulates_as_a_first_difference lost 3.00 (5.2 percent)
3. meter_accumulates_per_phase lost 3.00 (5.2 percent)
4. segment_boundary_resets_the_accumulator lost 3.00 (5.2 percent)
5. reserved_meter_repeats_the_previous_probe lost 3.00 (5.2 percent)
6. backlog_step_per_serve lost 3.00 (5.2 percent)
7. backlog_doubles_on_the_marked_tier lost 3.00 (5.2 percent)
8. back_to_back_serve_carries_its_extra lost 3.00 (5.2 percent)
9. and 13 more
Largest share one slip took: 8.6 percent (full_ledger_on_unseen_shift_alpha) against the cap 50 percent; all hidden input checks lost together 89.7 percent.
QC risk hints:
1. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 2. 28a29cf0-a25e-5de2-a8b9-140b24175727

Recommendation: FIX AND PUSH. trusted run under the gate (final 6.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 90.5 = gate 40.0 + levers 26.5 + QC 17.0 + effort 7.0. Distance to gate: -33.9.
Real score (trusted claude-opus-5 runs): 7.5 / 4.7 / 6.1. Recorded score (every paid run): 7.5 / 4.7 / 6.1.
Inventory: bundle at teammates/anubis-stage-2/28a29cf0-a25e-5de2-a8b9-140b24175727; present 10 of 10 kit files; data 180 KB in 23 files, 4 formats (.csv:13 .jsonl:5 .json:3 .md:2).
Tests now: 35 checks, positive weight 93.0; judge now: 16 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 7.5, rubric 4.7, final 6.1 (from pass_summary.json)
   folder teammates/anubis-stage-2/28a29cf0-a25e-5de2-a8b9-140b24175727/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1090) and make agent files readable (tests/test_output.py:1074): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 88.4, final 94.2 (from pass_summary.json)
   folder teammates/anubis-stage-2/28a29cf0-a25e-5de2-a8b9-140b24175727/trajectories/glm-5.3/run_1
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:607 hidden data generator or held out inputs (16 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/reports.md:104 Every digest is the lowercase hexadecimal sha256 of a run of UTF-8 bytes, taken
3. D4 a stated runtime on a large hidden input: instruction.md:17 The program takes two command line arguments, the input directory first and the output directory second, and w
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/gate.md` and `/app/data/reports.md` describe the gate and its four reports: the input  | instruction.md:7 The second worked shift uses the `calibration_` prefix. Its five input files sit beside `calibration_verdicts.
Checks the paid model lost (trusted runs, positive test weight 93.0):
1. full_ledger_on_unseen_shift_alpha lost 5.00 (5.4 percent)
2. full_ledger_on_unseen_shift_bravo lost 5.00 (5.4 percent)
3. full_ledger_on_unseen_shift_charlie lost 5.00 (5.4 percent)
4. full_ledger_on_unseen_shift_delta lost 5.00 (5.4 percent)
5. full_ledger_on_unseen_shift_echo lost 5.00 (5.4 percent)
6. full_ledger_on_unseen_shift_foxtrot lost 5.00 (5.4 percent)
7. full_ledger_on_unseen_shift_golf lost 5.00 (5.4 percent)
8. full_ledger_on_unseen_shift_hotel lost 5.00 (5.4 percent)
9. and 18 more
Largest share one slip took: 43.0 percent (full_ledger_on_unseen_shift_alpha and 7 similar) against the cap 50 percent; all hidden input checks lost together 89.2 percent.
QC risk hints:
1. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 3. f348165e-f7f6-5e73-b82d-b84ee751f3b0

Recommendation: FIX AND PUSH. trusted run under the gate (final 24.4); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 89.8 = gate 40.0 + levers 28.8 + QC 14.0 + effort 7.0. Distance to gate: -15.6.
Real score (trusted claude-opus-5 runs): 6.2 / 42.5 / 24.4. Recorded score (every paid run): 6.2 / 42.5 / 24.4.
Inventory: bundle at teammates/anubis-stage-2/f348165e-f7f6-5e73-b82d-b84ee751f3b0; present 10 of 10 kit files; data 163 KB in 26 files, 10 formats (.md:10 .rqb:5 .csv:2 .json:2 .docx:2).
Tests now: 102 checks, positive weight 352.0; judge now: 33 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 6.2, rubric 42.5, final 24.4 (from pass_summary.json)
   folder teammates/anubis-stage-2/f348165e-f7f6-5e73-b82d-b84ee751f3b0/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:37) and make agent files readable (tests/test_output.py:2047): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 2.8, rubric 42.5, final 22.7 (from pass_summary.json)
   folder teammates/anubis-stage-2/f348165e-f7f6-5e73-b82d-b84ee751f3b0/trajectories/glm-5.3/run_1
   note: tests drop the uid (tests/test_output.py:37) and make agent files readable (tests/test_output.py:2047): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:87 hidden data generator or held out inputs (191 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/ct_svc.md:9 File formats: the rate card, the model weight table and the pool profiles are Office Open XML files as ECMA-37 | environment/data/fm_reports.md:5 Byte forms. JSON reports are written with two-space indentation, keys sorted by code point, a comma at the end
3. D3 a documented rule misread or over applied: environment/data/ct_svc.md:7 Authority: the register, which is the register database (tn_reg.sqlite) together with the group crosswalk and  | environment/data/ct_svc.md:15 Prior output: the prior output file holds the settled reservations of an earlier settlement run of this period
4. D4 a stated runtime on a large hidden input: instruction.md:5 It will also be run on other extracts in the same layout, so nothing in it may depend on this particular perio
5. D8 carried state that never heals: environment/data/lg_rqb.md:49 ## Tables and running state
Checks the paid model lost (trusted runs, positive test weight 352.0):
1. held_out_00_scenario_reports lost 5.00 (1.4 percent)
2. held_out_00_pool_reports lost 5.00 (1.4 percent)
3. held_out_00_billing_reports lost 5.00 (1.4 percent)
4. held_out_01_scenario_reports lost 5.00 (1.4 percent)
5. held_out_01_pool_reports lost 5.00 (1.4 percent)
6. held_out_01_billing_reports lost 5.00 (1.4 percent)
7. held_out_02_scenario_reports lost 5.00 (1.4 percent)
8. held_out_02_pool_reports lost 5.00 (1.4 percent)
9. and 66 more
Largest share one slip took: 25.6 percent (held_out_00_scenario_reports and 17 similar) against the cap 50 percent; all hidden input checks lost together 93.8 percent.
QC risk hints:
1. TS-23 (03_Tests_QC.md:62): tests/test_output.py: 102 checks, over 35 (warn)
2. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 4. 75407a55-6665-505e-95d8-5ff9bdb3384f

Recommendation: FIX AND PUSH. trusted run under the gate (final 16.9); QC with the fix map, keep the design.
Score 86.4 = gate 40.0 + levers 19.4 + QC 17.0 + effort 10.0. Distance to gate: -23.1.
Real score (trusted claude-opus-5 runs): 23.1 / 10.7 / 16.9. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at teammates/anubis-stage-2/75407a55-6665-505e-95d8-5ff9bdb3384f; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 23.1, rubric 10.7, final 16.9 (from pass_summary.json)
   folder teammates/anubis-stage-2/75407a55-6665-505e-95d8-5ff9bdb3384f/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:13) and make agent files readable (tests/test_output.py:51): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 100.0, rubric 60.7, final 80.4 (from pass_summary.json)
   folder teammates/anubis-stage-2/75407a55-6665-505e-95d8-5ff9bdb3384f/trajectories/glm-5.3/run_1
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
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 5. 8defd7be-eb46-5779-a556-aec18521635e

Recommendation: FIX AND PUSH. trusted run under the gate (final 9.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 82.5 = gate 40.0 + levers 27.5 + QC 11.0 + effort 4.0. Distance to gate: -30.9.
Real score (trusted claude-opus-5 runs): 2.4 / 15.7 / 9.1. Recorded score (every paid run): 2.4 / 15.7 / 9.1.
Inventory: bundle at teammates/anubis-stage-2/8defd7be-eb46-5779-a556-aec18521635e; present 10 of 10 kit files; data 92 KB in 9 files, 4 formats (.csv:4 .json:2 .md:2 .jsonl:1).
Tests now: 42 checks, positive weight 83.0; judge now: 32 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 2.4, rubric 15.7, final 9.1 (from pass_summary.json)
   folder teammates/anubis-stage-2/8defd7be-eb46-5779-a556-aec18521635e/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1286) and make agent files readable (tests/test_output.py:1270): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 2.4, rubric 24.3, final 13.3 (from pass_summary.json)
   folder teammates/anubis-stage-2/8defd7be-eb46-5779-a556-aec18521635e/trajectories/glm-5.3/run_1
   note: tests drop the uid (tests/test_output.py:1286) and make agent files readable (tests/test_output.py:1270): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:405 hidden data generator or held out inputs (25 lines)
2. D4 a stated runtime on a large hidden input: instruction.md:13 The program takes two command-line arguments, the input directory first and the output directory second, and i
3. D8 carried state that never heals: instruction.md:3 The written notes in `/app/data/broker.md` and `/app/data/reports.md` describe the shape of the engine and the | environment/data/broker.md:60 ## Carried state
4. decoy decoys: solution/TRUTH.md:57 carries a decoy layout, and a partition that names the parent itself keeps
Checks the paid model lost (trusted runs, positive test weight 83.0):
1. full_ledger_on_unseen_run_alpha lost 5.00 (6.0 percent)
2. full_ledger_on_unseen_run_bravo lost 5.00 (6.0 percent)
3. full_ledger_on_unseen_run_charlie lost 5.00 (6.0 percent)
4. full_ledger_on_unseen_run_delta lost 5.00 (6.0 percent)
5. full_ledger_on_unseen_run_echo lost 5.00 (6.0 percent)
6. full_ledger_on_unseen_run_foxtrot lost 5.00 (6.0 percent)
7. full_ledger_on_unseen_run_golf lost 5.00 (6.0 percent)
8. full_ledger_on_unseen_run_hotel lost 5.00 (6.0 percent)
9. and 29 more
Largest share one slip took: 66.3 percent (full_ledger_on_unseen_run_alpha and 10 similar) against the cap 50 percent; all hidden input checks lost together 92.8 percent.
QC risk hints:
1. TS-23 (03_Tests_QC.md:62): tests/test_output.py: 42 checks, over 35 (warn)
2. SLIP (settings slip_cap_pct (PL answer, ENTRY 87)): one slip took 66.3 percent of positive test points (full_ledger_on_unseen_run_alpha and 10 similar), cap 50 percent
3. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 6. f357cd96-1afe-50bc-b553-a1be78c907e3

Recommendation: HARDEN WITH OWNER. trusted run 30.6 points over the gate; hardening changes the design, so the owner agrees first.
Score 61.4 = gate 15.5 + levers 15.9 + QC 20.0 + effort 10.0. Distance to gate: 30.6.
Real score (trusted claude-opus-5 runs): 70.7 / 70.6 / 70.7. Recorded score (every paid run): 70.7 / 70.6 / 70.7.
Inventory: bundle at teammates/anubis-stage-2/f357cd96-1afe-50bc-b553-a1be78c907e3; present 10 of 10 kit files; data 36 KB in 26 files, 3 formats (.json:17 .csv:8 .md:1).
Tests now: 35 checks, positive weight 99.0; judge now: 20 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 70.7, rubric 70.6, final 70.7 (from pass_summary.json)
   folder teammates/anubis-stage-2/f357cd96-1afe-50bc-b553-a1be78c907e3/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:320) and make agent files readable (tests/test_output.py:217): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 70.7, rubric 70.6, final 70.7 (from pass_summary.json)
   folder teammates/anubis-stage-2/f357cd96-1afe-50bc-b553-a1be78c907e3/trajectories/glm-5.3/run_1
   note: tests drop the uid (tests/test_output.py:320) and make agent files readable (tests/test_output.py:217): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:619 hidden data generator or held out inputs (54 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/README-input-schema.md:122 - `final_state.json` = `{"artifact_count": 10, "epoch_count": E, "folded_digest_sha256": "<sha256 hex>", "stre
3. D3 a documented rule misread or over applied: environment/data/README-input-schema.md:19 | `preemption_ladder.json` | JSON | Class x class precedence and cascade rules |
4. D4 a stated runtime on a large hidden input: tests/test_output.py:394 _, stderr = proc.communicate(timeout=20)
5. D8 carried state that never heals: environment/data/README-input-schema.md:55 Every stream not selected at this phase is a *deferred* stream and remains active in later epochs.
Checks the paid model lost (trusted runs, positive test weight 99.0):
1. hidden_tight_slo_fairness_matches_reference lost 5.00 (5.0 percent)
2. hidden_burst_arrival_fixed_point_matches_reference lost 5.00 (5.0 percent)
3. hidden_migration_dominant_objective_matches_reference lost 5.00 (5.0 percent)
4. hidden_oversubscribed_objective_matches_reference lost 5.00 (5.0 percent)
5. shipped_fixed_point_trace_converges_within_tolerance lost 3.00 (3.0 percent)
6. shipped_tenant_report_has_every_epoch lost 3.00 (3.0 percent)
7. shipped_final_state_matches_reviewed_result lost 3.00 (3.0 percent)
Largest share one slip took: 5.0 percent (hidden_tight_slo_fairness_matches_reference) against the cap 50 percent; all hidden input checks lost together 20.2 percent.
QC risk hints:
1. none found
Next: read the lost checks and families; propose a hardening that keeps the design; the owner agrees before any change (P13).

TASK 7. 65ba10c2-1913-5076-94a6-d8763828cf25

Recommendation: DROP. trusted run 38.5 points over the gate; levers would need a redesign.
Score 46.4 = gate 9.2 + levers 16.2 + QC 11.0 + effort 10.0. Distance to gate: 38.5.
Real score (trusted claude-opus-5 runs): 69.1 / 87.9 / 78.5. Recorded score (every paid run): 69.1 / 87.9 / 78.5.
Inventory: bundle at teammates/anubis-stage-2/65ba10c2-1913-5076-94a6-d8763828cf25; present 10 of 10 kit files; data 421 KB in 59 files, 15 formats (.md:22 .csv:13 .toml:6 .txt:3 .jsonl:2).
Tests now: 34 checks, positive weight 68.0; judge now: 40 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 69.1, rubric 87.9, final 78.5 (from pass_summary.json)
   folder teammates/anubis-stage-2/65ba10c2-1913-5076-94a6-d8763828cf25/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:5741) and make agent files readable (tests/test_output.py:5872): permission ruled out
2. TRUSTED, model glm-5.3 (not the paid model, shown only): tests 30.9, rubric 87.9, final 59.4 (from pass_summary.json)
   folder teammates/anubis-stage-2/65ba10c2-1913-5076-94a6-d8763828cf25/trajectories/glm-5.3/run_1
   note: tests drop the uid (tests/test_output.py:5741) and make agent files readable (tests/test_output.py:5872): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:4 hidden data generator or held out inputs (69 lines) | environment/data/corpus_sentinel_note.txt:4 This shift does not reach every branch the specifications
2. D2 carrier or encoding variation inside a named standard: environment/data/serialisation_and_digest_contract.md:6 Every published document is written in UTF-8 with no byte order | environment/data/serialisation_and_digest_contract.md:37 <?xml version="1.0" encoding="utf-8"?>
3. D3 a documented rule misread or over applied: environment/data/known_traps_and_footguns.md:17 which source system outranks which Y05 | environment/data/rounding_and_arithmetic_policy.yaml:10 is rounded only where a stage specification places a rounding
4. D4 a stated runtime on a large hidden input: tests/test_output.py:5941 _, stderr = proc.communicate(timeout=900)
5. D6 many interacting seeded faults: environment/data/yardledger_program_contract.md:28 class rank or a rung order written into the program is a defect,
6. D8 carried state that never heals: instruction.md:11 Deliver thirty nine documents. Write the fifteen of the stage spine: `/app/out/canonical_events.csv`, `/app/ou | instruction.md:19 Report, in your final message, the canonical event count and the orders set aside under each rung, the live sh
7. D9 one clause hardening contracts: environment/data/spec_stage_y07_move_admission.md:39 and will admit orders this terminal refuses.
8. decoy decoys: decoy named file environment/data/hold_reservation_notices.jsonl | decoy named file environment/data/legacy_tariff_extract.csv
Checks the paid model lost (trusted runs, positive test weight 68.0):
1. program_strained_vessel_exact lost 5.00 (7.3 percent)
2. program_wide_vessel_exact lost 5.00 (7.3 percent)
3. program_sparse_vessel_exact lost 5.00 (7.3 percent)
4. shipped_vessel_family_exact lost 3.00 (4.4 percent)
5. shipped_manifest_exact lost 3.00 (4.4 percent)
Largest share one slip took: 22.1 percent (program_strained_vessel_exact and 2 similar) against the cap 50 percent; all hidden input checks lost together 22.1 percent.
QC risk hints:
1. IN-17 (01_Instruction_QC.md:47): environment/data/known_traps_and_footguns.md:1 announced trap wording: KNOWN TRAPS AND FOOTGUNS
2. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
3. JD-12 (04_Judge_QC.md:89): tests/judge.toml: 40 criteria, over 35 (warn)
Next: leave it unless Ayush wants it; say why in one line.

