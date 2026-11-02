# BUILD_REPORT 7d363c8 outage-window-replan (Shape D, P-3 core, option c)

Status: DONE. Bundle `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/outage-window-replan/`, WORK `.../bundles/_work/outage-window-replan/`.
Tree sha (sorted paths + contents, first 12): `6b179e601d17`. 25 files, no `__pycache__`.

## Tree
| path | lines |
|---|---|
| environment/Dockerfile | 26 |
| environment/data/assets.jsonl | 2500 |
| environment/data/control_room.log | 2600 |
| environment/data/crew_roster.jsonl | 3094 |
| environment/data/customers.csv | 9001 |
| environment/data/load_forecast.tsv | 2185 |
| environment/data/network_constraints.json | 126 |
| environment/data/published_plan.json | 370 |
| environment/data/region_calendar.json | 42 |
| environment/data/requests.json | 561 |
| environment/data/risk_policy.toml | 14 |
| environment/data/docs/RULES.md, intake.md, output_schema.md, replan_contract.md | 19, 40, 46, 45 |
| instruction.md | 21 (about 1.8 k chars) |
| solution/solve.py, solve.sh, TRUTH.md | 472, 184, 89 |
| task.toml | 47 |
| tests/test_output.py, judge.toml, reward.toml, test.sh, Dockerfile | 1680, 217, 7, 10, 9 |

## Data
- 14 data files in 7 formats (jsonl, log, csv, tsv, json, toml, md). Total 20,643 lines (A5: >= 20,000 total; every csv/tsv/jsonl/log >= 2,000: 9001, 2185, 2500, 3094, 2600).
- Chains (length >= 4): customers.csv -> assets.jsonl -> request weight (risk_policy class weights) -> risk-days -> objective; load_forecast.tsv daily peak -> risk_policy bands -> day factor -> risk-days -> region/segment/summary; crew_roster.jsonl on-duty -> control_room.log CREW_LOSS (after published_at) -> lane capacity -> selected season -> every output; requests.json + log NEW_REQUEST -> intake checks -> data_quality / active requests -> published_plan.json -> moved -> level 2; network_constraints.json -> precedence -> deferral -> reason `predecessor_deferred`.
- Shipped data: `WORK/datagen.py --seed 594183 --tier shipped`, lanes rejection-sampled quiet (every kill solver exact). Hidden data: generator embedded in tests (`build_inputs`), seeds only in tests (h2 70413, h3 88261), per-seed release literals (published_at, public class weight 3/4, defer factor 5/6, band floors).

## Lever table (LEVERS.md)
| lever | rule written in | checks | weight |
|---|---|---|---|
| S-1 least total risk-days (incl. deferral penalty) | docs/replan_contract.md:35 (+ :31 risk-days) | h2/h3 region x4 (w5), policy_audit (w5), segments x2, summary (w3) | 68 (73.9%) |
| S-2 fewest moved outages (five stated cases) | docs/replan_contract.md:36 | same families | 68 (73.9%) |
| S-3 start list in asset_id order, deferred last | docs/replan_contract.md:37 | h2/h3 region x4, policy_audit, segments | 50 (54.3%) |
| coupling "Every published figure is computed from the one replanned season that the objective order selects." | docs/replan_contract.md:3 | amplification through every hidden family | - |
About 20 noise rules (intake checks, log semantics, bands, capacity, blackout, incompatible, precedence, reasons, output orders) are stated in docs/intake.md, docs/replan_contract.md, docs/output_schema.md; register docs/RULES.md; none budgeted as a lever.

## Weights and shares
- Tests: 26 checks, positive 92, negatives -8 (`negative_outside_library_import` -3, `negative_hardcoded_sample_answers` -5). Shipped 9 (9.8%), mutation 9 (9.8%), hidden 74 (80.4%), w5 held-out tier 50 (54.3%).
- Judge: 16 criteria, positive 35 (8 probes x3 = 24, 68.6% probe share; J4 3; J6 5; J10 3), negatives -17 (J3a -3, J3b -5, J3c -3, grader read -5, data edit -1). mode batched. reward.toml 0.5/92 and 0.5/35.

## Gates
| gate | result |
|---|---|
| structure_qc / instruction_qc / tests_qc / judge_qc | PASS 17/0/0, 5/0/0, 36/0/0 (O1 4% shared lines), 19/0/0 |
| validate_bundle.py --archetype domain-calculation | 41 passed, 0 failed, 0 warnings, GATE PASS |
| oracle x3 (Docker, solve.sh + rewardkit-equivalent driver, block3.log) | 92/92 = 1.0 x3, verifier 14-16 s; 8 self-check stages print `check <id> ok` |
| nop | 0/92 = 0.0, negatives silent |
| negative probe (fake program with `import requests` + 3 shipped ids) | both negatives fire |
| STACKING_CHECK | STACKING PASS (OUT/STACKING_CHECK.md) |
| precheck.sh | `PRECHECK CLEAN` (WARN JD-5 on the mandated anchored grader-read wording, kept) |
| check_exact.py (independent fwd/bwd DP + lex fixing pass) | EXACT 9/9 and PASS on shipped and 5 hidden seeds; 7 override-removal probes move output |
| GEN/QC fingerprints | 0 changed, 0 missing (re-checked 07:13) |
| 300-seed generator survival (G12) | not run as a separate block; generator ran on 10+ seeds with bounds asserts, no crash |

## Kill table on the final generator (block2.log, limit 60 s, Docker 4g/2 cpu)
| solver | h2..n3 | seconds | result |
|---|---|---|---|
| solve.py reference | 5 corpora | 2.4-2.9 (incl. start) | EXACT |
| design blind 7a33fe5 (contention components + exact DFS, no guard) | 5 | 60 | TIMEOUT 0/9 docs |
| comp_dfs (same, own write) | 5 | 60 | TIMEOUT |
| comp_dfs_guard, comp_heur_guard, bb_heur_guard (incumbent at 48 s) | 5 | 48 | WRONG 0/4 regions |
| g_weight, g_edf, g_id, repair, g_swap, nomove, dp_nofix | 5 (fire.py and kill2) | 0-11 | WRONG 0/4 regions (nomove 1/4 on h2) |
| lex-carrying state DP (escape class) | 5 | 1.9 | EXACT (this is the reference class) |
Shipped: every solver < 1 s and exact (BRANCH_FIRE shipped 0; hidden S-1 12/12, S-2 11-12/12, S-3 12/12 lanes).

## Expected loss per lever (COST_TABLE, real tests)
| lever | wrong reading alone | tests kept | lost | final if only this wrong (judge mid 34) |
|---|---|---|---|---|
| S-1 | greedy weight-first | 24/92 | 73.9% | 30.0 |
| S-2 | no moved term | 29/92 | 68.5% | 32.8 |
| S-3 | first optimum, no tie order | 27/92 | 70.7% | 31.7 |
Careful solver loses on h2/h3 region_*, policy_audit, segments, summary. Predicted first-write (guarded B&B) tests about 26, blind-class (no guard) about 24 by TIMEOUT; judge mid 34 (lower 17, upper 66); predicted final about 30. 35 mutants each fail >= 1 test (RULE_COVERAGE 0 uncovered).

## Open conflicts and notes
- Session rename: `name_session.py 7d363c8` printed `codex: no match` / `opencode: ['ses_e7682b365ffeo5a6nnmwzxy45X']`; the list did not show 7d363c8. Not retried.
- Option (c) timeout share: the no-guard blind class loses hidden lever points only by TIMEOUT (100%, above the 70% exception); guarded and heuristic solvers lose by WRONG. Reported, not tuned.
- Judge mid 34 is above the probe-mid 20 aim; the 55-70% probe-share band caps it.
- Q18 provenance: TRUTH keeps the scaffold provenance block; validator 15.5 and QC both pass, so no OPEN CONFLICT Q18.
- No G1a per-row OWNED masking: each hidden document is graded whole by exactly one check (whole-doc exactness stated in instruction line 15, CL-4 FC:491).

## Not run
- Real Harbor harness / rewardkit uvx run (a stub-rewardkit driver in Docker was used for oracle/nop).
- 300-seed survival block. (kill2 rows on all 5 hidden corpora finished 07:30, ALL_DONE_D, added above.)

## Fresh P13 blinds on the built bundle (07:35, WORK/blinds/BLINDS.md)
| blind | tests | lever pts lost (68) | TIMEOUT / WRONG share | h2 s | h3 s |
|---|---|---|---|---|---|
| 9aaa86f | 18/92 = 19.6% | 68 | 100% / 0% | >90 (timeout) | >90 (timeout) |
| 59480e5 | 18/92 = 19.6% | 68 | 100% / 0% | >90 | >90 |
| 25a31cb | 18/92 = 19.6% | 68 | 100% / 0% | >90 | >90 |
All three are exact on shipped and mutation checks and lose every hidden point by timeout, above the 70% option (c) timeout cap.

## Lessons for the master
- Generators with fixed role mixes silently skip filler-based fixtures at a new scale; count planted roles per corpus after every scale change | no change: caught by mutant block.
- A design blind exact at small scale became 0/9 at 60 s only after joining clusters (bridges) into one contention component per lane | no change: recorded in WORK/DESIGN_SUMMARY.md section option c.
- Validator 7.4 requires a test negative named `negative_hardcoded_sample_answers` and 15.8 that TRUTH names every negative test | no change: already in validator.
