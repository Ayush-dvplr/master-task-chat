# TRUTH.md - daaca581-de32-5fc7-bd44-dd51c8f26be3

## Defect

Nothing is broken in code: KVEC's November 2025 settlement was never run. `/app/data` holds exactly 100 files (85 in scope, 15 partial-authority decoys) in 19 formats from six head-end systems, MDM registers, SCADA, tariffs, CIS and governance documents. The agent must write `/app/out/transform.py`, a pipeline that applies the settlement data contract and the procedures manual and emits nine byte-exact deliverables. Every deliverable is coupled through the system UFE balance (injection + credited export - losses - billed import - deemed) and its largest-remainder allocation, so almost every graded byte depends on almost every file; the exception is daytype_calendar.csv, which depends on territory_rate_calendar.ics alone. The hidden tier is regenerated from EVAL_SEED with fresh ids, values and trap placements under the same documented rules.

1. (focal) Boundary resolution: snap reads within 900 s of the scheduled instant after clock correction, then corrections > actual > approved estimate (manual s3); every t-test.
2. (focal) Register arithmetic with anchors: exchanges, CT changes, resets, rollover (90/10 rule) versus invalidation, closing-day gap attribution (contract s4); t15_valid_outliers, t05_sentinels.
3. (focal) Six head-end parsers with firmware-dependent units and separators, channel maps, Excel 1900 serials, fixed-width layout switches, pre-multiplied exports; t02, t04, t08.
4. (focal) Entity resolution through time-valid crosswalks held only in decoys (Cirrus usage, migration wave 3, DW snapshot); dc04, dc05, dc13.
5. (focal) Billing determinants: SCD2 registry, merge chains, vacancy, disconnection, NEM plus inspection gating, effective-dated rate codes; t13, t06.
6. (focal) Pricing and UFE: errata supersession, riders and applicability, storm rider, day types, half-even monthly rounding, largest-remainder UFE; t12, t16.
7. (drift) Rounding: half-even once per monthly sum, not half-up and not per day (contract s6); t12_precision_and_rounding.
8. (drift) Gap energy is attributed to the closing day, never interpolated (contract s4); t05_sentinels, t12.
9. (drift) HOLIDAY outranks CPP and DTEND is exclusive (contract s6); t03_time_and_calendar, t11_window_boundaries.
10. (drift) Duplicates: closest to schedule wins, higher sequence only on equal distance, not latest-wins (contract s3); t07, t01.
11. (drift) UFE allocation by largest remainder on whole Wh with lower-id ties, price including riders (contract s8); t12, t16.
12. (trap) Fall-back DST repeat hour: north SCADA local stamps with CDT/CST tags, interval-ending (contract s1, s7); t03.
13. (trap) Excel 1900 serials of local wall time in Delta parquet (delta_ingest.ini); t03.
14. (trap) CIS 2400 times and layout switches (cis_legacy_layout.ini); t03, t08.
15. (trap) Aurora AU-2 firmware exports Wh into kWh columns (aurora_hes_profile.yaml); t02.
16. (trap) Cirrus CX-4.1 firmware writes decimal commas (cirrus_hes_profile.yaml); t04.
17. (trap) Fjord multiplier_applied flags, including November pilot entries in the 2026 profile; t02, dc14.
18. (trap) Holds released after the 2025-12-03 17:00 cutoff stay held (mailbox notice); t06.
19. (trap) Dollar and mill unit notes in tariff books, credit rider and rider schedule; t14.
20. (trap) SOX disconnection orders were cancelled (register note); t14.
21. (trap) Unexplained negative deltas invalidate the boundary instead of rolling over; t15, t16.
22. (trap) Late-posted in-window merges exist only in the December extract; dc01.
23. (trap) Reversal entry ids exist only on the restated workbook's Reversals sheet; dc06.
24. (drift) A surviving actual read outranks an approved VEE estimate for the same boundary (manual s3); t07_superseded_revisions.
25. (drift) HOLIDAY and CPP events on a Saturday or Sunday outrank WEEKEND (contract s6); t07_superseded_revisions.
26. (drift) Equal-instant multipliers: a CT_CHANGE order beats a same-instant verification, which beats a same-date registry row (contract s4); t02_unit_and_scale.
27. (drift) An approved draft erratum schedule row outranks an Appendix R register row with the same effective date (manual s1); dc09_draft_manual.
28. (drift) An in-window early-adopter migration outranks a rate history entry with the same effective date (manual s5); dc07_rate_crosswalk_2026.
29. (drift) A FAIL export inspection outranks a PASS inspection of the same date (contract s5); t06_voided_and_cancelled.
30. (drift) When two completed merges of one predecessor apply, the latest effective one wins (manual s5); t13_referential_integrity.
31. (trap) The vendor manifest record_count and the MDM batch log row count are delivered counts, not the number of data records a file holds: on 15 of the 34 read files the manifest disagrees with the parsed count and on 11 the batch log does, and the two also disagree with each other, so data_rows is counted from the file itself while manifest_rows reports the vendor's number unchanged (contract s9, manual s4); t09_delimiters_and_quoting, dc08_vendor_manifest.

Reference language: Python 3.12 (solution/solve.py, installed as /app/out/transform.py by solve.sh). Two channels grade the run: deterministic rewardkit criteria in tests/test_output.py and LLM-judged criteria in tests/judge.toml; tests/reward.toml gives each half.

Out of bounds: embedding visible ids or totals (negative_hardcoded_sample_answers), behaviour keyed on directory names or timestamps (negative_filename_dependent_behaviour), reading the shipped corpus while settling the hidden one or leaving files outside OUT_DIR (negative_io_outside_argument_dirs), nondeterministic output (negative_nondeterministic_output).

## Load-bearing work

- `/app/out/transform.py`
- `/app/out/account_settlement.csv`
- `/app/out/meter_summary.csv`
- `/app/out/read_resolution.csv`
- `/app/out/interval_injection.csv`
- `/app/out/lighting_deemed.csv`
- `/app/out/daytype_calendar.csv`
- `/app/out/feeder_balance.json`
- `/app/out/control_report.json`
- `/app/out/settlement_summary.json`

Each deliverable's columns, ordering and serialisation are fixed by contract section 9. transform.py must reproduce all nine on an unseen directory.

### Concepts (all load-bearing, interacting)

| id | concept | where it bites | dedicated tests | note |
|---|---|---|---|---|
| C1 | Multi-format ingestion and schema normalisation | header drift, layout switches, encodings, quoting, PDF and DOCX tables | t08, t09, t10 |  |
| C2 | Entity resolution with temporal crosswalks | identifier canonicalisation, device-period and service-point validity windows, legacy links | t01, t13, dc04, dc05, dc13 |  |
| C3 | Temporal normalisation | DST repeat hour, interval-ending stamps, Excel 1900 serials, 2400, clock offsets and sync, snapping | t03, t11 |  |
| C4 | Source precedence and revision handling | corrections over actuals over estimates, supersession, reversals, holds, quarantine, partial-authority decoys | t05, t06, t07, dc01-dc15 |  |
| C5 | Stateful cumulative-register differencing | anchors, rollover versus invalidation, resets, exchanges, CT splits, closing-day gap attribution | t15, t02 | expert-only: closing-day gap rule and multiplier one second before segment end |
| C6 | Unit and scale normalisation | Wh, kWh, MWh, kW demand to energy, CT multipliers, pre-multiplied exports, dollar and mill notes | t02, t14 |  |
| C7 | Effective-dated reference joins | SCD2 registry, rate history, riders, applicability, calendars, fixtures | t11, t06 | expert-only: HOLIDAY outranks CPP, DTEND exclusive |
| C8 | Reconciliation and allocation | energy balance, largest-remainder UFE allocation, price derivation, half-even rounding steps, batch control report | t12, t16, dc08 | expert-only: largest-remainder allocation and once-per-month half-even rounding |

Interaction chain: identity (C2) decides which reads exist; time (C3) decides their boundary; precedence (C4) decides the value; differencing (C5) and units (C6) turn values into Wh on a day; effective joins (C7) price that day; reconciliation (C8) couples every account through UFE.

### 100-file inventory

| file | type | rows | role | traps | unique contribution | depends on | depended on by |
|---|---|---|---|---|---|---|---|
| account_merges_2025.json | json | 5220 | in-scope | 20 | COMPLETED merges and their chains | 4 files | 8 files |
| account_rate_history.xlsx | xlsx | 10000 | in-scope | 20 | effective-dated rate code entries per account | 9 files | 11 files |
| account_rate_history_restated.xlsx | xlsx | 11154 | decoy | 256 | the Reversals list of erroneous rate history entries | 4 files | 3 files |
| aurora_hes_profile.yaml | yaml | 5735 | in-scope | 20 | Aurora firmware history deciding Wh versus kWh registers, timestamp formats, missing markers | 8 files | 8 files |
| aurora_reads_2025-11_p1.csv | csv | 5194 | in-scope | 20 | read export: boundary register reads of its head end and period | 18 files | 22 files |
| aurora_reads_2025-11_p2.csv | csv | 5198 | in-scope | 20 | read export: boundary register reads of its head end and period | 18 files | 22 files |
| aurora_reads_2025-11_p3.csv | csv | 5196 | in-scope | 20 | read export: boundary register reads of its head end and period | 18 files | 22 files |
| aurora_reads_2025-11_p4.csv | csv | 5197 | in-scope | 20 | read export: boundary register reads of its head end and period | 18 files | 22 files |
| aurora_reads_2025-11_p5.csv | csv | 5195 | in-scope | 20 | read export: boundary register reads of its head end and period | 18 files | 22 files |
| aurora_reads_2025-11_p6.csv | csv | 5197 | in-scope | 20 | read export: boundary register reads of its head end and period | 18 files | 22 files |
| borealis_channel_map.toml | toml | 5159 | in-scope | 20 | Borealis import and export channel numbers per meter and date | 8 files | 8 files |
| borealis_reads_2025-11_p1.xml | xml | 5153 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| borealis_reads_2025-11_p2.xml | xml | 5154 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| borealis_reads_2025-11_p3.xml | xml | 5152 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| borealis_reads_2025-11_p4.xml | xml | 5151 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| borealis_reads_2025-11_p5.xml | xml | 5152 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| borealis_reads_2025-11_p6.xml | xml | 5152 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cirrus_daily_usage_2025-11.jsonl | jsonl | 6388 | decoy | 101 | the only Cirrus device-to-meter link per period | 8 files | 8 files |
| cirrus_hes_profile.yaml | yaml | 5271 | in-scope | 20 | Cirrus firmware history deciding the decimal separator, schema directive keys | 8 files | 8 files |
| cirrus_reads_2025-11_p1.jsonl | jsonl | 5267 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cirrus_reads_2025-11_p2.jsonl | jsonl | 5267 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cirrus_reads_2025-11_p3.jsonl | jsonl | 5268 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cirrus_reads_2025-11_p4.jsonl | jsonl | 5266 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cirrus_reads_2025-11_p5.jsonl | jsonl | 5268 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cirrus_reads_2025-11_p6.jsonl | jsonl | 5266 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cis_account_master.csv | csv | 9603 | in-scope | 20 | account status and final_date (vacancy) and the rate code fallback for accounts without history | 8 files | 12 files |
| cis_account_master_2025-12.csv | csv | 6156 | decoy | 66 | late-posted in-window merges (late_posted = Y) | 4 files | 4 files |
| cis_legacy_layout.ini | ini | 5205 | in-scope | 20 | CIS fixed-width layouts 1 and 2, the 2400 rule, dial constants per legacy id | 5 files | 5 files |
| cis_legacy_reads_2025-11_a.txt | txt | 5249 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cis_legacy_reads_2025-11_b.txt | txt | 5249 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| cis_legacy_reads_2025-11_c.txt | txt | 5250 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| collector_events_2025-11.log | log | 5300 | in-scope | 20 | REGISTER_RESET pre and post values and CLOCK_SYNC instants | 35 files | 36 files |
| ct_ratio_verification_2025.xlsx | xlsx | 10000 | in-scope | 20 | CORRECT_RATIO verifications that change a meter's multiplier from a date | 6 files | 6 files |
| customer_portal_usage_export.html | html | 18226 | decoy | 76 | read dispute decisions (latest decided UPHELD excludes the read) | 36 files | 35 files |
| delta_ingest.ini | ini | 5201 | in-scope | 20 | service point est_policy deciding whether Delta vendor estimates are usable; Excel 1900 serial rule | 8 files | 8 files |
| delta_reads_2025-11_p1.parquet | parquet | 5194 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| delta_reads_2025-11_p2.parquet | parquet | 5192 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| delta_reads_2025-11_p3.parquet | parquet | 5193 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| delta_reads_2025-11_p4.parquet | parquet | 5191 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| delta_reads_2025-11_p5.parquet | parquet | 5192 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| delta_reads_2025-11_p6.parquet | parquet | 5191 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| disconnection_register_2025.docx | docx | 5200 | in-scope | 20 | disconnect and reconnect events (de-energised days) and the SOX note | 38 files | 2 files |
| dw_registry_snapshot_2025-12-03.db | db | 16782 | decoy | 90 | the only time-valid service point to meter links (sp_meter_xref) | 9 files | 8 files |
| export_meter_inspections_2025.xlsx | xlsx | 10000 | in-scope | 20 | export meter inspections (PASS or FAIL) gating export credit | 4 files | 4 files |
| field_service_orders.jsonl | jsonl | 5501 | in-scope | 20 | meter exchanges (final and initial registers, instants) and CT changes (ratio, register at change) | 38 files | 8 files |
| fjord_hes_profile.yaml | yaml | 5498 | in-scope | 20 | Fjord multiplier_applied flags (exported values pre-multiplied), header aliases | 11 files | 9 files |
| fjord_hes_profile_2026.yaml | yaml | 5200 | decoy | 28 | November pilot multiplier_applied entries (effective on or before 2025-11-30) | 9 files | 9 files |
| fjord_reads_2025-11_p1.tsv | tsv | 7747 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| fjord_reads_2025-11_p2.tsv | tsv | 7744 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| fjord_reads_2025-11_p3.tsv | tsv | 7745 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| fjord_reads_2025-11_p4.tsv | tsv | 7745 | in-scope | 20 | read export: boundary register reads of its head end and period | 20 files | 24 files |
| fjord_reads_2025-11_p4b.tsv | tsv | 7762 | decoy | 99 | REV reversal records that exclude original period 4 reads | 4 files | 4 files |
| fjord_reads_2025-11_p5.tsv | tsv | 7744 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| fjord_reads_2025-11_p6.tsv | tsv | 7743 | in-scope | 20 | read export: boundary register reads of its head end and period | 19 files | 23 files |
| hes_batch_manifest_2025-11.json | json | 5514 | decoy | 38 | vendor record counts per read file (delivered counts, 15 of which disagree with the parsed data rows) and withdrawn row ranges | 37 files | 35 files |
| hes_ingest_debug.log | log | 15906 | decoy | 70 | QUARANTINE and UNQUARANTINE decisions | 35 files | 35 files |
| hes_known_issues.md | md | 5202 | in-scope | 20 | OPEN known issues with their remedies (stuck, Wh-as-kWh, swapped registers) | 35 files | 35 files |
| kvec_settlement_procedures_manual.docx | docx | 6280 | in-scope | 20 | authority and precedence rules, Table F territory and loss factor per feeder, Appendix R read schedule register (boundary instants) | 99 files | 99 files |
| lighting_burn_hour_exceptions_2025.xlsx | xlsx | 10000 | in-scope | 20 | fixture-day burn-hour overrides | 6 files | 5 files |
| mdm_batch_control.log | log | 5200 | in-scope | 20 | MDM batch status per read file and PARTIAL rejected row ranges; its row counts are delivered counts, 11 of which disagree with the parsed data rows | 35 files | 37 files |
| mdm_october_close_reads.csv | csv | 6233 | in-scope | 20 | the 2025-11-01 boundary register of every meter (opening anchor) | 39 files | 35 files |
| mdm_ops_mailbox_2025-11.mbox | mbox | 5414 | in-scope | 20 | read holds and releases with send instants, CAB decisions, the release cutoff notice | 36 files | 36 files |
| mdm_read_corrections.csv | csv | 5401 | in-scope | 20 | VALIDATED corrected boundary registers (highest revision wins) | 35 files | 36 files |
| mdm_registry_east.db | db | 6231 | in-scope | 20 | SCD2 account link, multiplier and service history for F04-F06 meters | 18 files | 19 files |
| mdm_registry_north.db | db | 6254 | in-scope | 20 | SCD2 account link, multiplier and service history for F01-F03 meters | 18 files | 19 files |
| mdm_registry_southwest.db | db | 7842 | in-scope | 20 | SCD2 account link, multiplier and service history for F07-F12 meters | 21 files | 22 files |
| mdm_vee_estimates.tsv | tsv | 5305 | in-scope | 20 | estimated boundary registers used when no actual read survives | 35 files | 35 files |
| mdm_void_register.csv | csv | 5601 | in-scope | 20 | voids that remove specific head-end reads (reinstated = N) | 35 files | 35 files |
| meter_accuracy_test_results_2025.docx | docx | 5200 | in-scope | 20 | FAIL tests whose registration error corrects earlier daily import | 35 files | 2 files |
| meter_clock_offsets.toml | toml | 6261 | in-scope | 20 | meter clock offsets applied before CLOCK_SYNC | 36 files | 35 files |
| meter_registry_migration_wave3.xlsx | xlsx | 11487 | decoy | 81 | the only legacy id to meter link (ACTIVE Crosswalk rows) | 5 files | 5 files |
| net_metering_export_credit_rider.docx | docx | 7728 | in-scope | 20 | export credit rates and its dollar-unit note | 5 files | 5 files |
| netmetering_enrollments.csv | csv | 5301 | in-scope | 20 | APPROVED net metering windows that gate export credit | 37 files | 4 files |
| photocell_burn_hours.json | json | 8772 | in-scope | 20 | dusk-to-dawn hours per feeder and date | 6 files | 5 files |
| rate_code_crosswalk_2026.json | json | 6252 | decoy | 67 | ACTIVE legacy rate aliases and in-window early-adopter migrations | 4 files | 3 files |
| register_rollover.toml | toml | 6261 | in-scope | 20 | register digits per meter (rollover modulus) | 35 files | 35 files |
| register_scaling.ini | ini | 6261 | in-scope | 20 | register resolution (decimals) per meter for Delta raw counts | 8 files | 8 files |
| rider_applicability_matrix.html | html | 5382 | in-scope | 20 | rider applicability flags per rate code and territory over time | 4 files | 3 files |
| rider_schedule_2025.pdf | pdf | 5301 | in-scope | 20 | rider adders and windows, the mills note for R-LIEAP | 5 files | 4 files |
| scada_15min_gapfill_2025-11.csv | csv | 34741 | decoy | 216 | the only replacement values for invalid historian intervals (v3 PUBLISHED) | 7 files | 6 files |
| scada_alarm_journal.log | log | 7980 | in-scope | 20 | COMM_FAIL windows that invalidate historian intervals | 6 files | 7 files |
| scada_errata_notice.md | md | 5205 | in-scope | 20 | approved SCADA interval corrections and supersession links | 6 files | 7 files |
| settlement_data_contract.md | md | 6335 | in-scope | 20 | computation rules, output formats and Appendix T meter-to-feeder connectivity (only source of a meter's feeder, hence territory and day type) | 99 files | 99 files |
| settlement_procedures_manual_rev4_draft.docx | docx | 6296 | decoy | 64 | errata index: the only source of CAB-approved schedule rows and loss factor replacements | 3 files | 3 files |
| substation_east_monthly_report.pdf | pdf | 8666 | decoy | 35 | DONE relay-test replacement values for east feeders | 4 files | 3 files |
| substation_east_scada_2025-11.json | json | 8652 | in-scope | 20 | 15-minute energy for feeders F04-F06 | 6 files | 6 files |
| substation_north_scada_2025-11.csv | csv | 8654 | in-scope | 20 | 15-minute demand for feeders F01-F03 | 5 files | 5 files |
| substation_south_historian.log | log | 8655 | in-scope | 20 | 15-minute energy for feeders F07-F09 | 5 files | 5 files |
| substation_west_monthly_report.pdf | pdf | 8654 | in-scope | 20 | 15-minute energy for feeders F10-F12 | 5 files | 5 files |
| tariff_book_agri_lighting_q4.pdf | pdf | 5154 | in-scope | 20 | base energy rates for AGR and LIT codes and its dollar-unit note | 5 files | 9 files |
| tariff_book_commercial_q4.pdf | pdf | 5154 | in-scope | 20 | base energy rates for SGS and LGS codes and its dollar-unit note | 5 files | 5 files |
| tariff_book_industrial_q4.docx | docx | 5152 | in-scope | 20 | base energy rates for IND codes and its dollar-unit note | 5 files | 5 files |
| tariff_book_residential_2026.pdf | pdf | 5066 | decoy | 28 | Table S storm rider rows approved for November 2025 | 4 files | 3 files |
| tariff_book_residential_q4.docx | docx | 5152 | in-scope | 20 | base energy rates for RES codes and its dollar-unit note | 5 files | 6 files |
| tariff_errata_register.html | html | 5303 | in-scope | 20 | approved base-rate errata and supersession links | 6 files | 6 files |
| territory_rate_calendar.ics | ics | 5424 | in-scope | 20 | HOLIDAY and CPP events (CONFIRMED or CANCELLED) per territory | 7 files | 7 files |
| ufe_allocation_exemptions_register.pdf | pdf | 5202 | in-scope | 20 | accounts exempt from UFE allocation on 2025-11-30 | 4 files | 2 files |
| unmetered_fixture_audit_2025.xlsx | xlsx | 10000 | in-scope | 20 | audited wattage changes and removals with effective dates | 6 files | 5 files |
| unmetered_supply_inventory.json | json | 5132 | in-scope | 20 | lighting fixtures: account, feeder, nominal watts, burn profile, service dates | 6 files | 5 files |
| vee_estimate_review_2025.xlsx | xlsx | 10000 | in-scope | 23 | review decisions deciding which estimates are usable | 35 files | 35 files |

Dependency graph: 100 nodes, 1790 edges, 1 strongly connected component, min out-degree 3, min in-degree 2.

### Decoys

| decoy | why it looks authoritative | rule that demotes it | load-bearing roles | test |
|---|---|---|---|---|
| cis_account_master_2025-12.csv | newer extract, more columns, December statuses look final | manual section 5; its own header says forward-billing preview | (b)(d)(e) | dc01_december_master |
| scada_15min_gapfill_2025-11.csv | gap-free, every interval of every feeder | manual section 7 case 4; header says not revenue grade | (c)(d)(e) | dc02_scada_gapfill |
| fjord_reads_2025-11_p4b.tsv | newest copy of period 4 with values re-derived by the vendor | mdm_batch_control.log REJECTED; manual section 4 | (b)(d) | dc03_fjord_resend |
| cirrus_daily_usage_2025-11.jsonl | ready-made consumption per device | manual section 2; its header says informational | (c)(d) | dc04_cirrus_usage_crosswalk |
| meter_registry_migration_wave3.xlsx | one clean attribute table for every meter | manual section 2; first row says staging extract | (c)(d) | dc05_legacy_crosswalk |
| account_rate_history_restated.xlsx | one tidy rate code per account | manual section 5; header says pending regulatory approval | (b)(d) | dc06_restated_rate_history |
| rate_code_crosswalk_2026.json | authoritative-looking consolidation table | manual section 5 (ACTIVE aliases, in-window migrations) | (c)(e) | dc07_rate_crosswalk_2026 |
| hes_batch_manifest_2025-11.json | one count per file, looks like the control of record | manual section 4; note says vendor side, and 15 of its counts disagree with the parsed data rows | (a)(b) | dc08_vendor_manifest |
| settlement_procedures_manual_rev4_draft.docx | newer revision of the manual | manual section 1; its header and footer say DRAFT | (b)(d)(e) | dc09_draft_manual |
| tariff_book_residential_2026.pdf | newer tariff book | manual section 6; cover says pending commission order | (d)(e) | dc10_tariff_2026 |
| substation_east_monthly_report.pdf | formatted final monthly report | manual section 7 case 2; header says presentation copy | (c)(d)(e) | dc11_east_pdf_report |
| hes_ingest_debug.log | already-parsed values for many reads | manual section 4; header says diagnostics | (b)(d) | dc12_ingest_debug_log |
| dw_registry_snapshot_2025-12-03.db | latest attributes for every meter | manual section 2; first snapshot_log row says informational | (c)(d) | dc13_dw_snapshot |
| fjord_hes_profile_2026.yaml | newer profile | manual section 8; header says planned | (d)(e) | dc14_fjord_profile_2026 |
| customer_portal_usage_export.html | customer-facing usage per account | manual section 4; note says customer information only | (b)(d) | dc15_portal_export |

### Trap loops

Flags: D decoy-anchored, B entered by standard best practice, S survives sample checking (visible and hidden differ only on the hidden tier's placements), Cnn chained (escaping loop nn reveals this entry).

| loop | entry | reinforcement | tell (file) | exit | graded impact | flags |
|---|---|---|---|---|---|---|
| L01 | Trust the newest account master (cis_account_master_2025-12.csv) for status and rate codes | its codes agree with the restated history for most accounts; every account joins | cis_account_master.csv header as_of 2025-11-30 and the extract's own preview note | manual section 5 | dc01, t06, t16 | D B |
| L02 | After rejecting the December extract, ignore it entirely | the merge register looks complete; registry links resolve | late_posted = Y rows whose predecessor still carries consumption after the merge date | manual section 5 exception | dc01, t07, t13 | D C1 |
| L03 | Use the analytics gap-fill series for every interval because it has no gaps | its feeder totals sit within 1.5 percent of the historian | gap-fill header says not revenue grade; feeder residual_wh moves | manual section 7 | dc02, t16, t05 | D B |
| L04 | Drop the gap-fill file entirely | historian covers 99 percent of intervals | intervals left without a value although the contract requires 2884 per feeder | manual section 7 case 4 | dc02, t05, t06 | D C3 |
| L05 | Treat the Fjord period 4 resend as the corrected period 4 | its values match several corrections; its counts look clean | mdm_batch_control.log REJECTED line | manual section 4 | dc03, t07 | D B |
| L06 | Ignore the resend wholesale | period 4 reads look normal | REV records in the resend; reversed reads cause next-day invalidations | manual section 4 second paragraph | dc03, t06 | D C5 |
| L07 | Link Cirrus devices through any usage row, VOID rows included | every device resolves to a meter | VOID rows link devices to meters on non-Cirrus feeders (Appendix T) | manual section 2 | dc04, t13 | D |
| L08 | Use Cirrus usage kWh as consumption instead of differencing registers | usage agrees with differenced registers for 95 percent of devices | the usage file's informational header; disagreements on 5 percent of devices | contract section 4 | dc04, t16 | D B C7 |
| L09 | Resolve legacy ids through any crosswalk row, SUPERSEDED included | every CIS read resolves | legacy ids with two meters; meters with reads that never snap | manual section 2 | dc05, t13 | D |
| L10 | Take multipliers from the migration workbook Attributes sheet | it agrees with the registry for 96 percent of meters | staging banner on the Crosswalk sheet; CT meters' energy moves the feeder residual | manual section 2 | dc05, t02, t16 | D B |
| L11 | Apply the restated rate history because it is tidier | it matches the master snapshot for most accounts | PENDING REGULATORY APPROVAL banner | manual section 5 | dc06, t16 | D B |
| L12 | Ignore the restated workbook after rejecting it | history entries look plausible | Reversals entry ids equal erroneous history entry ids (a code that flips for a few days) | manual section 5 | dc06, t06 | D C11 |
| L13 | Resolve legacy rate aliases with the first matching alias row | aliases resolve to a code of the right class | duplicate aliases, one RETIRED | manual section 5 | dc07, t07, t01 | D |
| L14 | Ignore the 2026 crosswalk because it is a 2026 document | most history codes are canonical | alias codes such as R7 exist in no tariff book; early-adopter accounts keep old codes | manual section 5 | dc07, t11 | D C13 |
| L15 | Ignore the vendor manifest as vendor-side noise | MDM batch statuses look complete | withdrawn ranges produce invalidated boundaries; control_report withdrawn_rows | manual section 4 | dc08, t06, t09 | D |
| L16 | Use the first manifest entry per file | counts are plausible | a later non-superseded entry; counts disagree with the parsed data rows | manual section 4 | dc08, t07 | D C15 |
| L63 | Report a delivered count as data_rows (vendor record_count, batch log rows=, or whichever of the two agrees) | both numbers look like the control of record and agree with the file on about half the read files | 15 manifest counts and 11 batch log counts disagree with the parsed rows, and they disagree with each other | contract section 9; manual section 4 | t09, dc08 | D B |
| L17 | Adopt the revision 4 draft rules because the draft is newer | the draft says it supersedes revision 3 | DRAFT NOT APPROVED banner | manual section 1 | dc09, t07 | D B |
| L18 | Ignore the draft wholesale | revision 3 tables look complete | APPROVED CAB decisions in the mailbox for draft errata CR numbers; reads that never snap for those meters | manual section 1 exception | dc09, t11 | D C17 |
| L19 | Ignore the 2026 tariff filing as out of period | Q4 books cover every November date | Table S rows effective in November under docket 25-STORM | manual section 6 | dc10, t11 | D |
| L20 | Apply every Table S row | rows look like approved riders | WITHDRAWN status column | manual section 6 | dc10, t06 | D C19 |
| L21 | Use the east PDF report table because it looks final | values agree with the JSON to within 1 kWh | presentation copy banner; integer kWh values | manual section 7 | dc11, t12, t16 | D B |
| L22 | Ignore the east PDF report wholesale | the JSON covers every east interval | section 4 relay-test rows; the manual's case 2 | manual section 7 case 2 | dc11, t14 | D C21 |
| L23 | Reuse the debug log's parsed values to save parsing | 96 percent of echoed values match | diagnostics header; echoed values that disagree with the files | manual section 4 | dc12, t16 | D B |
| L24 | Ignore the debug log | it is a log of a service | QUARANTINE lines naming reads | manual section 4 | dc12, t06 | D C23 |
| L25 | Apply QUARANTINE lines without reading further | quarantined reads look suspicious | later UNQUARANTINE lines for the same reads | manual section 4 | dc12, t07 | D C24 |
| L26 | Take multipliers and accounts from the DW snapshot because it is the latest | it agrees with the registry for 97 percent of meters | informational SNAPSHOT_INFO row; post-month ratios applied to the whole month | manual section 2 | dc13, t16 | D B |
| L27 | Map service points with the latest xref row | every Delta read resolves | re-pointed service points at exchanges; old-meter reads land on the new meter | manual section 2 | dc13, t07, t13 | D |
| L28 | Apply every entry of the Fjord 2026 profile | it is the newer profile | planned header; 2026 effective dates | manual section 8 | dc14, t06 | D B |
| L29 | Ignore the 2026 profile | the current profile covers every Fjord meter | registers that jump by the multiplier mid-month for pilot meters | manual section 8 | dc14, t02 | D C28 |
| L30 | Apply any UPHELD dispute row | dispute rows look final | appeal decisions with later decided dates | manual section 4 | dc15, t07 | D |
| L31 | Use portal usage as a billing determinant | usage per account is close to settlement | customer information banner | manual section 4 | dc15, t16 | D B C30 |
| L32 | Interpolate gap energy linearly across the gap days | monthly meter totals are unchanged | contract section 4 closing-day rule; charges differ across day types | contract section 4 | t05, t12 | B S |
| L33 | Round money half-up | almost every account agrees | contract section 6 half-even | contract section 6 | t12 | B S |
| L34 | Round charges per day | per-day cents look reasonable | contract section 6 rounds monthly sums once | contract section 6 | t12 | B S C33 |
| L35 | Keep the latest read (highest sequence) for a boundary | duplicates resolve deterministically | far copies with higher sequence produce next-day invalidations | contract section 3 | t07, t01 | B |
| L36 | Treat every negative delta as a rollover | rollover meters settle | huge consumption on invalidation cases; feeder residual collapses | contract section 4 (90/10 rule) | t15, t16 | B |
| L37 | Drop extreme consumption days as meter errors | load profiles look smooth | no rule allows removal; feeder residual rises by the spike | contract section 4 | t15 | B |
| L38 | Ignore meter clock offsets | most meters read near midnight | offset meters lose boundaries (MISSING runs) | contract section 3 | t03, t11 | B |
| L39 | Apply clock offsets to every read | offset meters snap again | reads after a CLOCK_SYNC event miss their boundary | contract section 3 and the collector log | t03 | C38 |
| L40 | Use a fixed CST offset for the month | local midnights after 2025-11-02 convert correctly | boundaries of 2025-11-01 and 2025-11-02 go missing for every UTC-stamped head end | contract section 1 | t03 | B |
| L41 | Convert Delta serials from 1900-01-01 | times of day convert correctly | every Delta read lands one day late | delta_ingest.ini read_serial | t03 | B |
| L42 | Discard CIS times of 2400 as invalid | few rows are affected | boundaries missing exactly at local midnight | cis_legacy_layout.ini time note | t03, t11 |  |
| L43 | Read Cirrus values with a dot decimal always | most firmware works | CX-4.1 values parse 1000 times too large | cirrus_hes_profile.yaml | t04 | B |
| L44 | Treat all Aurora registers as kWh | most meters agree | AU-2 firmware registers 1000 times too large | aurora_hes_profile.yaml | t02 | B |
| L45 | Assume Borealis channel 1 is import | most meters use 1 and 2 | swapped and remapped channels produce negative deltas | borealis_channel_map.toml | t08, t02 | B |
| L46 | Use Fjord values as exported | mult 1 meters agree | multiplier_applied meters register mult times too much | fjord_hes_profile.yaml | t02 | B |
| L47 | Let the latest issued erratum win | most keys have one erratum | supersedes links that point back | tariff and SCADA errata headers | t07 | B S |
| L48 | Take the highest correction revision regardless of status | revisions look ordered | PROVISIONAL rev 3 values | manual section 3 | t07 | B |
| L49 | Take the highest estimate version regardless of review | versions look ordered | later REJECTED reviews | manual section 3 | t07, t05 | B |
| L50 | Accept any RELEASE | held reads return | releases sent after the cutoff | manual section 4; mailbox cutoff notice | t06 |  |
| L51 | Bill from the registry link only | every meter-day has an account | FINAL accounts with final_date in November still billed | contract section 5 | t13 | B |
| L52 | Apply only the first hop of a merge chain | most merges are single | chains A to B to C | manual section 5 | t13 |  |
| L53 | Count CANCELLED CPP events | CPP days look plausible | STATUS:CANCELLED | contract section 6 | t06 | S |
| L54 | Let CPP outrank a holiday | CPP is the most specific event | contract section 6 order | contract section 6 | t07 | S |
| L55 | Treat DTEND as inclusive | one-day events are unaffected | the two-day event spans one extra day | contract section 6 | t11 | S |
| L56 | Apply SOX disconnections | they look like service orders | the register note | disconnection register note | t14 |  |
| L57 | Credit export from enrollment alone | enrolled meters credit | FAIL inspections in November | contract section 5 | t06 | B |
| L58 | Round each account's UFE quota independently | per-account values look right | sum of ufe_wh differs from system UFE | contract section 8 | t12, t16 | B S |
| L59 | Price UFE on base energy only | price looks plausible | contract section 8 includes riders | contract section 8 | t12 | B |
| L60 | Let an approved VEE estimate replace the read it estimates | estimates look like reviewed, corrected values | approved estimates dated on boundaries that also carry a clean actual read | manual section 3 order (2) before (3) | t07 | B S |
| L61 | Classify Saturdays and Sundays as WEEKEND before consulting the calendar | weekends carry no events in most months | CONFIRMED weekend CPP and holiday events in territory_rate_calendar.ics | contract section 6 | t07 | B S |
| L62 | Break equal-instant multiplier ties by recency or file order | ties look rare | a registry row and a verification on the same date; a midnight CT_CHANGE order and a verification on the same date | contract section 4 | t02 | B S |

Loops 63; decoy-anchored 32; best-practice 36; chained 16; sample-surviving 11.

### Trap-family coverage matrix (traps per file and family)

| file | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| account_merges_2025.json | 5 | 0 | 4 | 0 | 0 | 8 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| account_rate_history.xlsx | 6 | 0 | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 6 | 2 | 0 | 0 | 0 | 0 |
| account_rate_history_restated.xlsx | 1 | 0 | 1 | 0 | 0 | 26 | 1 | 1 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 217 |
| aurora_hes_profile.yaml | 7 | 6 | 4 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| aurora_reads_2025-11_p1.csv | 4 | 0 | 2 | 2 | 2 | 0 | 0 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 5 | 0 |
| aurora_reads_2025-11_p2.csv | 4 | 0 | 3 | 3 | 0 | 0 | 1 | 1 | 2 | 1 | 2 | 0 | 2 | 0 | 1 | 0 |
| aurora_reads_2025-11_p3.csv | 4 | 0 | 3 | 3 | 0 | 0 | 0 | 2 | 3 | 2 | 1 | 0 | 0 | 0 | 2 | 0 |
| aurora_reads_2025-11_p4.csv | 5 | 0 | 3 | 3 | 0 | 0 | 0 | 2 | 3 | 1 | 3 | 0 | 0 | 0 | 0 | 0 |
| aurora_reads_2025-11_p5.csv | 3 | 0 | 3 | 3 | 2 | 0 | 0 | 1 | 2 | 1 | 2 | 0 | 2 | 0 | 1 | 0 |
| aurora_reads_2025-11_p6.csv | 3 | 0 | 3 | 3 | 1 | 0 | 1 | 1 | 2 | 1 | 2 | 0 | 2 | 0 | 1 | 0 |
| borealis_channel_map.toml | 7 | 0 | 4 | 0 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| borealis_reads_2025-11_p1.xml | 3 | 3 | 3 | 0 | 0 | 0 | 2 | 2 | 0 | 1 | 2 | 0 | 1 | 0 | 3 | 0 |
| borealis_reads_2025-11_p2.xml | 4 | 4 | 3 | 0 | 0 | 0 | 1 | 2 | 0 | 1 | 1 | 0 | 3 | 0 | 1 | 0 |
| borealis_reads_2025-11_p3.xml | 4 | 4 | 4 | 0 | 1 | 0 | 2 | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 0 |
| borealis_reads_2025-11_p4.xml | 4 | 4 | 4 | 0 | 1 | 0 | 0 | 2 | 0 | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| borealis_reads_2025-11_p5.xml | 4 | 4 | 4 | 0 | 1 | 0 | 1 | 2 | 0 | 2 | 0 | 0 | 1 | 0 | 1 | 0 |
| borealis_reads_2025-11_p6.xml | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 3 | 0 | 2 | 0 | 0 | 0 |
| cirrus_daily_usage_2025-11.jsonl | 2 | 0 | 0 | 1 | 0 | 30 | 20 | 1 | 0 | 1 | 0 | 0 | 15 | 0 | 0 | 31 |
| cirrus_hes_profile.yaml | 7 | 0 | 4 | 6 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cirrus_reads_2025-11_p1.jsonl | 4 | 0 | 2 | 3 | 1 | 0 | 0 | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| cirrus_reads_2025-11_p2.jsonl | 3 | 0 | 2 | 4 | 1 | 0 | 0 | 2 | 2 | 2 | 1 | 0 | 1 | 0 | 2 | 0 |
| cirrus_reads_2025-11_p3.jsonl | 4 | 0 | 1 | 3 | 3 | 0 | 0 | 2 | 2 | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| cirrus_reads_2025-11_p4.jsonl | 3 | 0 | 2 | 3 | 1 | 0 | 0 | 2 | 2 | 2 | 1 | 0 | 0 | 0 | 4 | 0 |
| cirrus_reads_2025-11_p5.jsonl | 4 | 0 | 2 | 3 | 3 | 0 | 0 | 2 | 2 | 2 | 1 | 0 | 1 | 0 | 0 | 0 |
| cirrus_reads_2025-11_p6.jsonl | 3 | 0 | 2 | 4 | 1 | 0 | 0 | 2 | 2 | 2 | 3 | 0 | 0 | 0 | 1 | 0 |
| cis_account_master.csv | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 2 | 0 | 0 | 8 | 0 | 0 | 0 |
| cis_account_master_2025-12.csv | 2 | 0 | 1 | 0 | 0 | 18 | 3 | 1 | 1 | 1 | 3 | 0 | 2 | 0 | 0 | 34 |
| cis_legacy_layout.ini | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cis_legacy_reads_2025-11_a.txt | 5 | 0 | 2 | 2 | 1 | 0 | 1 | 4 | 0 | 2 | 1 | 0 | 0 | 0 | 2 | 0 |
| cis_legacy_reads_2025-11_b.txt | 4 | 0 | 2 | 2 | 1 | 0 | 0 | 5 | 0 | 2 | 0 | 0 | 1 | 0 | 3 | 0 |
| cis_legacy_reads_2025-11_c.txt | 3 | 0 | 2 | 2 | 0 | 0 | 1 | 4 | 0 | 2 | 3 | 0 | 3 | 0 | 0 | 0 |
| collector_events_2025-11.log | 3 | 0 | 8 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 7 | 0 |
| ct_ratio_verification_2025.xlsx | 5 | 6 | 5 | 0 | 0 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| customer_portal_usage_export.html | 2 | 0 | 1 | 2 | 0 | 29 | 6 | 1 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 31 |
| delta_ingest.ini | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| delta_reads_2025-11_p1.parquet | 5 | 0 | 3 | 0 | 3 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 5 | 0 |
| delta_reads_2025-11_p2.parquet | 7 | 0 | 5 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 0 | 0 | 1 | 0 |
| delta_reads_2025-11_p3.parquet | 4 | 0 | 4 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 0 | 1 | 0 |
| delta_reads_2025-11_p4.parquet | 6 | 0 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 3 | 0 |
| delta_reads_2025-11_p5.parquet | 6 | 0 | 5 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 1 | 0 | 3 | 0 |
| delta_reads_2025-11_p6.parquet | 6 | 0 | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 1 | 0 |
| disconnection_register_2025.docx | 1 | 0 | 1 | 0 | 0 | 10 | 0 | 1 | 0 | 0 | 4 | 0 | 0 | 3 | 0 | 0 |
| dw_registry_snapshot_2025-12-03.db | 10 | 0 | 10 | 0 | 0 | 20 | 4 | 0 | 0 | 0 | 0 | 0 | 16 | 0 | 0 | 30 |
| export_meter_inspections_2025.xlsx | 5 | 0 | 5 | 0 | 0 | 7 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| field_service_orders.jsonl | 3 | 7 | 2 | 2 | 0 | 4 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| fjord_hes_profile.yaml | 10 | 0 | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fjord_hes_profile_2026.yaml | 2 | 6 | 2 | 0 | 0 | 1 | 1 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 13 |
| fjord_reads_2025-11_p1.tsv | 4 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 4 | 2 | 0 | 0 | 3 | 0 | 4 | 0 |
| fjord_reads_2025-11_p2.tsv | 5 | 0 | 0 | 0 | 3 | 0 | 0 | 3 | 4 | 2 | 2 | 0 | 1 | 0 | 0 | 0 |
| fjord_reads_2025-11_p3.tsv | 6 | 0 | 0 | 0 | 2 | 0 | 0 | 3 | 4 | 2 | 0 | 0 | 1 | 0 | 2 | 0 |
| fjord_reads_2025-11_p4.tsv | 5 | 0 | 0 | 0 | 1 | 0 | 1 | 3 | 5 | 2 | 0 | 0 | 1 | 0 | 2 | 0 |
| fjord_reads_2025-11_p4b.tsv | 1 | 0 | 0 | 0 | 0 | 8 | 7 | 1 | 1 | 1 | 0 | 0 | 8 | 0 | 0 | 72 |
| fjord_reads_2025-11_p5.tsv | 5 | 0 | 0 | 0 | 2 | 0 | 0 | 3 | 4 | 2 | 1 | 0 | 1 | 0 | 2 | 0 |
| fjord_reads_2025-11_p6.tsv | 5 | 0 | 0 | 0 | 1 | 0 | 0 | 3 | 4 | 2 | 3 | 0 | 0 | 0 | 2 | 0 |
| hes_batch_manifest_2025-11.json | 0 | 0 | 4 | 3 | 0 | 15 | 6 | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 4 |
| hes_ingest_debug.log | 2 | 0 | 2 | 0 | 0 | 30 | 6 | 1 | 0 | 1 | 0 | 0 | 5 | 0 | 0 | 23 |
| hes_known_issues.md | 7 | 0 | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 |
| kvec_settlement_procedures_manual.docx | 7 | 0 | 4 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| lighting_burn_hour_exceptions_2025.xlsx | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| mdm_batch_control.log | 0 | 0 | 7 | 3 | 0 | 7 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mdm_october_close_reads.csv | 4 | 0 | 4 | 2 | 0 | 0 | 6 | 0 | 0 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| mdm_ops_mailbox_2025-11.mbox | 5 | 0 | 3 | 0 | 0 | 7 | 0 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| mdm_read_corrections.csv | 4 | 0 | 2 | 2 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 |
| mdm_registry_east.db | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mdm_registry_north.db | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mdm_registry_southwest.db | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| mdm_vee_estimates.tsv | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 7 | 0 | 0 | 0 | 0 |
| mdm_void_register.csv | 3 | 0 | 3 | 0 | 0 | 8 | 4 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| meter_accuracy_test_results_2025.docx | 5 | 0 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 |
| meter_clock_offsets.toml | 10 | 0 | 5 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| meter_registry_migration_wave3.xlsx | 3 | 0 | 3 | 2 | 0 | 12 | 25 | 3 | 0 | 0 | 0 | 0 | 13 | 0 | 0 | 20 |
| net_metering_export_credit_rider.docx | 4 | 0 | 5 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 2 | 0 | 0 |
| netmetering_enrollments.csv | 3 | 0 | 3 | 0 | 0 | 7 | 0 | 0 | 1 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| photocell_burn_hours.json | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 |
| rate_code_crosswalk_2026.json | 1 | 0 | 1 | 0 | 0 | 5 | 8 | 1 | 0 | 0 | 19 | 0 | 12 | 0 | 0 | 20 |
| register_rollover.toml | 10 | 0 | 0 | 5 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| register_scaling.ini | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rider_applicability_matrix.html | 7 | 0 | 4 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| rider_schedule_2025.pdf | 2 | 0 | 3 | 3 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 0 | 0 |
| scada_15min_gapfill_2025-11.csv | 2 | 0 | 2 | 2 | 0 | 40 | 60 | 1 | 0 | 1 | 0 | 0 | 30 | 0 | 0 | 78 |
| scada_alarm_journal.log | 5 | 0 | 3 | 0 | 0 | 8 | 0 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| scada_errata_notice.md | 3 | 0 | 2 | 2 | 0 | 6 | 5 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| settlement_data_contract.md | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| settlement_procedures_manual_rev4_draft.docx | 3 | 0 | 2 | 0 | 0 | 5 | 5 | 2 | 0 | 0 | 0 | 0 | 4 | 3 | 0 | 40 |
| substation_east_monthly_report.pdf | 1 | 0 | 1 | 0 | 0 | 3 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 9 | 0 | 17 |
| substation_east_scada_2025-11.json | 5 | 0 | 3 | 2 | 6 | 0 | 0 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| substation_north_scada_2025-11.csv | 5 | 0 | 3 | 4 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| substation_south_historian.log | 3 | 0 | 3 | 2 | 6 | 0 | 0 | 2 | 0 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| substation_west_monthly_report.pdf | 3 | 0 | 4 | 2 | 6 | 0 | 0 | 3 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| tariff_book_agri_lighting_q4.pdf | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 6 | 0 | 2 | 0 | 0 |
| tariff_book_commercial_q4.pdf | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 6 | 0 | 2 | 0 | 0 |
| tariff_book_industrial_q4.docx | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 6 | 0 | 2 | 0 | 0 |
| tariff_book_residential_2026.pdf | 3 | 0 | 3 | 3 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 3 | 1 | 0 | 0 | 12 |
| tariff_book_residential_q4.docx | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 6 | 0 | 2 | 0 | 0 |
| tariff_errata_register.html | 2 | 0 | 1 | 1 | 0 | 5 | 6 | 1 | 0 | 0 | 3 | 1 | 0 | 0 | 0 | 0 |
| territory_rate_calendar.ics | 2 | 0 | 3 | 0 | 0 | 4 | 6 | 2 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| ufe_allocation_exemptions_register.pdf | 5 | 0 | 2 | 0 | 0 | 5 | 0 | 2 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| unmetered_fixture_audit_2025.xlsx | 5 | 5 | 2 | 2 | 0 | 4 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| unmetered_supply_inventory.json | 3 | 0 | 2 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 12 | 0 | 0 | 0 | 0 | 0 |
| vee_estimate_review_2025.xlsx | 3 | 0 | 5 | 0 | 0 | 0 | 12 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Traps: 3018 total, 1703 in scope, 1315 in decoys.

## Verification

tests/test.sh hardens the verifier and runs rewardkit; it writes no reward itself. tests/test_output.py regenerates the visible tier (SAMPLE_SEED, identical to environment/data: byte for byte except the SQLite page bytes of the four .db files, whose rows are identical) and the hidden tier (EVAL_SEED) inside the verifier. The hidden tier alone (the shipped corpus is unchanged) carries a fixture for each of four tie-breaks the visible inputs never reach, planted by `_tiebreak_fixtures` and `_ufe_tie_fixture` behind the `hidden` flag: a meter given a second November FAIL accuracy test so that the latest test date decides, and another given a same-date test so that the highest test id decides (contract section 4); a second VALIDATED revision of an in-window read correction, so that the highest revision decides (manual section 3); two APPROVED November tariff errata for one key issued the same day, so that the higher erratum number decides (manual section 6); and one approved SCADA erratum moved by a few Wh so that the UFE total lands with two equal-weight accounts tied at the largest-remainder cutoff, where the lower account id decides (contract section 8). It then re-derives both expected output sets, runs the delivered transform on the hidden tier twice and once relocated (each run from a root-staged 0644 copy, so an owner-only transform.py stays runnable, as an unprivileged user in its own session, capped at 1500 s, every leftover process killed), and compares exactly on both tiers. Grading keys off the semantic traps only: a test owns the exact output rows touched by the semantic traps of its family or decoy file. Representation traps (header drift, delimiters, encodings, locale formats and the like) are not graded on their own; a misparse caused by one surfaces in whichever test owns the affected row. Thirteen tests also own one share of the rows no semantic trap claims (t12 the settlement summary, t16 the residual account rows, dc02 the residual intervals, t04 the residual lighting rows, t10 the day-type rows, t09 the control report, feeder_balance_shape the feeder balance shape, and t02, t08, dc04, dc13, dc05, dc14 the residual meter and read-resolution rows of the Aurora, Borealis, Cirrus, Delta, CIS and Fjord meters). Eight of them (t09, t10, t16, dc02, dc04, dc05, dc13, feeder_balance_shape) carry no semantic trap on either tier and grade only their residual share. A row graded by value in one test is seen only by its key in the others. Each check needs only the deliverables it compares, so a missing deliverable costs the checks that grade it rather than the whole channel, and a check that compares nothing never passes. Account rows are compared without their ufe_wh, ufe_charge_cents and total_cents columns everywhere except t12, which grades those three columns once for every account together with the settlement summary, so a misread record costs four checks rather than every test that owns account rows: the test owning its meter row, the test owning its account row, the test owning that feeder's feeder_balance.json object (t03, t05 or dc11) and t12. The control report carries no copyable count: the vendor manifest disagrees with the parsed data rows on 15 of the 34 read files, the batch log on 11, and the two disagree with each other, so data_rows is earned by parsing each container while manifest_rows is the vendor's number reported unchanged. Files on both sides of that split sit in t09's residual share and in dc08's graded share on both tiers, which leaves no fixed preference between the two delivered counts that could pass either test.

Channel A: 32 positive checks worth 146 weight, 4 negative checks worth -18. Positives are weight 5 except the five narrow decoy checks dc01, dc06, dc07, dc08 and dc11 (weight 3) and the shape check feeder_balance_shape (weight 1).

- `t01_identifier_canonicalisation` (5)
- `t02_unit_and_scale` (5)
- `t03_time_and_calendar` (5)
- `t04_locale_numerics` (5)
- `t05_sentinels` (5)
- `t06_voided_and_cancelled` (5)
- `t07_superseded_revisions` (5)
- `t08_header_and_schema_drift` (5)
- `t09_delimiters_and_quoting` (5)
- `feeder_balance_shape` (1)
- `t10_encoding_and_line_endings` (5)
- `t11_window_boundaries` (5)
- `t12_precision_and_rounding` (5)
- `t13_referential_integrity` (5)
- `t14_prose_scope_rules` (5)
- `t15_valid_outliers` (5)
- `t16_decoy_authority` (5)
- `dc01_december_master` (3)
- `dc02_scada_gapfill` (5)
- `dc03_fjord_resend` (5)
- `dc04_cirrus_usage_crosswalk` (5)
- `dc05_legacy_crosswalk` (5)
- `dc06_restated_rate_history` (3)
- `dc07_rate_crosswalk_2026` (3)
- `dc08_vendor_manifest` (3)
- `dc09_draft_manual` (5)
- `dc10_tariff_2026` (5)
- `dc11_east_pdf_report` (3)
- `dc12_ingest_debug_log` (5)
- `dc13_dw_snapshot` (5)
- `dc14_fjord_profile_2026` (5)
- `dc15_portal_export` (5)
- `negative_hardcoded_sample_answers` (-5)
- `negative_filename_dependent_behaviour` (-5)
- `negative_io_outside_argument_dirs` (-5)
- `negative_nondeterministic_output` (-3)

Channel B: tests/judge.toml, 11 criteria (6 positive worth 18, 5 negative worth -17) on invariant checks, rule-based conflict resolution, reading order, decoy declarations, reuse, code quality, honesty and boundaries. tests/reward.toml gives each channel half of the reward.

### Test to rule trace

| test | rule locators |
|---|---|
| t01_identifier_canonicalisation | R-DUPLICATE: contract section 3 last paragraph; R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-RATE-CODE: manual section 5 (latest effective entry) |
| t02_unit_and_scale | R-AURORA-UNIT: aurora_hes_profile.yaml firmware_rules; R-CT-CHANGE: contract section 4 (multiplier in force); R-CT-VERIFY: contract section 4 (verification CORRECT_RATIO); R-FIXTURE-AUDIT: contract section 5 (audit findings); R-FORMAT-T2: contract section 9 (format) and the head-end profile of the file |
| t03_time_and_calendar | R-CLOCK: contract section 3 item 3; meter_clock_offsets.toml header; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-SCADA-TIME: contract section 1 and 7 (repeated hour, interval-ending) |
| t04_locale_numerics | R-CIRRUS-LOCALE: cirrus_hes_profile.yaml decimal_separator; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file |
| t05_sentinels | R-DELTA-EST: manual section 4; delta_ingest.ini est_flag; R-SCADA: contract section 7 (invalid intervals); R-SENTINEL: head-end profile missing_values |
| t06_voided_and_cancelled | R-BATCH: manual section 4 (batch control); R-CT-VERIFY: contract section 4 (verification CORRECT_RATIO); R-DAYTYPE: contract section 6 (HOLIDAY over CPP, DTEND exclusive, CANCELLED ignored); R-DISCONNECT: contract section 5; disconnection register SOX note; R-FIXTURE-AUDIT: contract section 5 (audit findings); R-HOLD: manual section 4; mailbox cutoff notice |
| t07_superseded_revisions | R-CORRECTION: manual section 3 (1); R-DAYTYPE: contract section 6 (HOLIDAY over CPP, DTEND exclusive, CANCELLED ignored); R-DUPLICATE: contract section 3 last paragraph; R-SCADA-ERRATA: manual section 7 (1); R-TARIFF-ERRATA: manual section 6; errata register header; R-VEE: manual section 3 (3) |
| t08_header_and_schema_drift | R-BOREALIS-CHANNEL: borealis_channel_map.toml; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file |
| t09_delimiters_and_quoting | control_report.json batches: contract section 9 (data_rows counts the data records in the file, which depend on quoted newlines, embedded commas and trailing delimiters per each head-end profile) and manual section 4 (a delivered count that disagrees with the file is reported, never substituted); no semantic trap of family T9 exists |
| feeder_balance_shape | feeder_balance.json: contract section 9 (`{"feeders": {F01: {...}, ...}}`, one object per feeder F01-F12, JSON written with json.dumps(obj, indent=2, sort_keys=True) and a newline) |
| t10_encoding_and_line_endings | daytype_calendar.csv: contract section 2 (record terminators, calendar continuation lines) and section 6 (day types); no semantic trap of family T10 exists |
| t11_window_boundaries | R-APPLICABILITY: contract section 6 (latest applicability flag); R-DAYTYPE: contract section 6 (HOLIDAY over CPP, DTEND exclusive, CANCELLED ignored); R-DISCONNECT: contract section 5; disconnection register SOX note; R-FIXTURE: contract section 5 (fixture service window); R-FORMAT-T11: contract section 9 (format) and the head-end profile of the file; R-NEM: contract section 5 (APPROVED window) |
| t12_precision_and_rounding | R-ACCURACY: contract section 4 (accuracy correction); R-FORMAT-T12: contract section 9 (format) and the head-end profile of the file |
| t13_referential_integrity | R-MERGE-CHAIN: manual section 5 (transitive chains); R-REMOVED-METER: contract section 3 item 3 (service window); R-UNKNOWN-METER: contract section 2 last sentence; R-VACANCY: contract section 5 (FINAL account) |
| t14_prose_scope_rules | R-DISCONNECT: contract section 5; disconnection register SOX note; R-EXPORT-UNIT: contract section 9 (format) and the head-end profile of the file; R-KNOWN-ISSUE: manual section 4; hes_known_issues.md remedies; R-RIDER-UNIT: contract section 9 (format) and the head-end profile of the file; R-TARIFF-UNIT: tariff book Note U |
| t15_valid_outliers | R-BURN-EXCEPTION: contract section 5 (exception hours); R-NEGATIVE: contract section 4 (invalidation); R-OUTLIER: contract section 4 (no outlier removal exists); R-RESET: contract section 4 (REGISTER_RESET); R-ROLLOVER: contract section 4 (90/10 rule); register_rollover.toml |
| t16_decoy_authority | contract section 9 |
| dc01_december_master | R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T10: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T9: contract section 9 (format) and the head-end profile of the file; R-LATE-MERGE: manual section 5 (late_posted exception) |
| dc02_scada_gapfill | R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T10: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-GAPFILL: manual section 7 (4) |
| dc03_fjord_resend | R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T10: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T9: contract section 9 (format) and the head-end profile of the file; R-RESEND: manual section 4 second paragraph; R-REVERSAL: manual section 4 second paragraph |
| dc04_cirrus_usage_crosswalk | R-CIRRUS-LINK: manual section 2 (device and period links); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T10: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file |
| dc05_legacy_crosswalk | R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-LEGACY-ATTR: manual section 2 (staging attributes not used); R-LEGACY-LINK: manual section 2 (ACTIVE crosswalk rows) |
| dc06_restated_rate_history | R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-RATE-REVERSAL: manual section 5 (Reversals sheet); R-RESTATED: manual section 5 (restated history not in force) |
| dc07_rate_crosswalk_2026 | R-EARLY-ADOPTER: manual section 5 (in-window migrations); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-RATE-ALIAS: manual section 5 (ACTIVE aliases) |
| dc08_vendor_manifest | R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-MANIFEST: manual section 4 (vendor manifest; the latest entry per file is reported and its count is not substituted for the parsed data rows); R-WITHDRAWN: manual section 4 (vendor manifest) |
| dc09_draft_manual | R-DRAFT: manual section 1 (drafts have no effect); R-DRAFT-ERRATA: manual section 1 (CAB-approved errata); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file |
| dc10_tariff_2026 | R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T12: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file; R-STORM: manual section 6 (Table S, APPROVED, on or before 2025-11-30); R-TARIFF-2026: manual section 6 (2026 base rates not in force) |
| dc11_east_pdf_report | R-EAST-REPORT: manual section 7 (presentation copy); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T12: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-RELAY-TEST: manual section 7 (2) |
| dc12_ingest_debug_log | R-DEBUG-ECHO: manual section 4 (echo lines carry no authority); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T10: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-QUARANTINE: manual section 4 (debug log) |
| dc13_dw_snapshot | R-DW-SNAPSHOT: manual section 2 (snapshot attributes not used); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-SPID-LINK: manual section 2 (time-valid sp_meter_xref) |
| dc14_fjord_profile_2026 | R-FJORD-MULT: fjord_hes_profile.yaml multiplier_applied; manual section 8; R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file |
| dc15_portal_export | R-DISPUTE: manual section 4 (portal disputes); R-FORMAT-T1: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T3: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T4: contract section 9 (format) and the head-end profile of the file; R-FORMAT-T8: contract section 9 (format) and the head-end profile of the file; R-PORTAL: manual section 4 (usage is customer information) |
| negative_hardcoded_sample_answers | instruction.md: reusable program, reads only DATA_DIR, identical bytes every run |
| negative_filename_dependent_behaviour | instruction.md: reusable program, reads only DATA_DIR, identical bytes every run |
| negative_io_outside_argument_dirs | instruction.md: reads nothing outside DATA_DIR, writes nothing outside OUT_DIR |
| negative_nondeterministic_output | instruction.md: reusable program, reads only DATA_DIR, identical bytes every run |

## Root cause

**Authority is documented, not inferred.** Every conflict is decided by a rule in a different file than the conflict: the manual decides between registries, extracts, profiles and errata; the contract decides the arithmetic.

**State crosses records.** A register difference needs the previous accepted anchor, so one wrong boundary moves energy into another day, another day type and another account's UFE share.

**The balance couples everything.** UFE is the residual of every input; its allocation touches every non-exempt account.

**Red lines.** No reading of /tests, no edits to /app/data, no network, no hard-coded visible values.

## Solution shape

1. Load the contract appendix (connectivity), manual tables, CAB decisions and approved draft errata.
2. Load registries, orders, CT verifications, clock offsets, digits, collector events.
3. Parse the six head-end families with their profiles and crosswalks into candidate reads.
4. Apply exclusions, snap to boundaries, resolve corrections, actuals and estimates.
5. Difference registers over anchors into daily Wh with multipliers and accuracy corrections.
6. Resolve accounts, vacancy, disconnection, export eligibility, rate codes and day types; price.
7. Compute lighting deemed energy, SCADA injection by precedence, losses, UFE, allocation and price.
8. Write the nine deliverables in contract section 9 formats.

## Ordered plan

1. Read the contract before writing any parser (R3), and the manual with it.
2. Inventory files and read every header, banner and footer; classify partial-authority files (R4).
3. Build parsers family by family, checking parsed counts against the manifest and trailers (R1).
4. Resolve conflicts only by cited rules (R2); revise when a residual or count check fails (R1).
5. Run the transform on a relocated or altered copy (R5); keep transform.py split into functions that each do one job a reader can follow (R6).

Human expert estimate (3-4 days): day 1 reading 100 files and the governing documents (6-8 h); day 2 six parsers and identity resolution (8 h); day 3 boundary precedence, register arithmetic and billing joins (8 h); day 4 SCADA, tariffs, UFE and reconciliation debugging against residuals and control counts (6-8 h).

## Pitfalls

- Trust the newest account master (cis_account_master_2025-12.csv) for status and rate codes: fails dc01, t06, t16.
- After rejecting the December extract, ignore it entirely: fails dc01, t07, t13.
- Use the analytics gap-fill series for every interval because it has no gaps: fails dc02, t16, t05.
- Drop the gap-fill file entirely: fails dc02, t05, t06.
- Treat the Fjord period 4 resend as the corrected period 4: fails dc03, t07.
- Ignore the resend wholesale: fails dc03, t06.
- Link Cirrus devices through any usage row, VOID rows included: fails dc04, t13.
- Use Cirrus usage kWh as consumption instead of differencing registers: fails dc04, t16.
- Resolve legacy ids through any crosswalk row, SUPERSEDED included: fails dc05, t13.
- Take multipliers from the migration workbook Attributes sheet: fails dc05, t02, t16.
- Apply the restated rate history because it is tidier: fails dc06, t16.
- Ignore the restated workbook after rejecting it: fails dc06, t06.
- Resolve legacy rate aliases with the first matching alias row: fails dc07, t07, t01.
- Ignore the 2026 crosswalk because it is a 2026 document: fails dc07, t11.
- Ignore the vendor manifest as vendor-side noise: fails dc08, t06, t09.
- Use the first manifest entry per file: fails dc08, t07.
- Report a delivered count (vendor record_count or batch log rows=) as data_rows instead of counting the file: fails t09, dc08.
- Adopt the revision 4 draft rules because the draft is newer: fails dc09, t07.
- Ignore the draft wholesale: fails dc09, t11.
- Ignore the 2026 tariff filing as out of period: fails dc10, t11.
- Apply every Table S row: fails dc10, t06.

## Provenance

```yaml
uuid: daaca581-de32-5fc7-bd44-dd51c8f26be3
instance_id: daaca581-de32-5fc7-bd44-dd51c8f26be3
task_name: terminal-bench/daaca581-de32-5fc7-bd44-dd51c8f26be3
fix_patch_sha256: 722f75393acbd9a924b5f817850df51113a20fa284f96036730be9bd4209ca73  # sha256 of solution/solve.sh
solve_py_sha256: 01871851ef60846d60dcb27a3b02f0847dcd3c68fe8b3b0b240b2cfd9c4fbc05  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # Harbor Step 10 figures are recorded in the hand-off report, test channel only
```
