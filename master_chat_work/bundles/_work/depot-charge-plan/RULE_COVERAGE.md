# RULE_COVERAGE (G11)

Each mutant drops one rule alone (WORK/tools/mutants.py on solution/solve.py); tests failed = real
test_output.py checks failed (logs tests-20261101T0320/logs/mut2_*.log, mut3.log, mut4_*.log).
rules.md = environment/data/docs/charging_rules.md; instr = instruction.md.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| command takes --data folder | instruction.md:7 | I_data_argument_ignored | 37 |
| command takes --out folder | instruction.md:7 | I_out_argument_ignored | 36 |
| docs rule 2 span end excluded | charging_rules.md:8 | R_span_inclusive_end | 30 |
| docs rule 4 retired vehicle rejected | charging_rules.md:13 | R_retired_accepted | 23 |
| docs rule 4 duplicate roster row rejected | charging_rules.md:13 | R_duplicate_accepted | 41 |
| docs rule 4 bad window (three conditions) | charging_rules.md:13 | R_bad_window_order_only | 36 |
| docs rule 7 trips of the day after the plan date | charging_rules.md:16 | R_trips_plan_date | 38 |
| docs rule 7 extra trips counted | charging_rules.md:16 | R_extra_trips_ignored | 38 |
| docs rule 7 extra trips only on the day after | charging_rules.md:16 | R_extra_trips_any_date | 30 |
| docs rule 7 reserve added | charging_rules.md:16 | R_reserve_ignored | 38 |
| docs rule 7 need not below zero | charging_rules.md:16 | R_need_no_floor | 38 |
| docs rule 8 unlisted contract is commercial | charging_rules.md:17 | R_unlisted_contract_public | 13 |
| docs rule 8 class weights from service_classes.ini | charging_rules.md:17 | R_class_weight_ignored | 12 |
| docs rule 10 depot cabinet limit (lever F) | charging_rules.md:22 | L_cabinets_ignored | 34 |
| docs rule 10 cabinet outages | charging_rules.md:22 | R_outage_ignored | 8 |
| docs rule 11 shared feeder limit (lever F) | charging_rules.md:23 | L_feeder_ignored | 34 |
| docs rule 11 feeder derating | charging_rules.md:23 | R_derate_ignored | 34 |
| docs rule 12 meter convention (lever M) | charging_rules.md:27 | L_meter_identity | 34 |
| docs rule 12 settled kWh in equal parts per slot | charging_rules.md:27 | R_settled_start_price | 42 |
| docs rule 13 published row outside window rejected | charging_rules.md:28 | R_published_outside_kept | 13 |
| docs rule 14 moved energy term | charging_rules.md:29 | R_moved_term_ignored | 38 |
| docs rule 14 moved energy counts shortfall only | charging_rules.md:29 | R_moved_absolute | 5 |
| docs rule 15 tie-break (lever T) | charging_rules.md:33 | L_tiebreak_first_found | 34 |
| docs rule 15 tie order slot then bus id | charging_rules.md:33 | L_tiebreak_reversed_order | 34 |
| docs rule 17 unmet_reason window | charging_rules.md:40 | R_unmet_reason_no_window | 6 |
| docs rule 17 changed compares every slot | charging_rules.md:40 | R_changed_by_total | 10 |
| docs rule 18 slot feeder_kwh is the fleet load | charging_rules.md:41 | R_slot_feeder_is_group | 26 |
| docs rule 21 data_quality order by file then line | charging_rules.md:44 | R_quality_file_order | 3 |
| docs rule 22 missing input named on stderr | charging_rules.md:48 | R_missing_file_unnamed | 1 |

Every row fails at least 1 test. No row 0.
