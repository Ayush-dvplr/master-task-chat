# Source manifest

Every file the settlement consumes appears below under its logical source. A file named
here and absent from the export folder makes the export incomplete. An incomplete export
cannot be settled, and the settlement writes no documents for it.

- contract: campaign_contract.md carry_rules.md corpus_index.md data_quality_rules.md entitlement_rules.md errata_notice.md identity_rules.md lot_state_machine.md output_contract.md provenance_rules.md ration_rules.md round_calendar_rules.md substitution_rules.md supply_rules.md temporal_rules.md
- configuration: authority_scopes.json reason_codes.json source_declarations.properties unit_declarations.ini
- field_intake: requisitions_r01_r04.csv requisitions_r05_r08.csv requisitions_r09_r12.csv requisitions_r13_r16.csv requisitions_r17_r20.csv requisitions_r21_r24.csv
- dispatch_stream: dispatch_p1.jsonl dispatch_p2.jsonl dispatch_p3.jsonl dispatch_p4.jsonl
- registry: registry_q1.tsv registry_q2.tsv registry_q3.tsv registry_q4.tsv
- visit_events: visit_events_p1.jsonl visit_events_p2.jsonl visit_events_p3.jsonl
- amendments: amendment_notices_p1.jsonl amendment_notices_p2.jsonl amendment_notices_p3.jsonl
- lot_register: lot_register_p1.csv lot_register_p2.csv lot_register_p3.csv
- release_certificates: release_certificates_h1.csv release_certificates_h2.csv
- assay: potency_assays_h1.txt
- ceilings: block_ceilings_h1.csv block_ceilings_h2.csv
- reference: block_alias_map.csv block_master.csv calendar_exceptions.csv campaign_phases.csv depot_clock_offsets.csv dose_factors.csv potency_factors.csv priority_register.csv substitution_graph.csv
- observations: clearance_observations.log governance_observations.log
- legacy: legacy_runbook.md
