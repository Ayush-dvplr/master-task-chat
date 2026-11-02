# C card: inference-gate-replay

Base `T=.../Perfect_for_Delivery/Dinshi_Jain/inference-gate-replay`. No QC report exists for this task.

## 1 Scores and verdict
- Recorded overall 21.77, tests 36.56, rubric 6.98 (score.json; final = mean of the two).
- Verdict **GENUINE** (A file). Genuine test points lost 59/93: 7 state checks x3 (21), 1 axis check x1, 8 unseen-shift ledgers x5 (40, scored per decision but recorded near 0). No negative fired. The program ran under the privilege drop (`program_writes_the_four_reports_from_two_directory_arguments` passed, and it runs `build_unseen`), so this is not an H6 artefact.

## 2 Inventory
- Domain: inference-serving admission gate (per-endpoint meters, backlog, budgets, verdict ladder, report rollups). Archetype: **constant recovery with no candidate list** + reusable program `/app/out/gate.py <data> <out>` writing 4 reports.
- Data files: gate.md 8.4 KB (stages), reports.md (report forms), callers/endpoints/runtimes/variants .csv, probes.jsonl, digest.json (sha256 of the 4 reports), and a worked example (example_probes.jsonl, 4 example_ tables, example_verdicts.jsonl).
- Instruction 1016 words. 7200 s, with a stop instruction for constant hunting at 1500 s.
- Tests (stacking_check): 35 checks, positive 93, negatives -14 (4). 8 checks w1, 15 w3, 8 w5. Judge 18 criteria, positive 35, batched. Reward = (tests + rubric)/2.
- Shares (stacking_check): hidden_rows 46.2%, isolated 47.3%, whole_doc 5.4%, shipped_only 1.1%.

## 3 Test architecture
- Expected values: **a full reference implementation inside the test file** (constants `_adjust_precision` 94, `_adjust_accel` 104, `_adjust_phase` 120, `_adjust_kernel` 128, `_band` 138, `_plan_limit` 148, `_verdict` 158, `_backlog_step` 170; `resolve` 179-374; `derive` 376). Nothing is precomputed; every expectation comes from running the reference on the same generated input.
- Inputs: all hidden and generated. `TestCase` builder class (416-572), `_neutral_case` 574 / `_axis_case` 583 (one axis varied, others neutral), `build_probe` 607, `build_state_probe` 628 (one state rule exercised), `build_unseen(seed)` 810 (docstring: every rule fires somewhere), `build_empty` 1002.
- Isolation: each w3 state check builds a small probe sequence where one rule decides the result (`_state` 1288, `_state_rollup` 1294) and checks it with `_holds` (1316, bool). This is fine-grained: one wrong constant should cost one check plus the ledgers.
- Partial credit: the 8 unseen ledgers use `_score` (1325-1340) built on `_ledger_fraction` (1200-1279), which scores per decision (whole verdict record per probe, endpoint rows, precision rows, SHIFT_KEYS 1051). Recorded passed:false on all 8 and the arithmetic fits a score of 0 for each (34/93 = 36.56 exactly), so INFERRED: the pipeline recorded a fraction below the pass line as 0, or the upstream errors touched every decision.
- Sandbox: `_demoted` 1089, `_grant_read` 1081, `_open_up` 1071, `_launch` 1108 (25 s limit), `_run` 1172.
- Negatives: hardcoded -5, third-party -3, filename -3, nondeterministic -3. All are cheat acts. No wrong-reading negatives.
- No mutation tests in the cohort sense; the axis and state builders play that role.

## 4 Lever table (failed checks)
Lever family: constants the notes say exist but never list, with the only signal being an all-or-nothing digest. One extra timing lever.

| id | w | rule graded | locations (quotes) | form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|
| accelerator_responses_match_the_reference | 1 | fpga response `figure - (figure % 7)`, meter scale x5 (test 113-114, 214-215) | gate.md:71-73 "Which accelerator and what scale are missing constants" | constant withheld, no candidate list | gate.py:40 fpga ('a',0) no adjustment, COARSE_SCALE 10 | worked example does not exercise fpga (agent's own final message lists it as untested) | NO by design (recover from digest); only signal is digest | NEW: withheld constant, digest-only signal |
| backlog_stops_at_its_ceiling | 3 | ceiling 120 (test 281-282) | gate.md:139-145 "Backlog has a ceiling it never passes" | constant withheld | BACKLOG_CEILING 200 "recovered from the recorded shift's deliberately-built blocks" (step 64) | digest red, so no confirmation | NO by design | same |
| segment_budget_reads_the_whole_shift | 3 | budget = floor + (running_total // 400) % 25 (test 270-272) | gate.md:88-91 "derived from the scores the gate has already resolved across the whole shift up to that probe" | shape stated, formula withheld | running_total // 1000 | same | NO by design | same |
| segment_boundary_resets_the_accumulator | 3 | meters cleared **before** the reset probe is scored (test 203-204) | gate.md:58-64 "the first probe of a segment carries the counter itself ... a segment boundary restarts every counter the endpoint holds" (meter section); the mode switch is applied in carry update gate.md:139-145 | **split across sections / rule placement vs use** | cleared `state.meters` in the carry update after scoring (gate.py ~263) | the worked example passed byte-identically, so it does not separate the two timings (INFERRED) | Partly: "first probe of a segment carries the counter itself" states the outcome; the ordering is implied | L3 stateful stream / H6 state consumed early |
| verdict_ladder_takes_the_first_condition | 3 | ordered ladder, first holding condition wins | gate.md:133-137 | plain sentence | agent's ladder matches; INFERRED fail via budget/backlog constants inside the probe | as above | yes (rule); fails by cascade | cascade |
| endpoint_total_counts_the_reference_verdicts | 3 | rollup counts ok+flagged; top_tag tie -> later wins (test 309-310) | reports.md:56 tie break is a missing constant | constant withheld | TOP_TAG_TIE_LAST False (earliest wins) | step 64: "The report-only constants ... could not be tested at all while the verdict digest is red" | NO by design | NEW (as above) |
| endpoint_dispositions_follow_strikes_and_backlog | 3 | throttle when backlog_end > 40 | reports.md:86 (top_endpoint tie missing constant) | constant + cascade | throttle 40 correct; INFERRED fail via ceiling 200 changing backlog_end | as above | cascade | cascade |
| full_ledger_on_unseen_shift_alpha..hotel | 8x5 | every rule | all of the above | composite | all of the above | as above | cascade | cascade |

Agent's honesty: the final message (step 64) says the four digests do not match and names the suspect constants. So the loss is a known failure, not a silent wrong answer.

## 5 How tests handle QC (no QC report; read from code)
- TS-13: each w3 state check is one rule on a probe built for it; each w1 axis check is one table. Ledgers bundle everything but are scored per decision.
- TS-16: four negatives, all cheat acts.
- TS-19: every withheld constant has its own state or axis check. The constants are learnable only through the digest, which gives a yes/no signal on four whole reports; under our rulings this is near the "shipped-slice promise" line. INFERRED learnable (the authors' oracle recovers them; no report confirms).
- TS-20: 1/3/5. Weight-1 on axis checks (stacking flags them) – they are table lookups, so not core.
- TS-26: stacking groups all 31 positives as one "duplicate" group only because they all run gate.py; by hand they use different builders and observables, so no double pay.
- IN-15/IN-16: constants are intentionally unstated, with an explicit sentence that they are missing (gate.md:150-155 "Not one of them is written down in this directory, and neither is a list of them"). IN-16 judged per constant would be "missing by design".
- AL-28: PASS (stacking: four acts plus judge R5 -5 unmatched, under cap).
- CL-4: per-decision ledger scoring is the CL-4 answer, but the recorded result was a cliff (0 on all 8).
- JD-7: unknown (no report). Rubric 6.98: the judge punished the result almost entirely (INFERRED from figure criteria R6-R14, R18 flagged by stacking as quoting figures).

## 6 Leak avoidance
- W1/W3: gate.md:64 "Which mode opens a segment is a missing constant." Names that a value is missing without explaining the trap. Same at :71-73 and reports.md:56, :86.
- No candidate list (gate.md:150-155), unlike h3. This removes the "sweep and pick the one that fits" path, so the digest becomes the only judge.
- instruction.md:7 "There is no partial signal underneath it" – honest about the signal, no hint at values.
- Worked example covers only the axis tables, so the stateful constants have no shipped separating case (W5/W6).
- Expected values live in reference code inside the hidden tests; the agent sees none.
- LEAK_LIBRARY: avoids "shipped boundary rows let agent watch rules fire" (no shipped case fires the ceiling, budget or fpga) and "trap spelled out".

## 7 Agent behaviour
- Read gate.md, reports.md, csvs and worked example in steps 2-6 (first 15 s).
- Fitting scripts on the worked example steps 9-24 (minute 1-8). First full program gate.py at step 25 (19:18:57, minute 15).
- Steps 30-55: brute-force digest searches (~45M combinations) to 20:08, past the 1500 s stop instruction. Graded constants changed only at the step 56-58 rewrite.
- Self-tests: byte-identical worked example; 32/32 hand-derived targets from its own reading (circular).
- Final claim (step 64): honest that digests fail and which constants are suspect.

## 8 Passed checks
- 7 w1 checks (program runs, serialization, empty shift, throughput, precision/phase/kernel tables): the worked example pins those tables.
- 9 w3 state checks (first difference, per phase, reserved meter, backlog step, tier doubling, back-to-back extra, repeated tag, credit once, plan tolerances): their constants appear in the worked example.

## 9 Take-aways
- SAFE adopt: reference implementation inside the tests with builders for one-axis and one-state-rule probes, plus a seeded "every rule fires" generator scored per decision.
- RISKY: constants with no candidate list and only a whole-report digest as signal. Strong (Opus lost 59/93) but near our "shipped-slice promise" ban and would fail TS-19 learnability if QC could not reproduce recovery.
- SAFE adopt: one sentence that a value is missing, placed where the value is used, with no explanation.
- Avoid: a per-decision partial-credit scorer that still records 0 when upstream constants are wrong; check that the curve does not collapse.
