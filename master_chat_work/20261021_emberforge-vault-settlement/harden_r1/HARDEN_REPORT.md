# HARDEN REPORT: emberforge-vault-settlement, round 1 (21 Oct 2026, IST)

All scores are tests-only, P3 method (b): the real `tests/test_output.py` under rewardkit 0.2.1 in the exe_copy tests image, oracle 1.0 and nop 0.0 on the final file. No judged run happened (no OPENAI_API_KEY); judge figures below are estimates from what each program would let an agent state.

## What changed
- The answer key is gone. `calibration_reference_bundle.json` is deleted. `example_workshop_report.json` is cut to one workshop's returned units ({R01 2, R04 2, R05 3, R06 8}). The controls plus that cut pin the visible draw as 1 of 840. The controls alone leave 21 draws, and no other single field pins it. The fields, order and written form of every record now live in the new `record_shapes.md`.
- Rules are explicit and visible. A4 states that the cap is judged on the charge a forge would carry, so a forge the floor or a retired reagent also refuses still closes its workshop. V9 adds retired reagents (the shipped `retired_patch` column) with the RETIRED_REAGENT code. The register defines `consumed` over the forges tested against the floor, and N3 lists the retired reagent. The instruction states the bound: up to 48 requisitions within 38 seconds on 2 CPUs. It also asks the final message for 4 facts that no test reads.
- Shipped season: one bulk order L0305 (999 units at gloamworks, day 27) and R14 retired from P05. Nothing in the data labels either.
- Tests: 34 checks became 50 (positive 155, negatives -7). Every visible value check was dropped. Weight 1 stays only on 5 presence and written-form checks. Every value check runs the program on a reseeded season, each under its own draw. For each season, `select_draws.py` picks the draw under which every graded observable differs from the same season settled under the visible draw.
- Judge: 12 criteria became 9 (positive 19, negatives -14).
- Validator fixes: §5.3 (one apt layer), §5.4, §5.5, §7.2 (seeds, `main`, `__main__`), §11.3 and §11.5 (two negatives at -1).

## Levers before and after
| lever | before: points, run earned, status | after: points, run's program earns (no bundle) | status |
|---|---|---|---|
| L7, cap and floor at a closed workshop | 11, 1, HELD | folded into LV-EF-1 | HELD |
| LV-EF-1 cap and floor at one forge | new | 38, 0 | HELD, HIDDEN-ONLY |
| LV-EF-2 retired reagent | new | 38, 0 | HELD, HIDDEN-ONLY |
| LV-EF-3 consumed reference | new | 38, 0 | HELD, HIDDEN-ONLY |
| LV-EF-4 requisition ladder | new | 18, 3 (12 rung only) | HELD, HIDDEN-ONLY |
| L2 draw recovery | 10, 0 (cascade), LEAKED | inside every value check | DERIVABLE by design |
| L3, L5, L6 (answer-key fit) | 20, 15, LEAKED | key removed; L5 and L6 still gate the slice search | DERIVABLE by design |
| B, L1, L4, L8 visible-season checks | 76, 66, LEAKED | dropped (graded only on reseeded seasons) | |
| isolated rules on reseeded seasons | | 18, 18 | paid |
| structure | 3, 3 | 5, 5 | paid |

## New checks (each season exercises 1 lever; the other levers are kept out of reach)
- `cap_and_floor_{one,two}_*` checks seasons lv1a (seed 23, RS-C/half-up/FSG/opening) and lv1b (seed 29, RS-E/floor/FGS/opening). Each has a bulk order at an open workshop and lower caps.
- `retired_reagent_{one,two}_*` checks lv2a (24, RS-G/half-up/SFG/acquired) and lv2b (30, RS-C/half-even/GSF/acquired). Each has abundant stock, a retired plain reagent and a bulk order that needs it.
- `consumed_reference_{one,two}_*` checks lv3a (25, RS-E/ceil/SFG/consumed) and lv3b (31, RS-G/ceil/FSG/consumed). Each has abundant stock and low caps.
- Each of those 6 seasons gets 5 checks: findings (5), workshop figures (5), vault audit (3), reconciliation (3) and guild reports (3).
- `requisitions_12/24/48_first/48_second_allocation` (3/5/5/5) run on ld12, ld24, ld48a and ld48b. A third of the requisitions name a scarce reagent held to its salvage returns, so the Q5 limit binds and follows the draw. Half of the requisitions sit in charter pairs (Q6).
- Isolated-rule checks, 6 at weight 3: `priority_tie_allocation`, `cap_boundary_workshop_figures`, `partition_guild_reports`, `temporal_boundary_vault_audit`, `merge_chain_smith_rows` and `quiet_rules_findings`.
- Structure checks, 5 at weight 1. Negatives: hardcoded replay -3; filename-dependent, nondeterministic, reads `/app/data` at runtime and plants an import hook, -1 each.
- Isolation is shown in `seasons_r1.json` and in the S3 table. Each S3_k loses exactly its own lever's checks, and the pairs lose additively: LV1+LV2 lose 76 = 38+38, and LV3+LV4 lose 53 = 38+15.

## Time limit and exhaustive search
- N: oracle on ld48a took 3.61, 3.75 and 3.63 s; on ld48b, 3.50, 3.45 and 3.61 s (Docker `--cpus 2`, pinned python:3.12-slim, host load 100 to 150). N = max(30, 10 x 3.75) = 38 s.
- Timing per solver:
  - The oracle runs a season in about 4 s.
  - The exhaustive reflex (the run's own search) passes ld12 in about 5 s. It hits the limit on ld24, ld48a and ld48b in every scoring run.
- Arithmetic: any exhaustive enumeration visits every feasible plan as a distinct leaf, so the feasible-plan count bounds its run time from below.
  - `check_exact.py` counts feasible plans exactly, by dynamic programming over charter groups: ld12 has 2,231, ld24 has 5.97e16, ld48a has 1.56e26 and ld48b has 6.63e24.
  - For the 48 cases, `count_plans_lower_bound.py` counts only the plans that fund no scarce-reagent requisition, so Q5 never binds them and every such plan is feasible. That gives ld48a 39,457,115,197,021,934,961,381 (3.9e22) and ld48b 15,083,185,347,881,707,274,831 (1.5e22).
  - Even at 10^7 plans per second (well above what a Python search reaches), ld48b needs at least 1.5e15 s. 100 x N is 3,800 s, so the bound exceeds it by a factor of about 4e11. ld24 needs at least 6.0e9 s.
- Exactness: on ld12, ld24, ld48a and ld48b, `check_exact.py` AGREES with both the oracle and the grader (exact counts: ld48a 1.56e26 feasible plans, optimum 192; ld48b 6.63e24, optimum 180; `_work/.../check_exact_final.log`).

## Judge before and after
| before (12) | verdict in run | after (9) | weight | run's program would state |
|---|---|---|---|---|
| R1 reads only /app/data | yes, trivial | dropped | | |
| R2 /app/data untouched | yes, trivial | R6 writes under /app/data | -5 | (negative) |
| R3 stdlib | yes, trivial | R7 non-stdlib import | -3 | (negative) |
| R4 no network | yes, trivial | R8 network call | -3 | (negative) |
| R5 quotes conventions | yes | R1 the four values RS-C, half-even, GFS, opening-plus-acquired | 3 | right |
| R6 states 3 figures | yes, effort | R2 total charge 124974 | 3 | 163070, wrong |
| R7 reads rulebooks first | yes, effort | R3 L0305 closed gloamworks, L0290 closed verdigris | 5 | L0246 and L0155, wrong |
| R8 draw by search | yes, effort | R4 the 7 forges with two findings (6 x CAP+RETIRED_REAGENT, L0305 CAP+STOCK_FLOOR) | 5 | none, wrong |
| R9 conservation check | yes, effort | dropped | | |
| R10 two runs compared | yes, effort | dropped | | |
| R11 false claim | no | R9 claims an unrun check | -3 | (negative) |
| R12 code quality | yes | R5 code quality | 3 | likely yes |

- Overlap check: no positive test reads the shipped season's values. The structure checks read only presence and written form.
- Estimate for a run like this one (not measured): judge 6/19 = 0.32, tests 0.168, overall 0.24. That is below 0.30, below 90 on tests and below 90 on the rubric.

## Gates (Phase 3)
- QC scripts: structure_qc, instruction_qc and judge_qc have 0 FAIL and 0 WARN. tests_qc has 0 FAIL and WARN A3 (50 checks, above the 35 cap, approved up to 70).
- Validator (no `--archetype`): 3 FAIL remain.
  - §1.12 is N/A: no archetype matches.
  - §15.5 and §15.7 are OPEN CONFLICT Q18: the provenance is kept as the bundle has it.
- Playground static:
  - A1, A3 and A4 PASS.
  - A5 is WAIVED: it is a generator volume check, not a QC rule, and volume is not the difficulty.
  - A2 WARN lists only test-internal keys: mutation names, cache keys and engine state.
- Oracle 1.0, nop 0.0 (tests channel, final test file).

## Baselines (tests-only, `_work/.../baselines.json`)
| solver | round 0 | round 1 |
|---|---|---|
| S0 nop | 0.0 | 0.0 |
| S1 stub | 0.0 | 0.0 |
| S2 lazy | 0.08 | 0.0258 |
| S4 careful | 0.68 | 0.1677 |
| S5 oracle | 1.0 | 1.0 |
| S3 LV-EF-1 / -2 / -3 / -4 | | 0.7548 / 0.7548 / 0.7548 / 0.9032 |
| S3 L1 / L2 / L4 / L5 / L6 / L8 / L9 | 0.592 / 0.92 / 0.104 / 0.008 / 0.008 / 0.96 / 0.976 | 0.6839 / 0.0323 / 0.0516 / 0.0065 / 0.0065 / 0.4903 / 0.9935 |
| best shortcut | 0.184 (hardcoded draw + L5) | 0.0323 (hardcoded draw) |
| replay of the shipped records | | 0.0129 (pays the -3 negative) |
| run's program, as delivered | 0.68 | 0.0065 (stops on the missing reference bundle) |
| run's program, reading only what ships | | 0.1677 |

- Verdict: PASS.
  - S4 is in 0.10..0.20 and S2 is at most 0.10.
  - S1 is at most 0.25.
  - Every S3 loses points.
  - Every counted lever is HIDDEN-ONLY.
  - The shortcut scores at most 0.10.
- Composition share: 0.871.
- Shortcut hunt (only instruction.md and environment/):
  - Replaying the visible records and keying on visible names both score 0.0129.
  - Hardcoding the draw scores 0.0323.
  - The image has no answer: the reference bundle is gone, and no settled visible figure appears under environment/.
- One fix made during Phase 3: an earlier scoring pass gave the hardcoded-draw solver 0.2516. The cause was 7 graded observables that did not move with the draw. The draw-selection rule and season changes above fixed it, and the scoring was then rerun once.
