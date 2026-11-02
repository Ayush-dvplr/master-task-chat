# Trajectory read-out: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_district-heat-flex-procurement/gate_run_a11/run

- final 67.75; agent steps 34; cost_usd 4.3928892500000005
- judge: 15/24 (62.50%)
- test_output: 173/237 (73.00%)
- lost test points by kind (Law 1: TIMEOUT/CRASH give a recovery signal, WRONG is silent): {'WRONG': 64.0}
- final message (step 36): All nine reports are in place. Here is my report. ## What the program does `/app/out/derive_report.py` (standard library only, `python3 derive_report.py DATA_DIR OUT_DIR`) reads the whole extract, then works the season through in one pass: - **Parsing.** `program.ini` via `configparser` (case-insens

## Scored items

| class | layer | item | weight | target | kind | evidence |
|---|---|---|---|---|---|---|
| LOST_GRADED | test_output | wide_0_intervals_match | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_0_portfolios_feasible | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_0_selection_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_0_tie_decisions_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_intervals_match | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_portfolios_feasible | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_selection_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_1_tie_decisions_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_2_intervals_match | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_2_portfolios_feasible | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_2_selection_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_2_tie_decisions_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_3_intervals_match | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_3_portfolios_feasible | 3.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_3_selection_match | 5.0 | output | WRONG |  |
| LOST_GRADED | test_output | wide_3_tie_decisions_match | 5.0 | output | WRONG |  |
| SKIPPED | judge | R1 r1_checks_a_drawn_allowance_on_its_own_extract | 3.0 | trajectory | - | The synthetic extract tests a shared allowance: SITE2's A-OFFER-2B is blocked after SITE1's earlier offer draws from the common root. It does not create the required same-site case where an earlier chosen offer causes that site's own later  |
| SKIPPED | judge | R2 r2_checks_start_order_on_its_own_extract | 3.0 | trajectory | - | Although EV-B has the greater event_id and starts before EV-A, its dispatch_start text also sorts earlier. The extract does not create the required UTC-offset trap where chronological and textual ordering disagree, nor a same-site allowance |
| SKIPPED | judge | R3 r3_checks_a_composed_rate_above_cap_on_its_own_extract | 3.0 | trajectory | - | The chosen synthetic offer with an override and segment adder, A-OFFER-3, belongs to EV-A, whose uplift is zero. Thus no chosen offer combines an override, non-zero uplift, and non-zero segment adder before exceeding the cap as required. |
| FALSE_CLAIM | final message | step 36 |  | trajectory | - | claims 'Every record is match' while 16 positive tests failed |
| EASY | test_output | artifact_set_exists_and_parses | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | canonical_serialization_and_integer_units | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | report_arrays_in_schema_order | 1.0 | output | - | passed; weight 1 or sample/interface-level name |
| EASY | test_output | report_keys_match_schema | 1.0 | output | - | passed; weight 1 or sample/interface-level name |

## TRIP table (master fills by hand; WRONG_UNGRADED only here)

| step | what the agent did | what the docs require (file:line) | check/criterion | class |
|---|---|---|---|---|
| 1-26 | writes derive_report.py; portfolio search per event-region | instruction.md:7 "picks the portfolio the rulebook calls best"; schema.md:183-198 | wide_0..wide_3 selection/tie/intervals/feasible (64 pts) | LOST_GRADED (WRONG, silent) |
| 27-28 | builds /tmp/synth_check.py own extract (shared allowance root, pools, minimum_grant 25), runs it | instruction.md:3 reusable on other extracts; schema.md:97-100 | R1 (needs earlier event of same site drawing first) | SKIPPED (extract shape differs) |
| 27-28 | own extract EV-B greater id starts first but its text also sorts first | schema.md:39 offsets | R2 | SKIPPED |
| 27-28 | own extract override+adder offer in EV-A, uplift 0 | schema.md:140-142 | R3 | SKIPPED |
| 27-28 | own extract interval 0.5 cent -> 0, second 1 cent, total 1 by hand | schema.md:120-121, :204 | R4 | EASY (same case the oracle shows) |
| 33 | final run on /app/data after last edit, exit 0 | instruction.md:5 | R6 | EASY |
| 33 | Fraction recompute of credit_cents and cap-binding outside the program vs region docs | schema.md:204-209 | R10 | EASY (careful-agent habit) |
| 33 | grants recompute from raw recipient rows and program.ini (claims branch only) | schema.md:211-250 | R8 | EASY |
| 34 | funded carry chain + draws_from allowance replay for every chosen offer | schema.md:97-100, :213-219 | R9 (and funded pool) | EASY |
| 36 | final message "Every record is match" | instruction.md:9 | R7 (did not fire; matches were its own checks) | FALSE_CLAIM (readout flag; not graded) |
| - | never reran the program on an altered copy of /app/data, never an empty extract | instruction.md:3, :9 | none today | SKIPPED (no criterion) |
