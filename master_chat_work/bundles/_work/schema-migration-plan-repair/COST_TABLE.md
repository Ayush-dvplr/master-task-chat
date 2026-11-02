# COST_TABLE (wave 1, board e3e74e6): measured

Positive test weight 241 (65 checks), negatives 14 (6 checks). Lever = world_29..world_36, 8 x 5 = 40 (16.6%).

## Full test runs (Docker, verifier image, `run_checks.py` on the bundle tests, --cpus 2)

Logs: `proto/chain_w1.log` (Opus), `/tmp/opencode-logs/smpr_w1_cost.log`; per-check results `proto/cost_*.json`, `proto/b7_opus.json`.

| program | earned / 241 | tests % | core worlds | other checks lost | seconds |
|---|---|---|---|---|---|
| oracle (solution/solve.py) | 241 | 100.0 | 8/8 | none | 17 |
| first write = Opus a4 deliverable (plain Dijkstra planner, every other fix right) | 201 | 83.4 | 0/8 (each killed at 60.4-60.9 s) | none | 496 |
| all-but-one = oracle with the pre-wave plain Dijkstra planner | 200 | 83.0 | 0/8 (killed at 60 s) | module_core_claims_match_archive (+1, see note) | 494 |
| blind cee149a program (prior blind read) | 44 | 18.3 | 0/8 (killed at 60.3-60.4 s) | 28 old worlds, 2 mutations, 2 receipt checks (no receipt_mismatches key: predates the r1 receipt lever), module_core claims | 491 |
| memory runaway (planner allocates 6 GiB on graphs over 1,000 schemas) | 200 | 83.0 | 0/8 (refused by the 4,096 MiB cap in 0.27-0.43 s) | module_core claims (+1, same note) | 21 |

Note: the all-but-one and memory programs swap only `planner.py` inside the oracle archive, so the oracle's
`module_core.json` claims no longer match the archived planner; that one weight-1 loss is an artefact of the
swap, not of the lever. True all-but-one = 201/241 = 83.4% (equal to the measured Opus a4 run). No negative
fired in any run.

## Planner-only solvers (kill test, `KILL_TEST.md`)

Each keeps 0 of 40 lever points. If every other fix is right, tests% <= (201 + 0) / 241 = 83.4%.

| solver | lever points kept | tests % upper bound |
|---|---|---|
| (a) speed-tuned plain Dijkstra | 0 | 83.4 |
| (b) dominance pruning | 0 (wrong plan) | 83.4 |
| (c) greedy incumbent + cost pruning | 0 | 83.4 |
| (d) bidirectional | 0 (wrong plan) | 83.4 |
| (e) state keyed by prerequisite fields only | 0 | 83.4 |
| greedy / schema-only / exhaustive / plain Dijkstra | 0 | 83.4 |
| Opus a4 planner, blind cee149a planner | 0 | 83.4 / 18.3 measured |

Lever loss for a strong first write: 40/241 = 16.6% (target band 10-30%). All-but-one 83.4% (<= 92).

## Gate v3.6 harden (board f0331ad, 28 Oct 2026): measured on the shipped tests (291 positive, 81 checks)

Docker (verifier image, `--memory 4g --cpus 2`), `proto/cost_g36.sh`, logs `proto/g36_cost1.log` (a5, abo) and
`proto/g36_cost2.log` (bl2), both ALL_DONE; per-check results `proto/g36_cost_<who>.json`.
Lever = world_29..world_46, 18 x 5 = 90 (30.9%).

| program | earned / 291 | tests % | core worlds | other checks lost | seconds |
|---|---|---|---|---|---|
| oracle (solution/solve.py, `proto/g36_oracle.log`) | 291 | 100.0 | 18/18 | none | 11 |
| run a5 deliverable (first write of the real run) | 201 | 69.07 | 0/18 (each killed at 60.2-60.3 s) | none | 1093 |
| blind 4f7606c deliverable | 201 | 69.07 | 0/18 (killed at 60.2-60.3 s) | none | 1092 |
| all-but-one = oracle with the pre-wave plain planner | 200 | 68.73 | 0/18 | module_core_claims_match_archive (swap artefact, +1) | 1092 |

True all-but-one = 201/291 = 69.07% (<= 75). No negative fired in any run.
Not re-run (earlier evidence): Opus a4 deliverable 201/241 with all 8 core worlds TIMEOUT; its planner TIMEOUT on
worlds 37-46 too (KILL_TEST) -> 201/291 = 69.07. Blind cee149a 44/241, planner TIMEOUT 10/10 -> <= 44/291 = 15.1%.
Generic planner-only solvers (KILL_TEST gate v3.6 table) keep 0 of 90 -> upper bound 201/291 = 69.07%.

## Gate v3.7 measured final costs (board 9111ecc)

| Program | Earned / positive | Tests % | Wall s | Lever lost (WRONG / TIMEOUT+CRASH) | Old core lost (T+C) | Crash+timeout / positive | Crash+timeout / lost | Cap 70% |
|---|---|---|---|---|---|---|---|---|
| a6 final repo (bar) | 291/591 | 49.24 | 982 | 300/300 (0 / 300) | 0/90 | 50.76% | 100.00% | ok |
| a5 agent program | 201/591 | 34.01 | 2060 | 300/300 (0 / 300) | 90/90 | 65.99% | 100.00% | ok |
| blind cee149a | 42/591 | 7.11 | 2163 | 300/300 (0 / 300) | 90/90 | 65.99% | 71.04% | ok |
| blind 4f7606c | 199/591 | 33.67 | 2126 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.49% | ok |
| blind d721 | 199/591 | 33.67 | 2084 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.49% | ok |
| blind d2fb | 199/591 | 33.67 | 2101 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.49% | ok |
| first write (Opus a4) | 199/591 | 33.67 | 2074 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.49% | ok |
| generic greedy | 121/591 | 20.47 | 155 | 300/300 (300 / 0) | 0/90 | 0.00% | 0.00% | ok |
| generic schema-only | 34/591 | 5.75 | 172 | 300/300 (300 / 0) | 0/90 | 0.00% | 0.00% | ok |
| generic dominance | 129/591 | 21.83 | 411 | 300/300 (300 / 0) | 0/90 | 0.00% | 0.00% | ok |
| all-but-one (oracle + plain Dijkstra planner) | 200/591 | 33.84 | 2159 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.74% | ok |
| generic A* schema bound | 290/591 | 49.07 | 1070 | 300/300 (0 / 300) | 0/90 | 50.76% | 99.67% | ok |
| generic prerequisite-keyed | 200/591 | 33.84 | 2091 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.74% | ok |
| generic incumbent | 200/591 | 33.84 | 2095 | 300/300 (0 / 300) | 90/90 | 65.99% | 99.74% | ok |
| generic bidirectional | 197/591 | 33.33 | 2096 | 300/300 (0 / 300) | 90/90 | 65.99% | 98.98% | ok |
| generic exhaustive | 167/591 | 28.26 | 2348 | 300/300 (0 / 300) | 90/90 | 71.57% | 99.76% | OVER |

Each row is a complete final-test run (141 checks, 591 positive) in Docker, 4 GiB and 2 CPUs. Loss kinds come from each check's emitted first_difference. The cap column uses the master's measure (crash+timeout points / positive test points, under which a5 390/591 = 65.99% is inside the raised 70% limit); the share of lost points is shown beside it. Slowest measured verifier run: generic exhaustive, 2348 s (limit 2,430 s).

### Lost points outside the core worlds

- a6 final repo (bar): none
- a5 agent program: none
- blind cee149a: summary_json_matches_delivered_run WRONG w1, module_core_claims_match_archive WRONG w1, module_parser_claims_match_archive WRONG w1, receipt_skips_lines_rejected_at_parse WRONG w3, receipt_counts_partner_rejected_lines WRONG w3, world_01_state_null_corrections_summary WRONG w5, world_02_tie_tokens_replay_feed WRONG w5, world_03_state_policy_tokens_corrections WRONG w5, world_04_scale_state_replay_summary WRONG w5, world_05_null_policy_replay_cli WRONG w5, world_06_tie_corrections_feed_summary WRONG w5, world_07_state_tie_null_tokens_summary WRONG w5, world_08_scale_policy_corrections_feed WRONG w5, world_09_policy_tokens_replay_corrections_cli WRONG w5, world_10_state_feed_replay_summary WRONG w5, world_11_null_tie_corrections_cli WRONG w5, world_12_scale_tokens_null_summary WRONG w5, world_13_state_policy_feed_cli WRONG w5, world_14_tie_policy_replay_summary WRONG w5, world_15_scale_corrections_tokens_feed WRONG w5, world_16_null_state_replay_corrections WRONG w5, world_17_tie_policy_null_feed_summary WRONG w5, world_18_scale_tie_replay_cli WRONG w5, world_19_state_tokens_corrections_replay_feed_summary WRONG w5, world_20_reject_pad_state_corrections WRONG w5, world_21_scope_damage_null_replay WRONG w5, world_22_reject_scope_feed_summary WRONG w5, world_23_pad_damage_tokens_policy WRONG w5, world_24_reject_damage_tie_cli WRONG w5, world_25_scope_pad_corrections_summary WRONG w5, world_26_reject_scope_pad_damage WRONG w5, world_27_pad_scope_state_tokens_cli WRONG w5, world_28_damage_reject_scale_replay WRONG w5, mutation_receipt_moves_only_mismatches WRONG w5, mutation_tokens_move_only_that_partner WRONG w5
- blind 4f7606c: module_core_claims_match_archive WRONG w1, module_parser_claims_match_archive WRONG w1
- blind d721: module_core_claims_match_archive WRONG w1, module_parser_claims_match_archive WRONG w1
- blind d2fb: module_core_claims_match_archive WRONG w1, module_parser_claims_match_archive WRONG w1
- first write (Opus a4): module_core_claims_match_archive WRONG w1, module_parser_claims_match_archive WRONG w1
- generic greedy: summary_json_matches_delivered_run WRONG w1, module_core_claims_match_archive WRONG w1, ladder_large_state WRONG w3, world_01_state_null_corrections_summary WRONG w5, world_03_state_policy_tokens_corrections WRONG w5, world_04_scale_state_replay_summary WRONG w5, world_07_state_tie_null_tokens_summary WRONG w5, world_08_scale_policy_corrections_feed WRONG w5, world_10_state_feed_replay_summary WRONG w5, world_12_scale_tokens_null_summary WRONG w5, world_13_state_policy_feed_cli WRONG w5, world_15_scale_corrections_tokens_feed WRONG w5, world_16_null_state_replay_corrections WRONG w5, world_18_scale_tie_replay_cli WRONG w5, world_19_state_tokens_corrections_replay_feed_summary WRONG w5, world_20_reject_pad_state_corrections WRONG w5, world_27_pad_scope_state_tokens_cli WRONG w5, world_28_damage_reject_scale_replay WRONG w5
- generic schema-only: summary_json_matches_delivered_run WRONG w1, module_core_claims_match_archive WRONG w1, plan_revisits_schema_with_new_state WRONG w3, plan_tie_first_edge_decides WRONG w3, ladder_large_state WRONG w3, pipe_rejection_codes WRONG w3, tokens_match_exactly WRONG w3, world_01_state_null_corrections_summary WRONG w5, world_02_tie_tokens_replay_feed WRONG w5, world_03_state_policy_tokens_corrections WRONG w5, world_04_scale_state_replay_summary WRONG w5, world_05_null_policy_replay_cli WRONG w5, world_06_tie_corrections_feed_summary WRONG w5, world_07_state_tie_null_tokens_summary WRONG w5, world_08_scale_policy_corrections_feed WRONG w5, world_09_policy_tokens_replay_corrections_cli WRONG w5, world_10_state_feed_replay_summary WRONG w5, world_11_null_tie_corrections_cli WRONG w5, world_12_scale_tokens_null_summary WRONG w5, world_13_state_policy_feed_cli WRONG w5, world_14_tie_policy_replay_summary WRONG w5, world_15_scale_corrections_tokens_feed WRONG w5, world_16_null_state_replay_corrections WRONG w5, world_17_tie_policy_null_feed_summary WRONG w5, world_18_scale_tie_replay_cli WRONG w5, world_19_state_tokens_corrections_replay_feed_summary WRONG w5, world_20_reject_pad_state_corrections WRONG w5, world_21_scope_damage_null_replay WRONG w5, world_22_reject_scope_feed_summary WRONG w5, world_23_pad_damage_tokens_policy WRONG w5, world_24_reject_damage_tie_cli WRONG w5, world_25_scope_pad_corrections_summary WRONG w5, world_26_reject_scope_pad_damage WRONG w5, world_27_pad_scope_state_tokens_cli WRONG w5, world_28_damage_reject_scale_replay WRONG w5, mutation_receipt_moves_only_mismatches WRONG w5, mutation_tokens_move_only_that_partner WRONG w5
- generic dominance: module_core_claims_match_archive WRONG w1, plan_revisits_schema_with_new_state WRONG w3, ladder_large_state WRONG w3, world_01_state_null_corrections_summary WRONG w5, world_03_state_policy_tokens_corrections WRONG w5, world_04_scale_state_replay_summary WRONG w5, world_07_state_tie_null_tokens_summary WRONG w5, world_10_state_feed_replay_summary WRONG w5, world_12_scale_tokens_null_summary WRONG w5, world_13_state_policy_feed_cli WRONG w5, world_16_null_state_replay_corrections WRONG w5, world_18_scale_tie_replay_cli WRONG w5, world_19_state_tokens_corrections_replay_feed_summary WRONG w5, world_20_reject_pad_state_corrections WRONG w5, world_27_pad_scope_state_tokens_cli WRONG w5, world_28_damage_reject_scale_replay WRONG w5
- all-but-one (oracle + plain Dijkstra planner): module_core_claims_match_archive WRONG w1
- generic A* schema bound: module_core_claims_match_archive WRONG w1
- generic prerequisite-keyed: module_core_claims_match_archive WRONG w1
- generic incumbent: module_core_claims_match_archive WRONG w1
- generic bidirectional: module_core_claims_match_archive WRONG w1, plan_tie_first_edge_decides WRONG w3
- generic exhaustive: module_core_claims_match_archive WRONG w1, ladder_large_state TIMEOUT w3, world_04_scale_state_replay_summary TIMEOUT w5, world_08_scale_policy_corrections_feed TIMEOUT w5, world_12_scale_tokens_null_summary TIMEOUT w5, world_15_scale_corrections_tokens_feed TIMEOUT w5, world_18_scale_tie_replay_cli TIMEOUT w5, world_28_damage_reject_scale_replay TIMEOUT w5
