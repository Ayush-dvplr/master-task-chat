# Corpus index

Every file the settlement desk holds for window W-2026Q2 is listed here.
No other file is part of the corpus.

| file | concern |
| --- | --- |
| audit_tally_history.csv | closed window tallies with their exclusion flags |
| business_day_exceptions.csv | zone level declarations that open a weekend date |
| channel_policy.ini | routing of desk calls between the client and the interface |
| corpus_index.md | index of every file held in the settlement corpus |
| counterparty_ack_feed_prior.jsonl | counterparty acknowledgements effective before the window opened |
| counterparty_ack_feed_window.jsonl | counterparty acknowledgements effective from the window opening |
| counterparty_alias_map.csv | alias forms seen in correspondence and their holder keys |
| counterparty_closure_overrides.csv | holder specific closures and special openings |
| counterparty_directory.csv | holder keys, legal names, business zones and status |
| counterparty_receipts.tsv | holder issued receipts quoting raw pledge references |
| countersignature_register.csv | countersignatures recorded against standing orders |
| cycle_findings.csv | closed window findings for mutually dependent pledges |
| dependency_rules.md | how prerequisites bear on a pledge |
| desk_policy.ini | desk defaults for mode, boundary band and home zone |
| desk_transition_log.log | call sequences recorded during earlier settlement sessions |
| discharge_evidence_desk.csv | register evidence lodged through the desk channel |
| discharge_evidence_portal.csv | register evidence lodged through the portal channel |
| duplicate_record_audit.csv | closed window rulings on identical competing records |
| entity_resolution.md | name normalisation and holder key resolution |
| grace_allocation.md | eligibility, ceilings and the shape of a grace round |
| grace_precedent_rounds.csv | closed grace rounds with their granted minutes |
| inbox_handle_registry.csv | thread handles mapped to holder keys |
| inbox_thread_extracts.jsonl | thread extracts carrying due and evidence claims |
| lateness_rounding_cases.csv | closed window lateness figures for given instants |
| legacy_code_crosswalk.tsv | retired holder codes mapped to holder keys |
| mode_selection.md | the layers that settle the governing mode |
| output_contract.md | the exact shape of every artifact the desk files |
| pledge_class_catalog.csv | class facts by effective period |
| pledge_register_2024.csv | register entries with a 2024 origin |
| pledge_register_2025.csv | register entries with a 2025 origin |
| pledge_register_2026.csv | register entries with a 2026 origin |
| precedence_worked_cases.csv | closed window rulings on competing records |
| prereq_edges.tsv | pledge level prerequisite edges by window |
| principal_standing_orders.csv | standing orders issued by the principal |
| provenance_precedence.md | source ranking per field class |
| readiness_examples.csv | closed window readiness outcomes for stated inputs |
| reason_codes.md | the closed set of reason codes |
| recurring_series_definitions.csv | recurring commitment definitions |
| register_amendments_prior.csv | register amendments effective before the window opened |
| register_amendments_window.csv | register amendments effective from the window opening |
| rejected_call_samples.jsonl | refused calls captured in earlier sessions |
| retraction_notices.csv | notices that withdraw a named record |
| series_expansion_log.jsonl | expansion of each series for one closed period |
| series_instance_overrides.csv | period level actions against a series |
| service_probe_log.log | request and response field shapes per endpoint |
| service_protocol.md | the call protocol the settlement interface enforces |
| settlement_charter.md | docket scope, window handling and the settlement bar |
| source_manifest.md | every evidence file with its source and field classes |
| temporal_rules.md | zones, business days, due expressions and minute handling |
| travel_itinerary.csv | legs describing where the principal was located |
| unit_declarations.ini | declared units for every quantity in the corpus |
| voice_memo_transcripts.jsonl | dictated notes retained for reference |
| waiver_grants.csv | waiver grants with the source that issued them |
| window_directives.jsonl | directive revisions issued for each settlement window |
| zone_holiday_calendar.csv | zone holiday observances |
| zone_offset_table.csv | zone offsets by local effective period |

Files whose name ends in md carry rules. Files whose name ends in ini carry
settings. Every other file carries records.
