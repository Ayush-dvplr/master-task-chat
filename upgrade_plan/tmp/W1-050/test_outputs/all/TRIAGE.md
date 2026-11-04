TRIAGE (read only, triage_tasks.py 1.0)

Tasks folders: tasks_copy_20261022T0105, teammates, mix
Gate: tests under 85, rubric under 85, final under 40; slip cap 50 percent; paid model claude-opus-5; settings from defaults (85, 85, 40, 50).
Kit ids: default ids (no kit folder given).
Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.
Every QC risk and family line is a hint with its file and line, never a verdict.

RANKED TABLE

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 03_inference-gate-replay | 95.9 | FIX AND PUSH | 10.8 / 2.3 / 6.5 | 10.8 / 2.3 / 6.5 | 1 0 0 | none | -33.5 | D1 D2 D4 D8 | 43.0 | 0 | trusted run under the gate (final 6.5); QC with the fix map, keep the design |
| 2 | 04_speculative-decode-arbiter | 93.8 | FIX AND PUSH | 16.0 / 7.7 / 11.8 | 16.0 / 7.7 / 11.8 | 1 0 0 | none | -28.2 | D1 D2 D3 D4 D6 D8 decoy | 16.0 | 1 | trusted run under the gate (final 11.8); QC with the fix map, keep the design |
| 3 | 05_quillfen-sla-settlement-repair | 93.8 | FIX AND PUSH | 15.9 / 10.1 / 13.0 | 15.9 / 10.1 / 13.0 | 1 0 0 | none | -27.0 | D1 D2 D3 D5 D6 decoy | 11.4 | 1 | trusted run under the gate (final 13.0); QC with the fix map, keep the design |
| 4 | 01_assay-plate-triage | 91.3 | FIX AND PUSH | 3.3 / 7.7 / 5.5 | 3.3 / 7.7 / 5.5 | 1 0 0 | none | -34.5 | D1 D2 D4 D8 | 44.4 | 1 | trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 5 | assay-plate-triage | 91.3 | FIX AND PUSH | 3.3 / 7.7 / 5.5 | 3.3 / 7.7 / 5.5 | 1 0 0 | none | -34.5 | D1 D2 D4 D8 | 44.4 | 1 | trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 6 | 05550e00-2e66-4fab-8bce-727bfbbce24c | 91.0 | FIX AND PUSH | 5.2 / 4.7 / 4.9 | 5.2 / 4.7 / 4.9 | 1 0 0 | none | -35.1 | D1 D2 D4 D8 | 8.6 | 1 | trusted run under the gate (final 4.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 7 | 02_modulus-sieve-replay | 90.8 | FIX AND PUSH | 6.2 / 5.6 / 5.9 | 6.2 / 5.6 / 5.9 | 1 0 0 | none | -34.1 | D1 D4 D6 D8 | 18.8 | 1 | trusted run under the gate (final 5.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 8 | 06_grain-intake-settlement | 90.7 | FIX AND PUSH | 6.4 / 41.6 / 24.0 | 6.4 / 41.6 / 24.0 | 1 0 0 | none | -16.0 | D1 D2 D4 D8 | 10.6 | 1 | trusted run under the gate (final 24.0); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 9 | 28a29cf0-a25e-5de2-a8b9-140b24175727 | 90.5 | FIX AND PUSH | 7.5 / 4.7 / 6.1 | 7.5 / 4.7 / 6.1 | 1 0 0 | none | -33.9 | D1 D2 D4 D8 | 43.0 | 1 | trusted run under the gate (final 6.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 10 | f348165e-f7f6-5e73-b82d-b84ee751f3b0 | 89.8 | FIX AND PUSH | 6.2 / 42.5 / 24.4 | 6.2 / 42.5 / 24.4 | 1 0 0 | none | -15.6 | D1 D2 D3 D4 D8 | 25.6 | 2 | trusted run under the gate (final 24.4); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 11 | 75407a55-6665-505e-95d8-5ff9bdb3384f | 86.4 | FIX AND PUSH | 23.1 / 10.7 / 16.9 | 23.1 / 10.7 / 16.9 | 1 0 0 | none | -23.1 | D2 D4 | 19.2 | 1 | trusted run under the gate (final 16.9); QC with the fix map, keep the design |
| 12 | 8defd7be-eb46-5779-a556-aec18521635e | 82.5 | FIX AND PUSH | 2.4 / 15.7 / 9.1 | 2.4 / 15.7 / 9.1 | 1 0 0 | none | -30.9 | D1 D4 D8 decoy | 66.3 | 3 | trusted run under the gate (final 9.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first |
| 13 | f357cd96-1afe-50bc-b553-a1be78c907e3 | 61.4 | HARDEN WITH OWNER | 70.7 / 70.6 / 70.7 | 70.7 / 70.6 / 70.7 | 1 0 0 | none | 30.6 | D1 D2 D3 D4 D8 | 5.0 | 0 | trusted run 30.6 points over the gate; hardening changes the design, so the owner agrees first |
| 14 | 65ba10c2-1913-5076-94a6-d8763828cf25 | 46.4 | DROP | 69.1 / 87.9 / 78.5 | 69.1 / 87.9 / 78.5 | 1 0 0 | none | 38.5 | D1 D2 D3 D4 D6 D8 D9 decoy | 22.1 | 3 | trusted run 38.5 points over the gate; levers would need a redesign |
| 15 | cohort-retention-reconciliation | 46.0 | RE RUN FIRST | none | none | 0 0 0 | none | unknown | D1 D4 |  | 0 | no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score |
| 16 | 07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760 | 43.0 | RE RUN FIRST | none | 15.7 / 35.3 / 25.5 | 0 1 0 | permission denied (inferred) | unknown | D1 D8 | 9.8 | 1 | no trusted claude-opus-5 run: BROKEN permission denied (inferred) |
| 17 | 09_ninefold-crown-settlement-recompute | 43.0 | RE RUN FIRST | none | 15.3 / 43.1 / 29.2 | 0 0 1 | permission risk | unknown | D1 D2 D3 D4 D8 decoy | 24.7 | 3 | no trusted claude-opus-5 run: UNSURE permission risk |
| 18 | 10_reefer-power-dispatch-recompute | 43.0 | RE RUN FIRST | none | 8.1 / 50.6 / 29.4 | 0 0 1 | permission risk | unknown | D1 D2 D3 D4 D8 D9 decoy | 24.2 | 3 | no trusted claude-opus-5 run: UNSURE permission risk |
| 19 | 08_registry-lock-footprint-resolution | 40.0 | RE RUN FIRST | none | 2.2 / 52.6 / 27.4 | 0 1 0 | permission denied (inferred) | unknown | D1 D4 | 7.2 | 2 | no trusted claude-opus-5 run: BROKEN permission denied (inferred) |

Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).

TASK 1. 03_inference-gate-replay

Recommendation: FIX AND PUSH. trusted run under the gate (final 6.5); QC with the fix map, keep the design.
Score 95.9 = gate 40.0 + levers 25.9 + QC 20.0 + effort 10.0. Distance to gate: -33.5.
Real score (trusted claude-opus-5 runs): 10.8 / 2.3 / 6.5. Recorded score (every paid run): 10.8 / 2.3 / 6.5.
Inventory: bundle at tasks_copy_20261022T0105/03_inference-gate-replay; present 10 of 10 kit files; data 86 KB in 14 files, 4 formats (.csv:8 .jsonl:3 .md:2 .json:1).
Tests now: 35 checks, positive weight 93.0; judge now: 16 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. CL-4: instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 3. 05_quillfen-sla-settlement-repair

Recommendation: FIX AND PUSH. trusted run under the gate (final 13.0); QC with the fix map, keep the design.
Score 93.8 = gate 40.0 + levers 26.8 + QC 17.0 + effort 10.0. Distance to gate: -27.0.
Real score (trusted claude-opus-5 runs): 15.9 / 10.1 / 13.0. Recorded score (every paid run): 15.9 / 10.1 / 13.0.
Inventory: bundle at tasks_copy_20261022T0105/05_quillfen-sla-settlement-repair; present 10 of 10 kit files; data 15489 KB in 50 files, 41 formats (.md:4 .log:3 .xml:3 .csv:3 .xferlog:1).
Tests now: 35 checks, positive weight 88.0; judge now: 31 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. CL-4: instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 4. 01_assay-plate-triage

Recommendation: FIX AND PUSH. trusted run under the gate (final 5.5); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 91.3 = gate 40.0 + levers 27.3 + QC 17.0 + effort 7.0. Distance to gate: -34.5.
Real score (trusted claude-opus-5 runs): 3.3 / 7.7 / 5.5. Recorded score (every paid run): 3.3 / 7.7 / 5.5.
Inventory: bundle at tasks_copy_20261022T0105/01_assay-plate-triage; present 10 of 10 kit files; data 165 KB in 32 files, 4 formats (.csv:16 .json:8 .jsonl:6 .md:2).
Tests now: 33 checks, positive weight 90.0; judge now: 15 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 5. assay-plate-triage

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
1. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 6. 05550e00-2e66-4fab-8bce-727bfbbce24c

Recommendation: FIX AND PUSH. trusted run under the gate (final 4.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 91.0 = gate 40.0 + levers 27.0 + QC 17.0 + effort 7.0. Distance to gate: -35.1.
Real score (trusted claude-opus-5 runs): 5.2 / 4.7 / 4.9. Recorded score (every paid run): 5.2 / 4.7 / 4.9.
Inventory: bundle at teammates/anubis-stage-2/05550e00-2e66-4fab-8bce-727bfbbce24c; present 10 of 10 kit files; data 92 KB in 14 files, 4 formats (.csv:8 .jsonl:3 .md:2 .json:1).
Tests now: 28 checks, positive weight 58.0; judge now: 16 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 7. 02_modulus-sieve-replay

Recommendation: FIX AND PUSH. trusted run under the gate (final 5.9); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 90.8 = gate 40.0 + levers 26.8 + QC 17.0 + effort 7.0. Distance to gate: -34.1.
Real score (trusted claude-opus-5 runs): 6.2 / 5.6 / 5.9. Recorded score (every paid run): 6.2 / 5.6 / 5.9.
Inventory: bundle at tasks_copy_20261022T0105/02_modulus-sieve-replay; present 10 of 10 kit files; data 189 KB in 14 files, 4 formats (.csv:9 .jsonl:2 .md:2 .json:1).
Tests now: 35 checks, positive weight 96.0; judge now: 29 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 8. 06_grain-intake-settlement

Recommendation: FIX AND PUSH. trusted run under the gate (final 24.0); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 90.7 = gate 40.0 + levers 26.7 + QC 17.0 + effort 7.0. Distance to gate: -16.0.
Real score (trusted claude-opus-5 runs): 6.4 / 41.6 / 24.0. Recorded score (every paid run): 6.4 / 41.6 / 24.0.
Inventory: bundle at tasks_copy_20261022T0105/06_grain-intake-settlement; present 10 of 10 kit files; data 208 KB in 29 files, 4 formats (.csv:15 .json:7 .jsonl:5 .md:2).
Tests now: 35 checks, positive weight 94.0; judge now: 30 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 9. 28a29cf0-a25e-5de2-a8b9-140b24175727

Recommendation: FIX AND PUSH. trusted run under the gate (final 6.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 90.5 = gate 40.0 + levers 26.5 + QC 17.0 + effort 7.0. Distance to gate: -33.9.
Real score (trusted claude-opus-5 runs): 7.5 / 4.7 / 6.1. Recorded score (every paid run): 7.5 / 4.7 / 6.1.
Inventory: bundle at teammates/anubis-stage-2/28a29cf0-a25e-5de2-a8b9-140b24175727; present 10 of 10 kit files; data 180 KB in 23 files, 4 formats (.csv:13 .jsonl:5 .json:3 .md:2).
Tests now: 35 checks, positive weight 93.0; judge now: 16 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 10. f348165e-f7f6-5e73-b82d-b84ee751f3b0

Recommendation: FIX AND PUSH. trusted run under the gate (final 24.4); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 89.8 = gate 40.0 + levers 28.8 + QC 14.0 + effort 7.0. Distance to gate: -15.6.
Real score (trusted claude-opus-5 runs): 6.2 / 42.5 / 24.4. Recorded score (every paid run): 6.2 / 42.5 / 24.4.
Inventory: bundle at teammates/anubis-stage-2/f348165e-f7f6-5e73-b82d-b84ee751f3b0; present 10 of 10 kit files; data 163 KB in 26 files, 10 formats (.md:10 .rqb:5 .csv:2 .json:2 .docx:2).
Tests now: 102 checks, positive weight 352.0; judge now: 33 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. TS-23: tests/test_output.py: 102 checks, over 35 (warn)
2. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 11. 75407a55-6665-505e-95d8-5ff9bdb3384f

Recommendation: FIX AND PUSH. trusted run under the gate (final 16.9); QC with the fix map, keep the design.
Score 86.4 = gate 40.0 + levers 19.4 + QC 17.0 + effort 10.0. Distance to gate: -23.1.
Real score (trusted claude-opus-5 runs): 23.1 / 10.7 / 16.9. Recorded score (every paid run): 23.1 / 10.7 / 16.9.
Inventory: bundle at teammates/anubis-stage-2/75407a55-6665-505e-95d8-5ff9bdb3384f; present 10 of 10 kit files; data 11 KB in 10 files, 3 formats (.jsonl:7 .json:2 .md:1).
Tests now: 15 checks, positive weight 52.0; judge now: 17 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. CL-4: instruction.md: no exact bar sentence found (CL-4 exemption needs one)
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 12. 8defd7be-eb46-5779-a556-aec18521635e

Recommendation: FIX AND PUSH. trusted run under the gate (final 9.1); QC with the fix map, keep the design; very low tests: confirm solvability (DS-21) first.
Score 82.5 = gate 40.0 + levers 27.5 + QC 11.0 + effort 4.0. Distance to gate: -30.9.
Real score (trusted claude-opus-5 runs): 2.4 / 15.7 / 9.1. Recorded score (every paid run): 2.4 / 15.7 / 9.1.
Inventory: bundle at teammates/anubis-stage-2/8defd7be-eb46-5779-a556-aec18521635e; present 10 of 10 kit files; data 92 KB in 9 files, 4 formats (.csv:4 .json:2 .md:2 .jsonl:1).
Tests now: 42 checks, positive weight 83.0; judge now: 32 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. TS-23: tests/test_output.py: 42 checks, over 35 (warn)
2. SLIP (settings slip_cap_pct (PL answer, ENTRY 87)): one slip took 66.3 percent of positive test points (full_ledger_on_unseen_run_alpha and 10 similar), cap 50 percent
3. DS-21: trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score
Next: P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate.

TASK 13. f357cd96-1afe-50bc-b553-a1be78c907e3

Recommendation: HARDEN WITH OWNER. trusted run 30.6 points over the gate; hardening changes the design, so the owner agrees first.
Score 61.4 = gate 15.5 + levers 15.9 + QC 20.0 + effort 10.0. Distance to gate: 30.6.
Real score (trusted claude-opus-5 runs): 70.7 / 70.6 / 70.7. Recorded score (every paid run): 70.7 / 70.6 / 70.7.
Inventory: bundle at teammates/anubis-stage-2/f357cd96-1afe-50bc-b553-a1be78c907e3; present 10 of 10 kit files; data 36 KB in 26 files, 3 formats (.json:17 .csv:8 .md:1).
Tests now: 35 checks, positive weight 99.0; judge now: 20 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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

TASK 14. 65ba10c2-1913-5076-94a6-d8763828cf25

Recommendation: DROP. trusted run 38.5 points over the gate; levers would need a redesign.
Score 46.4 = gate 9.2 + levers 16.2 + QC 11.0 + effort 10.0. Distance to gate: 38.5.
Real score (trusted claude-opus-5 runs): 69.1 / 87.9 / 78.5. Recorded score (every paid run): 69.1 / 87.9 / 78.5.
Inventory: bundle at teammates/anubis-stage-2/65ba10c2-1913-5076-94a6-d8763828cf25; present 10 of 10 kit files; data 421 KB in 59 files, 15 formats (.md:22 .csv:13 .toml:6 .txt:3 .jsonl:2).
Tests now: 34 checks, positive weight 68.0; judge now: 40 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. IN-17: environment/data/known_traps_and_footguns.md:1 announced trap wording: KNOWN TRAPS AND FOOTGUNS
2. CL-4: instruction.md: no exact bar sentence found (CL-4 exemption needs one)
3. JD-12: tests/judge.toml: 40 criteria, over 35 (warn)
Next: leave it unless Ayush wants it; say why in one line.

TASK 15. cohort-retention-reconciliation

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

TASK 16. 07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN permission denied (inferred).
Score 43.0 = gate 15.0 + levers 4.0 + QC 17.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 15.7 / 35.3 / 25.5.
Inventory: bundle at tasks_copy_20261022T0105/07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760; present 10 of 10 kit files; data 8 KB in 6 files, 3 formats (.json:3 .md:2 .csv:1).
Tests now: 35 checks, positive weight 51.0; judge now: 11 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. TS-24: tests/test_output.py:20 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

TASK 17. 09_ninefold-crown-settlement-recompute

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: UNSURE permission risk.
Score 43.0 = gate 15.0 + levers 10.0 + QC 11.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 15.3 / 43.1 / 29.2.
Inventory: bundle at tasks_copy_20261022T0105/09_ninefold-crown-settlement-recompute; present 10 of 10 kit files; data 561 KB in 58 files, 16 formats (.md:22 .csv:10 .toml:5 .json:4 .tsv:3).
Tests now: 34 checks, positive weight 85.0; judge now: 35 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. CL-4: instruction.md: no exact bar sentence found (CL-4 exemption needs one)
2. CL-4: tests/test_output.py: 92 percent of positive weight on whole document checks, no per row or per field check
3. TS-24: tests/test_output.py:5810 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

TASK 18. 10_reefer-power-dispatch-recompute

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: UNSURE permission risk.
Score 43.0 = gate 15.0 + levers 10.0 + QC 11.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 8.1 / 50.6 / 29.4.
Inventory: bundle at tasks_copy_20261022T0105/10_reefer-power-dispatch-recompute; present 10 of 10 kit files; data 532 KB in 59 files, 16 formats (.md:22 .csv:13 .toml:6 .txt:3 .tsv:2).
Tests now: 35 checks, positive weight 62.0; judge now: 35 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. IN-17: environment/data/known_traps_and_footguns.md:1 announced trap wording: # Known traps and footguns
2. CL-4: tests/test_output.py: 97 percent of positive weight on whole document checks, no per row or per field check
3. TS-24: tests/test_output.py:5849 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

TASK 19. 08_registry-lock-footprint-resolution

Recommendation: RE RUN FIRST. no trusted claude-opus-5 run: BROKEN permission denied (inferred).
Score 40.0 = gate 15.0 + levers 4.0 + QC 14.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): 2.2 / 52.6 / 27.4.
Inventory: bundle at tasks_copy_20261022T0105/08_registry-lock-footprint-resolution; present 10 of 10 kit files; data 26 KB in 29 files, 4 formats (.pidx:15 .md:10 .csv:3 .json:1).
Tests now: 35 checks, positive weight 139.0; judge now: 9 criteria.
Structure problems:
1. S3 warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)
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
1. CL-4: instruction.md: no exact bar sentence found (CL-4 exemption needs one)
2. TS-24: tests/test_output.py:1865 runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)
Next: ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.

