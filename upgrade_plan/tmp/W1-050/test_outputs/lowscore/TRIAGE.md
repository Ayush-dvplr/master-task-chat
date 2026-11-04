TRIAGE (read only, triage_tasks.py 1.0)

Tasks folders: tasks_copy_20261022T0105
Gate: tests under 85, rubric under 85, final under 40; slip cap 50 percent; paid model claude-opus-5; settings from settings.json.
Kit ids: located in the given kit folder.
Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.
Every QC risk and family line is a hint with its file and line, never a verdict.

RANKED TABLE

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 03_inference-gate-replay | 95.9 | FIX AND PUSH | 10.8 / 2.3 / 6.5 | 10.8 / 2.3 / 6.5 | 1 0 0 | none | -33.5 | D1 D2 D4 D8 | 43.0 | 0 | trusted run under the gate (final 6.5); QC with the fix map, keep the design |
| 2 | 04_speculative-decode-arbiter | 93.8 | FIX AND PUSH | 16.0 / 7.7 / 11.8 | 16.0 / 7.7 / 11.8 | 1 0 0 | none | -28.2 | D1 D2 D3 D4 D6 D8 decoy | 16.0 | 1 | trusted run under the gate (final 11.8); QC with the fix map, keep the design |
| 3 | 05_quillfen-sla-settlement-repair | 93.8 | FIX AND PUSH | 15.9 / 10.1 / 13.0 | 15.9 / 10.1 / 13.0 | 1 0 0 | none | -27.0 | D1 D2 D3 D5 D6 decoy | 11.4 | 1 | trusted run under the gate (final 13.0); QC with the fix map, keep the design |
| 4 | 01_assay-plate-triage | 91.3 | FIX AND PUSH | 3.3 / 7.7 / 5.5 | 3.3 / 7.7 / 5.5 | 1 0 0 | none | -34.5 | D1 D2 D4 D8 | 44.4 | 1 | trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 5 | 02_modulus-sieve-replay | 90.8 | FIX AND PUSH | 6.2 / 5.6 / 5.9 | 6.2 / 5.6 / 5.9 | 1 0 0 | none | -34.1 | D1 D4 D6 D8 | 18.8 | 1 | trusted run under the gate (final 5.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 6 | 06_grain-intake-settlement | 90.7 | FIX AND PUSH | 6.4 / 41.6 / 24.0 | 6.4 / 41.6 / 24.0 | 1 0 0 | none | -16.0 | D1 D2 D4 D8 | 10.6 | 1 | trusted run under the gate (final 24.0); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 7 | 07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760 | 43.0 | RE RUN FIRST | none | 15.7 / 35.3 / 25.5 | 0 1 0 | permission denied (inferred) | unknown | D1 D8 | 9.8 | 1 | no trusted claude-opus-5 run: BROKEN permission denied (inferred) |
| 8 | 09_ninefold-crown-settlement-recompute | 43.0 | RE RUN FIRST | none | 15.3 / 43.1 / 29.2 | 0 0 1 | permission risk | unknown | D1 D2 D3 D4 D8 decoy | 24.7 | 3 | no trusted claude-opus-5 run: UNSURE permission risk |
| 9 | 10_reefer-power-dispatch-recompute | 43.0 | RE RUN FIRST | none | 8.1 / 50.6 / 29.4 | 0 0 1 | permission risk | unknown | D1 D2 D3 D4 D8 D9 decoy | 24.2 | 3 | no trusted claude-opus-5 run: UNSURE permission risk |
| 10 | 08_registry-lock-footprint-resolution | 40.0 | RE RUN FIRST | none | 2.2 / 52.6 / 27.4 | 0 1 0 | permission denied (inferred) | unknown | D1 D4 | 7.2 | 2 | no trusted claude-opus-5 run: BROKEN permission denied (inferred) |

Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).

TASK 1. 03_inference-gate-replay

Recommendation: FIX AND PUSH. trusted run under the gate (final 6.5); QC with the fix map, keep the design.
Score 95.9 = gate 40.0 + levers 25.9 + QC 20.0 + effort 10.0. Distance to gate: -33.5.
Real score (trusted claude-opus-5 runs): 10.8 / 2.3 / 6.5. Recorded score (every paid run): 10.8 / 2.3 / 6.5.
Inventory: bundle at tasks_copy_20261022T0105/03_inference-gate-replay; present 10 of 10 kit files; data 86 KB in 14 files, 4 formats (.csv:8 .jsonl:3 .md:2 .json:1).
Tests now: 35 checks, positive weight 93.0; judge now: 16 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 10.8, rubric 2.3, final 6.5 (from pass_summary.json)
   folder tasks_copy_20261022T0105/03_inference-gate-replay/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1090) and make agent files readable (tests/test_output.py:1074): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:607 hidden data generator or held out inputs (16 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/reports.md:102 Every digest is the lowercase hexadecimal sha256 of a run of UTF-8 bytes, taken
3. D4 a stated runtime on a large hidden input: instruction.md:15 The program takes two command line arguments, the input directory first and the output directory second, and w
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/gate.md` and `/app/data/reports.md` describe the gate and its four reports: the input  | instruction.md:7 The second part is thinner. `/app/data/probes.jsonl` and the four lookup tables beside it are the recorded shi
Checks the paid model lost (trusted runs, positive test weight 93.0):
1. full_ledger_on_unseen_shift_alpha lost 5.00 (5.4 percent)
2. full_ledger_on_unseen_shift_bravo lost 5.00 (5.4 percent)
3. full_ledger_on_unseen_shift_charlie lost 5.00 (5.4 percent)
4. full_ledger_on_unseen_shift_delta lost 5.00 (5.4 percent)
5. full_ledger_on_unseen_shift_echo lost 5.00 (5.4 percent)
6. full_ledger_on_unseen_shift_foxtrot lost 5.00 (5.4 percent)
7. full_ledger_on_unseen_shift_golf lost 5.00 (5.4 percent)
8. full_ledger_on_unseen_shift_hotel lost 5.00 (5.4 percent)
9. and 17 more
Largest share one slip took: 43.0 percent (full_ledger_on_unseen_shift_alpha and 7 similar) against the cap 50 percent; all hidden input checks lost together 86.0 percent.
QC risk hints:
1. none found
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 2. 04_speculative-decode-arbiter

Recommendation: FIX AND PUSH. trusted run under the gate (final 11.8); QC with the fix map, keep the design.
Score 93.8 = gate 40.0 + levers 26.8 + QC 17.0 + effort 10.0. Distance to gate: -28.2.
Real score (trusted claude-opus-5 runs): 16.0 / 7.7 / 11.8. Recorded score (every paid run): 16.0 / 7.7 / 11.8.
Inventory: bundle at tasks_copy_20261022T0105/04_speculative-decode-arbiter; present 10 of 10 kit files; data 978 KB in 50 files, 12 formats (.jsonl:11 .logfmt:7 .psv:7 .md:6 .tsv:6).
Tests now: 30 checks, positive weight 94.0; judge now: 24 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 16.0, rubric 7.7, final 11.8 (from pass_summary.json)
   folder tasks_copy_20261022T0105/04_speculative-decode-arbiter/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1804) and make agent files readable (tests/test_output.py:1850): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:37 hidden data generator or held out inputs (31 lines)
2. D2 carrier or encoding variation inside a named standard: instruction.md:196 Every file you write is UTF-8 with no byte order mark, uses a line feed as its | environment/data/SPEC-SDA.md:274 Every file the replay writes is UTF-8 without a byte order mark, uses a line
3. D3 a documented rule misread or over applied: instruction.md:14 document is the authority on identifiers, repairs, token [redacted], the | instruction.md:67 superseded is a stream like any other for every purpose here.
4. D4 a stated runtime on a large hidden input: tests/test_output.py:1884 timeout=10)
5. D6 many interacting seeded faults: instruction.md:74 identifier, with the value of K the recording asked for after repair, how many | instruction.md:105 repair code, including any code that no window needed.
6. D8 carried state that never heals: instruction.md:120 number of live leases it ever carried at one tick. | environment/data/SPEC-SDA.md:57 nothing about the accounting and is carried through to the registry unchanged.
7. decoy decoys: decoy named file environment/data/windows-draft-10.jsonl | decoy named file environment/data/windows-draft-06.jsonl
Checks the paid model lost (trusted runs, positive test weight 94.0):
1. k_schedule_matches_reference lost 5.00 (5.3 percent)
2. acceptance_ledger_matches_reference lost 5.00 (5.3 percent)
3. window_disposition_first_section_matches_reference lost 5.00 (5.3 percent)
4. window_disposition_second_section_matches_reference lost 5.00 (5.3 percent)
5. window_disposition_third_section_matches_reference lost 5.00 (5.3 percent)
6. token_accounting_matches_reference lost 5.00 (5.3 percent)
7. stream_metrics_matches_reference lost 5.00 (5.3 percent)
8. tenant_cost_matches_reference lost 5.00 (5.3 percent)
9. and 10 more
Largest share one slip took: 16.0 percent (window_disposition_first_section_matches_reference and 2 similar) against the cap 50 percent; all hidden input checks lost together 80.8 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 3. 05_quillfen-sla-settlement-repair

Recommendation: FIX AND PUSH. trusted run under the gate (final 13.0); QC with the fix map, keep the design.
Score 93.8 = gate 40.0 + levers 26.8 + QC 17.0 + effort 10.0. Distance to gate: -27.0.
Real score (trusted claude-opus-5 runs): 15.9 / 10.1 / 13.0. Recorded score (every paid run): 15.9 / 10.1 / 13.0.
Inventory: bundle at tasks_copy_20261022T0105/05_quillfen-sla-settlement-repair; present 10 of 10 kit files; data 15489 KB in 50 files, 41 formats (.md:4 .log:3 .xml:3 .csv:3 .xferlog:1).
Tests now: 35 checks, positive weight 88.0; judge now: 31 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 15.9, rubric 10.1, final 13.0 (from pass_summary.json)
   folder tasks_copy_20261022T0105/05_quillfen-sla-settlement-repair/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:4307) and make agent files readable (tests/test_output.py:4604): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:1180 hidden data generator or held out inputs (12 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/partition_deletions.html:2 <html><head><meta charset="utf-8"><title>Partition deletions</title></head><body> | environment/data/settlement-contract.md:117 `sla_minutes`, analytics `sla_seconds` divided by 60, finance ISO 8601 duration, legacy `NhMm` form. Each line
3. D3 a documented rule misread or over applied: environment/data/settlement-contract.md:142 **4.4 Precedence.** `FREEZE` is tested before `PAUSE`, and `PAUSE` before `HOLIDAY`. | environment/data/settlement-contract.md:177 **5.8 Evidence tiers.** The tiers in precedence order are `physical`, `worker`, `scheduler` and `operator`. Th
4. D5 one detail buried in a very long document: environment/data/heartbeats.txt has 60120 words | environment/data/settlement-contract.md:10 reference. Where this contract names a record of practice instead of stating a rule, the practice those record
5. D6 many interacting seeded faults: instruction.md:1 Quillfen settles its scheduled job commitments once a month, and the March 2026 settlement is wrong. The engin | instruction.md:5 Deliver the repaired repository as `/app/out/patched-repo.zip`, in the archive layout the output contract desc
6. decoy decoys: decoy named file environment/data/crontab_legacy.cron | decoy named file environment/data/sched_legacy.syslog
Checks the paid model lost (trusted runs, positive test weight 88.0):
1. test_ledger_statuses_match_unseen_extracts lost 5.00 (5.7 percent)
2. test_ledger_penalties_match_unseen_extracts lost 5.00 (5.7 percent)
3. test_blame_parents_match_unseen_extracts lost 5.00 (5.7 percent)
4. test_chargeback_penalties_match_unseen_extracts lost 5.00 (5.7 percent)
5. test_source_reading_probe_settles lost 5.00 (5.7 percent)
6. test_evidence_probe_settles lost 5.00 (5.7 percent)
7. test_summary_and_settlement_records_match_shipped_month lost 5.00 (5.7 percent)
8. test_summary_penalties_and_settlement_money_match_shipped_month lost 5.00 (5.7 percent)
9. and 9 more
Largest share one slip took: 11.4 percent (test_ledger_statuses_match_unseen_extracts and 1 similar) against the cap 50 percent; all hidden input checks lost together 63.6 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 4. 01_assay-plate-triage

Recommendation: FIX AND PUSH. trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 91.3 = gate 40.0 + levers 27.3 + QC 17.0 + effort 7.0. Distance to gate: -34.5.
Real score (trusted claude-opus-5 runs): 3.3 / 7.7 / 5.5. Recorded score (every paid run): 3.3 / 7.7 / 5.5.
Inventory: bundle at tasks_copy_20261022T0105/01_assay-plate-triage; present 10 of 10 kit files; data 165 KB in 32 files, 4 formats (.csv:16 .json:8 .jsonl:6 .md:2).
Tests now: 33 checks, positive weight 90.0; judge now: 15 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 3.3, rubric 7.7, final 5.5 (from pass_summary.json)
   folder tasks_copy_20261022T0105/01_assay-plate-triage/trajectories/claude-opus-5/run_1
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

TASK 5. 02_modulus-sieve-replay

Recommendation: FIX AND PUSH. trusted run under the gate (final 5.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 90.8 = gate 40.0 + levers 26.8 + QC 17.0 + effort 7.0. Distance to gate: -34.1.
Real score (trusted claude-opus-5 runs): 6.2 / 5.6 / 5.9. Recorded score (every paid run): 6.2 / 5.6 / 5.9.
Inventory: bundle at tasks_copy_20261022T0105/02_modulus-sieve-replay; present 10 of 10 kit files; data 189 KB in 14 files, 4 formats (.csv:9 .jsonl:2 .md:2 .json:1).
Tests now: 35 checks, positive weight 96.0; judge now: 29 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 6.2, rubric 5.6, final 5.9 (from pass_summary.json)
   folder tasks_copy_20261022T0105/02_modulus-sieve-replay/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1289) and make agent files readable (tests/test_output.py:1282): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:4 hidden data generator or held out inputs (23 lines)
2. D4 a stated runtime on a large hidden input: instruction.md:15 The program takes two command line arguments, the input directory first and the output directory second, and w
3. D6 many interacting seeded faults: environment/data/engine.md:78 - fault count: starts at zero. | environment/data/engine.md:122 figure alone. A lane whose fault count has reached the figure that seals it
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/engine.md` and `/app/data/reports.md` describe the mill and its four reports: the inpu | environment/data/engine.md:70 ## Carried lane state
Checks the paid model lost (trusted runs, positive test weight 96.0):
1. residue_ledger_on_unseen_passes lost 5.00 (5.2 percent)
2. lane_rollup_on_unseen_passes lost 5.00 (5.2 percent)
3. pass_rollups_on_unseen_passes lost 5.00 (5.2 percent)
4. normalisation_gain lost 3.00 (3.1 percent)
5. governing_count_columns lost 3.00 (3.1 percent)
6. least_absolute_residue lost 3.00 (3.1 percent)
7. sector_adjustment_upper lost 3.00 (3.1 percent)
8. sector_adjustment_lower lost 3.00 (3.1 percent)
9. and 20 more
Largest share one slip took: 18.8 percent (sector_adjustment_upper and 5 similar) against the cap 50 percent; all hidden input checks lost together 87.5 percent.
QC risk hints:
1. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 6. 06_grain-intake-settlement

Recommendation: FIX AND PUSH. trusted run under the gate (final 24.0); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 90.7 = gate 40.0 + levers 26.7 + QC 17.0 + effort 7.0. Distance to gate: -16.0.
Real score (trusted claude-opus-5 runs): 6.4 / 41.6 / 24.0. Recorded score (every paid run): 6.4 / 41.6 / 24.0.
Inventory: bundle at tasks_copy_20261022T0105/06_grain-intake-settlement; present 10 of 10 kit files; data 208 KB in 29 files, 4 formats (.csv:15 .json:7 .jsonl:5 .md:2).
Tests now: 35 checks, positive weight 94.0; judge now: 30 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. TRUSTED, model claude-opus-5: tests 6.4, rubric 41.6, final 24.0 (from pass_summary.json)
   folder tasks_copy_20261022T0105/06_grain-intake-settlement/trajectories/claude-opus-5/run_1
   note: tests drop the uid (tests/test_output.py:1213) and make agent files readable (tests/test_output.py:1198): permission ruled out
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:530 hidden data generator or held out inputs (35 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/engine.md:51 - its bytes are not valid UTF-8, or the text is not one JSON object; | environment/data/reports.md:82 Both digests are lowercase hex sha256 over UTF-8 text built from the three
3. D4 a stated runtime on a large hidden input: tests/test_output.py:1228 proc.wait(timeout=5) | instruction.md:15 The program takes two command line arguments, the input directory first and the output directory second, and i
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/engine.md` and `/app/data/reports.md` give the file shapes, how the engine screens the | environment/data/engine.md:86 changes no carried value. `elevator.json` counts what screening did; see
Checks the paid model lost (trusted runs, positive test weight 94.0):
1. mode_bit_chain_tare lost 5.00 (5.3 percent)
2. mode_bit_dockage_echo lost 5.00 (5.3 percent)
3. mode_bit_role_lookback lost 5.00 (5.3 percent)
4. mode_bit_band_tier_shift lost 5.00 (5.3 percent)
5. mode_bit_testweight_floor lost 5.00 (5.3 percent)
6. mode_bit_custom_haul lost 5.00 (5.3 percent)
7. mode_bit_tare_delta lost 5.00 (5.3 percent)
8. mode_bit_testweight_order lost 5.00 (5.3 percent)
9. and 20 more
Largest share one slip took: 10.6 percent (mode_bit_testweight_floor and 1 similar) against the cap 50 percent; all hidden input checks lost together 93.6 percent.
QC risk hints:
1. DS-21 (02_Data_Solution_QC.md:70): trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 7. 07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN permission denied (inferred).
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 15.7 / 35.3 / 25.5.
Inventory: bundle at tasks_copy_20261022T0105/07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760; present 10 of 10 kit files; data 8 KB in 6 files, 3 formats (.json:3 .md:2 .csv:1).
Tests now: 35 checks, positive weight 51.0; judge now: 11 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (permission denied (inferred)), model claude-opus-5: tests 15.7, rubric 35.3, final 25.5 (from pass_summary.json); evidence: tests drop the uid at tests/test_output.py:20; no read grant for the delivered program found; agent listed derive_report.py as -rw------- (agent/trajectory.json step 13); 4 shipped or interface checks passed while all 26 other positive checks failed
   folder tasks_copy_20261022T0105/07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760/trajectories/claude-opus-5/run_1
   also BROKEN missing outputs: tasks_copy_20261022T0105/07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760/trajectories/claude-opus-5/run_1/result.json exception_info: RewardFileNotFoundError: No reward file found at /home/ec2-user/Terminal 2.0/harness/Terminal_2.0_Harbor_Harness/jobs/2026-10-19__17-30-56/fdc5a20d-2dfe-5f64-a3fa-2c
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:144 hidden data generator or held out inputs (82 lines)
2. D8 carried state that never heals: instruction.md:27 Records are scored in file order and each one carries a running state forward, | instruction.md:65 predicts positive, and the running state is replayed over the records in file
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 51.0):
1. hidden_full_report_matches_fresh_derivation lost 5.00 (9.8 percent)
2. fresh_carry_state_replays_in_file_order lost 5.00 (9.8 percent)
3. fresh_hinge_basis_and_winsorization lost 5.00 (9.8 percent)
4. fresh_calibration_temperature_and_prior_shift lost 5.00 (9.8 percent)
5. fresh_report_canonical_serialization lost 1.00 (2.0 percent)
6. fresh_banker_rounding_precision lost 1.00 (2.0 percent)
7. fresh_zero_variance_feature_zeroed lost 1.00 (2.0 percent)
8. fresh_unseen_category_contributes_zero lost 1.00 (2.0 percent)
9. and 19 more
Largest share one slip took: 9.8 percent (hidden_full_report_matches_fresh_derivation) against the cap 50 percent; all hidden input checks lost together 82.3 percent.
QC risk hints:
1. TS-24 (03_Tests_QC.md:68): tests/test_output.py:20 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

TASK 8. 09_ninefold-crown-settlement-recompute

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: UNSURE permission risk.
Score 43.0 = gate 15.0 + levers 10.0 + QC 11.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 15.3 / 43.1 / 29.2.
Inventory: bundle at tasks_copy_20261022T0105/09_ninefold-crown-settlement-recompute; present 10 of 10 kit files; data 561 KB in 58 files, 16 formats (.md:22 .csv:10 .toml:5 .json:4 .tsv:3).
Tests now: 34 checks, positive weight 85.0; judge now: 35 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. UNSURE (permission risk), model claude-opus-5: tests 15.3, rubric 43.1, final 29.2 (from pass_summary.json); evidence: tests drop the uid at tests/test_output.py:5810; no read grant for the delivered program found; 8 shipped or interface checks passed while all 19 other positive checks failed; negative negative_hardcoded_sample_answers fired, which a program that never ran can trip
   folder tasks_copy_20261022T0105/09_ninefold-crown-settlement-recompute/trajectories/claude-opus-5/run_1
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:4 hidden data generator or held out inputs (69 lines) | environment/data/corpus_sentinel_note.txt:3 This event does not reach every branch the specifications describe. The
2. D2 carrier or encoding variation inside a named standard: environment/data/serialisation_and_digest_contract.md:5 Every delivered document is UTF-8 with line feed line endings, no | environment/data/serialisation_and_digest_contract.md:33 `<?xml version="1.0" encoding="UTF-8"?>` on its own line. Indentation is
3. D3 a documented rule misread or over applied: instruction.md:5 Three papers are not plain text and carry values found nowhere else. `/app/data/panel_capacity_workbook.xlsx`  | environment/data/crown_settlement_overview.md:41 The arithmetic policy, the boundary conventions, the revision precedence,
4. D4 a stated runtime on a large hidden input: tests/test_output.py:5975 proc.communicate(timeout=30) | environment/data/crownsettle_program_contract.md:15 - Python standard library only. No package is installed at run time.
5. D8 carried state that never heals: environment/data/rounding_and_arithmetic_policy.yaml:8 deferral: forbidden | environment/data/spec_stage_p05_round_eligibility.md:12 ## The running state
6. decoy decoys: decoy named file environment/data/legacy_season_extract.csv
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 85.0):
1. contested_core_exact lost 5.00 (5.9 percent)
2. contested_pairing_exact lost 5.00 (5.9 percent)
3. contested_standings_exact lost 5.00 (5.9 percent)
4. wide_core_exact lost 5.00 (5.9 percent)
5. wide_pairing_exact lost 5.00 (5.9 percent)
6. wide_standings_exact lost 5.00 (5.9 percent)
7. thin_core_exact lost 5.00 (5.9 percent)
8. thin_pairing_exact lost 5.00 (5.9 percent)
9. and 11 more
Largest share one slip took: 24.7 percent (contested_core_exact and 4 similar) against the cap 50 percent; all hidden input checks lost together 78.8 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
2. CL-4 (Final_checklist.md:494): tests/test_output.py: 92 percent of positive weight on whole document checks, no per row or per field check
3. TS-24 (03_Tests_QC.md:68): tests/test_output.py:5810 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

TASK 9. 10_reefer-power-dispatch-recompute

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: UNSURE permission risk.
Score 43.0 = gate 15.0 + levers 10.0 + QC 11.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 8.1 / 50.6 / 29.4.
Inventory: bundle at tasks_copy_20261022T0105/10_reefer-power-dispatch-recompute; present 10 of 10 kit files; data 532 KB in 59 files, 16 formats (.md:22 .csv:13 .toml:6 .txt:3 .tsv:2).
Tests now: 35 checks, positive weight 62.0; judge now: 35 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. UNSURE (permission risk), model claude-opus-5: tests 8.1, rubric 50.6, final 29.4 (from pass_summary.json); evidence: tests drop the uid at tests/test_output.py:5849; no read grant for the delivered program found; no run evidence either way
   folder tasks_copy_20261022T0105/10_reefer-power-dispatch-recompute/trajectories/claude-opus-5/run_1
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:4 hidden data generator or held out inputs (66 lines) | environment/data/corpus_sentinel_note.txt:3 This operating day does not reach every branch the stage
2. D2 carrier or encoding variation inside a named standard: environment/data/serialisation_and_digest_contract.md:3 Every published document is written as utf-8 with a line feed as the | environment/data/serialisation_and_digest_contract.md:25 <?xml version="1.0" encoding="utf-8"?>, indents every nesting
3. D3 a documented rule misread or over applied: environment/data/data_lineage.md:30 | reconciliation_pass_policy.toml | p06 p09 | the scope of the spill and of the redistribution | | environment/data/data_lineage.md:31 | priority_precedence_policy.toml | p04 p11 | the precedence hierarchy and the absent call sentinel |
4. D4 a stated runtime on a large hidden input: tests/test_output.py:5977 result = subprocess.run(_untrusted(command), cwd=str(work), timeout=900,
5. D8 carried state that never heals: environment/data/readme_first.txt:21 carried by the topology paper. Every register in this directory | environment/data/rounding_and_arithmetic_policy.yaml:11 half_up: a remainder of exactly one half is carried away from zero
6. D9 one clause hardening contracts: environment/data/dispatch_admission_ladder.txt:22 the plug zone refuses the temperature class the reefer declares
7. decoy decoys: decoy named file environment/data/legacy_tariff_extract.csv
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 62.0):
1. program_strained_early_exact lost 5.00 (8.1 percent)
2. program_strained_middle_exact lost 5.00 (8.1 percent)
3. program_strained_late_exact lost 5.00 (8.1 percent)
4. program_wide_early_exact lost 5.00 (8.1 percent)
5. program_wide_middle_exact lost 5.00 (8.1 percent)
6. program_wide_late_exact lost 5.00 (8.1 percent)
7. program_sparse_early_exact lost 5.00 (8.1 percent)
8. program_sparse_middle_exact lost 5.00 (8.1 percent)
9. and 5 more
Largest share one slip took: 24.2 percent (program_strained_early_exact and 2 similar) against the cap 50 percent; all hidden input checks lost together 72.6 percent.
QC risk hints:
1. IN-17 (01_Instruction_QC.md:47): environment/data/known_traps_and_footguns.md:1 announced trap wording: # Known traps and footguns
2. CL-4 (Final_checklist.md:494): tests/test_output.py: 97 percent of positive weight on whole document checks, no per row or per field check
3. TS-24 (03_Tests_QC.md:68): tests/test_output.py:5849 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

TASK 10. 08_registry-lock-footprint-resolution

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN permission denied (inferred).
Score 40.0 = gate 15.0 + levers 4.0 + QC 14.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 2.2 / 52.6 / 27.4.
Inventory: bundle at tasks_copy_20261022T0105/08_registry-lock-footprint-resolution; present 10 of 10 kit files; data 26 KB in 29 files, 4 formats (.pidx:15 .md:10 .csv:3 .json:1).
Tests now: 35 checks, positive weight 139.0; judge now: 9 criteria.
Structure problems:
1. S3 (structure_qc.py:28) warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
Runs:
1. BROKEN (permission denied (inferred)), model claude-opus-5: tests 2.2, rubric 52.6, final 27.4 (from pass_summary.json); evidence: tests drop the uid at tests/test_output.py:1865; no read grant for the delivered program found; agent listed optimize.py as -rw------- (agent/trajectory.json step 35); 3 shipped or interface checks passed while all 27 other positive checks failed
   folder tasks_copy_20261022T0105/08_registry-lock-footprint-resolution/trajectories/claude-opus-5/run_1
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:40 hidden data generator or held out inputs (60 lines) | environment/data/calibration.md:3 The calibration shards, tier marker 1, are a held out rehearsal population that never enters any lock
2. D4 a stated runtime on a large hidden input: tests/test_output.py:1971 proc.wait(timeout=10)
Checks the paid model lost (untrusted (no trusted run) runs, positive test weight 139.0):
1. trap_mask_bytes lost 5.00 (3.6 percent)
2. trap_chain_version lost 5.00 (3.6 percent)
3. trap_delta2_day lost 5.00 (3.6 percent)
4. trap_drift_key lost 5.00 (3.6 percent)
5. trap_block_permute lost 5.00 (3.6 percent)
6. trap_backref_deps lost 5.00 (3.6 percent)
7. trap_endian_island lost 5.00 (3.6 percent)
8. trap_biased_count lost 5.00 (3.6 percent)
9. and 20 more
Largest share one slip took: 7.2 percent (trap_drift_key and 1 similar) against the cap 50 percent; all hidden input checks lost together 97.1 percent.
QC risk hints:
1. CL-4 (Final_checklist.md:494): instruction.md: no exact bar sentence found (CL-4 exemption needs one)
2. TS-24 (03_Tests_QC.md:68): tests/test_output.py:1865 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

