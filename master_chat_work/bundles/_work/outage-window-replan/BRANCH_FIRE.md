# BRANCH_FIRE (Phase 0b, measured)

Shape D. A hard branch fires in a lane (region x crew type, 12 lanes per corpus) when a plausible solver's plan differs from the lexicographic optimum at that level. Measured with `WORK/proto/fire.py 2 <dirs>` in Docker (log `WORK/proto/logs/fire1.log`). Shipped = `WORK/design_blind/environment/data` (datagen seed 594183, shipped tier, rejection-sampled quiet); hidden = datagen hidden tier seeds 1, 2, 3 (`WORK/proto/hidden/s1..s3`).

| rule | branch (solver that exposes it) | fires on shipped (count of 12 lanes) | fires on hidden (seeds 1/2/3, lanes of 12) |
|---|---|---|---|
| S-1 min total risk-days | g_weight, g_edf, g_id, repair, g_swap or capped bb plan has higher risk (or is infeasible) | 0 | 12 / 12 / 12 |
| S-2 fewest moved | `nomove` (reference with level 2 skipped) plan moves more | 0 | 12 / 12 / 12 |
| S-3 start-list tie-break | `dp_nofix` or `bb_nolex` (first optimum in its own order) has a later start list | 0 | 12 / 12 / 11 |

Regions exact (all 3 lanes of a region equal to the optimum), per solver: shipped 4/4 for every solver; hidden seeds 1-3: 0/4 for every solver (g_weight, g_edf, g_id, repair, g_swap, bb_id, bb_heur, bb_nolex, nomove, dp_nofix). The reference (`proto/solve_proto.py`, state sweep carrying the lexicographic best) agrees with the independent `proto/lane.py` (forward/backward DP + fixing pass) on 12/12 lanes of all 4 corpora.

Reference run time (Docker, 2 CPUs): shipped 0.27 s, hidden 0.31-0.38 s per corpus.

Shipped deferrals: 0 (shipped summary: 88 requests, 88 scheduled, moved 1, risk_days 2408). Deferral reasons are exercised on hidden corpora only; Phase 2 adds shipped no_feasible_start requests (not a hard branch) so the reason strings appear on shipped data.
