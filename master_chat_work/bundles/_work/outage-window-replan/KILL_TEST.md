# KILL_TEST 7d363c8 outage-window-replan (prototype, lane level)

All runs in Docker: `docker run --rm --init --memory 4g --cpus 2 -v proto:/w python:3.12-slim perl -e 'alarm N; exec @ARGV' python3 -B <script>`.
Instance = one lane (one region x one crew type) from `proto/lanegen.py`. A hidden corpus holds 12 lanes (4 regions x 3 crew types); every region test owns 3 lanes, so a region is exact only if all 3 of its lanes are exact.
Reference = `proto/lane.py` day-sweep DP over (pending set, running set, deferred predecessors) + lexicographic fixing pass. Reference == brute force on 20/20 tiny lanes (H 18, n 3-5).
Logs: `proto/logs/lane_hidden2.log`, `proto/logs/lane_comp.log`, `proto/logs/longcap.log`.

| solver | instance | seconds | result | lever points kept |
|---|---|---|---|---|
| reference (sweep DP + lex fix) | hidden 1-8 | 0.01-0.19 | EXACT | all |
| reference | shipped 1-4 | < 0.1 | EXACT | all |
| g_weight (w*dur desc, cheapest feasible) | hidden 1-8 | < 0.01 | WRONG:risk 8/8 | 0 |
| g_edf (latest finish asc) | hidden 1-8 | < 0.01 | WRONG:risk 8/8 | 0 |
| g_id (asset-id order greedy) | hidden 1-8 | < 0.01 | WRONG:risk 8/8 | 0 |
| repair (keep feasible published starts, greedy rest) | hidden 1-8 | < 0.01 | WRONG:risk 4/8, INFEAS 4/8 | 0 |
| g_swap (greedy + relocate/pair local search) | hidden 1-8 | 0.01-0.41 | WRONG:risk 8/8 | 0 |
| bb_id (id-order DFS, sum-min LB, greedy incumbent, guard 15 s) | hidden 1-8 | 8.6-15 | WRONG:risk 7/8 (capped), EXACT 1/8 | about 1/8 of lanes |
| bb_heur (w*dur-desc DFS, guard 15 s) | hidden 1-8 | 2.1-15 | WRONG:risk 6/8, EXACT 2/8 | about 2/8 of lanes |
| bb_nolex ((risk, moved) only, `>=` prune) | hidden 1-8 | 2.1-15 | WRONG:risk 6/8, EXACT 2/8 | about 2/8 of lanes |
| dp_nofix (same sweep DP, first optimal edge, no lex pass) | hidden 1-8 | 0.01-0.09 | WRONG:tie 8/8 | 0 (ties planted per lane) |
| comp_id (window-overlap components + id-order B&B, guard 60 s) | hidden 1-8 | 0.75-60 | WRONG:risk 5/8, EXACT 3/8 | about 3/8 of lanes |
| comp_heur (components + heuristic B&B, guard 60 s) | hidden 1-8 | 0.22-60 | WRONG:risk 3/8, EXACT 5/8 (2 of them capped but incumbent optimal) | about 5/8 of lanes |
| comp_heur long guard 280 s per lane (more than the whole 300 s run allows for 12 lanes) | hidden 1, 4, 7 (its 60 s failures) | 280 (capped all 3) | EXACT 1/3 (seed 1), WRONG:risk 2/3 (seeds 4, 7) | about 6/8 of lanes at an impossible budget |

Shipped tier (seeds 1-4, n 6-10): every solver < 0.1 s. Greedy variants and dp_nofix are not always exact on raw shipped draws (seed 4 g_weight WRONG:risk; dp_nofix WRONG:tie 3/4), so the shipped generator rejection-samples each lane until every solver in this table is EXACT on it (BRANCH_FIRE shipped count 0).

## Reading per region
A region test passes only when all 3 lanes of the region are exact. For the strongest generic solver (comp_heur, about 5/8 lanes exact at a 60 s guard), a region with 3 contended lanes is exact with probability about (5/8)^3 = 0.24; over 4 regions x 2 corpora it keeps about 24% of region points, so it loses about 76% of lever points by WRONG output. Every greedy-class and local-search solver loses 100%. A sweep DP without the level-3 pass loses all region points by WRONG:tie (summary and segment files can survive a pure tie; the region files and policy_audit rows cannot).

## Long guard
Even at 280 s per lane (a stated 300 s per-run limit gives about 25 s per lane over 12 lanes) the strongest component B&B stays WRONG:risk on 2 of 8 lanes, so a region (3 lanes) is exact with probability about 0.42 at that impossible budget and about 0.24 at a realistic one. The loss is a valid but WRONG document, not a timeout.

## Escape path (recorded, not hidden)
A day-sweep DP (or backward memo over day, unstarted set, running set) that carries the lexicographic minimum (value, start vector of the remaining requests in asset-id order) per state is exact and fast; this is the reference class. The kill test asks whether plausible first-write programs reach it: PREMORTEM puts that near 10%.

## Final generator (tests/ hgen, 60 s stated limit), kill2.py in Docker, 07:15 IST
| solver | instance | seconds | result | lever points kept |
|---|---|---|---|---|
| ref_lane_dp | h2 | 4.69 | EXACT 4/4 | all |
| solve_proto_lexdp | h2 | 1.93 | EXACT 4/4 | all |
| comp_dfs (blind method, no guard) | h2 | 60.0 | TIMEOUT 0/4 | 0 |
| comp_dfs_guard | h2 | 48.1 | WRONG 0/4 | 0 |
| comp_heur_guard | h2 | 48.1 | WRONG 0/4 | 0 |
| bb_heur_guard | h2 | 48.1 | WRONG 0/4 | 0 |
| g_weight | h2 | 0.0 | WRONG 0/4 | 0 |
| g_swap | h2 | 10.2 | WRONG 0/4 | 0 |
| repair | h2 | 0.0 | WRONG 0/4 | 0 |
| nomove | h2 | 5.9 | WRONG 1/4 | 1 region |
| dp_nofix | h2 | 1.4 | WRONG 0/4 | 0 |
| ref_lane_dp | h3 | 4.69 | EXACT 4/4 | all |
| solve_proto_lexdp | h3 | 1.99 | EXACT 4/4 | all |
| comp_dfs | h3 | 60.0 | TIMEOUT 0/4 | 0 |
| comp_dfs_guard, comp_heur_guard, bb_heur_guard | h3 | 48.1 | WRONG 0/4 | 0 |
| g_weight, repair | h3 | 0.0 | WRONG 0/4 | 0 |
| g_swap | h3 | 10.4 | WRONG 0/4 | 0 |
| nomove | h3 | 7.2 WRONG 0/4 | 0 |
| dp_nofix | h3 | 1.7 | WRONG 0/4 | 0 |
| ref_lane_dp | n1 | 5.10 | EXACT 4/4 | all |
| solve_proto_lexdp | n1 | 1.95 | EXACT 4/4 | all |
| comp_dfs | n1 | 60.0 | TIMEOUT 0/4 | 0 |
| comp_dfs_guard, comp_heur_guard, bb_heur_guard | n1 | 48.1 | WRONG 0/4 | 0 |
| g_weight, repair | n1 | 0.0 | WRONG 0/4 | 0 |
| g_swap | n1 | 10.1 | WRONG 0/4 | 0 |
| nomove | n1 | 7.3 WRONG 0/4 | 0 |
| dp_nofix | n1 | 1.8 | WRONG 0/4 | 0 |
| ref_lane_dp | n2 | 4.45 | EXACT 4/4 | all |
| solve_proto_lexdp | n2 | 1.81 | EXACT 4/4 | all |
| comp_dfs | n2 | 60.0 | TIMEOUT 0/4 | 0 |
| comp_dfs_guard, comp_heur_guard, bb_heur_guard | n2 | 48.1 | WRONG 0/4 | 0 |
| g_weight, repair | n2 | 0.0 | WRONG 0/4 | 0 |
| g_swap | n2 | 9.2 | WRONG 0/4 | 0 |
| nomove | n2 | 5.7 WRONG 0/4 | 0 |
| dp_nofix | n2 | 1.4 | WRONG 0/4 | 0 |
| ref_lane_dp | n3 | 4.61 | EXACT 4/4 | all |
| solve_proto_lexdp | n3 | 1.72 | EXACT 4/4 | all |
| comp_dfs | n3 | 60.0 | TIMEOUT 0/4 | 0 |
| comp_dfs_guard, comp_heur_guard, bb_heur_guard | n3 | 48.1 | WRONG 0/4 | 0 |
| g_weight, repair | n3 | 0.0 | WRONG 0/4 | 0 |
| g_swap | n3 | 11.1 | WRONG 0/4 | 0 |
| nomove | n3 | 6.5 WRONG 0/4 | 0 |
| dp_nofix | n3 | 1.5 | WRONG 0/4 | 0 |

Max lane / contention component: h2 40/37, h3 41/41, n1 41/40, n2 40/36, n3 42/39. block2.log ALL_DONE_D (07:30): every generic solver WRONG or TIMEOUT on all 5 hidden corpora; only nomove keeps 1 region on h2.
