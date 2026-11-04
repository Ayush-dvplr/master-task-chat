TRIAGE (read only, triage_tasks.py 1.0)

Tasks folders: qc_copies
Gate: tests under 85, rubric under 85, final under 40; slip cap 50 percent; paid model claude-opus-5; settings from settings.json.
Kit ids: located in the given kit folder.
Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.
Every QC risk and family line is a hint with its file and line, never a verdict.

RANKED TABLE

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | assay-plate-triage | 50.0 | RE RUN FIRST | none | none | 0 0 0 | none | unknown | D1 D2 D4 D8 |  | 0 | no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score |
| 2 | cohort-retention-reconciliation | 46.0 | RE RUN FIRST | none | none | 0 0 0 | none | unknown | D1 D4 |  | 0 | no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score |

Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).

TASK 1. assay-plate-triage

Recommendation: RE RUN FIRST. no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score.
Score 50.0 = gate 15.0 + levers 8.0 + QC 20.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): none.
Inventory: bundle at qc_copies/QC/copies/df9f49f/assay-plate-triage; present 10 of 10 kit files; data 166 KB in 32 files, 4 formats (.csv:16 .json:8 .jsonl:6 .md:2).
Tests now: 33 checks, positive weight 90.0; judge now: 15 criteria.
Structure problems: none found.
Runs:
1. none found
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:442 hidden data generator or held out inputs (18 lines)
2. D2 carrier or encoding variation inside a named standard: environment/data/reports.md:81 Both digests are lowercase hex sha256 over UTF-8 text built from the three
3. D4 a stated runtime on a large hidden input: instruction.md:15 The program takes two command line arguments, the input directory first and the output directory second, and i
4. D8 carried state that never heals: instruction.md:3 The notes in `/app/data/engine.md` and `/app/data/reports.md` give the file shapes, the carried plate state, t | environment/data/engine.md:55 ## Carried plate state
QC risk hints:
1. none found
Next: ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice.

TASK 2. cohort-retention-reconciliation

Recommendation: RE RUN FIRST. no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run gives the score.
Score 46.0 = gate 15.0 + levers 4.0 + QC 20.0 + effort 7.0. Distance to gate: unknown.
Real score (trusted claude-opus-5 runs): none. Recorded score (every paid run): none.
Inventory: bundle at qc_copies/QC/copies/4089e5c/cohort-retention-reconciliation; present 10 of 10 kit files; data 14 KB in 14 files, 3 formats (.csv:8 .json:4 .md:2).
Tests now: 24 checks, positive weight 71.0; judge now: 8 criteria.
Structure problems: none found.
Runs:
1. none found
Levers and traps (likely families, hints):
1. D1 a documented branch only the hidden data fires: tests/test_output.py:42 hidden data generator or held out inputs (73 lines)
2. D4 a stated runtime on a large hidden input: tests/test_output.py:831 _, stderr = process.communicate(timeout=60)
QC risk hints:
1. none found
Next: ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice.

