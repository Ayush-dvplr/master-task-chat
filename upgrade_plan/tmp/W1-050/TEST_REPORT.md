W1-050 TEST REPORT: triage_tasks.py (P19), 4 Nov 2026

Deliverable: upgrade_plan/triage/ (triage_tasks.py, README.md, TRIAGE_PROMPT.md). All runs below used Python 3.9.25 (uv) with -I, settings upgrade_plan/drafts/P1/settings.json (gate 85, 85, 40; slip cap 50) and the kit Input_Bundle_QC from origin/main 00d358c4 extracted to scratch. Outputs are copied to upgrade_plan/tmp/W1-050/test_outputs/<set>/ (TRIAGE.md, triage.csv, triage.json).

TEST SETS

1. lowscore: master_chat_work/20261022_lowscore-study/tasks_copy_20261022T0105/ read in place (10 bundles, one claude-opus-5 run each). Known answers from that study's SYNTHESIS.md and tasks/*.md: 07 and 08 broken by the permission trap (confirmed by the Phase B replay), 09 broken (confirmed), 10 genuine but with the same hazard, 01 to 06 not hit by the permission trap.
2. teammates: 7 bundles with trajectories extracted by git archive from origin/main anubis-stage-2/ (05550e00, 28a29cf0, 8defd7be, 75407a55, f348165e low scorers; f357cd96 and 65ba10c2 high scorers), each with a claude-opus-5 and a glm-5.3 run.
3. qc: 2 of Ayush's QC copies from origin/main QC/copies/ (df9f49f assay-plate-triage, 4089e5c cohort-retention-reconciliation), bundles only.
4. mix: the QC copy of assay-plate-triage plus a separate folder holding only the trajectories of task 01 (joined by task_name in result.json), and the QC copy of cohort-retention-reconciliation plus its local Harbor gate jobs (oracle, nop, stub, forgery, owner only, an oracle run at mode 0600, three errored build timeouts).
5. synthetic: 6 copies of 75407a55, each with one planted sign: judge reasoning with a 429 rate limit error, result.json VerifierTimeoutError, an empty verifier folder, a renamed and so changed test check, an Errno 13 Permission denied line in test-stdout.txt, a ctrf with 0 tests and an ImportError in test-stdout.txt.
6. all: lowscore, teammates and mix in one call, no settings (defaults) and no kit, to test several tasks folders at once.

RANKED TABLE, lowscore (first 11 columns; full table in test_outputs/lowscore/TRIAGE.md)

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 03_inference-gate-replay | 95.9 | FIX AND PUSH | 10.8 / 2.3 / 6.5 | 10.8 / 2.3 / 6.5 | 1 0 0 | none | -33.5 | D1 D2 D4 D8 | 43.0 |
| 2 | 04_speculative-decode-arbiter | 93.8 | FIX AND PUSH | 16.0 / 7.7 / 11.8 | 16.0 / 7.7 / 11.8 | 1 0 0 | none | -28.2 | D1 D2 D3 D4 D6 D8 decoy | 16.0 |
| 3 | 05_quillfen-sla-settlement-repair | 93.8 | FIX AND PUSH | 15.9 / 10.1 / 13.0 | 15.9 / 10.1 / 13.0 | 1 0 0 | none | -27.0 | D1 D2 D3 D5 D6 decoy | 11.4 |
| 4 | 01_assay-plate-triage | 91.3 | FIX AND PUSH | 3.3 / 7.7 / 5.5 | 3.3 / 7.7 / 5.5 | 1 0 0 | none | -34.5 | D1 D2 D4 D8 | 44.4 |
| 5 | 02_modulus-sieve-replay | 90.8 | FIX AND PUSH | 6.2 / 5.6 / 5.9 | 6.2 / 5.6 / 5.9 | 1 0 0 | none | -34.1 | D1 D4 D6 D8 | 18.8 |
| 6 | 06_grain-intake-settlement | 90.7 | FIX AND PUSH | 6.4 / 41.6 / 24.0 | 6.4 / 41.6 / 24.0 | 1 0 0 | none | -16.0 | D1 D2 D4 D8 | 10.6 |
| 7 | 07_fdc5a20d-2dfe-5f64-a3fa-2c023318a760 | 43.0 | RE RUN FIRST | none | 15.7 / 35.3 / 25.5 | 0 1 0 | permission denied (inferred) | unknown | D1 D8 | 9.8 |
| 8 | 09_ninefold-crown-settlement-recompute | 43.0 | RE RUN FIRST | none | 15.3 / 43.1 / 29.2 | 0 0 1 | permission risk | unknown | D1 D2 D3 D4 D8 decoy | 24.7 |
| 9 | 10_reefer-power-dispatch-recompute | 43.0 | RE RUN FIRST | none | 8.1 / 50.6 / 29.4 | 0 0 1 | permission risk | unknown | D1 D2 D3 D4 D8 D9 decoy | 24.2 |
| 10 | 08_registry-lock-footprint-resolution | 40.0 | RE RUN FIRST | none | 2.2 / 52.6 / 27.4 | 0 1 0 | permission denied (inferred) | unknown | D1 D4 | 7.2 |

KNOWN CASES, lowscore: all 10 right.
1. 07: BROKEN, permission denied (inferred). Evidence: tests drop the uid at tests/test_output.py:20; no read grant for the delivered program; agent listed derive_report.py as -rw------- (agent/trajectory.json step 13); 4 shipped or interface checks passed while all 26 other positive checks failed. Second sign: result.json exception_info RewardFileNotFoundError (missing outputs). Matches the study (same file lines: study cites test_output.py:20 to 21, traj step 13).
2. 08: BROKEN, permission denied (inferred). Evidence: uid drop at tests/test_output.py:1865, optimize.py -rw------- at trajectory step 35, 3 shipped checks passed while all 27 other positive checks failed. Matches the study (setpriv at :1865, traj steps 35, 36, 41).
3. 09: UNSURE, permission risk. Evidence: uid drop at tests/test_output.py:5810, 8 shipped checks passed while all 19 other positive checks failed, the negative negative_hardcoded_sample_answers fired (a program that never ran can trip it). The study confirmed it broken by Docker replay; the script stays at UNSURE because the trajectory never lists the program's mode (the study also marked the mode UNVERIFIED). Accepted: the task asks BROKEN or UNSURE with the permission sign.
4. 10: UNSURE, permission risk. Evidence: uid drop at tests/test_output.py:5849, no read grant, no run evidence either way (4 of 5 shipped checks failed too, so no split). The study judged it GENUINE with the hazard present; UNSURE is the honest class.
5. 01 to 06: TRUSTED. Each run carries a note that rules the hazard out with the read grant line: 01 test_output.py:847, 02 :1282, 03 :1074, 04 :1850 (staged copy), 05 :4604 (fresh zip extraction), 06 :1198. The study ruled the trap out for all six.
6. The real versus recorded score column shows the broken score for 07 to 10 and no real score, so they rank last with RE RUN FIRST; the next step line asks Ayush for an oracle replay with readable modes, a regrade, or one new paid run after a tests fix that the owner agrees.
7. Read only: sha256sum -c of master_chat_work/20261022_lowscore-study/tasks_copy.sha256 inside the copy gives 691 of 691 OK after all runs.

RANKED TABLE, teammates (first 11 columns)

| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 05550e00-2e66-4fab-8bce-727bfbbce24c | 91.0 | FIX AND PUSH | 5.2 / 4.7 / 4.9 | 5.2 / 4.7 / 4.9 | 1 0 0 | none | -35.1 | D1 D2 D4 D8 | 8.6 |
| 2 | 28a29cf0-a25e-5de2-a8b9-140b24175727 | 90.5 | FIX AND PUSH | 7.5 / 4.7 / 6.1 | 7.5 / 4.7 / 6.1 | 1 0 0 | none | -33.9 | D1 D2 D4 D8 | 43.0 |
| 3 | f348165e-f7f6-5e73-b82d-b84ee751f3b0 | 89.8 | FIX AND PUSH | 6.2 / 42.5 / 24.4 | 6.2 / 42.5 / 24.4 | 1 0 0 | none | -15.6 | D1 D2 D3 D4 D8 | 25.6 |
| 4 | 75407a55-6665-505e-95d8-5ff9bdb3384f | 86.4 | FIX AND PUSH | 23.1 / 10.7 / 16.9 | 23.1 / 10.7 / 16.9 | 1 0 0 | none | -23.1 | D2 D4 | 19.2 |
| 5 | 8defd7be-eb46-5779-a556-aec18521635e | 82.5 | FIX AND PUSH | 2.4 / 15.7 / 9.1 | 2.4 / 15.7 / 9.1 | 1 0 0 | none | -30.9 | D1 D4 D8 decoy | 66.3 |
| 6 | f357cd96-1afe-50bc-b553-a1be78c907e3 | 61.4 | HARDEN WITH OWNER | 70.7 / 70.6 / 70.7 | 70.7 / 70.6 / 70.7 | 1 0 0 | none | 30.6 | D1 D2 D3 D4 D8 | 5.0 |
| 7 | 65ba10c2-1913-5076-94a6-d8763828cf25 | 46.4 | DROP | 69.1 / 87.9 / 78.5 | 69.1 / 87.9 / 78.5 | 1 0 0 | none | 38.5 | D1 D2 D3 D4 D6 D8 D9 decoy | 22.1 |

Checks on teammates:
1. Every score equals the FEATURES.csv row of upgrade_plan/tmp/S2-FEATURES (opus_tests, opus_rubric, opus_final) for all 7 ids.
2. The glm-5.3 runs are listed as not the paid model and never enter the real score.
3. 75407a55 drops the uid with a read grant written as st_mode | (0o555 or 0o444) (tests/test_output.py:51): ruled out, TRUSTED.
4. 8defd7be: slip 66.3 percent over the cap (full_ledger_on_unseen_run_alpha and 10 similar, one whole ledger per unseen run), flagged SLIP and CL-4 whole document grading: the structure the PL slip cap rule targets.
5. 65ba10c2 shows an IN-17 hint for a shipped file named known_traps_and_footguns.md (line 1); f348165e and 8defd7be show TS-23 warns (102 and 42 checks).

SYNTHETIC SIGNS: all 6 found.
1. syn_judge_api: BROKEN judge or API error, evidence reward-details.json judge R1 "Judge call failed: litellm.RateLimitError: Error code: 429".
2. syn_grader_timeout: BROKEN grader timeout, evidence result.json exception_info VerifierTimeoutError.
3. syn_missing_outputs: BROKEN missing outputs, no verifier score file.
4. syn_regrade: REGRADE, "tests: 1 added, 1 removed, 0 reweighted since the run" (the run itself stays TRUSTED).
5. syn_perm_text: BROKEN permission denied, evidence verifier/test-stdout.txt:1 "[Errno 13] Permission denied".
6. syn_grader_crash: BROKEN grader crash, evidence ctrf.json summary tests 0, also test-stdout.txt:1 ImportError.

MIX AND QC
1. qc: both QC copies come out RE RUN FIRST with "no claude-opus-5 run in the folder; P13 step 3b: QC first, then one paid run", structure clean, families from the docs.
2. mix: the runs only folder is joined to the assay-plate-triage QC copy by task_name and gives the same trusted 3.3 / 7.7 / 5.5 as task 01. No REGRADE: the QC copy has the same check names and weights as the run.
3. mix cohort gates: 10 Harbor trial folders found. The three errored build timeouts are BROKEN (two grader timeout from EnvironmentStartTimeoutError, one grader crash from CancelledError); the oracle runs at 1.000, including the oracle run at mode 0600, are TRUSTED; nop 0.000 TRUSTED; all are shown as not the paid model and do not count. The stub run shows UNSURE permission risk; it is an oracle agent run and does not count.
4. all: 19 tasks from three folders in one table; same classes as the single folder runs.
5. Privacy check: no person name from the low score study INDEX.tsv and no author name from any task.toml in the test sets appears in any output; no email appears.

FOUND AND FIXED DURING TESTING
1. Test check names declared several per line (criteria.a(weight=5);criteria.b(weight=5)) were missed: the parser now reads every one.
2. A model name was read from the scratch path (claude-0): model detection now reads only the path inside the tasks folder and takes oracle or nop from agent_info.
3. The slip grouping chained every hidden check into one family (92 percent on f348165e): it now groups names that differ in one name part only, without chaining (25.6 percent).
4. The split test now needs 75 percent of the shipped check weight to pass, so task 10 (whose shipped checks also failed) is not read as a permission split.
5. The kit id lookup now prefers each id's home file (CL-4 at Final_checklist.md:494).

LIMITS SEEN IN TESTING
1. 09 is a confirmed broken grade that the script can only mark UNSURE without a Docker replay; 10 is genuine but also UNSURE. The class is honest; the deep read and the replay decide.
2. The family hints are broad: most tasks show D1, D4 and D8 because their docs say held out, seconds and running state. They point at lines to read, never at a verdict.
3. The ranking puts the withheld constant tasks (01, 02, 03, 06 and 05550e00, 28a29cf0, 8defd7be, all trusted tests under 10) high because they are far under the gate; each carries the DS-21 hint and a 3 point effort cut, and the why line says to confirm solvability first. The low score study judged 01 and 06 at the edge of QC solvability.
4. No real judge API error, grader crash or permission denied text exists in this repository's run folders; those three signs were tested on synthetic copies only.
