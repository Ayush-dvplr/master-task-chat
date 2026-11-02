# Data lineage

Every paper in this directory, the stage it feeds and what it
settles.

| paper | stage | what it settles |
| --- | --- | --- |
| substation_topology.xml | p01 | the operating day and its reference, the feeders in force and their plugs |
| feeder_capacity_register.csv | p01 p05 p06 | the nominal capacity and the standing reserve of every feeder |
| plug_assignment_register.csv | p01 | the feeder and the zone of every plug |
| reefer_service_register.csv | p01 | the reefers presented for the operating day |
| energy_declaration_returns.psv | p01 | the declared energy of a reefer |
| unit_register_dictionary.toml | p01 | the conversion of every quoted unit into its base unit |
| vessel_call_register.csv | p01 p04 | the applicable call of every vessel |
| withdrawn_call_journal.tsv | p01 | the call revisions the berth office withdrew |
| interval_grid_calendar.csv | p02 p08 p10 | the ninety six intervals and the tariff band of each |
| maintenance_window_register.csv | p02 p07 p08 | the booked windows that take a resource out |
| ambient_condition_returns.json | p03 | the ambient class of every interval and the multiplier table |
| plug_zone_admission_matrix.csv | p04 | the temperature classes a plug zone admits |
| dispatch_admission_ladder.txt | p04 | the rungs and the order they are read in |
| exception_notices.jsonl | p04 p11 | the zone waivers and the priority overrides |
| priority_ordering_directive.docx | p04 | the ordering keys and the class ranks |
| feeder_derating_notices.csv | p05 | the derating that applies to a feeder over a span |
| crane_duty_feed.ndjson | p07 | the crane duty demand of every interval |
| crane_confirmation_journal.jsonl | p07 | whether a crane duty landed or was called off |
| battery_operating_policy.toml | p08 | the battery capacity, reserve, limits and efficiencies |
| battery_telemetry_returns.csv | p08 | the intervals the battery was online for |
| substation_capacity_workbook.xlsx | p03 p09 p10 | the damping fraction, the maintenance coefficients, the base service charge, the vessel share ceilings and the substation ceilings |
| dispatch_operations_memo.pdf | p09 p11 p13 | the pass budget, the minimum step, the protection depth and the surcharge ladder |
| reconciliation_pass_policy.toml | p06 p09 | the scope of the spill and of the redistribution |
| priority_precedence_policy.toml | p04 p11 | the precedence hierarchy and the absent call sentinel |
| revision_precedence.toml | every stage | how a register row is set aside and which sequence field settles it |
| tariff_interval_schedule.csv | p10 | the price of every interval |
| demand_charge_bands.tsv | p10 | the demand charge band of a substation peak |
| source_priority_register.csv | p04 | the priority rank of a source system |
| reporting_feeder_roster.conf | p14 | the substations whose report is published |
| rounding_and_arithmetic_policy.yaml | every stage | where each stage rounds and by which rule |
| boundary_conventions.yaml | every stage | the inclusive and exclusive boundaries |
| publication_form_rules.toml | p14 | the written form of every published quantity |
| output_schema_reference.md | p14 | the header, the column order and the row order of every document |
| serialisation_and_digest_contract.md | p14 | the encoding, the line endings and the two digests |
| reeferdispatch_program_contract.md | p14 | the contract the delivered program answers |
| worked_examples.md | p14 | the form of the free text documents |
| glossary_and_field_dictionary.md | reference | the field names and what they mean |
| known_traps_and_footguns.md | reference | the readings that have gone wrong before |
| corpus_sentinel_note.txt | reference | the branches this operating day leaves unreached |

## Papers that govern nothing

Three papers are retained for the audit file and settle no published
quantity on this operating day.

reefer_thermal_supplement.csv carries probe set points. No stage
reads a set point.

legacy_tariff_extract.csv carries a retired price extract. The price
of an interval is settled by tariff_interval_schedule.csv alone.

night_office_audit.db carries desk entries against earlier operating
days. No stage reads it.
