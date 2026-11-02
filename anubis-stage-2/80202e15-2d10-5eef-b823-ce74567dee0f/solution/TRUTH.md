# TRUTH.md - 80202e15-2d10-5eef-b823-ce74567dee0f

Corvid Cloud Platform's monthly SLA service-credit close: one hundred heterogeneous exports reduce to one exact record per in-scope subscription plus rollups, reproducible on the next month with carried quarter state.

## Defect

1. (focal) C1 Multi-collector ingestion: Six collectors overlap; per subscription and window the highest-precedence valid record wins, highest seq within a collector; replayed batches, voids (with RESTORE), tombstones, quarantined or misrouted hosts and placeholder rows are invalid.
2. (focal) C2 Time normalization: Local ISO with offsets, epoch seconds and milliseconds, Excel 1900 serials (UTC) and 1904 serials (local), host-clock readings corrected by the measured skew in force, SDK device clocks replaced by server receipts, EU DST computed from the documented rule.
3. (drift) C3 Ordered schema rollout: LB schema v1 counts 429 inside err_5xx; the version per host at each window is the highest-seq rollout or rollback event with ts <= window over the latest manifest revision of its wave, ignoring aborted rollouts; LB sampling multiplies counts.
4. (focal) C4 Eligibility: Active days, suspensions (log state machine plus active orders), approved planned maintenance after ics overrides and cancellations with notice at least five site business days ahead; exclusions with a fixed precedence.
5. (drift) C5 Dependency attribution: A downstream bad window is attributed, not counted, when the same account owns an active upstream subscription in the region, the link is active at the window and a final incident on the upstream product covers it after updates.
6. (focal) C6 Entity resolution: Account aliases then charter decisions in date order with chains, plan at month end with reverts and legacy codes, region aliases, regrouping effective mid-month, enrollment class and segment.
7. (drift) C7 Credit computation: SLA version by pin or contract signature cutover, custom enterprise schedules unless revoked, tier selection, list price with platform-wide discount or approved override, proration, half-even minor units, claims within ten site business days, auto-credit, hourly FX, quarter caps applied in subscription order with ledger, goodwill and --prior carry.
8. (drift) C8 Controls and HELD gate: Per file, 100-record blocks with control sums of the first field's digits must match the highest-revision register row (companions in two decoys); any missing or mismatched file holds the whole close. The per-source reconciliation is graded by concept_controls and the hidden-month state test, and a hidden-month copy with one failing block must come out HELD.
9. (focal) All 100 data_quality.sources entries must be exact (records, control blocks, control result per file); concept_controls and the hidden-month state test grade them.
10. (focal) Charter-designated sections of the fifteen draft, preliminary, snapshot, mirror, unofficial and proposed files are authoritative; the rest is bait.
11. (trap) T1 near-duplicate identifier spellings (case, separators, prefix forms) must canonicalize.
12. (trap) T2 unit variants: 'k' suffixes, thousands-scaled service counts, major-unit money with currency suffix.
13. (trap) T3 the same instant appears as offsets, epoch seconds, milliseconds and serials.
14. (trap) T4 locale numerics: NBSP, thin space and apostrophe grouping, decimal commas.
15. (trap) T5 placeholder twins (-1, N/A) with higher versions must never supersede.
16. (trap) T6 voided, withdrawn, rescinded, retracted and lifted records.
17. (trap) T7 superseded revisions and older-effective twins.
18. (trap) T8 re-emitted CSV headers in a new order, camelCase keys, a mid-file fixed-width layout switch.
19. (trap) T9 embedded delimiters, quotes, newlines and CDATA.
20. (trap) T10 BOMs, zero-width characters, Latin-1 lines and escaped first characters.
21. (trap) T11 records one window before the period, effective exactly at period end or the day after.
22. (trap) T12 half-even ties in money conversion.
23. (trap) T13 homoglyph identifiers that digit extraction would wrongly join.
24. (trap) T14 misrouted hosts whose reported lane hides the documented lane.
25. (trap) T15 three agreeing stale copies outvote the authoritative record.
26. (trap) T16 records invalidated only by decoy evidence and decoy bait that looks authoritative.

Entities, contracts and quotas are shared between the visible August 2026 close and the hidden September 2026 close; telemetry, probes, incidents, maintenance, claims and rates differ per period. Every trap sits on a row that feeds a graded record, and under the documented rules it changes nothing: a reader that follows the conventions recovers the same facts.

Out of bounds: network access, modifying /app/data, reading paths other than the given directories, and copying any value observed in this month's files into the transform.

## Load-bearing work

| Concept | Kind | Summary |
|---|---|---|
| C1 Multi-collector ingestion | focal | Six collectors overlap; per subscription and window the highest-precedence valid record wins, highest seq within a collector; replayed batches, voids (with RESTORE), tombstones, quarantined or misrouted hosts and placeholder rows are invalid. |
| C2 Time normalization | focal | Local ISO with offsets, epoch seconds and milliseconds, Excel 1900 serials (UTC) and 1904 serials (local), host-clock readings corrected by the measured skew in force, SDK device clocks replaced by server receipts, EU DST computed from the documented rule. |
| C3 Ordered schema rollout | drift | LB schema v1 counts 429 inside err_5xx; the version per host at each window is the highest-seq rollout or rollback event with ts <= window over the latest manifest revision of its wave, ignoring aborted rollouts; LB sampling multiplies counts. |
| C4 Eligibility | focal | Active days, suspensions (log state machine plus active orders), approved planned maintenance after ics overrides and cancellations with notice at least five site business days ahead; exclusions with a fixed precedence. |
| C5 Dependency attribution | drift | A downstream bad window is attributed, not counted, when the same account owns an active upstream subscription in the region, the link is active at the window and a final incident on the upstream product covers it after updates. |
| C6 Entity resolution | focal | Account aliases then charter decisions in date order with chains, plan at month end with reverts and legacy codes, region aliases, regrouping effective mid-month, enrollment class and segment. |
| C7 Credit computation | drift | SLA version by pin or contract signature cutover, custom enterprise schedules unless revoked, tier selection, list price with platform-wide discount or approved override, proration, half-even minor units, claims within ten site business days, auto-credit, hourly FX, quarter caps applied in subscription order with ledger, goodwill and --prior carry. |
| C8 Controls and HELD gate | drift | Per file, 100-record blocks with control sums of the first field's digits must match the highest-revision register row (companions in two decoys); any missing or mismatched file holds the whole close. The per-source reconciliation is graded by concept_controls and the hidden-month state test, and a hidden-month copy with one failing block must come out HELD. |

Inventory: 100 files, 19 extensions {".csv": 14, ".docx": 7, ".html": 3, ".ics": 1, ".ini": 3, ".json": 6, ".jsonl": 8, ".log": 5, ".mbox": 1, ".md": 3, ".parquet": 6, ".pdf": 7, ".sqlite": 4, ".toml": 3, ".tsv": 8, ".txt": 3, ".xlsx": 8, ".xml": 6, ".yaml": 4}, 685728 records (814712 physical lines); smallest file enterprise_sla_schedules.pdf with 5006 records. 85 in-scope files and 15 decoys.

| # | File | Records | Traps | Decoy | Unique contribution | Depends on | Dependents |
|---|---|---|---|---|---|---|---|
| 1 | account_aliases.tsv | 5207 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 2 | account_caps.xlsx | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 3 | account_snapshot_legacy.sqlite | 9630 | 65 | D07 | c: ban column is the only BAN to account crosswalk for back-office claims | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 4 | accounts_master.csv | 9601 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 5 | audit_control_register.pdf | 6774 | 14 |  | records consumed by the rules of its catalog role | 99 files | 99 files |
| 6 | cdn_attestations.xlsx | 10017 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 7 | cdn_logs_akamoto.xml | 5309 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 8 | cdn_logs_fastedge.xml | 6095 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 9 | change_calendar.ics | 6739 | 14 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 10 | claims_backoffice.xlsx | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 11 | claims_crm_legacy.csv | 5320 | 36 | D14 | c: case to subscription crosswalk for support tickets | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 12 | claims_portal.csv | 6203 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 13 | claims_workflow.log | 9860 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 14 | client_sdk_dedup.jsonl | 10721 | 72 | D03 | c: INSTALL rows are the only install to subscription crosswalk | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 15 | collector_schema_proposed.yaml | 6459 | 44 | D11 | e: edge_layout_v7 is the only definition of the V7 fixed-width layout | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 16 | contracts_register.xlsx | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 17 | credit_ledger.sqlite | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 18 | credit_operations_manual.docx | 9600 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 19 | credit_preferences.json | 9600 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 20 | credit_tiers_2026.xlsx | 15838 | 106 | D05 | e: Ratified sheet carries the only v5 targets | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 21 | dependency_links.tsv | 5307 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 22 | deploy_events.log | 5602 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 23 | deploy_manifests.xml | 6127 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 24 | edge_legacy_a.txt | 5311 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 25 | edge_legacy_b.txt | 5311 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 26 | edge_legacy_c.txt | 5311 | 11 |  | records consumed by the rules of its catalog role | 7 files | audit_control_register.pdf, source_register.md |
| 27 | enterprise_sla_schedules.pdf | 5006 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 28 | fee_overrides.xlsx | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 29 | fx_hourly_treasury.csv | 9617 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 30 | fx_rates_unofficial.json | 11867 | 80 | D08 | e: TRY and KWD rates exist only here | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 31 | governance_charter.docx | 5019 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | 17 files |
| 32 | host_clock_edge_a.ini | 5208 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 33 | host_clock_edge_b.ini | 5292 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 34 | host_clock_edge_c.ini | 5208 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 35 | host_inventory.csv | 6400 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | 20 files |
| 36 | incident_attribution_policy.docx | 5151 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 37 | incident_register.xml | 6356 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 38 | incident_register_preliminary.xml | 6009 | 41 | D06 | c: Preliminary id to final id crosswalk resolves incident updates | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 39 | ingest_batches.jsonl | 7921 | 16 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | 20 files |
| 40 | ingest_reprocess.log | 5373 | 36 | D13 | a: CONTROL lines are the only control blocks for edge_legacy_c.txt | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, edge_legacy_c.txt, source_register.md |
| 41 | lb_errors_central.csv | 9164 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 42 | lb_errors_east.csv | 9161 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 43 | lb_errors_east_replay.csv | 5305 | 36 | D01 | b: VOID markers are the only void evidence for east LB records | 7 files | audit_control_register.pdf, source_register.md |
| 44 | lb_errors_north.csv | 9162 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 45 | lb_errors_south.csv | 9163 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 46 | lb_errors_west.csv | 9168 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 47 | lb_sampling.parquet | 5309 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 48 | lifecycle_events.log | 5602 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 49 | maintenance_changes.xlsx | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 50 | maintenance_notices.mbox | 5293 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 51 | maintenance_policy.docx | 5840 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 52 | noc_outage_declarations.pdf | 5253 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 53 | plan_changes_central.tsv | 6128 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 54 | plan_changes_east.json | 6416 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 55 | plan_changes_north.xml | 5896 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 56 | plan_changes_south.yaml | 5712 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 57 | plan_changes_west.log | 5463 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 58 | price_book.toml | 5638 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, region_groups_2025.toml, source_register.md | audit_control_register.pdf, source_register.md |
| 59 | probe_results_mirror.tsv | 5432 | 37 | D12 | c: VANTAGE rows are the only vantage code to vantage id crosswalk | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 60 | probe_targets.json | 6401 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 61 | probes_compute.tsv | 5603 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 62 | probes_core.tsv | 5603 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 63 | probes_data.tsv | 5603 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 64 | quota_changes.tsv | 5402 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 65 | quotas_central.yaml | 5624 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 66 | quotas_east.toml | 5924 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 67 | quotas_north.sqlite | 5321 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 68 | quotas_south.md | 5221 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 69 | quotas_west.html | 5017 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 70 | region_groups_2025.toml | 6529 | 43 | D15 | c: region_alias and region_site are the only region alias and calendar site crosswalks | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, price_book.toml, source_register.md |
| 71 | schema_registry.yaml | 6402 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 72 | sdk_builds.json | 5200 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 73 | sdk_events_1.jsonl | 9159 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 74 | sdk_events_2.jsonl | 9161 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 75 | sdk_events_3.jsonl | 9162 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 76 | sdk_server_receipts.csv | 5200 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 77 | sla_enrollment_central.md | 5776 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 78 | sla_enrollment_east.html | 6079 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 79 | sla_enrollment_north.pdf | 5483 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 80 | sla_enrollment_south.pdf | 5376 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 81 | sla_enrollment_west.csv | 5125 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 82 | sla_policy_2026.docx | 5236 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 83 | sla_policy_v4_draft.docx | 5048 | 34 | D04 | e: the Legacy schedule v2 targets, tiers and thresholds remain in force | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 84 | sla_report_draft.pdf | 13252 | 89 | D10 | b: Voided July postings is the only voiding of ledger postings | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 85 | source_register.md | 5331 | 11 |  | records consumed by the rules of its catalog role | 99 files | 99 files |
| 86 | subscriptions_central.csv | 5603 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 87 | subscriptions_east.parquet | 5906 | 12 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 88 | subscriptions_north.sqlite | 5304 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 89 | subscriptions_south.jsonl | 5202 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 90 | subscriptions_west.xlsx | 10000 | 20 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 91 | support_tickets.jsonl | 6002 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 92 | suspension_orders.pdf | 5208 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 93 | svc_metrics_compacted.parquet | 5406 | 37 | D02 | b: TOMBSTONE rows are the only invalidation of service records | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |
| 94 | svc_metrics_part1.parquet | 9162 | 19 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 95 | svc_metrics_part2.parquet | 6879 | 14 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 96 | svc_metrics_part3.parquet | 5309 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, host_inventory.csv, ingest_batches.jsonl, source_register.md, telemetry_collection_standard.docx, telemetry_voids.jsonl | audit_control_register.pdf, source_register.md |
| 97 | telemetry_collection_standard.docx | 6443 | 13 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | 20 files |
| 98 | telemetry_quarantine.json | 5209 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | audit_control_register.pdf, source_register.md |
| 99 | telemetry_voids.jsonl | 5201 | 11 |  | records consumed by the rules of its catalog role | audit_control_register.pdf, source_register.md | 20 files |
| 100 | uptime_dashboard_snapshot.html | 6182 | 42 | D09 | c: Retired probe targets is the only crosswalk for retired target ids | audit_control_register.pdf, governance_charter.docx, source_register.md | audit_control_register.pdf, source_register.md |

Decoys (each load-bearing two ways; ignoring or trusting any one fails at least one HARD test):

| Id | File | Looks like | Role 1 | Role 2 | Bait | Records in slice (changed when its designated content is ignored, plus bait targets) | Test |
|---|---|---|---|---|---|---|---|
| D01 | lb_errors_east_replay.csv | replay copy of the east LB feed | b: VOID markers are the only void evidence for east LB records | e: GAPFILL rows are the only LB telemetry for ist1 inside the declared collector gap | REPLAY rows | 107 | decoy_d01_lb_errors_east_replay |
| D02 | svc_metrics_compacted.parquet | compacted service-metric aggregates | b: TOMBSTONE rows are the only invalidation of service records | c: ALIAS rows are the only svc-node to host crosswalk | AGG rows | 5215 | decoy_d02_svc_metrics_compacted |
| D03 | client_sdk_dedup.jsonl | deduplicated SDK event feed | c: INSTALL rows are the only install to subscription crosswalk | d: WITHDRAWN_BUILD rows declare builds out of scope (charter confirms) | EVENT rows | 7402 | decoy_d03_client_sdk_dedup |
| D04 | sla_policy_v4_draft.docx | superseded v4 draft policy | e: the Legacy schedule v2 targets, tiers and thresholds remain in force | c: Legacy plan codes is the only legacy plan crosswalk | draft v4 tiers and draft pins | 8687 | decoy_d04_sla_policy_v4_draft |
| D05 | credit_tiers_2026.xlsx | 2026 credit tier workbook | e: Ratified sheet carries the only v5 targets | b: RATIFIED revocations are the only evidence that enterprise schedules were withdrawn | Draft sheet | 5104 | decoy_d05_credit_tiers_2026 |
| D06 | incident_register_preliminary.xml | preliminary incident register | c: Preliminary id to final id crosswalk resolves incident updates | b: Retraction elements are the only retractions of NOC declarations | preliminary incident times | 360 | decoy_d06_incident_register_preliminary |
| D07 | account_snapshot_legacy.sqlite | legacy account snapshot | c: ban column is the only BAN to account crosswalk for back-office claims | d: internal_flag declares internal accounts out of scope (charter confirms) | stale segment and currency columns | 2414 | decoy_d07_account_snapshot_legacy |
| D08 | fx_rates_unofficial.json | unofficial hourly rates | e: TRY and KWD rates exist only here | b: recalls are the only evidence that treasury fixings were withdrawn | rates for treasury currencies | 1031 | decoy_d08_fx_rates_unofficial |
| D09 | uptime_dashboard_snapshot.html | dashboard uptime snapshot | c: Retired probe targets is the only crosswalk for retired target ids | d: Beta product-regions declares beta scope (SLA policy confirms no SLA) | Daily uptime table | 13661 | decoy_d09_uptime_dashboard_snapshot |
| D10 | sla_report_draft.pdf | unapproved draft SLA report | b: Voided July postings is the only voiding of ledger postings | c: Claim references is the only CR- to claim crosswalk for withdrawals | draft subscription results | 1608 | decoy_d10_sla_report_draft |
| D11 | collector_schema_proposed.yaml | proposed collector schema | e: edge_layout_v7 is the only definition of the V7 fixed-width layout | b: aborted_rollouts are the only evidence that rollout events never took effect | proposed per-host schema | 34 | decoy_d11_collector_schema_proposed |
| D12 | probe_results_mirror.tsv | probe results mirror | c: VANTAGE rows are the only vantage code to vantage id crosswalk | b: FLAPVOID rows are the only invalidation of flapping probe results | MIRROR rows | 17359 | decoy_d12_probe_results_mirror |
| D13 | ingest_reprocess.log | ingest reprocessing log | a: CONTROL lines are the only control blocks for edge_legacy_c.txt | b: REPLAY lines are the only evidence that some loaded batches were replays | REPROCESSED lines | 552 | decoy_d13_ingest_reprocess |
| D14 | claims_crm_legacy.csv | legacy CRM case export | c: case to subscription crosswalk for support tickets | e: SMB cases filed before the CRM cutover are claims and exist only here | post-cutover and stale cases | 2498 | decoy_d14_claims_crm_legacy |
| D15 | region_groups_2025.toml | 2025 region grouping | c: region_alias and region_site are the only region alias and calendar site crosswalks | a: control rows are the only control blocks for price_book.toml | host_group assignments | 12237 | decoy_d15_region_groups_2025 |

Traps: 1974 total (1176 in-scope, 798 in decoys); in-scope per file 11-20, decoys at least 34; one per 500-record band. Families by file count: {"T1": 83, "T10": 67, "T11": 46, "T12": 9, "T13": 74, "T14": 12, "T15": 37, "T16": 32, "T2": 24, "T3": 82, "T4": 35, "T5": 29, "T6": 38, "T7": 51, "T8": 35, "T9": 24}. Decoy pull/push directions: {"account_snapshot_legacy.sqlite": {"pull": 11, "push": 54}, "claims_crm_legacy.csv": {"pull": 5, "push": 31}, "client_sdk_dedup.jsonl": {"pull": 13, "push": 59}, "collector_schema_proposed.yaml": {"pull": 43, "push": 1}, "credit_tiers_2026.xlsx": {"pull": 36, "push": 70}, "fx_rates_unofficial.json": {"pull": 19, "push": 61}, "incident_register_preliminary.xml": {"pull": 5, "push": 36}, "ingest_reprocess.log": {"pull": 35, "push": 1}, "lb_errors_east_replay.csv": {"pull": 34, "push": 2}, "probe_results_mirror.tsv": {"pull": 35, "push": 2}, "region_groups_2025.toml": {"pull": 43}, "sla_policy_v4_draft.docx": {"pull": 34}, "sla_report_draft.pdf": {"pull": 35, "push": 54}, "svc_metrics_compacted.parquet": {"pull": 28, "push": 9}, "uptime_dashboard_snapshot.html": {"pull": 39, "push": 3}}.

Coverage matrix (traps per file and family):

| File | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 |
|---|---|---|---|---|---|---|---|
| account_aliases.tsv | 1 | 0 | 2 | 0 | 0 | 0 | 1 | 2 | 0 | 1 | 1 | 0 | 2 | 0 | 1 | 0 |
| account_caps.xlsx | 4 | 5 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 5 | 0 | 0 | 0 | 0 |
| account_snapshot_legacy.sqlite | 6 | 0 | 0 | 0 | 0 | 11 | 10 | 0 | 11 | 7 | 0 | 0 | 9 | 0 | 0 | 11 |
| accounts_master.csv | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 10 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| audit_control_register.pdf | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 0 |
| cdn_attestations.xlsx | 1 | 1 | 1 | 3 | 3 | 1 | 1 | 0 | 0 | 1 | 2 | 0 | 1 | 2 | 2 | 1 |
| cdn_logs_akamoto.xml | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 1 | 1 |
| cdn_logs_fastedge.xml | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 |
| change_calendar.ics | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 10 | 0 |
| claims_backoffice.xlsx | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| claims_crm_legacy.csv | 1 | 0 | 1 | 0 | 0 | 7 | 4 | 8 | 5 | 1 | 0 | 0 | 4 | 0 | 0 | 5 |
| claims_portal.csv | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 4 | 2 | 0 | 0 | 3 | 0 | 0 | 0 |
| claims_workflow.log | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 4 | 0 | 0 | 4 | 0 | 0 | 0 |
| client_sdk_dedup.jsonl | 1 | 0 | 0 | 0 | 0 | 12 | 13 | 27 | 0 | 5 | 0 | 0 | 1 | 0 | 0 | 13 |
| collector_schema_proposed.yaml | 1 | 0 | 1 | 0 | 0 | 14 | 13 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 13 |
| contracts_register.xlsx | 6 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| credit_ledger.sqlite | 1 | 7 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 10 | 0 | 0 | 0 | 0 |
| credit_operations_manual.docx | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| credit_preferences.json | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| credit_tiers_2026.xlsx | 1 | 0 | 8 | 18 | 19 | 4 | 3 | 0 | 0 | 9 | 19 | 0 | 16 | 0 | 8 | 1 |
| dependency_links.tsv | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 6 | 0 | 1 | 0 | 0 | 0 |
| deploy_events.log | 1 | 0 | 1 | 7 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| deploy_manifests.xml | 1 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 5 | 0 |
| edge_legacy_a.txt | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 3 |
| edge_legacy_b.txt | 1 | 0 | 0 | 0 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 3 |
| edge_legacy_c.txt | 1 | 0 | 0 | 0 | 2 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 2 |
| enterprise_sla_schedules.pdf | 1 | 0 | 1 | 3 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| fee_overrides.xlsx | 1 | 12 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 5 | 0 | 0 | 0 | 0 |
| fx_hourly_treasury.csv | 0 | 0 | 1 | 3 | 4 | 0 | 6 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 |
| fx_rates_unofficial.json | 1 | 0 | 3 | 15 | 14 | 2 | 10 | 12 | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 19 |
| governance_charter.docx | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 5 | 0 | 1 | 0 | 1 | 0 |
| host_clock_edge_a.ini | 1 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| host_clock_edge_b.ini | 4 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| host_clock_edge_c.ini | 5 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| host_inventory.csv | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 10 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| incident_attribution_policy.docx | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 7 | 0 | 1 | 0 | 0 | 0 |
| incident_register.xml | 1 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 3 | 0 | 0 | 0 |
| incident_register_preliminary.xml | 1 | 0 | 1 | 0 | 0 | 27 | 4 | 0 | 0 | 1 | 0 | 0 | 2 | 0 | 0 | 5 |
| ingest_batches.jsonl | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| ingest_reprocess.log | 1 | 0 | 1 | 0 | 0 | 6 | 6 | 0 | 0 | 15 | 0 | 0 | 1 | 0 | 0 | 6 |
| lb_errors_central.csv | 1 | 4 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 2 | 1 |
| lb_errors_east.csv | 1 | 4 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 2 | 1 | 1 |
| lb_errors_east_replay.csv | 1 | 17 | 1 | 1 | 1 | 1 | 1 | 1 | 9 | 1 | 0 | 0 | 1 | 0 | 0 | 1 |
| lb_errors_north.csv | 1 | 5 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 2 | 1 |
| lb_errors_south.csv | 1 | 4 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 2 | 1 |
| lb_errors_west.csv | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 3 | 3 | 1 |
| lb_sampling.parquet | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 |
| lifecycle_events.log | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 7 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| maintenance_changes.xlsx | 1 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| maintenance_notices.mbox | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 9 | 0 | 0 | 0 |
| maintenance_policy.docx | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| noc_outage_declarations.pdf | 1 | 0 | 1 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 6 | 0 | 1 | 0 | 0 | 0 |
| plan_changes_central.tsv | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 8 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| plan_changes_east.json | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 4 | 0 | 1 | 5 | 0 | 1 | 0 | 0 | 0 |
| plan_changes_north.xml | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 7 | 0 | 1 | 0 | 0 | 0 |
| plan_changes_south.yaml | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 4 | 0 | 3 | 0 | 0 | 0 |
| plan_changes_west.log | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 3 | 0 | 0 | 0 |
| price_book.toml | 0 | 4 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 3 | 0 | 0 | 1 | 0 |
| probe_results_mirror.tsv | 1 | 0 | 1 | 0 | 0 | 6 | 12 | 2 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 13 |
| probe_targets.json | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| probes_compute.tsv | 1 | 0 | 1 | 5 | 0 | 1 | 0 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| probes_core.tsv | 1 | 0 | 1 | 5 | 0 | 1 | 0 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| probes_data.tsv | 1 | 0 | 1 | 5 | 0 | 1 | 0 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| quota_changes.tsv | 1 | 0 | 1 | 4 | 0 | 0 | 0 | 2 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| quotas_central.yaml | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 7 | 0 |
| quotas_east.toml | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 7 | 0 |
| quotas_north.sqlite | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 6 | 0 |
| quotas_south.md | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 6 | 0 |
| quotas_west.html | 0 | 0 | 1 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 4 | 0 |
| region_groups_2025.toml | 2 | 0 | 1 | 0 | 0 | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 12 |
| schema_registry.yaml | 0 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| sdk_builds.json | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| sdk_events_1.jsonl | 1 | 7 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 1 |
| sdk_events_2.jsonl | 1 | 5 | 1 | 1 | 3 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 1 |
| sdk_events_3.jsonl | 1 | 4 | 1 | 1 | 4 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 1 |
| sdk_server_receipts.csv | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 5 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| sla_enrollment_central.md | 1 | 0 | 1 | 0 | 0 | 0 | 4 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 3 | 0 |
| sla_enrollment_east.html | 1 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 3 | 1 | 0 | 1 | 0 | 3 | 0 |
| sla_enrollment_north.pdf | 1 | 0 | 1 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 4 | 0 |
| sla_enrollment_south.pdf | 1 | 0 | 1 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 3 | 0 |
| sla_enrollment_west.csv | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 5 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 0 |
| sla_policy_2026.docx | 1 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 1 | 0 | 1 | 0 | 3 | 0 |
| sla_policy_v4_draft.docx | 1 | 0 | 1 | 1 | 0 | 13 | 1 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 15 |
| sla_report_draft.pdf | 21 | 0 | 0 | 5 | 24 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 32 | 0 | 0 | 2 |
| source_register.md | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 8 | 0 | 0 | 1 | 0 | 0 | 0 |
| subscriptions_central.csv | 1 | 2 | 1 | 0 | 2 | 0 | 0 | 2 | 0 | 1 | 0 | 2 | 1 | 0 | 0 | 0 |
| subscriptions_east.parquet | 1 | 2 | 1 | 0 | 5 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| subscriptions_north.sqlite | 1 | 2 | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 2 | 1 | 0 | 0 | 0 |
| subscriptions_south.jsonl | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 3 | 0 | 1 | 0 | 2 | 1 | 0 | 0 | 0 |
| subscriptions_west.xlsx | 1 | 3 | 1 | 7 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 2 | 0 | 0 | 0 | 0 |
| support_tickets.jsonl | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 7 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| suspension_orders.pdf | 2 | 0 | 1 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| svc_metrics_compacted.parquet | 1 | 0 | 1 | 23 | 0 | 1 | 2 | 0 | 0 | 6 | 0 | 0 | 1 | 0 | 0 | 2 |
| svc_metrics_part1.parquet | 1 | 6 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 2 | 1 | 1 |
| svc_metrics_part2.parquet | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 1 | 1 | 1 |
| svc_metrics_part3.parquet | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | 1 |
| telemetry_collection_standard.docx | 1 | 0 | 1 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 6 | 0 |
| telemetry_quarantine.json | 1 | 0 | 1 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| telemetry_voids.jsonl | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 7 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| uptime_dashboard_snapshot.html | 1 | 0 | 1 | 10 | 6 | 1 | 2 | 0 | 0 | 4 | 0 | 0 | 1 | 0 | 0 | 16 |

Trap loops (Entry / Reinforcement / Tell / Exit / Graded impact; flags c chained, b best-practice entered, d decoy anchored, s survives sample checking):

| Loop | Entry | Reinforcement | Tell | Exit | Graded impact | Flags |
|---|---|---|---|---|---|---|
| L01 | lb_errors_east_replay.csv REPLAY rows look like extra LB records | same columns and seq as lb_errors_east.csv | marker column; charter designates only VOID and GAPFILL | drop REPLAY, apply VOID, admit GAPFILL inside the gap | records in the slice and concept tests | d |
| L02 | east LB records voided only by markers | telemetry_voids.jsonl is the obvious void registry | VOID markers target record ids absent from the registry | union of registry and D01 VOID markers | records in the slice and concept tests | dc |
| L03 | ist1 gap windows look empty | lb_errors_east.csv has no ist1 rows in the gap | Collector gap windows table | GAPFILL rows count only inside the gap | records in the slice and concept tests | ds |
| L04 | svc node names do not match host_inventory | host ids look unrelated | ALIAS rows in the compacted parquet | map node to host via D02 | records in the slice and concept tests | dc |
| L05 | TOMBSTONE rows inside a compacted file | compacted aggregates look like a summary to ignore | charter designates TOMBSTONE | invalidate tombstoned records | records in the slice and concept tests | d |
| L06 | SDK install ids cannot be joined | events carry no subscription | INSTALL rows in the dedup feed | join via D03 INSTALL | records in the slice and concept tests | dc |
| L07 | withdrawn builds look GA in sdk_builds.json | status GA | WITHDRAWN_BUILD rows, charter confirms | drop their events | records in the slice and concept tests | dc |
| L08 | device-clock SDK timestamps | ISO Z looks authoritative | sdk_builds clock DEVICE | use sdk_server_receipts received_at | records in the slice and concept tests | c |
| L09 | v4 draft tiers look newer than the 2026 policy | draft is newer and complete | charter designates only the legacy v2 sections | use policy v3-v5, D04 v2 tables | records in the slice and concept tests | bd |
| L10 | legacy plan codes on subscriptions | codes look like unknown plans | Legacy plan codes table | map then segment | records in the slice and concept tests | dc |
| L11 | Draft sheet of credit tiers | same shape as Ratified, earlier sheet | sheet name and charter | v5 targets from Ratified latest effective <= period end | records in the slice and concept tests | bd |
| L12 | enterprise schedules look in force | schedule effective dates | RATIFIED revocations | revoked schedules fall back to versions | records in the slice and concept tests | dc |
| L13 | PRE- ids in incident updates | they look like orphans | Preliminary final_id | resolve then apply updates in (at, id) order | records in the slice and concept tests | dc |
| L14 | CONFIRMED NOC declarations | status CONFIRMED | Retraction elements | retracted declarations add no outage | records in the slice and concept tests | d |
| L15 | BAN on back-office receipts | BAN looks like an account id | ban column in snapshot | receipt valid only if BAN account equals subscription account | records in the slice and concept tests | dc |
| L16 | internal accounts look ordinary | accounts_master shows ACTIVE | internal_flag, charter confirms | INTERNAL_ACCOUNT exclusion | records in the slice and concept tests | d |
| L17 | unofficial rates cover every currency | hourly and complete | treasury is authoritative where it publishes | D08 only for TRY and KWD | records in the slice and concept tests | bd |
| L18 | treasury fixing with a recall | highest revision wins | recall entry | recalled fixing falls back to the previous available hour | records in the slice and concept tests | dc |
| L19 | retired probe targets look unknown | probe rows referencing TGT-7xxxx | Retired probe targets | map to current target | records in the slice and concept tests | dc |
| L20 | beta product-regions look covered | subscriptions enrolled | Beta product-regions, SLA policy confirms | BETA_PRODUCT_REGION exclusion | records in the slice and concept tests | d |
| L21 | Draft SLA report uptime per subscription | numbers look like answers | unapproved draft | never copy draft results | records in the slice and concept tests | bds |
| L22 | voided July postings | ledger posting counts as QTD | Voided July postings | exclude from quarter-to-date | records in the slice and concept tests | dc |
| L23 | CR- refs in withdrawals | refs do not match claim ids | Claim references crosswalk | withdrawn claims invalid | records in the slice and concept tests | dc |
| L24 | proposed host schema v2 everywhere | newer than registry baseline | proposal only; charter designates edge_layout_v7 and aborted_rollouts | baseline plus rollouts | records in the slice and concept tests | bd |
| L25 | V7 fixed-width records | records misparse under V6 | H record layout switch; layout only in D11 | parse V7 with D11 widths | records in the slice and concept tests | dc |
| L26 | aborted rollouts in deploy log | ROLLOUT events look effective | aborted_rollouts list | skip aborted events | records in the slice and concept tests | dc |
| L27 | mirror DOWN rows | mirror doubles outage evidence | kind MIRROR | ignore mirror rows | records in the slice and concept tests | d |
| L28 | vantage codes | two codes look like two vantages | VANTAGE crosswalk | count distinct vantage ids | records in the slice and concept tests | dc |
| L29 | flapping probes | two DOWN rows | FLAPVOID | flap-voided probe rows invalid | records in the slice and concept tests | dc |
| L30 | REPROCESSED lines | look like replays | event name | only REPLAY lines replay batches | records in the slice and concept tests | d |
| L31 | edge_legacy_c has no register rows | file looks uncontrolled | CONTROL lines in ingest_reprocess.log | check its blocks there | records in the slice and concept tests | dc |
| L32 | legacy CRM cases | cases look like claims | cutover and segment rule | only SMB pre-cutover cases are claims; others are crosswalk | records in the slice and concept tests | dc |
| L33 | 2025 host groups | complete host to group map | region regroupings in charter | group via Regions plus regroupings | records in the slice and concept tests | bd |
| L34 | price_book controls | register lacks price_book.toml | control rows in D15 | check them there | records in the slice and concept tests | dc |
| L35 | LB err_5xx includes 429 under v1 | column name says 5xx | schema registry and rollouts | subtract 429 for v1 windows | records in the slice and concept tests | bc |
| L36 | LB sampled hosts | raw counts look final | lb_sampling one_in | multiply counts | records in the slice and concept tests | c |
| L37 | quota equality | 429 always counts | quota rule R <= quota counts; 0 unlimited | count 429 only within quota | records in the slice and concept tests | bs |
| L38 | bad-window threshold equality | strict greater looks natural | inclusive >= in the standard | inclusive comparison | records in the slice and concept tests | s |
| L39 | misrouted hosts | host_inventory lane matches | Host lane assignments in the standard | lane per docx | records in the slice and concept tests | bc |
| L40 | quarantined hosts | records look normal | quarantine intervals ACTIVE | drop records inside | records in the slice and concept tests | c |
| L41 | lower-seq resends | first record wins | seq | highest seq within collector | records in the slice and concept tests | bs |
| L42 | lower-precedence duplicates | most complete collector looks better | Collector precedence table | precedence first | records in the slice and concept tests | b |
| L43 | placeholder -1 rows | they look like zero traffic | placeholder convention | ignore and never supersede | records in the slice and concept tests | s |
| L44 | homoglyph identifiers | digit extraction joins them | malformed id invalidates record | drop record | records in the slice and concept tests | s |
| L45 | account alias chains | single hop alias | charter decisions in date order | follow chain to master | records in the slice and concept tests | bc |
| L46 | plan reverts | last APPLY wins | REVERT voids target | latest non-reverted APPLY | records in the slice and concept tests | c |
| L47 | ist1 regrouping mid-month | provisioning group east | Region regroupings effective date | month-end group south | records in the slice and concept tests | b |
| L48 | maintenance ics reschedules | workbook times look canonical | highest SEQUENCE, CANCELLED | ics overrides | records in the slice and concept tests | c |
| L49 | maintenance notice exactly five business days | calendar days | site calendars | business days per site | records in the slice and concept tests | s |
| L50 | claim deadline | ten calendar days | site calendar of account | tenth business day local date | records in the slice and concept tests | c |
| L51 | auto-credit | claims always needed | enterprise always, corporate by preference | AUTO with month-close FX hour | records in the slice and concept tests | b |
| L52 | quarter cap carry | cap per month | QTD ledger, goodwill and --prior in subscription order | running QTD | records in the slice and concept tests | c |
| L53 | half-even ties | half-up rounding | documented half-even | half-even everywhere | records in the slice and concept tests | s |

53 loops: chained 29, best-practice entered 14, decoy anchored 33, survive sample checking 9.

## Verification

tests/test_output.py registers 48 checks. Positive: 2 checks at weight 1 (outputs_have_documented_shape; outputs_use_documented_encoding), 41 at weight 5 (8 concept projections, 16 trap-family slices, 15 decoy slices, and the two hidden next-month tests that run the agent's transform on regenerated September exports with --prior) and 1 at weight 3 (eval_held_close_exact: the same exports with one support ticket removed must give a HELD close). Positive weight total = 210. Negative tests: negative_hardcoded_sample_answers (-5, the hidden run reports August's period or replays August's records), negative_filename_dependent_behaviour (-5) and negative_reads_training_corpus_at_runtime (-5), both only when a repeat run is byte-identical, and negative_nondeterministic_output (-3). Only concept_controls and the hidden-month state test grade the 100 source entries; every other slice and concept compares records only. Each decoy slice holds the records that change when that decoy's designated content is ignored, plus the records its bait rows target. The judge carries 9 criteria (positive total 18, negative total 13); reward = 0.5 x tests + 0.5 x judge.

Measured on the test channel only (tests-only copy built by exe_copy.py, harbor 0.24.0; the judged channel has no oracle score): oracle 1.0 (all 210 positive points, no negative fired), nop 0.0, empty-artifact stub 0.0. With one data_quality source count wrong the channel reads 0.9762 (only concept_controls is lost); a transform that fails on the next month keeps its visible-tier score and draws no penalty.

## Root cause

No single file determines any graded value: telemetry needs the collector standard, batch registry, voids, host lanes, rollouts, sampling and clocks; credits need entities, contracts, policy, decoy-held tables, claims, rates, caps and the prior close; and the control register binds all of them. The difficulty is adversarial reasoning across documented interacting rules, not hidden information.

## Solution shape

A reader per format producing ordered tables, a normalizer per documented field type, a control pass that can hold the close, then entity resolution, eligibility, telemetry winner selection, outage and attribution, credit and cap computation, and deterministic writers. solution/solve.py is that program; solve.sh installs it as /app/out/transform.py and runs it.

## Ordered plan

1. Read source_register.md, governance_charter.docx and the policies they name.
2. Implement readers for all formats and verify record counts and control sums against the register and its two companions.
3. Resolve regions, accounts, subscriptions, plans, enrollment and versions.
4. Compute active, suspended and maintenance windows.
5. Select telemetry winners with validity, schema, sampling, quota and threshold rules.
6. Add probe and NOC outages, then attribution.
7. Compute fees, credits, claims, FX, caps and statuses in subscription order with prior carry.
8. Write outputs and rerun with --prior on a copy to check determinism.

Human time: about 3.5 expert days (format readers and controls 0.75 day, entity and eligibility rules 0.75 day, telemetry and schema rollout 1 day, attribution, credits, claims and caps 0.75 day, verification 0.25 day).

## Pitfalls

- Treating whole decoy files as authoritative or as noise.
- Counting 429s inside err_5xx for v1 hosts.
- Using the newest-looking proposal or draft over the ratified source.
- Applying caps per month instead of quarter-to-date in subscription order.
- Letting placeholder or homoglyph rows supersede real ones.
- Ignoring the control register, which holds the close on any mismatch.

## Provenance

```yaml
uuid: 80202e15-2d10-5eef-b823-ce74567dee0f
instance_id: 80202e15-2d10-5eef-b823-ce74567dee0f
task_name: terminal-bench/80202e15-2d10-5eef-b823-ce74567dee0f
fix_patch_sha256: d47e669d4c93887db145810be21a765ca8a693b7deaac1fe53a5c0269f40b794
solve_py_sha256: f2a2f2416149304a6d2499a06d85b56c78c981b448c440b6848e87c2b175a7e4
language: python
sample_period: 2026-08
eval_period: 2026-09
```
