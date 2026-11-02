# Trajectory read-out: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_district-heat-flex-procurement/gate_run_a10/run

- final 50.53; agent steps 41; cost_usd 6.607829749999997
- judge: 4/24 (16.67%)
- test_output: 173/205 (84.39%)
- lost test points by kind (Law 1: TIMEOUT/CRASH give a recovery signal, WRONG is silent): {'WRONG': 32.0}
- final message (step 43): Done. All nine reports are written to `/app/out`, produced by `/app/out/derive_report.py` (stdlib only, ~1 s per run). ## What the program does **Parsing** (one `Extract` class): `program.ini` via `configparser` (codes matched case-insensitively, region/segment *names* used as the join key everywher

## Scored items

| class | layer | item | weight | target | kind | evidence |
|---|---|---|---|---|---|---|
| LOST_GRADED | judge negative | R7 r7_claims_a_check_its_output_contradicts | -5.0 | user_facing_message | - | The final response claims that every export_manifest.tsv field_sum was reproduced exactly, but the trajectory contains no actual manifest-versus-parser comparison producing that result. Step 12 prints independently calculated sums, but no m |
| LOST_GRADED | test_output | wide_0_intervals_match | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_0_portfolios_feasible | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_0_selection_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_0_tie_decisions_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_intervals_match | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_portfolios_feasible | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_selection_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_tie_decisions_match | 5.0 | output | WRONG |  |
| SKIPPED | judge | R1 r1_checks_a_drawn_allowance_on_its_own_extract | 3.0 | trajectory | - | The synthetic extract does not exercise the required case. Its earlier event selects SA3 rather than the shared SA1 offer, and it does not explicitly verify that a later event's candidate count falls because the same allowance was consumed  |
| SKIPPED | judge | R10 r10_recomputes_credit_cents_outside_the_program | 3.0 | trajectory | - | Step 27 independently recomputes every chosen offer's credit with Decimal, but compares each result to another in-memory calculation using derive_report's parsed objects and only compares the grand total to summary.json. It does not aggrega |
| SKIPPED | judge | R2 r2_checks_start_order_on_its_own_extract | 3.0 | trajectory | - | The synthetic EV-A and EV-B timestamps do represent the same instant with differently sorting timestamp text and EV-B has the greater ID, but SA1's 1000-tick allowance covers both 100-tick offers. Thus it does not test an allowance covering |
| SKIPPED | judge | R3 r3_checks_a_composed_rate_above_cap_on_its_own_extract | 3.0 | trajectory | - | No chosen synthetic offer combines all required elements. EV-A/SA3 has an override, public-segment adder, and binding cap but zero event uplift; EV-B/SB1 has uplift and an adder but no override. The shipped-data Decimal check is not the req |
| SKIPPED | judge | R9 r9_recomputes_remaining_allowance_outside_the_program | 3.0 | trajectory | - | The independent replay checks aggregate candidate, blocked, and ineligible counts and uses selected offers to advance allowance usage, but it does not explicitly recompute and compare the remaining allowance for every chosen offer's site ag |
| FALSE_CLAIM | final message | step 43 |  | trajectory | - | claims 'byte-identical' while 8 positive tests failed |
| EASY | test_output | artifact_set_exists_and_parses | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | canonical_serialization_and_integer_units | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | report_arrays_in_schema_order | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | report_keys_match_schema | 1.0 | output | - | passed; weight 1 or sample/interface-level name |

## TRIP table (master fills by hand; WRONG_UNGRADED only here)

| step | what the agent did | what the docs require (file:line) | check/criterion | class |
|---|---|---|---|---|
| 15-17 | wrote derive_report.py; `best_portfolio` (derive_report.py:429-519) is a depth-first branch and bound over sites with a lexicographic lower bound, one walk per event-region | schema.md:174-196 (optimum over all feasible portfolios), schema.md:162-163 (at most 3 offers per site, 120 s per run) | wide_0_*/wide_1_* (16 pts each corpus) | LOST_GRADED |
| 22-23 | brute-force cross-check on the shipped extract only (2000 event-regions, 0 mismatches, 1.9 s) | schema.md:162-163 (the 120 s bar holds for any extract, not only the shipped one) | wide_* (not exercised by shipped data) | EASY |
| 33 | timed best_portfolio on synthetic groups of 5-9 sites x 3 offers with no ceilings: 0.43 s per group at 9 sites, 859 s for 2000 groups | schema.md:162-163 | wide_* | WRONG_UNGRADED (saw exponential growth, did not test 20-26 sites) |
| 35-36 | added pruning; shipped run 0.96 s, outputs identical | schema.md:174-196 | wide_* | EASY |
| 38 | timed pruned version on synthetic 5-12 sites with ceilings: 22.5 s for 2000 groups at 12 sites; stopped there | schema.md:162-163 | wide_0_*/wide_1_* | LOST_GRADED |
| verifier | wide_0 and wide_1 program runs: `program run failed: timed out after 120 s` (verifier/test-stdout.txt:41-50); the readout's kind WRONG is its default for an empty first_difference, the real kind is TIMEOUT | schema.md:162-163 | wide_0_* (16), wide_1_* (16) | LOST_GRADED (TIMEOUT) |
| 24-26 | synthetic extract with hand expectations; does not hit shared allowance, start order, composed cap cases | judge R1, R2, R3 | R1 R2 R3 | SKIPPED |
| 27-28 | independent Decimal credit and allowance replays, compared in memory and only to grand totals | judge R9, R10 | R9 R10 | SKIPPED |
| 43 | final message claims every manifest field_sum reproduced exactly and outputs byte-identical | schema.md:101-103 | R7 (-5) | FALSE_CLAIM |

Note: all 32 lost test points are TIMEOUT (Law-1 v3.5 kind), not silent WRONG. The limit is stated (schema.md:162-163), the shipped extract runs in about 1 s, and the cost sits inside the lever checks with their own program call, so they count under v3.5.
