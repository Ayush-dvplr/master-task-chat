# COST_TABLE 7d363c8 (G10)

Each row: wrong reading injected alone into a copy of solution/solve.py, run through the real tests/test_output.py (Docker, block2.log). Score = positive test points kept of 92. Predicted final = (tests % + judge mid 34) / 2.

| rule / lever | file:line | wrong reading | tests kept | points lost | lost % | predicted final if only this is wrong |
|---|---|---|---|---|---|---|
| load band: largest min_mw not above peak | docs/replan_contract.md:11 | band needs peak strictly above min_mw | 22 | 70 | 76.1 | 29.0 |
| blackout forbids a start only | docs/replan_contract.md:22 | blackout forbids every day out | 17 | 75 | 81.5 | 26.2 |
| rejection checks in stated order | docs/intake.md:11 | out_of_season and window_too_short swapped | 86 | 6 | 6.5 | 63.7 |
| crew_days = crews x days | docs/output_schema.md:22 | crew_days ignores crews | 65 | 27 | 29.3 | 52.3 |
| defer factor from risk_policy.toml | docs/replan_contract.md:31 | defer factor fixed at 4 | 24 | 68 | 73.9 | 30.0 |
| duplicate_request counts withdrawn | docs/intake.md:16 | withdrawn asset not counted as accepted | 55 | 37 | 40.2 | 46.9 |
| end = last day out | docs/output_schema.md:12 | end one day past the last day | 36 | 56 | 60.9 | 36.6 |
| HEARTBEAT has no effect, not counted | docs/intake.md:28 | HEARTBEAT counted in ignored_lines | 83 | 9 | 9.8 | 62.1 |
| incompatible pairs never out together | docs/replan_contract.md:24 | incompatible list ignored | 49 | 43 | 46.7 | 43.6 |
| log position 1-based line | docs/intake.md:37 | 0-based log position | 83 | 9 | 9.8 | 62.1 |
| capacity less CREW_LOSS | docs/replan_contract.md:15 | CREW_LOSS ignored | 12 | 80 | 87.0 | 23.5 |
| CREW_LOSS notices add up | docs/intake.md:36 | overlapping notices take the max | 59 | 33 | 35.9 | 49.1 |
| malformed lines count in ignored_lines | docs/intake.md:33 | malformed lines not counted | 83 | 9 | 9.8 | 62.1 |
| missing input named in message | instruction.md:11 | message without the file name | 89 | 3 | 3.3 | 65.4 |
| published deferred now scheduled is moved | docs/replan_contract.md:36 | not counted as moved | 36 | 56 | 60.9 | 36.6 |
| deferred stays deferred is not moved | docs/replan_contract.md:36 | counted as moved | 36 | 56 | 60.9 | 36.6 |
| control-room request never moved | docs/replan_contract.md:36 | control-room requests counted moved | 24 | 68 | 73.9 | 30.0 |
| no_feasible_start checks blackout and capacity | docs/replan_contract.md:43 | window only | 76 | 16 | 17.4 | 58.3 |
| out_of_season rejection | docs/intake.md:14 | check dropped | 3 | 89 | 96.7 | 18.6 |
| daily peak = max load_mw | docs/replan_contract.md:11 | first period used | 12 | 80 | 87.0 | 23.5 |
| precedence | docs/replan_contract.md:25 | precedence list ignored | 17 | 75 | 81.5 | 26.2 |
| after starts after before's last day | docs/replan_contract.md:25 | after may start on before's last day | 72 | 20 | 21.7 | 56.1 |
| events at or before published_at no effect | docs/intake.md:34 | pre-publication events applied | 18 | 74 | 80.4 | 26.8 |
| class weights from risk_policy.toml | docs/replan_contract.md:7 | public weight 1 | 12 | 80 | 87.0 | 23.5 |
| deferral reasons in stated order | docs/replan_contract.md:41 | predecessor_deferred checked after displaced | 82 | 10 | 10.9 | 61.6 |
| rejected ordered by source then position | docs/output_schema.md:43 | ordered by position only | 83 | 9 | 9.8 | 62.1 |
| capacity = on_duty rows | docs/replan_contract.md:15 | every non-leave row counted | 12 | 80 | 87.0 | 23.5 |
| region schedule ordered by start then asset_id | docs/output_schema.md:21 | ordered by asset_id | 52 | 40 | 43.5 | 45.3 |
| deferred_risk_days per class | docs/output_schema.md:32 | whole weight on each segment | 80 | 12 | 13.0 | 60.5 |
| unknown_asset rejection | docs/intake.md:13 | dropped silently | 83 | 9 | 9.8 | 62.1 |
| window_too_short rejection | docs/intake.md:15 | check dropped | 3 | 89 | 96.7 | 18.6 |
| WITHDRAW of non-request counts in ignored_lines | docs/intake.md:38 | not counted | 83 | 9 | 9.8 | 62.1 |
| **S-1 smallest total risk-days** | docs/replan_contract.md:35 | greedy lane plan (weight x duration first) | 24 | 68 | 73.9 | 30.0 |
| **S-2 fewest moved outages** | docs/replan_contract.md:36 | moved count left out of the objective | 29 | 63 | 68.5 | 32.8 |
| **S-3 start-day list tie-break** | docs/replan_contract.md:37 | first optimum found kept (no level-3 compare) | 27 | 65 | 70.7 | 31.7 |

## Gate
- Shape D: every lever alone >= 25%: S-1 73.9%, S-2 68.5%, S-3 70.7% lost (PASS).
- All-but-one rows (only that lever wrong) predicted final 30.0-32.8, every row < 70 (PASS).
- One-fact-wrong score (CL-4) = the tests-kept column of that rule's row.
- Every row loses >= 1 test (RULE_COVERAGE).

## Kill rows on the final generator (block2.log, kill2.py, stated limit 60 s, Docker 4g/2 cpu)
| solver | corpora | seconds | result |
|---|---|---|---|
| ref_lane_dp | h2 h3 n1 n2 n3 | 4.45-5.10 | EXACT 4/4 |
| solve_proto_lexdp (reference class) | 5 | 1.72-1.99 | EXACT 4/4 |
| comp_dfs (blind method, no guard) | 5 | 60.0 | TIMEOUT 0/4 |
| comp_dfs_guard, comp_heur_guard, bb_heur_guard | 5 | 48.1 | WRONG 0/4 |
| g_weight, repair | 5 | 0.0 | WRONG 0/4 |
| g_swap | 5 | 9.2-11.1 | WRONG 0/4 |
| nomove | 5 | 5.7-7.3 | WRONG 0/4 (h2 1/4) |
| dp_nofix | 5 | 1.4-1.8 | WRONG 0/4 |
