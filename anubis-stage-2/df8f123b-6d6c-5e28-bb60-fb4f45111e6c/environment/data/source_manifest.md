# Source manifest

| file | source | field classes |
| --- | --- | --- |
| counterparty_ack_feed_prior.jsonl | counterparty_ack | due_instant |
| counterparty_ack_feed_window.jsonl | counterparty_ack | due_instant |
| counterparty_receipts.tsv | counterparty_ack | discharge_evidence |
| discharge_evidence_desk.csv | register | discharge_evidence |
| discharge_evidence_portal.csv | register | discharge_evidence |
| inbox_thread_extracts.jsonl | inbox_thread | due_instant, discharge_evidence |
| pledge_register_2024.csv | register | due_instant |
| pledge_register_2025.csv | register | due_instant |
| pledge_register_2026.csv | register | due_instant |
| register_amendments_prior.csv | register | due_instant |
| register_amendments_window.csv | register | due_instant |
| voice_memo_transcripts.jsonl | voice_memo | due_instant, waiver |
| waiver_grants.csv | stated in the source column | waiver |

waiver_grants.csv carries grants from more than one source and names the source
on every row.

Reference files carry no field class. counterparty_directory.csv,
counterparty_alias_map.csv, legacy_code_crosswalk.tsv, inbox_handle_registry.csv,
zone_offset_table.csv, zone_holiday_calendar.csv, business_day_exceptions.csv,
counterparty_closure_overrides.csv, pledge_class_catalog.csv,
recurring_series_definitions.csv, series_instance_overrides.csv,
window_directives.jsonl, principal_standing_orders.csv,
countersignature_register.csv, prereq_edges.tsv and retraction_notices.csv are
reference files.

Closed window files record how earlier windows were settled.
audit_tally_history.csv, cycle_findings.csv, duplicate_record_audit.csv,
grace_precedent_rounds.csv, lateness_rounding_cases.csv,
precedence_worked_cases.csv, readiness_examples.csv, rejected_call_samples.jsonl,
series_expansion_log.jsonl, desk_transition_log.log and service_probe_log.log are
closed window files. They describe practice that holds for this window too.

travel_itinerary.csv records where the principal was located. A location never
changes a governing due instant.
