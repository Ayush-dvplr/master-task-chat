# Diagnosis, dispatch-plan-reoptimization v0 (board eedf614)

Run: claude-opus-5, Run 1, 19 Oct 2026 18:28 to 19:00 UTC, job `baseline_v0/trajectory_job_dispatch-plan-reoptimization_78826e`.

## Scores

| channel | value |
|---|---|
| combined reward | 0.6419 |
| tests only (ctrf) | 27 of 91 = 0.2967, 31 tests, 15 passed, 16 failed |
| judge | ran, 77 of 78 (only R16 "solver free of dead code" missed) |

The judge did run (judge_response.txt present). Reported as fact.

## Permission trap: FIRED

The agent wrote `/app/out/solver.py` with the editor tool and ran `chmod +x` (step 36), leaving mode 0711. The v0 verifier ran `/app/out/solver.py` in place as `nobody` with no read grant, so both solver-run checks (`test_reusable_regenerates_elsewhere` 5, `test_hidden_perturbation_recomputes` 5) failed with a permission error. I re-ran the v0 test functions locally (stub rewardkit, non-root, solver at 0755) on the agent's own `/app/out`: both PASS. The real v0 tests score was 37 of 91 = 0.4066. Verified locally outside Docker, not in the harness.

## Why the rest failed: one lot-sizing tie

Every other failure comes from one documented rule the agent misread. Handbook s10: "When two schedules cost the same, the schedule whose production period is earlier in fiscal order wins." For K13 two schedules tie at 424155083 cents (production + setup + holding). The oracle makes one lot at P23 covering P23 to P04. The agent's backward DP keeps the later P02 production period, even though its own docstring says ties prefer the earlier one. That one flipped lot changes handling, shortfall, sourcing, certificates and totals, so 14 chained checks fail (objective 446474706 against gold 446527364).

## Lever outcome

Out of 17 reconstructed levers, 1 held and 16 leaked. The table with step quotes is in `_work/dispatch-plan-reoptimization/LEVERS.md`.

What made them derivable:
1. `solver_run_report.json` has an `assumptions` block that lists every wrong setting the previous run used (cutoff 9999, holding 75 bps, surcharge 0, steering budget 4200000, greedy ratio, lot for lot, half even, no lifecycle log, no EUR conversion, no dozen expansion, no override, no zone uplift, no shortfall). The agent read it at step 21 and treated it as a checklist of things to fix.
2. Paragraph 3 of instruction.md names the trap topics ("rounding rule, sequence cutoff, unit scales, currency conversion and tie break rules").
3. Every rule sits in the handbook next to the file that settles it, and s15 worked examples confirm the readings.
4. All graded artifacts except one hidden perturbation are computed on the shipped data, so the agent can check its outputs with no feedback and only one lever (the K13 tie) had any constructed case behind it.

## Score composition (v0)

| share | weight | of 91 |
|---|---|---|
| isolated single-rule checks (corrected_coefficients 5, coefficient_corrections 5, retrofit_selection 5, budget_utilization 3, data_quality 3, rejected_records 3) | 24 | 26.4% |
| static format checks (exists, shebang, encoding) | 3 | 3.3% |
| shipped-data-only checks (19 exact checks on shipped data + reusable rerun on shipped data) | 86 | 94.5% |
| hidden input checks (perturbation) | 5 | 5.5% |

## Causes and where Phase 2 fixes them

| cause | Phase 2 fix |
|---|---|
| verifier ran an owner-only solver as nobody without a read grant | 2.1: copy the solver into a grader temp dir at 0644 (dirs 0755) before the uid drop, own session, kill by own pgid then by uid under a file lock |
| confirmer run report lists every trap | 2.3: assumptions block removed, report keeps only figures |
| trap topic list in instruction | 2.3: instruction rewritten as a plain end-state brief |
| 94.5% shipped-data-only grading | 2.3: chain and whole downstream documents graded on reseeded hidden corpora, shipped-only checks at or below 5% |
| one constructed tie only | 2.3: new levers with constructed hidden cases |

Phase 2 addresses every cause, so there is no DIAGNOSIS CONFLICT.
