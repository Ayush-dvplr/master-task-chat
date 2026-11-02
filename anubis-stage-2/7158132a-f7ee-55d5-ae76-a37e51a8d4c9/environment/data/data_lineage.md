# data lineage

Which file feeds which stage, and which file feeds nothing.

| file | stage | role |
| --- | --- | --- |
| mission_register.csv | S01 S06 | mission identity and registered class |
| mission_alias_crosswalk.csv | S01 | presentation identifier to mission |
| ground_segment_register.tsv | S01 S02 | station identity and accounting offset |
| aperture_register.csv | S01 | aperture identity and label resolution |
| aperture_service_windows.csv | S02 | declared operating windows |
| maintenance_dockets.csv | S02 | aperture outage subtraction |
| blackout_advisories.psv | S02 | station outage subtraction |
| station_accounting_calendar.csv | S02 S04 | station local period windows |
| station_local_accounting.ini | S02 | period shape and boundary convention |
| pass_plan_of_record.csv | S03 | the passes to settle |
| campaign_schedule.xml | S03 | mission phase admission |
| cancellation_notices.csv | S03 | cancellation and late cancellation |
| contact_event_journal.ndjson | S03 S04 S06 | event class, actual times, commit evidence |
| operator_roster.tsv | S06 | operator authority grade |
| reference_lookups.sqlite | S01 S03 S06 | scope, priority rank, commit grades |
| settlement_audit_trace.db | S01 S08 | contract identity, validity and carry flag |
| rate_schedule_effective.psv | S05 | effective dated rates |
| aperture_contract_workbook.xlsx | S05 S09 S13 | per contact cap, period budget, credit rates |
| workbook_sheet_selection.json | S05 | which workbook sheet binds |
| network_operations_memo.pdf | S03 S06 S09 S13 | commit lead, pass budget shape, outage floor |
| precedence_directive.docx | S06 | precedence order and the commit exception |
| precedence_override_register.jsonl | S06 | narrow class overrides |
| contract_terms_amendments.tsv | S07 S08 S13 | obligation, entitlement, reserve, carry cap |
| prior_period_settlement.json | S08 | opening carry buckets |
| onboard_backlog_reports.csv | S09 S10 | opening backlog per mission period |
| outage_claims.psv | S13 | outage qualification |
| unit_scaling_rules.json | S05 S09 S13 | scale divisors and damping terms |
| rounding_and_precision.yml | all | the floor at every stage boundary |
| ordering_dependencies.yaml | all | the stage edges including the S08 back edge |
| exception_code_dictionary.xml | S03 S14 | the reject reason slug and the exception report class |
| unit_test_vectors.json | none | self check vectors for the arithmetic |
| sample_worked_records.jsonl | none | scheduled spans only, before clipping |
| legacy_flat_rate_table.csv | S14 only | retired, read for the discrepancy report |

## files that decide nothing

legacy_flat_rate_table.csv is retired and binds no capacity. It exists
because the discrepancy report has to name the apertures whose retired
flat rate sits outside the effective band, and that report is graded.

downlink_reports.csv is a reported figure and never an accepted one. It
is read at S14 for the discrepancy report only.

sample_worked_records.jsonl restates scheduled spans from the pass plan.
It is a convenience for checking that a reader parses the plan and it
carries no clipped, capped or settled value.

unit_test_vectors.json is the arithmetic self check. Every vector is one
documented operation with its exact expected output. A run that
reproduces every vector has the arithmetic right; it says nothing about
whether the stages were ordered right.

The superseded rows inside mission_register.csv, aperture_register.csv,
contract_terms_amendments.tsv and legacy_flat_rate_table.csv are real
history, not padding. They are what makes the binding row a choice.
