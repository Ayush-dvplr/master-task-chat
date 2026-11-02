# 03_inference-gate-replay: low-score study report

Paths: `T/` = `master_chat_work/20261022_lowscore-study/tasks_copy_20261022T0105/03_inference-gate-replay/`; `R/` = `T/trajectories/claude-opus-5/run_1/`. Score: overall 6.54 %, tests 10.75 % (10/93), rubric 2.33 % (1/43) (`T/trajectories/claude-opus-5/pass_summary.json`). No runs; all from saved files; guesses marked UNVERIFIED.

## 1. Shape

- Instruction `T/instruction.md`: 38 lines, 1016 words. One artifact `/app/out/gate.py` (`T/task.toml:2`), run as `gate.py INPUT_DIR OUTPUT_DIR`, writes `verdicts.jsonl`, `endpoints.json`, `precision.csv`, `shift.json` (`instruction.md:15`). Final message must state ten figures (`:19-32`).
- Timeouts: `task.toml` [agent] `timeout_sec = 7200.0`, [verifier] 1200 s; cpus 2, 4096 MB. The instruction says "You have 2700 seconds" (`instruction.md:38`) and caps constant recovery at 1500 s (`:36`): a mismatch with `task.toml` (live QC IN-1 wants N equal to the agent timeout, `Input_Bundle_QC/01_Instruction_QC.md:31`).
- Data (15 files, `T/environment/data/`): 2 docs (`gate.md` 155 lines, `reports.md`); recorded shift (231 probes, 47 endpoints, 4 runtimes, 7 variants of which `MVR-5..7` name a base, 4 callers); `digest.json` (4 sha256); worked example (130 probes, 26 endpoints, `example_verdicts.jsonl` 130 lines, no rollups).
- Tests `T/tests/test_output.py` (1723 lines): 35 checks = 31 positive (8 at w1, 15 at w3, 8 at w5 = 93) + 4 negative (-5, -3, -3, -3 = -14) (`:1689-1723`). It contains the reference gate (`resolve`, `:179-373`) and seeded generators.
- Judge `T/tests/judge.toml`: 16 criteria, positives 43 (#1-4 w1 conduct, #6-10 w5, #11-13 w3, #14-15 w1, #16 w3), negative #5 (-5). Channels 0.5/93 and 0.5/43 (`T/tests/reward.toml`).
- Run: 57 steps, 05:55:00 to 07:41:39 = 6399 s (107 min), 1.58M prompt tokens (`R/result.json`).

## 2. Is the low score genuine? (static screen)

ctrf: 35 tests, 10 passed (6 positive + 4 negative), 25 failed. Positive passes: `program_writes_the_four_reports_from_two_directory_arguments` (1), `report_serialization_carries_the_documented_byte_form` (1), `empty_shift_reports_are_written` (1), `throughput_normalisation_gain` (1), `meter_accumulates_as_a_first_difference` (3), `reserved_meter_repeats_the_previous_probe` (3) = 10/93 = 10.75 %. Negatives listed "passed" with no penalty by arithmetic.

a. Classification: READ = `negative_hardcoded_sample_answers` (`:1424-1429`) and `negative_third_party_dependency` (`:1432-1454`). EXEC = every other check: `_run` (`:1171-1182`) -> `_launch` -> `Popen(_demoted(argv))` (`:1107-1132`) with `_demoted` = `setpriv --reuid=nobody --regid=nogroup --clear-groups` (`:1088-1091`); even the shape and empty-shift checks call `_run`.

b. EXEC passes: all six passed positives. E.g. `empty_shift_reports_are_written` = `_ledger("empty", 0)` (`:1279-1281`, `:1192-1196`): exit 0 and four byte-equal reports; `throughput_normalisation_gain` = `_probe("gain")` (`:1284-1286`, `:1199-1202`): `verdicts.jsonl` byte-equal to the reference on six probe shapes. So `gate.py` ran as `nobody` and produced reference-equal output: the permission trap did not hit the program.

c. (not needed) Mitigations present: `_open_up(SCRIPT)`, `_grant_read(APP_ROOT)`, `_grant_read(OUT_DIR)`, `_grant_read(SCRIPT)` (`:1175-1178`), temp dirs 0777, data 0644 (`:1164-1167`).

d. Other breakers: none. Per-run budget 25 s (`:1107`) against a program that ran in well under a second (verifier total 44 s, `R/result.json`). Corpora are seeded in the verifier. No `MEP-` literal in `R/artifacts/app/out/gate.py` (0 matches), imports are stdlib only (`gate.py:19-23`), no `/tests` or `/logs/verifier` reference in the trajectory (grep). The 2700 vs 7200 timeout mismatch did not affect grading (no cutoff happened; the agent stopped itself at 6399 s).

Label: GENUINE - six EXEC checks passed under the setpriv drop; the 25 failures are constants and rounding the delivered program has wrong (step 4).

## 3. Instruction anatomy

- Narrative first (`instruction.md:1`). Withheld numbers: "What they do not give is any of the numbers, and they do not list them. Every figure the stages apply, every mode the carry update names and every threshold the ladder and the rollups consult was a controller constant nobody wrote down, and working out what that list even holds is part of the job." (`:3`).
- It says the evidence is thin: for the worked example "Nothing else was published for that shift and nothing says which parts of the gate it exercises, so what it settles and what it leaves open is yours to work out." (`:5`); for the digests "There is no partial signal underneath it and no score is confirmed until the whole shift is. Everything the worked example leaves open has to be reasoned out of the stage order and the carried state, then confirmed in one go." (`:7`).
- Deliverable is exact (`:9-15`). Method paragraph (`:17`): held-back block, rival-reading input, second calculation, digest check of own files. Ten named figures (`:19-32`).
- Clock: "Put a first working version of the program at the deliverable path early" (`:34`); "Work on the constants for at most 1500 seconds... reaching it is a failure even if the code was close" (`:36`); "You have 2700 seconds" (`:38`).
- Rules: stage order and carried state `gate.md:93-146`; byte forms `reports.md`; constants nowhere.
- Versus ours: ours say rules are stated in named files and the job is application; this one withholds every number, says the example may not show the rules, and adds a stopping rule. It is longer and more procedural about work and clock than ours. Evidence on the operator's hypothesis: against it (the procedural text did not help; the missing thing is information, see step 7).

## 4. Every failed positive check and every fired negative

ctrf: 35 tests, 25 failed positives, 0 fired negatives; all covered below.

Reference rules (hidden, in `T/tests/test_output.py`): gain 800 (`:225`); precision fp16 *7//8, bf16 +11, int8 *3//2 (`:94-101`); accel cuda *6//5, rocm -13, xla *4//5, npu +8, fpga `f-(f%7)`, wasm //3 (`:104-117`), fpga meter x5 (`:218-219`); phase decode *9//10, batch +14 (`:120-125`); kernel fused *5//4, eager -9, traced +6 (`:128-135`); bands 300/150/55 (`:138-145`); plan limits gold 60, silver 38, bronze 17, trial 0 (`:148-155`); backlog step `width//30`, tier 3 doubles, +9 after a serve (`:170-176`), ceiling 120 (`:284-285`); trail 4 (`:291`); credit //3 (`:250-252`); reset budget `floor + (running_total // 400) % 25` (`:272-274`); throttle above 40 (`:315`); top_tag tie later seq (`:309`); top_endpoint tie larger id (`:349`); charged precision via base (`:79-83`). Agent: `gate.py:32-102` (gain 1000, per-key tuples such as fp32 -40, bf16 -26, none +28, prefill -14, fused +25 and graph/eager/traced *4/5; fpga scale 1; band base 100; credit //2; plan tolerances gold 0, silver 20, bronze 40, trial 60; backlog //10, +5, ceiling 500, trail 3, throttle at or above 200; budget = running total at `:265`; inheritance off at `:102`).

| Check (w) | Cause | Evidence |
|---|---|---|
| precision / accelerator / phase / kernel responses (4 x 1) | Wrong parametrisation of stages 5-8: gain 1000 with relative kernel scaling and per-key offsets; reference gain 800 with per-stage floors. Other (rounding/format) + hidden-input generalisation | `gate.py:32-65` vs `test_output.py:94-135, 225` |
| meter_accumulates_per_phase (3) | Accumulation rule matches (`gate.py:195-201` vs `:206-217`), but the probe uses decode and batch phases whose adjustments are wrong | same |
| segment_boundary_resets_the_accumulator (3), segment_budget_reads_the_whole_shift (3) | budget = running total (`gate.py:264-265`) vs `floor + (running//400)%25` (`:272-274`); undiscoverable from the example (all drain) | step 55 docstring |
| backlog_step_per_serve (3) | //10 vs //30 | `gate.py:93` vs `:171` |
| backlog_doubles_on_the_marked_tier (3) | tier 3 correct (`gate.py:94`) but step wrong | |
| back_to_back_serve_carries_its_extra (3) | +5 vs +9 | `gate.py:95` vs `:175` |
| backlog_stops_at_its_ceiling (3) | 500 vs 120 | `gate.py:96` vs `:284` |
| repeated_tag_takes_the_recorded_score (3) | trail 3 vs 4 | `gate.py:97` vs `:291` |
| credit_applies_once (3) | //2 vs //3 | `gate.py:78` vs `:251` |
| verdict_ladder_takes_the_first_condition (3) | ladder order is right (`gate.py:238-248`), failing via backlog and tolerance values | |
| plan_tolerances_separate_flagged_from_ok (3) | tolerances in reverse order (gold 0 ... trial 60) vs gold 60 ... trial 0 | `gate.py:86` vs `:148-155` |
| endpoint_total_counts_the_reference_verdicts (3) | counted set ok + flagged is right (`gate.py:100`), but scores and backlog wrong | |
| endpoint_dispositions_follow_strikes_and_backlog (3) | throttle `>= 200` vs `> 40` | `gate.py:99, 302` vs `:315` |
| full_ledger_on_unseen_shift_alpha .. hotel (8 x 5) | all four reports byte for byte; every decision fires in each (`solution/TRUTH.md:128-132`) | any wrong constant fails |

Passed checks a lazy agent would also pass: report shape, byte form, empty shift. The other two passed checks (first difference, reserved meter) were guessable: the agent's `RESERVED_METER = -1` and `reset` as segment mode happen to equal the reference. Negatives: none fired.

Trajectory facts: at step 37 (`fit10.py`) the agent's variant V2 held exactly the reference additives (bf16 +11, npu +8, rocm -13, batch +14, eager -9, traced +6) and missed 36 of 130 example scores by one; steps 40-49 moved to other fits and the delivered file scores 0/130 exact scores on the example (agent final message). Cause class for all rows: hidden-input generalisation failed; for the four axis probes also rounding order. The final message says earlier turns had fabricated tool outputs ("BEST hits 130/130", "V1 misses=4/130"); my search of the saved steps finds only the real outputs (step 37 V1 89/130; step 48 best 30/130), so that statement is UNVERIFIED.

## 5. Levers

Share = points lost / 93.

| Lever | Family | Share | Triggered |
|---|---|---|---|
| Example shows one mode only (all 130 probes are `drain`, `ok`, backlog 0), so backlog arithmetic, tolerances, throttle, ceiling, credit, record size, budget formula, fpga scale and base inheritance are unobservable | NEW (evidence-blind constants) | 11 state/rollup probes = 33/93 = 35.5 % | yes |
| Hash-only oracle on the recorded shift, no partial signal (`instruction.md:7`) | NEW | underlies the lever above; the 8 unseen checks that need all 56 decisions = 40/93 = 43.0 % (E stacked) | yes |
| Stage 5-8 functional form and rounding order (gain 800, per-stage floor) | NEW | 4 axis probes + phase tracks + counted = 10/93 = 10.8 % | yes |
| Shift-wide budget install from the running total | B dependent chain | 6/93 = 6.5 % | yes |
| Per-phase meter tracks and reserved meter value | traps (A-like) | earned 6, lost 3 (per phase) | partly |
| Base-variant precision inheritance (variants.csv rows exist, example has none) | A/NEW | part of the unseen checks | yes |
| Ten figures measured on the recorded shift | E | 36/43 = 83.7 % of judge weight | yes |

## 6. Judge

From `R/verifier/score.json`: rubric 1/43 = 2.33 %.
- #1 held-back block of the recorded shift (w1): failed; the agent held back `seq > 100` of the example in `solve_add.py`.
- #2 rival-reading input (w1): failed; only example exploration and an empty-shift smoke test.
- #3 second calculation (w1): failed; `figures.py` reads the delivered reports.
- #4 digest of each own file checked against the published ones (w1): PASSED (`figures.py` printed "differs" four times).
- #5 (-5) editing `/app/data`: listed passed true, no penalty (1/43); semantics UNVERIFIED.
- #6 total_score 688900, #7 clear_score 679698, #8 saturate_band_score 685972, #9 top_score_total 296755, #10 budget_end_total 7958 (w5 each): agent 561912, 545136, 556297, 245061, 331427; all failed. #11 total_backlog 1148 (w3): 3577. #12 flagged_score 3500: 6470. #13 high_band_score 2199: 3550. #14 base_band_score 445 (w1): 403. #15 throttle_endpoints 2: 0.
- #16 delivered program is clean readable Python (w3): failed; `resolve` is one long function though constants are named.
Design: figures exist in no file, and 5 of 10 are w5; conduct criteria quote `instruction.md:17`; no overlap with tests.

## 7. How it passes QC and still beats the agent

- Documented: stage order, carried state, ladder, byte forms, digest construction (`gate.md:93-146`, `reports.md`), and the warning that the example may not exercise everything (`instruction.md:5`). Withheld by design: all numbers, and even the list of constants (`gate.md:148-155`).
- Live QC lets an author withhold constants if a solver can still test a guess (IN-9, `01_Instruction_QC.md:39`) and asks whether an expert with unlimited time could reach the graded answer from the agent-visible files (DS-21, `02_Data_Solution_QC.md:70`). Here, for the unobservable constants, the only test of a guess is a 4-hash digest on the recorded shift; the joint space is far too large to climb without partial signal, and the instruction says so itself (`:7`). `TRUTH.md:56-61` claims the reference "confirms that reading against ... all four published digests", which proves the reference is consistent, not that the constants are discoverable. UNVERIFIED that any route exists; this looks like a DS-21 weakness QC accepted.
- Easy to miss: reversed-looking plan tolerances (gold 60), throttle threshold, budget formula, base inheritance (recorded `variants.csv` has base rows, the example none), per-phase tracks.
- Anti-cheat: negatives for 5+ `MEP-` ids as literals (`test_output.py:1424-1429`), third-party imports (`:1432-1454`), behaviour that depends on the input directory name (`:1457-1489`), nondeterminism (`:1492-1507`), all inverted polarity (`TRUTH.md:137-139`).
- Bundle inconsistency: `instruction.md:38` says 2700 s and `task.toml` allows 7200 s; whether this changed after QC is UNVERIFIED.

## 8. Trajectory story

57 steps, 107 min.
- Steps 3-6 read `gate.md`, `reports.md` and the data; 7-10 `explore.py`; 11-23 per-key fits; a first `/app/out/gate.py` was in place at 06:09 (14 min), following `instruction.md:34`.
- Steps 25-39: more fits and a constraint solver (`csp.py`, no candidate for most keys, then a traceback); step 37 gave the near-right variant V2 (36 misses).
- Steps 40-49: solver attempts, inspection of recorded repeated tags and odd meters (step 46), `chain.py` random search (30/130 best), `addfit.py` (43 misses).
- Steps 50-56: wrote the final file, deleted and rewrote it three times, ran determinism, empty shift, example replay and digest comparison (all four digests differ); step 57 finish.
- Recovery work ran 05:56 to 07:32 (5760 s) against the instruction's 1500 s cap; no cutoff was enforced because `task.toml` allows 7200 s.
- Docs never opened: none relevant. Self-test was good (example replay, determinism, empty shift, digests). The final message is candid: unrecovered offsets, digests red, figures unconfirmed, best fit 87/130, delivered 0/130; it also retracts "fabricated" earlier outputs (see step 4, UNVERIFIED).

## 9. Reusable patterns / things to avoid

- Reserved sentinel meter, per-phase tracks and a shift-wide derived budget are cheap, realistic traps that look like ordinary accumulation.
- Mechanism probes at w3 on neutral endpoints plus 8 unseen shifts at w5 is a sensible ladder, but only if each probed constant is identifiable from something shipped.
- Avoid: a worked example that exercises one mode only combined with a hash-only oracle; constants become unidentifiable, not just hard. Keep every graded constant identifiable from some shipped output.
- Avoid: contradictory timing text (2700 vs 7200) and a self-policing "stop at 1500 s" rule the harness cannot enforce.
- Avoid: a conduct criterion on code readability (#16) when partial work is the likely outcome.
- Note: per-key "(num, den, offset)" fits are non-identifiable when the real model has a different gain and per-stage floor; a shipped example should pin the gain with a neutral row.

```json
[
  {"task":"03_inference-gate-replay","name":"example_exercises_one_mode_only","family":"NEW","mechanism":"Every example probe is drain, ok, backlog 0, so backlog arithmetic, tolerances, throttle, ceiling, credit, record size, budget formula and fpga scale are unobservable","where_documented":"instruction.md:5 (warns the example may not show them); gate.md:148-155","weight_share":0.355,"triggered":true,"cause_of_failure":"hidden-input generalisation failed (constants guessed)","evidence":"11 state and rollup probes failed; agent docstring gate.py:14-17 and step 55 say all 130 example probes are drain/ok/backlog 0"},
  {"task":"03_inference-gate-replay","name":"hash_only_oracle_no_partial_signal","family":"NEW","mechanism":"Only four sha256 digests over the recorded shift confirm a reading; no per-endpoint or per-probe signal","where_documented":"instruction.md:7; gate.md:49-54","weight_share":0.43,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"all four digests differ in the final run (step 56); eight unseen-shift checks (40/93) need all 56 decisions at once"},
  {"task":"03_inference-gate-replay","name":"stage_5_8_parametrisation_and_rounding","family":"NEW","mechanism":"Per-stage floors with gain 800 and multiplicative, additive and modular adjustments; a gain 1000 plus relative scaling model cannot reproduce them","where_documented":"gate.md:99-118 (stage order only)","weight_share":0.108,"triggered":true,"cause_of_failure":"other: rounding and parametrisation","evidence":"step 37 V2 had the right additives and missed 36/130 by one; delivered constants score 0/130 exact on the example (final message)"},
  {"task":"03_inference-gate-replay","name":"shift_wide_budget_install","family":"B","mechanism":"A segment boundary installs floor + (running_total // 400) % 25, using scores resolved across all endpoints","where_documented":"gate.md:88-91, 139","weight_share":0.065,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"gate.py:264-265 budget = running; reference test_output.py:272-274"},
  {"task":"03_inference-gate-replay","name":"per_phase_meter_and_reserved_value","family":"A","mechanism":"First-difference meter accumulated per endpoint and phase; one reserved value repeats the previous meter","where_documented":"gate.md:56-69","weight_share":0.032,"triggered":true,"cause_of_failure":"other: first_difference and reserved_meter were passed (guessed right); the per-phase check was lost only through the stage 5-8 error","evidence":"ctrf: first_difference and reserved_meter passed, meter_accumulates_per_phase failed (share is the one lost check, 3/93)"},
  {"task":"03_inference-gate-replay","name":"base_variant_precision_inheritance","family":"A","mechanism":"Charged precision comes from the variant's base; the example has no base rows so it is unobservable there","where_documented":"gate.md:32-35 (inherit-or-not is listed as a missing constant)","weight_share":0.1,"triggered":true,"cause_of_failure":"hidden-input generalisation failed; weight share approximate (part of the unseen checks), UNVERIFIED","evidence":"gate.py:102 CHARGE_INHERITED_PRECISION = False; reference test_output.py:79-83"},
  {"task":"03_inference-gate-replay","name":"ten_figures_on_recorded_shift","family":"E","mechanism":"Ten closing figures in no file, each depending on all constants","where_documented":"instruction.md:19-32","weight_share":0.837,"triggered":true,"cause_of_failure":"hidden-input generalisation failed","evidence":"score.json #6-#15 all failed; share is of judge weight 43"}
]
```
