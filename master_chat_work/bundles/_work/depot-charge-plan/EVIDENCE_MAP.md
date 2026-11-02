# EVIDENCE_MAP: graded properties settled by a shipped fact rather than a sentence

Every graded rule has a sentence in environment/data/docs/charging_rules.md (RULE_TRACE.md). The rows below are deliverable properties that the rules leave to one determinate shipped fact (LEVER_RULES 0b).

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| time of day of slot 0 is the first_slot clock time | all region/segment/summary tests (cost fields), fresh_h*_* | environment/data/grid.ini:3 `first_slot = 2026-03-14T12:00`; tariff.xml bands start at 12:00 | slot 0 = midnight (bands would be misaligned; shipped cost total would not match settled cents at shift 0) |
| settlements rows are billed at whole cents | fresh_h*_region_*, summary | environment/data/settlements.csv:2.. (`kwh` and `cents` integers; every row reconciles at the stated reading) | fractional cents / rounding per slot |
| bus ids order as strings | fresh_h*_policy_audit_exact (tie-break order "then bus id") | environment/data/fleet_register.csv:2 ids all `B` + 4 digits, as in roster.csv | numeric vs string order coincide on fixed-width ids, so no second reading exists |

## Added P12 fix v2 (board 0d6348c)

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| derated feeder limit binds on the plan date | shipped_policy_audit_exact, shipped_summary_exact, shipped_segment_public_exact, shipped_region_east_exact | environment/data/disruption_notice.md:10 `feeder limit 90 kWh per slot`; docs/charging_rules.md:23 rule 11 | copying published_plan.csv (published load exceeds 90 in that window); ignoring the notice |
| first applicable rejection reason wins | shipped_data_quality_exact, fresh_h1/h3_data_quality_exact, fresh_h*_summary_exact | environment/data/roster.csv:2434 (B9991, arrive after depart), :2497 (retired B8875, arrive after depart), :4329 (duplicate B1113, arrive after depart); docs/charging_rules.md:13 rule 4 order | bad_window reported for an unknown, retired or duplicate row; two reasons for one row |
| published row of a bus not on the plan is ignored | fresh_h*_summary_exact, fresh_h*_data_quality_exact (hidden row only) | docs/charging_rules.md:28 rule 13 sentence "is ignored and is not rejected" | rejecting it as published_row_outside_window; crashing on it |
| unreadable file stops the run naming it | malformed_tariff_stops_naming_file | docs/charging_rules.md:48 rule 22 "cannot be read as these rules describe" | traceback without the file name; exit 0 with partial output |

Settled by an instruction sentence, not by a shipped fact (kept out of the table above):

- bare command uses the default folders: default_paths_run_summary_exact, negative_run_writes_outside_output_folder; instruction.md:9 "`--data` defaulting to `/app/data` and `--out` defaulting to `/app/out`", "writes only into the output folder"; rules out: flags required, outputs written into the working directory or a temp folder.
- data folder left as found: judge R16 (r16_changes_data_folder); instruction.md:19 "Leave /app/data as you found it."; rules out: scratch files or fixes written into /app/data.

## Added Harden r3 (board c5b188a)

| rule | test ids | stated fact file:line | wrong readings it contradicts |
|---|---|---|---|
| a derated feeder limit replaces the grid.ini limit, also when it is higher | fresh_u1..u9_{policy_audit,region_*,segment_*,summary}_exact (72) | docs/charging_rules.md:23 rule 11 "`feeder_kwh_per_slot` in `grid.ini` section `[feeder]`, replaced by the derated limit for any slot the disruption notice lists under feeder derating"; :8 rule 2 span; held-out notice line `- from X to Y: feeder limit N kWh per slot` with N > feeder_kwh_per_slot (shipped line format, disruption_notice.md:10) | min(base, listed limit): not stated anywhere (WORK/h3_a1/grep_derate.txt: no sentence of instruction.md, docs/, grid.ini or the notice bounds a listed limit by the base); ignoring the line |

The shipped notice (limit 90 < 1300) does not separate the two readings; the separating case is held-out only (LEVER_RULES 0b W5), and the sentence is the settling evidence, not the shipped data.
