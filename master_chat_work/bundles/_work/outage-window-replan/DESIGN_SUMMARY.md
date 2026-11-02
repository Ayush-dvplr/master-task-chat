# DESIGN_SUMMARY 7d363c8 outage-window-replan (Shape D, P-3 + N2 + S2 + P-5)

Core: transmission maintenance replan after a disruption notice. Per lane (region x crew type) choose start or deferral for each request; lexicographic objective S-1 min risk-days (weight x load-band factor per day out; deferral = weight x duration x defer factor), S-2 fewest published outages moved, S-3 smaller start-day list in ascending asset_id order (deferred after every day). Contract sentence: "Every published figure is computed from the one replanned season that the objective order selects."

Data: 13 files, 7 formats (md, json, jsonl, csv, tsv, toml, log), about 20 stated noise rules, chains C1-C5 (customers -> weight -> risk; load_forecast -> band -> factor; roster + control_room.log crew loss -> capacity; log new/withdrawn requests -> request set; published_plan -> moved). Shipped lanes rejection-sampled quiet: every greedy/B&B/DP solver exact on them (BRANCH_FIRE shipped 0).

Reference: day-sweep DP over (pending, running, deferred predecessors) + lexicographic fixing pass; == brute force 20/20 tiny lanes; 0.01-0.19 s per contended hidden lane (~3 s per corpus).

Kill test (Docker, WORK/KILL_TEST.md, hidden lanes 1-8):
- greedy by weight / EDF / id order / repair / greedy+swap: WRONG 8/8 lanes (risk or infeasible).
- guarded B&B (id order, heuristic order, (risk,moved)-only): WRONG:risk 6-7/8 at a 15 s guard.
- component split + B&B (60 s guard): comp_id WRONG 5/8, comp_heur WRONG 3/8 -> keeps ~24% of region points (3 lanes per region must all be exact).
- sweep DP without lex pass: WRONG:tie 8/8 (tie pairs planted per lane, own RNG).
- comp_heur with a 280 s guard per lane (impossible inside a 300 s run of 12 lanes): still WRONG:risk on seeds 4 and 7, EXACT on seed 1.
- Escape: a DP carrying the lex-min (value, start vector) per state is exact and fast; PREMORTEM puts a first-write at ~10%. This is the main risk.

Tests: 3 shipped (w3), 2 hidden corpora H2/H3 x 9 tests (4 region files w5, policy_audit w5, 2 segments w3, summary w3, data_quality w3), 3 mutation (w3), 1 grader-read negative (-5). Positive 92; hidden 80.4%; w5 tier 54.3%; lever families 73.9%. Invocation `python3 /app/out/derive_report.py --data <dir> --out <dir>`, per-run limit 300 s, verifier limit 2700 s (worst 1510 s = 56%).

Judge: 8 probes w3 (P-a, P-a2, P-b, P-c, P-d, P-e, P-g, P-h), J4 w3, J6 w5, J10 w3; J3a/b/c + grader-read negatives; probe share 68.6%; mid 32.9% (lower 15, upper 55). The probe-band share (55-70%) caps the mid above the 20 aim; recorded honestly.

Predicted: first-write tests ~28 (PREMORTEM a: guarded B&B), all-but-S-3 46, cost alone S-1 74 / S-2 61 / S-3 54 (each >= 25%).
DESIGN READY bar: (a) final (28 + 32.9)/2 = 30.5 <= 35; (b) lever 73.9%, w5 54.3%; (c) strongest generic ~39 tests < 65; (d) 56% <= 90%; (e) every generic solver loses >= 15% lever points by WRONG, shipped < 0.1 s, reference << 75 s.

Open risks: (1) lex-carrying DP escape (exact); (2) judge mid 32.9 > 20 aim; (3) S-2 keep pairs not yet prototyped (Phase 0b); (4) session rename showed ses_e7682b365ffeo5a6nnmwzxy45X, not 7d363c8.

Files: WORK/PREMORTEM.md, DESIGN.md, KILL_TEST.md, BRANCH_FIRE.md, QC_DEFENCE.md, proto/.

## 04:35 design blind result
P13 blind 7a33fe5 is exact 9/9 on the shipped sample and hidden seeds 1-3 (1/2/90/28 s of 300 s):
contention-aware components + asset-id-order exact DFS. Lever points kept 100% -> PAUSED (NO CORE under G-6). See DESIGN_BLIND.md.

## option c (master go 04:40; measured 05:22-06:10 IST)
Hidden tier now G scale (datagen defaults CL_N 7-9, NCL 3, N_RANGE 26-32, CL_W 6-9, BRIDGE 1-2): lanes 26-34 requests, one contention component per lane (32-33). Stated per-run limit: 60 s (instruction). Shipped tier unchanged (6-10 per lane, rejection-sampled quiet, every solver < 1 s).
| program | corpus | seconds | result |
|---|---|---|---|
| reference solve.py (lex-carrying state DP) | G_s41/42/43 | 1.1 / 1.4 / 1.5 (incl container) | EXACT 9/9 |
| lane day-sweep DP + fixing pass (check_exact engine) | G_s41/42/43 | 2.3 / 2.9 / 4.0 | EXACT |
| blind 7a33fe5 (contention split + id-order DFS, no guard) | G_s41/42/43 | > 120 (alarm) | TIMEOUT x3 |
| comp_dfs (own write of blind method) | G/H 6 seeds, 20 s | cap | TIMEOUT 6/6 |
| comp_dfs_guard / comp_heur_guard (incumbent at 0.8 limit) | G 3 seeds, 60 s | 48.1 | WRONG 0/4 regions x3 |
| bb_heur_guard, g_weight, g_swap, repair, nomove, dp_nofix | G/H 6 seeds, 20 s | 0.0-16 | WRONG 0/4 regions all |
Bar: reference 1.5 s <= 15 s (1/4 of 60); blind loses 100% of hidden lever points (all TIMEOUT); verifier worst ~ 6 runs x 60 s + pytest ~ 450 s <= 2430; lever share 73.9%; predicted blind-class tests ~ 20 (shipped + mutation only) -> final (20 + 32.9)/2 = 26.5; first-write (guarded B&B, WRONG) ~ 20-28 -> final <= 31.
Open: the no-guard blind class loses by TIMEOUT only (timeout share 100% > the 70% exception for that one program); every guarded or heuristic solver loses by WRONG. A careful agent reading the 60 s limit adds a guard and loses by WRONG. Reported, not tuned.
