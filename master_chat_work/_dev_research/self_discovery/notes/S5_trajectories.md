# S5 Trajectories (claude-opus-5, Run 1)

Tree used: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/jobs/` (newer, superset). Older tree `Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/` duplicates (vendor 195182 B = _archive vendor; cohort 89667 B = _archive cohort; no district) -> skipped as duplicate.
Path: `jobs/<slug>/trajectory/claude-opus-5/Run 1/{agent/trajectory.json, verifier/reward-details.json, ctrf.json}`. Abbrev T(<slug>).
ctrf.json has status only, no messages; test-stdout.txt only "reward: x". reward-details.json has per-criterion value/weight/description (+ judge reasoning).

## Per-run table
| slug | reward | steps | dur s | write steps | judge | tests lost (genuine?) |
|---|---|---|---|---|---|---|
| 7ef8d80a | 0.9911 | 50 | 2722 | - | all met | reconciliation_measured_fields only |
| caldermoor | 0.8722 | 33 | 2618 | 19-26,30 | 95, all met | 8: audit_and_reconciliation_exact, cadence_and_waiver_exact, cadence_streak_and_waiver_semantics_exact, closure_and_blocked_exact, unseen_alpha/beta/gamma_full_exact, validation_report_residuals_zero (GENUINE hidden-input) + negative_directory_iteration_order fired |
| cohort-retention a2 | 1.0 | 19 | 282 | 9, 11 | all | none |
| cohort-uplift | 1.0 | 25 | 1313 | 10,13,17,19 | all | none |
| dispatch | 0.6419 | 50 | 1880 | 25..45 | 77, lost R16 | 16 incl objective_exact, hidden_perturbation_recomputes (0711 artefact + K13 tie HELD per D1:21) |
| district a4 | 1.0 | 29 | 703 | - | all | none |
| emberforge (conv) | 0.4307 | 23 | 2799 | - | all | 3/50 pass = permission artefact |
| match-replay | 0.8043 | 102 | 2374 | 94 | 42, lost R3 | 12 trap_*_inverse (GENUINE) |
| numeric-reduction | 0.874 | 20 | 543 | - | lost R5,R12,R20 | bottleneck_analysis_matches_reference |
| pcggc | 1.0 | 18 | 630 | 11 | all | none |
| schema v0 | 0.8443 | 58 | 2266 | - | 32, lost R8,R10,R14 | module_core_claims_match_archive |
| season-ladder | 0.8209 | 23 | 1217 | 9,11,12,19 | 49, all met | 11: every generalisation_* + determinism_two_runs_byte_identical (GENUINE; mechanism UNVERIFIED, all-together pattern suggests one failure mode such as crash on hidden seasons) |
| sensor | 0.7115 | 33 | 1418 | 20,22 | 22, lost R2,R9-R16,R18 | none (judge-only loss) |
| sentinel | 0.7778 | 36 | 1001 | - | lost R6,R11,R12 | none (judge-only) |
| specdec | 1.0 | 20 | 583 | - | all | none |
| vendor a2 | 1.0 | 41 | 659 | - | all | none |
| _archive cohort v0 | 0.5868 | 28 | 476 | - | lost R3 | 12 (Errno13 artefact) |
| _archive emberforge pre-conv | 0.84 | 26 | 3208 | - | 41 all | c03_vault_stock_and_timing, stage_04_finding_details, gen_draw_shift_alpha/beta, gen_priority_tie_flip, gen_temporal_boundary, gen_identity_merge_chain, gen_nonapplying_rules (GENUINE generator-family) |
| _archive vendor v0 | 0.5241 | 54 | 2613 | - | 36 all | 7 pass only (permission artefact) |
| _archive match-replay 1020T111343 | none | - | - | - | - | ApiOverloadedError, no reward |

## Observations (with quotes)
- T5-1 Our three hardened tasks (cohort a2, vendor a2, district a4) scored 1.0 in 282, 659, 703 s. Cohort a2: read schema s4, audit_policy s5, data s6, plan s8 think, created program s9/s11 (only two writes), ran s12, built synthetic extract /tmp/t1 s14-16, determinism snapshot s17. Agent finishes far inside the 7200 s budget.
- T5-2 Genuine tests-channel losses occur ONLY where hidden worlds exercise behaviours absent from shipped data and the rule text: season-ladder 11 generalisation_* (descriptions: "settles a season whose fixtures carry contradicting filings", "...in which the cumulative debit cap binds", "...chained renames and a circular merge"); caldermoor unseen_alpha/beta/gamma_full_exact + "a waiver suppresses a period and leaves the streak standing"; match-replay trap_*_inverse ("a capture set carrying only the label mask settles to its whole scenario report"); old emberforge gen_priority_tie_flip, gen_identity_merge_chain, gen_nonapplying_rules; dispatch tie (D1:21).
- T5-3 Calibration-fit habit: season-ladder final msg "I fixed these against the calibration slice, where exactly one assignment reproduces all four published figures; with it my program regenerates `example_division_report.json` byte for byte." Then lost all 10 generalisation checks -> reproducing the shipped example is taken as proof of correctness (study rule 7 confirmed: anything that confirms the full answer on shipped data stops the agent; the hidden worlds still caught it).
- T5-4 Exhaustive search over withheld constants: match-replay s9-s93 probes 11 withheld constants one by one against published digests (CTRL-A..K), final msg table "each pinned against its own control figure"; first write of optimize.py at s94. Judge R1/R2 PAY this behaviour ("writes the full candidate set ... before its first write") -> judge 42 near-full. Lost only the inverse traps (single-transform capture sets).
- T5-5 Self-verification is by internal consistency: caldermoor final "A second run is byte-for-byte identical", "All five identity residuals are zero"; then lost validation_report_residuals_zero on hidden inputs and 7 hidden exact checks.
- T5-6 Judge channel: criteria worded "The response states X" are met nearly always (season-ladder R1 "states the three season constants", R2 "states that the earliest live filing ... supersedes seven filings"; caldermoor 95/95; R1 "builds the closure in a staging directory"). Judge losses only on sensor/sentinel/numeric where criteria demanded figures the agent did not report.
- T5-7 Run duration vs outcome: lowest-scoring genuine runs (season-ladder 1217 s, caldermoor 2618 s, match-replay 2374 s) still stopped < 45 % of budget; no run hit 7200 s except district timeouts (previous rounds, S3a_district).
- T5-8 Process: 4 of 19 rewards are permission artefacts (emberforge conv 0.4307, _archive cohort 0.5868, _archive vendor 0.5241, dispatch partly 0711); one ApiOverloadedError run with no reward.
