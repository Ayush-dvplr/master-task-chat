# TRUTH.md - 9f5486ac-ace6-5767-85e3-14ebb268f410

## Defect

Release TR-2026.09 of the Sentinel card-fraud training set has to be built from 100 delivered exports that disagree, overlap and partly impersonate each other. Nothing in the corpus is broken by accident: every hazard is documented somewhere in /app/data, usually in a different file from the data it governs. The agent must build a reusable builder (/app/out/transform.py) and the nine release outputs, and the same builder is re-run by the verifier on the hidden next release (TR-2027.01) as a delta release on top of the agent's own outputs.

1. (focal) Six transaction systems encode the same payment differently (offset ISO, epoch ms, local account time, local merchant time, terminal clock with skew); dedup and every partition control depend on normalizing them. Defeated tests: exclusion_register_exact, source_manifest_exact.
2. (focal) Labels must be resolved from analyst cases, three chargeback networks and weighted vendor votes with maturity censoring. Defeated test: labels_exact.
3. (focal) Merchant risk and IP reputation features must be joined point-in-time with publication schedules, outages, lags and corrections. Defeated test: point_in_time_features_exact.
4. (focal) Splits must follow device-linked account clusters with exemptions, pins and salted hashing. Defeated test: cluster_splits_exact.
5. (focal) Preprocessing, vocabularies and class weights are fitted on the train split only and frozen for delta releases. Defeated test: preprocessing_state_exact, eval_delta_examples_exact.
6. (focal) The release is gated on lineage controls of all 100 files; one missing or mis-parsed file holds the release. Defeated test: every test (HELD outputs); the HELD branch itself is graded by held_release_when_catalog_file_missing, which removes one catalog file from the hidden exports.
7. (focal) The builder must reproduce the hidden delta release exactly from the prior state it wrote itself. Defeated test: eval_delta_state_and_exclusions_exact.
8. (drift) Robust scaling with nearest-rank quantiles replaces the textbook StandardScaler/interpolated percentiles. Defeated test: preprocessing_state_exact.
9. (drift) Effective-number class weights replace inverse-frequency weights. Defeated test: class_weights_exact.
10. (drift) Point-in-time availability uses publication instant plus lag, not the snapshot as_of date. Defeated test: point_in_time_features_exact.
11. (drift) Immature labels are censored, not defaulted to legitimate; analyst-confirmed fraud is exempt. Defeated test: labels_exact.
12. (drift) Kiosk and listed shared devices never link accounts, although union-find over all devices is the obvious build. Defeated test: cluster_splits_exact.
13. (trap) T1 near-duplicate identifiers (case, padding, NBSP, homoglyphs). Defeated test: slice_t1_near_duplicate_keys.
14. (trap) T2 unit flips (major/minor keys, x10 scores). Defeated test: slice_t2_t4_t12_numeric_formats.
15. (trap) T3 time encodings (offsets, epochs, zones, skew, serials, DST). Defeated test: slice_t3_time_zones_epochs.
16. (trap) T4 EU numerics and grouping characters. Defeated test: slice_t2_t4_t12_numeric_formats.
17. (trap) T5 sentinels with source-specific meaning. Defeated test: slice_t5_sentinels.
18. (trap) T6 voids, withdrawals, reversals, recalls, quarantines. Defeated test: slice_t6_voids_reversals.
19. (trap) T7 supersession (revisions, corrections, latest-wins). Defeated test: slice_t7_supersession.
20. (trap) T8 header drift mid-file. Defeated test: slice_t8_t9_header_drift_and_framing.
21. (trap) T9 record framing. Defeated test: slice_t8_t9_header_drift_and_framing.
22. (trap) T10 mixed encodings and line ends. Defeated test: slice_t10_encodings_line_ends.
23. (trap) T11 half-open window boundaries, including one approved SDK event dated exactly at window_end in each corpus (exclusion outside_window). Defeated test: slice_t11_boundaries.
24. (trap) T12 half-even conversion ties. Defeated test: slice_t2_t4_t12_numeric_formats.
25. (trap) T13 referential breaks (merges, crosswalks, reassigned ARNs). Defeated test: slice_t13_referential_breaks.
26. (trap) T14 prose and table overrides. Defeated test: slice_t14_prose_overrides.
27. (trap) T15 statistical bait (legitimate outliers). Defeated test: slice_t15_statistical_bait.
28. (trap) T16 decoys agreeing on 95 percent of rows. Defeated test: slice_t16_decoy_agreement.

The reference implementation is Python (solution/solve.py, installed as /app/out/transform.py by solve.sh). Two channels grade the run: deterministic rewardkit checks in tests/test_output.py and LLM-judged trajectory criteria in tests/judge.toml; tests/reward.toml gives each channel half of the reward.

Out of bounds: a builder that replays this release on the next release's exports (negative_hardcoded_sample_answers, -5: fires when the completed hidden run reports this release's release_id or more than half of its rows equal visible rows, compared on per-record facts only; a crash, timeout or wrong hidden run is graded by the eval checks, never as hardcoding), behaviour that depends on the input directory path (negative_filename_dependent_behaviour, -5), reading /app/data when another input directory is given (negative_reads_training_corpus_at_runtime, -5), and nondeterministic output (negative_nondeterministic_output, -3). The path and /app/data checks only fire for a builder whose same-condition repeat run is byte-identical, so a nondeterministic builder pays -3 once.

## Load-bearing work

Fourteen artifacts are collected, and every one of them is graded:

- `/app/out/transform.py`
- `/app/out/normalized.jsonl`
- `/app/out/summary.json`
- `/app/out/data_quality.json`
- `/app/out/product_summary.json`
- `/app/out/region_central.json`
- `/app/out/region_east.json`
- `/app/out/region_north.json`
- `/app/out/region_south.json`
- `/app/out/region_west.json`
- `/app/out/segment_consumer.json`
- `/app/out/segment_corporate.json`
- `/app/out/segment_enterprise.json`
- `/app/out/segment_smb.json`

### Concepts (each load-bearing, each feeding the next)

- C1 Point-in-time feature joins with availability lag: merchant risk and IP reputation values are usable only once their effective publication instant (calendar or schedule, delayed past feature-store outages) plus the source lag (default, hourly override, partial rev2) is at or before event_time; corrections become visible at corrected_at + lag. Feeds C5 (missingness drives imputation) and C8. Graded by slice_t3_time_zones_epochs, point_in_time_features_exact.
- C2 Label resolution with maturity censoring: analyst > chargeback > vendor > no_chargeback, fraud-class first chargebacks inside [event date, +90d), withdrawals and reversals void disputes, immature examples are censored unless analyst-confirmed fraud, vendor votes weighted by tier at submission. Labels feed C6 (class counts) and C8 (AUC). Graded by labels_exact.
- C3 Cross-system deduplication and keeper selection: errata first, then identifier resolution, replay removal and second-precision fingerprints with an auth code; keeper by system precedence then effective batch ingestion; attributes filled from members. Decides which record carries evidence (C2), velocity context (features) and which file a released example belongs to. Graded by exclusion_register_exact and source_manifest_exact.
- C4 Leakage-safe grouped splitting: device-linked account clusters by union-find (kiosk and listed shared devices exempt, revocations honoured), salted SHA-256 buckets on the cluster id, active pins forcing whole clusters, sticky splits in delta releases, OOT by time. The train split defines every fitted parameter (C5, C6, C7). Graded by cluster_splits_exact.
- C5 Train-only winsorization, imputation and robust scaling (expert variant): nearest-rank q(0.01)/q(0.99) clipping, median imputation and (x - median)/(q3 - q1) on the train split only, exact rational arithmetic, half-even at 6 decimals. Textbook StandardScaler or interpolated percentiles break every row. Graded by preprocessing_state_exact.
- C6 Effective-number class weights (expert variant): w_c proportional to (1 - beta)/(1 - beta^n_c) with beta = 0.9999, normalized to sum 2, on train counts after censoring and dedup; sklearn 'balanced' inverse frequency is the tempting wrong variant. Graded by class_weights_exact.
- C7 Train-fitted categorical vocabularies with rare bucketing: tokens with train count >= 25 indexed by descending count then token, index 0 for rare and unseen tokens; the token itself comes from C3 attribute fill (entry code, BIN) and from point-in-time merchant classification. Graded by categorical_vocab_exact.
- C8 Baseline evaluation and drift monitoring: linear baseline score from the 6-decimal scaled features plus merchant offsets, Mann-Whitney AUC with half ties per split, PSI between frozen train deciles and the OOT split in 40-digit decimal arithmetic. Graded by scores_auc_psi_exact and slice_reports_exact.

Expert-only variants (drift): C1 availability instant + lag, C2 maturity censoring, C5 nearest-rank robust scaling, C6 effective-number weights.

### Measured release

Visible release: counts {"train": {"n": 23746, "positives": 1223}, "val": {"n": 5760, "positives": 306}, "test": {"n": 7139, "positives": 364}, "oot": {"n": 11034, "positives": 595}}; AUC {"val": "0.544254", "test": "0.557329", "oot": "0.551536"}. Hidden delta release counts {"train": {"n": 6524, "positives": 352}, "val": {"n": 1705, "positives": 102}, "test": {"n": 1957, "positives": 105}, "oot": {"n": 3057, "positives": 196}}.

### 100-file inventory

| # | file | type | records | scope | unique contribution | depends on | depended on by | ablation |
|---|---|---|---|---|---|---|---|---|
| 1 | settlement_nbp_2026-05.csv | csv | 7799 | in-scope | settlement records (precedence-1 keepers) for May; ARN link targets | 11 files | 2 files | 0.0066 (HELD) |
| 2 | settlement_nbp_2026-06.csv | csv | 7881 | in-scope | settlement records for June | 11 files | 2 files | 0.0066 (HELD) |
| 3 | settlement_nbp_2026-07.csv | csv | 8281 | in-scope | settlement records for July | 11 files | 2 files | 0.0066 (HELD) |
| 4 | settlement_nbp_2026-08.csv | csv | 8636 | in-scope | settlement records for August outside the export incident | 13 files | 2 files | 0.0066 (HELD) |
| 5 | settlement_nbp_lookback_2026-04.csv | csv | 5706 | in-scope | lookback-only settlement records: velocity context and lookback_context exclusions | 11 files | 2 files | 0.0066 (HELD) |
| 6 | gateway_auth_2026-05.tsv | tsv | 9805 | in-scope | gateway auths (declines, descriptors, IP refs) May | 12 files | 2 files | 0.0066 (HELD) |
| 7 | gateway_auth_2026-06.tsv | tsv | 5509 | in-scope | gateway auths June | 12 files | 2 files | 0.0066 (HELD) |
| 8 | gateway_auth_2026-07.tsv | tsv | 5781 | in-scope | gateway auths July | 13 files | 2 files | 0.0066 (HELD) |
| 9 | gateway_auth_2026-08.tsv | tsv | 6045 | in-scope | gateway auths August | 12 files | 2 files | 0.0066 (HELD) |
| 10 | sdk_events_2026-05_2026-06.jsonl | jsonl | 7095 | in-scope | mobile SDK events (devices, IP refs) May-June | 11 files | 2 files | 0.0066 (HELD) |
| 11 | sdk_events_2026-07_2026-08.jsonl | jsonl | 5649 | in-scope | mobile SDK events Jul-Aug, including one event at window_end | 12 files | 2 files | 0.0066 (HELD) |
| 12 | core_legacy_batch_2026-05_2026-06.txt | fwf | 6388 | in-scope | core-legacy records in local account time May-June | 14 files | 2 files | 0.0066 (HELD) |
| 13 | core_legacy_batch_2026-07_2026-08.txt | fwf | 5367 | in-scope | core-legacy records Jul-Aug outside the extract incident | 15 files | 2 files | 0.0066 (HELD) |
| 14 | partner_api_orders_eu_2026-05_2026-06.xml | xml | 6716 | in-scope | EU partner orders (local merchant time, EU numerics) May-June | 13 files | 2 files | 0.0066 (HELD) |
| 15 | partner_api_orders_eu_2026-07_2026-08.xml | xml | 5212 | in-scope | EU partner orders Jul-Aug outside the feed incident | 14 files | 2 files | 0.0066 (HELD) |
| 16 | terminal_batches_2026-05_2026-06.parquet | parquet | 7067 | in-scope | card-present terminal records (clock skew) May-June | 12 files | 2 files | 0.0066 (HELD) |
| 17 | terminal_batches_2026-07_2026-08.parquet | parquet | 5533 | in-scope | card-present terminal records Jul-Aug | 12 files | 2 files | 0.0066 (HELD) |
| 18 | settlement_nbp_2026-08_final.csv | csv | 8968 | decoy D1 | only copy of set_m4 partition controls; only copy of settlement rows inside the export incident window | 11 files | 3 files | 0.0066 (HELD) |
| 19 | gateway_auth_2026-07_replay.tsv | tsv | 5781 | decoy D2 | only ARN links for July gateway records | 11 files | 3 files | 0.0066 (HELD) |
| 20 | sdk_events_2026-07_2026-08_dedup.jsonl | jsonl | 5570 | decoy D4 | only copy of sdk_b partition controls | 11 files | 3 files | 0.0066 (HELD) |
| 21 | partner_api_orders_eu_2026-07_2026-08_resend.xml | xml | 5319 | decoy D8 | only copy of par_b partition controls; only partner rows inside the feed incident window | 11 files | 3 files | 0.0066 (HELD) |
| 22 | core_legacy_batch_2026-07_2026-08_reextract.txt | fwf | 5450 | decoy D15 | only trailer controls of leg_b; only legacy rows inside the extract incident window | 11 files | 3 files | 0.0066 (HELD) |
| 23 | chargebacks_kestrel_2026-09.csv | csv | 6650 | in-scope | Kestrel dispute lifecycle rows | 9 files | 2 files | 0.0066 (HELD) |
| 24 | chargebacks_orbis_2026-09.tsv | tsv | 6564 | in-scope | Orbis dispute rows (legacy codes before the renumbering day) | 9 files | 2 files | 0.0066 (HELD) |
| 25 | chargebacks_vantage_2026-09.xml | xml | 6360 | in-scope | Vantage dispute rows | 8 files | 2 files | 0.0066 (HELD) |
| 26 | dispute_notices_2026-09.mbox | mbox | 5200 | in-scope | Kestrel/Orbis withdrawal and reinstatement notices | 5 files | 4 files | 0.0066 (HELD) |
| 27 | case_management_2026-09.db | sqlite | 10000 | in-scope | primary analyst cases and decisions | 7 files | 2 files | 0.0066 (HELD) |
| 28 | case_reversion_audit_2026-09.log | log | 5301 | in-scope | only record of reverted decisions | 5 files | 3 files | 0.0066 (HELD) |
| 29 | vendor_annotations_batch_A_2026-09.jsonl | jsonl | 7605 | in-scope | vendor votes of odd batches | 10 files | 2 files | 0.0066 (HELD) |
| 30 | vendor_annotations_batch_B_2026-09.jsonl | jsonl | 7716 | in-scope | vendor votes of even batches | 11 files | 2 files | 0.0066 (HELD) |
| 31 | annotation_task_assignments_2026-09.xml | xml | 5107 | in-scope | task -> event record links | 5 files | 4 files | 0.0066 (HELD) |
| 32 | annotator_roster.xlsx | xlsx | 10000 | in-scope | annotator vendors and effective-dated tiers (1904 serials) | 5 files | 4 files | 0.0066 (HELD) |
| 33 | vendor_label_taxonomy_map_v2.tsv | tsv | 5040 | in-scope | raw vendor label -> class per guideline version | 5 files | 4 files | 0.0066 (HELD) |
| 34 | vendor_batch_manifest_2026-09.json | json | 5107 | in-scope | guideline version and recall status per task | 5 files | 4 files | 0.0066 (HELD) |
| 35 | arn_crosswalk_2026-09.db | sqlite | 5125 | in-scope | ARN -> event record links (all but July gateway) | 5 files | 5 files | 0.0066 (HELD) |
| 36 | vendor_annotations_batch_B_2026-09_relabel.jsonl | jsonl | 8958 | decoy D3 | only withdrawn-annotation flags; only VeriTask annotator id crosswalk | 5 files | 3 files | 0.0066 (HELD) |
| 37 | chargeback_case_tracker_2026-09.xlsx | xlsx | 5278 | decoy D6 | only ARN reassignments; only Vantage withdrawals | 5 files | 4 files | 0.0066 (HELD) |
| 38 | case_management_2026-09_replica.db | sqlite | 10052 | decoy D12 | only decisions recorded during the case-management outage | 5 files | 3 files | 0.0066 (HELD) |
| 39 | merchant_risk_snapshots_2026-05.xlsx | xlsx | 10000 | in-scope | merchant risk snapshots and corrections Apr-May | 7 files | 2 files | 0.0066 (HELD) |
| 40 | merchant_risk_snapshots_2026-06.xlsx | xlsx | 10000 | in-scope | merchant risk snapshots June | 7 files | 2 files | 0.0066 (HELD) |
| 41 | merchant_risk_snapshots_2026-07.xlsx | xlsx | 10000 | in-scope | merchant risk snapshots July | 7 files | 2 files | 0.0066 (HELD) |
| 42 | merchant_risk_snapshots_2026-08.xlsx | xlsx | 10000 | in-scope | merchant risk snapshots August | 8 files | 2 files | 0.0066 (HELD) |
| 43 | merchant_risk_snapshots_2026-08_v2.xlsx | xlsx | 5000 | decoy D5 | only merchant-risk void flags | 4 files | 3 files | 0.0066 (HELD) |
| 44 | ip_reputation_feed_2026-05_2026-06.jsonl | jsonl | 9124 | in-scope | IP reputation observations Apr-Jun | 7 files | 2 files | 0.0066 (HELD) |
| 45 | ip_reputation_feed_2026-07_2026-08.jsonl | jsonl | 6198 | in-scope | IP reputation observations Jul-Aug | 7 files | 2 files | 0.0066 (HELD) |
| 46 | ip_reputation_corrections_2026-09.tsv | tsv | 5475 | in-scope | IP observation voids and rescores | 4 files | 4 files | 0.0066 (HELD) |
| 47 | snapshot_publication_calendar_2026-09.ics | ics | 5508 | in-scope | merchant-risk publication instants and cancellations | 4 files | 6 files | 0.0066 (HELD) |
| 48 | feature_lag_overrides_2026-09.csv | csv | 7344 | in-scope | hourly lag overrides | 4 files | 7 files | 0.0066 (HELD) |
| 49 | feature_snapshot_registry_2026-09.json | json | 5508 | in-scope | withdrawn merchant-risk snapshots | 4 files | 6 files | 0.0066 (HELD) |
| 50 | feature_store_export_manifest_2026-09.json | json | 6120 | decoy D7 | only quarantined IP partitions | 4 files | 4 files | 0.0066 (HELD) |
| 51 | account_kyc_reviews_2026-09.xlsx | xlsx | 10000 | in-scope | KYC reviews and appeals | 5 files | 2 files | 0.0066 (HELD) |
| 52 | account_registry_2026-04.yaml | yaml | 5620 | in-scope | pre-revision segments/postals and base accounts | 4 files | 25 files | 0.0066 (HELD) |
| 53 | account_registry_2026-07.yaml | yaml | 6369 | in-scope | created_at corrections, effective changes, new accounts | 5 files | 2 files | 0.0066 (HELD) |
| 54 | account_registry_2026-09.yaml | yaml | 6558 | decoy D13 | only legacy-id crosswalk | 4 files | 4 files | 0.0066 (HELD) |
| 55 | account_merge_events_2026-09.log | log | 5100 | in-scope | account merges recorded by the id resolver | 5 files | 3 files | 0.0066 (HELD) |
| 56 | account_merge_map_2026-09.json | json | 7294 | in-scope | account merges recorded by billing | 5 files | 3 files | 0.0066 (HELD) |
| 57 | merchant_master.parquet | parquet | 5600 | in-scope | merchant classification at base date, pre-window merges | 7 files | 24 files | 0.0066 (HELD) |
| 58 | merchant_master_2026-09.parquet | parquet | 5600 | decoy D9 | only in-window merchant merges | 4 files | 3 files | 0.0066 (HELD) |
| 59 | merchant_aliases_v2.csv | csv | 6409 | in-scope | effective-dated descriptor aliases | 4 files | 6 files | 0.0066 (HELD) |
| 60 | merchant_mcc_reassignments_2026-09.json | json | 6257 | in-scope | merchant classification history | 4 files | 3 files | 0.0066 (HELD) |
| 61 | merchant_settlement_tz.ini | ini | 5600 | in-scope | merchant zone aliases | 4 files | 4 files | 0.0066 (HELD) |
| 62 | device_link_events_2026-09.log | log | 6729 | in-scope | device LINK/UNLINK events | 8 files | 3 files | 0.0066 (HELD) |
| 63 | device_fingerprints_2026-09_reexport.parquet | parquet | 6622 | in-scope | device first_seen observations | 7 files | 3 files | 0.0066 (HELD) |
| 64 | device_link_revocations_2026-09.csv | csv | 5200 | in-scope | link revoke/restore actions | 4 files | 4 files | 0.0066 (HELD) |
| 65 | device_registry.yaml | yaml | 9600 | in-scope | device kinds (kiosk exemption) | 4 files | 3 files | 0.0066 (HELD) |
| 66 | bin_ranges_issuer.csv | csv | 6100 | in-scope | BIN prefix -> issuer group | 4 files | 2 files | 0.0066 (HELD) |
| 67 | consent_withdrawals_portal_2026-09.csv | csv | 5315 | in-scope | portal consent events | 6 files | 2 files | 0.0066 (HELD) |
| 68 | erasure_orders_legal_2026-09.json | json | 5100 | in-scope | executed erasure orders | 4 files | 3 files | 0.0066 (HELD) |
| 69 | opt_out_registry_support.ini | ini | 5660 | in-scope | support consent status | 4 files | 3 files | 0.0066 (HELD) |
| 70 | terminal_clock_skew.ini | ini | 5300 | in-scope | terminal clock skews | 4 files | 4 files | 0.0066 (HELD) |
| 71 | fx_rates_daily_2026-09.parquet | parquet | 7320 | in-scope | vendor FX rates (non-treasury currencies) | 5 files | 2 files | 0.0066 (HELD) |
| 72 | fx_reference_rates_treasury_2026-09.xml | xml | 5175 | in-scope | treasury fixings | 4 files | 24 files | 0.0066 (HELD) |
| 73 | fx_corrections_2026-09_final.csv | csv | 7320 | in-scope | vendor rate corrections | 4 files | 3 files | 0.0066 (HELD) |
| 74 | timezone_rules.toml | toml | 5323 | in-scope | zone rules and postal prefix zones | 4 files | 4 files | 0.0066 (HELD) |
| 75 | region_crosswalk_postal.csv | csv | 9200 | in-scope | postal -> region (KYC defaults) | 4 files | 3 files | 0.0066 (HELD) |
| 76 | release_build_specification.docx | docx | 5100 | in-scope | outputs contract, exclusion precedence, split-tender exceptions | 2 files | 40 files | 0.0066 (HELD) |
| 77 | label_policy_v3.docx | docx | 5600 | in-scope | label rules, merchant dispute profiles | 3 files | 18 files | 0.0066 (HELD) |
| 78 | label_policy_v4.docx | docx | 5100 | decoy D10 | only Orbis reason code renumbering table | 3 files | 3 files | 0.0066 (HELD) |
| 79 | split_and_leakage_policy.docx | docx | 5222 | in-scope | cluster/split rules, shared-device exemptions | 3 files | 5 files | 0.0066 (HELD) |
| 80 | preprocessing_standard.docx | docx | 5200 | in-scope | preprocessing rules, MCC sub-code risk groups | 3 files | 4 files | 0.0066 (HELD) |
| 81 | data_governance_charter.docx | docx | 6265 | in-scope | source authority windows (decoy demotion) | 4 files | 24 files | 0.0066 (HELD) |
| 82 | dedup_runbook.docx | docx | 5773 | in-scope | fingerprint/keeper rules, replay batch register | 3 files | 40 files | 0.0066 (HELD) |
| 83 | reason_code_catalog.pdf | pdf | 5250 | in-scope | reason code classes | 3 files | 5 files | 0.0066 (HELD) |
| 84 | feature_availability_spec.pdf | pdf | 6120 | in-scope | PIT rules, default lags, IP partition schedule | 3 files | 15 files | 0.0066 (HELD) |
| 85 | feature_availability_spec_rev2.pdf | pdf | 6120 | decoy D11 | only rev2 IP lag (effective from its scope date) | 3 files | 3 files | 0.0066 (HELD) |
| 86 | baseline_scorer_card.pdf | pdf | 5608 | in-scope | coefficients, merchant offsets, PSI rule | 4 files | 2 files | 0.0066 (HELD) |
| 87 | currency_and_fx_handbook.pdf | pdf | 5530 | in-scope | minor units, conversion rule, fixing calendar | 3 files | 29 files | 0.0066 (HELD) |
| 88 | timezone_and_clock_handbook.pdf | pdf | 5520 | in-scope | DST rules, zone aliases, serial epochs | 3 files | 4 files | 0.0066 (HELD) |
| 89 | annotation_guidelines.pdf | pdf | 5886 | in-scope | vote weights, gold-check failures | 3 files | 4 files | 0.0066 (HELD) |
| 90 | entry_mode_codes.html | html | 5160 | in-scope | entry code -> entry_mode | 3 files | 24 files | 0.0066 (HELD) |
| 91 | errata_bulletins_2026-09.html | html | 5100 | in-scope | record corrections | 3 files | 24 files | 0.0066 (HELD) |
| 92 | errata_bulletins_2026-09_consolidated.html | html | 5203 | decoy D14 | only errata withdrawals | 3 files | 2 files | 0.0066 (HELD) |
| 93 | source_register.md | md | 6219 | in-scope | catalog, column map, batch index | 99 files | 99 files | 0.0066 (HELD) |
| 94 | release_notes_TR-2026.05.md | md | 5100 | in-scope | retracted event refs | 3 files | 2 files | 0.0066 (HELD) |
| 95 | data_dictionary.md | md | 5280 | in-scope | identifier rules, sentinels, status codes | 3 files | 43 files | 0.0066 (HELD) |
| 96 | lineage_controls_2026-09.db | sqlite | 7484 | in-scope | lineage controls of every file | 99 files | 99 files | 0.0066 (HELD) |
| 97 | ingestion_delivery_audit_2026-09.log | log | 6052 | in-scope | effective batch ingestion (keeper tiebreak) | 3 files | 2 files | 0.0066 (HELD) |
| 98 | pipeline_incident_log_2026-09.log | log | 5200 | in-scope | incident windows (partial decoys, outages) | 3 files | 6 files | 0.0066 (HELD) |
| 99 | release_config.toml | toml | 5201 | in-scope | release parameters, pins | 4 files | 2 files | 0.0066 (HELD) |
| 100 | feature_definitions.toml | toml | 5610 | in-scope | feature definitions, KYC default tiers | 3 files | 39 files | 0.0066 (HELD) |

### Decoys

| decoy | file | looks authoritative because | demoted by | load-bearing roles | ignore fails | trust fails |
|---|---|---|---|---|---|---|
| D1 | settlement_nbp_2026-08_final.csv | FINAL label, reconciled re-run, newest delivery, fixes amounts | charter: event_rows only inside the settlement-export incident | (a) only set_m4 controls; (e) only rows inside the incident window | HELD (controls) | slice_t16, decoy_group_event_mirrors |
| D2 | gateway_auth_2026-07_replay.tsv | cleaner gateway schema with ARN column | own header comment + charter (crosswalk only) | (c) only July ARN links; (d) | decoy_group_event_mirrors | slice_t16 |
| D3 | vendor_annotations_batch_B_2026-09_relabel.jsonl | relabel pass marked approved | annotation guidelines + charter | (b) only withdrawn annotations; (c) VeriTask id crosswalk | decoy_group_label_sources | decoy_group_label_sources |
| D4 | sdk_events_2026-07_2026-08_dedup.jsonl | 'dedup' export already deduplicated | own _meta line authoritative false + charter | (a) only sdk_b controls; (d) | HELD (controls) | slice_t16 |
| D5 | merchant_risk_snapshots_2026-08_v2.xlsx | v2 revision of the August risk workbook | workbook title SUPERSEDED DRAFT + charter | (b) only void flags; (d) | decoy_group_feature_sources | slice_t16 |
| D6 | chargeback_case_tracker_2026-09.xlsx | operations tracker with FINAL outcomes | label policy v3 + charter | (c) only ARN reassignments; (b) only Vantage withdrawals | decoy_group_label_sources | decoy_group_label_sources |
| D7 | feature_store_export_manifest_2026-09.json | per-partition export manifest with lags | status candidate + charter (void_evidence only) | (b) only quarantines; (d) | decoy_group_feature_sources | decoy_group_feature_sources |
| D8 | partner_api_orders_eu_2026-07_2026-08_resend.xml | complete partner resend | charter: event_rows only inside the partner-feed incident | (a) only par_b controls; (e) | HELD (controls) | slice_t16 |
| D9 | merchant_master_2026-09.parquet | newest merchant master | charter: merges only | (c) only in-window merges; (e) value columns out of scope | decoy_group_feature_sources | slice_t16 |
| D10 | label_policy_v4.docx | label policy v4 approved for the next cycle | charter footnote + own footnote | (c) only Orbis renumbering; (d) | decoy_group_documents | labels_exact |
| D11 | feature_availability_spec_rev2.pdf | availability spec rev2 | own scope paragraph + charter partial grant | (e) partial by date; (d) | decoy_group_feature_sources | decoy_group_feature_sources |
| D12 | case_management_2026-09_replica.db | case replica holding more decisions | charter: label_evidence only inside the case-management outage | (e) only outage decisions; (b) | decoy_group_label_sources | slice_t16 |
| D13 | account_registry_2026-09.yaml | newest account registry snapshot | status provisional + charter (crosswalk only) | (c) only legacy-id crosswalk; (d) | HELD-free but legacy rows invalid | slice_t16 |
| D14 | errata_bulletins_2026-09_consolidated.html | consolidated errata edition | own paragraph 'NOT the source of record' + charter | (b) only errata withdrawals; (d) | decoy_group_documents | slice_t16 |
| D15 | core_legacy_batch_2026-07_2026-08_reextract.txt | core-legacy re-extract | charter: event_rows only inside the legacy-extract incident | (a) only leg_b trailer controls; (e) | HELD (controls) | slice_t16 |

Out of bounds by design: no shipped expected outputs, no sample answer files; every expected value lives only as a digest in tests/test_output.py.

## Verification

tests/test.sh hardens /logs/verifier and runs rewardkit over /tests. Channel A (tests/test_output.py) carries 31 positive checks with positive weight total 149 (one shape check at weight 1, twenty-nine hard checks at weight 5, and the HELD check at weight 3) and four negative checks with negative weight total -18, so the theoretical range is -18/149 to 1. Partial-solver ceiling from the shape check alone: 1/149. Channel B (tests/judge.toml) carries 11 binary criteria with positive total 19 and negative total 14. tests/reward.toml combines both channels, each at half weight (0.5/149 and 0.5/19).

The trap and decoy slice checks compare per-record facts only (example_id, event_ref, account_id, cluster_id, split, event_time, label, label_source, and the exclusion reason or cluster split of the touched records); the train-fitted fields (scaled features, categorical indices, sample_weight, score) are graded once, by the concept checks, so one wrong train label costs labels_exact, class_weights_exact, scores_auc_psi_exact and the hidden checks rather than every slice.

The hidden tier regenerates the next release's exports with the corpus generator whose readable source is embedded in tests/test_output.py as GENERATOR_SOURCES (15 Python modules; integrity digest GENERATOR_SHA256, the SHA-256 over each sorted file name, a NUL, its UTF-8 source and a NUL). The generator writes only into its own output directory and makes no network calls. The expected per-record digests of the trap slices are stored as zlib-compressed JSON data in SLICES; nothing decoded from it is executed. The delivered builder runs as uid 65534 in its own session, with read-only inputs, a private output directory and a 1500-second limit per run (the instruction promises 25 minutes); its process group and every remaining uid-65534 process are killed after each run. Five runs at most (primary, repeat, moved path, poisoned /app/data, HELD variant) plus generation (900-second limit) fit inside the 9000-second verifier timeout.

Positive checks:

- outputs_have_documented_shape (1)
- point_in_time_features_exact (5)
- labels_exact (5)
- exclusion_register_exact (5)
- source_manifest_exact (5)
- cluster_splits_exact (5)
- preprocessing_state_exact (5)
- class_weights_exact (5)
- categorical_vocab_exact (5)
- scores_auc_psi_exact (5)
- slice_reports_exact (5)
- slice_t1_near_duplicate_keys (5)
- slice_t2_t4_t12_numeric_formats (5)
- slice_t3_time_zones_epochs (5)
- slice_t5_sentinels (5)
- slice_t6_voids_reversals (5)
- slice_t7_supersession (5)
- slice_t8_t9_header_drift_and_framing (5)
- slice_t10_encodings_line_ends (5)
- slice_t11_boundaries (5)
- slice_t13_referential_breaks (5)
- slice_t14_prose_overrides (5)
- slice_t15_statistical_bait (5)
- slice_t16_decoy_agreement (5)
- decoy_group_event_mirrors (5)
- decoy_group_label_sources (5)
- decoy_group_feature_sources (5)
- decoy_group_documents (5)
- eval_delta_examples_exact (5)
- eval_delta_state_and_exclusions_exact (5)
- held_release_when_catalog_file_missing (3)

Negative checks: negative_hardcoded_sample_answers (-5), negative_filename_dependent_behaviour (-5), negative_reads_training_corpus_at_runtime (-5), negative_nondeterministic_output (-3).

Judged criteria:

- R1 r1_reconciles_lineage_controls (+3): The agent compares its parsed event exports with the partition controls of the lineage controls database, counting records and summing amounts per partition, before it writes the final release outputs.
- R2 r2_triages_lookalike_with_charter (+3): The agent decides how to use at least one look-alike export, such as a file marked final, v2, rev2, replica, relabel, resend or consolidated, from the source authority windows of the governance charter.
- R3 r3_checks_candidate_accounting (+3): The agent checks that every candidate record of each event export ends up either as a released example or as exactly one exclusion, and reports the result of that check.
- R4 r4_checks_cluster_leakage (+3): The agent checks that every account cluster of its release appears in at most one of train, val and test.
- R5 r5_reruns_builder_for_determinism (+1): The agent runs its builder at least twice on the same inputs and compares the two outputs.
- R6 r6_reports_status_and_counts (+3): The response states the release status and the number of released examples in each of the splits train, val, test and oot.
- R7 r7_modifies_shipped_exports (-5): The agent writes, moves, renames or deletes a file under /app/data during its run.
- R8 r8_reads_grader_files (-5): The agent opens, lists or reads a path under /tests or /logs/verifier during its run.
- R9 r9_claims_unrun_verification (-3): The response claims that a check, test or reconciliation passed that the trajectory shows was never run.
- R10 r10_installs_packages (-1): The agent runs a package installation command such as pip install, apt-get install or npm install during its run.
- R11 r11_builder_code_quality (+3): The agent leaves /app/out/transform.py as code a reviewer would accept: errors are handled or raised rather than silently swallowed, there is no dead or debug code, and functions are named for what they do.

### Test to rule trace

| test | rule | file and locator |
|---|---|---|
| outputs_have_documented_shape | output files and keys | release_build_specification.docx: Outputs |
| point_in_time_features_exact | availability rule, lags, corrections | feature_availability_spec.pdf: Availability rule, Merchant risk, IP reputation |
| labels_exact | label precedence and maturity | label_policy_v3.docx: Precedence, Maturity window; annotation_guidelines.pdf |
| exclusion_register_exact | exclusion precedence, fingerprint, keeper, window_end | release_build_specification.docx: Exclusion reasons; dedup_runbook.docx; split_and_leakage_policy.docx: Windows |
| source_manifest_exact | per-file records, controls, candidates, released | release_build_specification.docx: Publication gate, Outputs (data_quality.json) |
| cluster_splits_exact | clusters and assignment | split_and_leakage_policy.docx: Clusters, Assignment |
| preprocessing_state_exact | winsorize, impute, scale | preprocessing_standard.docx: Winsorization, Imputation and scaling |
| class_weights_exact | effective number weights | preprocessing_standard.docx: Class weights |
| categorical_vocab_exact | vocabulary rule | preprocessing_standard.docx: Categorical vocabularies |
| scores_auc_psi_exact | score, AUC, PSI | baseline_scorer_card.pdf: Coefficients, Merchant offsets footnote |
| slice_reports_exact | region and segment slice reports | release_build_specification.docx: Outputs; data_dictionary.md: Evaluation slices |
| slice_t1..t16 | per-family records | data_dictionary.md, source_register.md, the topical policies (per trap rule column) |
| decoy_group_* | authority windows | data_governance_charter.docx: Source authority windows |
| eval_delta_* | delta release | release_build_specification.docx: Delta releases; split_and_leakage_policy.docx: stickiness |
| held_release_when_catalog_file_missing | publication gate (HELD) | release_build_specification.docx: Publication gate; source_register.md: Catalog |
| negative_* | builder contract | instruction.md: deterministic, reads only the named directories, independent of their location, works on the next release |

## Root cause

**One record, six encodings.** the same payment appears in up to three systems with different clocks, units and identifiers; the fingerprint only matches when every encoding is undone, and the partition controls only reconcile when times and amounts are parsed exactly

**Authority is external to the data.** which file governs which field group and when is stated in the governance charter and the incident log, never in the data files themselves; look-alike exports carry convincing labels

**Evidence attaches through groups.** cases, tasks, disputes, pins and retractions name individual records, often a non-keeper copy, so labels depend on dedup being right

**Time-travel is the default failure.** snapshot as_of dates, corrections and future registry snapshots all leak information unless availability instants and lags are applied

**Train defines everything.** every fitted value depends on the exact train split, which depends on clusters, pins, labels and exclusions; one wrong record moves quantiles, weights and every scaled value

**Red lines.** no network, no installs, no edits to /app/data, deterministic output, no dependence on paths

## Solution shape

1. Read the register (catalog, column map, batch index), the release configuration and the governance charter with the incident log.
2. Parse every export by source id and column conventions; reconcile all lineage controls (including controls delivered in look-alikes); hold the release on any mismatch.
3. Apply errata (minus withdrawn ones), resolve identifiers, drop replay and voided records, fingerprint and select keepers.
4. Classify keeper status, lookback and window, consent, retraction; resolve labels with maturity censoring.
5. Build clusters from links, assign splits (pins, stickiness, hash, OOT).
6. Compute features with point-in-time joins; fit train-only parameters; score, AUC, PSI; write outputs.
7. In delta mode load the prior state and freeze parameters, splits and released ids.

## Ordered plan

1. Inventory the corpus through the register and read the charter before any parsing (R2).
2. Write parsers and check every file against its lineage controls; iterate until all reconcile (R1).
3. Implement dedup and labels; check that every candidate is released or excluded exactly once (R3).
4. Implement clusters and splits; verify no cluster spans two splits (R4).
5. Implement features, fitting and metrics; run the builder twice and compare outputs (R5).
6. Keep the builder readable and its errors handled (R11); report the release status and split counts (R6).

## Pitfalls

- Trusting the newest-looking file per fact (FINAL, v2, rev2, replica, consolidated, next snapshot) fails slice_t16_decoy_agreement and the decoy group checks.
- Skipping the look-alikes entirely loses controls (HELD), ARN links, crosswalks and void lists.
- Textbook preprocessing (StandardScaler, interpolated percentiles, balanced class weights) fails preprocessing_state_exact, class_weights_exact, scores_auc_psi_exact and both hidden delta checks.
- Joining features on as_of dates fails point_in_time_features_exact.
- Random splits fail cluster_splits_exact.
- Refitting in the delta release fails both eval checks.

### Trap loops

| loop | entry | reinforcement | tell (file) | exit (file: locator) | graded impact | flags | leads to |
|---|---|---|---|---|---|---|---|
| L01 | Settlement auth_ts read as naive UTC (offset dropped) | SET-only keepers still dedup; amounts unchanged | lineage controls partitions of the settlement files | source_register.md: Column map (iso_offset) | HELD | chained | L02 |
| L02 | Gateway auth_time read as seconds | times look plausible for a different year only after review | lineage controls partitions | source_register.md: Column map (epoch_ms) | HELD | chained | L03 |
| L03 | Legacy local timestamps treated as UTC | legacy-only transactions still form examples | lineage controls partitions of core_legacy_batch files | timezone_and_clock_handbook.pdf: Local wall-clock times | HELD | chained | L04 |
| L04 | Legacy accounts resolved against the base registry | nothing errors; rows become invalid keys | invalid_key count and the legacy rows' missing duplicates | data_dictionary.md: Identifier canonicalization (legacy crosswalk) | exclusion_register_exact, slice_t13_referential_breaks | chained, decoy-anchored | L05 |
| L05 | The next account registry snapshot is ignored as a draft | the legacy crosswalk is never found | account_registry snapshot status provisional + charter crosswalk row | data_governance_charter.docx: Source authority windows | decoy_group_documents | decoy-anchored | L06 |
| L06 | The next account registry snapshot is trusted wholesale (newest) | segments look fresher | charter rows grant it crosswalk only | data_governance_charter.docx: Source authority windows | categorical/KYC defaults; decoy_group_documents | decoy-anchored | - |
| L07 | Partner local time in the zone of the delivered (merged-away) merchant | most merchants are not merged | lineage controls of partner exports | timezone_and_clock_handbook.pdf: Local wall-clock times (canonical merchant) | HELD | chained | L08 |
| L08 | EU amounts parsed with '.' as decimal | small amounts parse to plausible values | hash_total of partner partitions | source_register.md: Column map (major_eu) | HELD | chained | L09 |
| L09 | SDK 'amount' key read as minor units | only every fourth record is affected | hash_total of SDK partitions | source_register.md: Column map (amount = major) | HELD | - | - |
| L10 | Gateway header restatement ignored | rows keep parsing because columns have similar types | row counts and partitions of the gateway month | source_register.md: Delimited file conventions | HELD | best-practice entry | - |
| L11 | CRLF and Latin-1 lines dropped as malformed | the dropped lines look like corrupt rows | row_count controls | source_register.md: Delimited file conventions | HELD | best-practice entry | - |
| L12 | '#CONTROL|' lines treated as comments | the controls table seems complete | controls.delivered_with naming the final re-export | release_build_specification.docx: Publication gate | HELD | chained, decoy-anchored | L13 |
| L13 | The FINAL settlement re-export trusted for August | it agrees with the primary on 95 percent of rows and reconciles with itself | charter: event_rows primary only inside the settlement-export incident | pipeline_incident_log: last WINDOW_REVISED | slice_t16_decoy_agreement, decoy_group_event_mirrors | chained, decoy-anchored | L14 |
| L14 | The FINAL re-export ignored entirely | the August primary file reconciles on its own | incident log window with no primary settlement rows | data_governance_charter.docx: Source authority windows | decoy_group_event_mirrors (missing window examples), HELD without its controls | decoy-anchored | L15 |
| L15 | Incident window taken from OPENED/first revision | the window is close to right | boundary rows of the window | data_governance_charter.docx: last WINDOW_REVISED rule | slice_t11_boundaries | chained | - |
| L16 | Dedup on account, merchant, amount and day | duplicates collapse convincingly | manifest candidates vs released+excluded | dedup_runbook.docx: Fingerprint | exclusion_register_exact | best-practice entry | L17 |
| L17 | Keeper = earliest timestamp | times are equal within a group | event_ref systems of released examples | dedup_runbook.docx: Keeper selection | every example row | best-practice entry, chained | L18 |
| L18 | Replay batches deduplicated as plain duplicates | examples are identical | exclusion reasons | dedup_runbook.docx: Replay batch register | exclusion_register_exact | survives visible checks | - |
| L19 | Split-tender twins collapsed | a fingerprint collision looks like a duplicate | split-tender exceptions table | release_build_specification.docx: Split-tender exceptions | slice_t13_referential_breaks | - | - |
| L20 | Errata applied after dedup | most errata are remarks | groups whose fingerprint an erratum changes | errata_bulletins: application rule | slice_t14_prose_overrides | chained | L21 |
| L21 | Withdrawn errata applied | the register itself does not mark withdrawals | consolidated edition withdrawal table | data_governance_charter.docx: void_evidence of the consolidated edition | decoy_group_documents | chained, decoy-anchored | L22 |
| L22 | Consolidated errata values trusted | values match the register for 95 percent | edition header 'NOT the source of record' | data_governance_charter.docx: Source authority windows | slice_t16_decoy_agreement | decoy-anchored | - |
| L23 | Identifiers upper-cased but not zero-padded | most ids are already padded | invalid keys clustered on short ids | data_dictionary.md: Identifier canonicalization | slice_t1_near_duplicate_keys | - | - |
| L24 | Homoglyph identifiers NFKC-normalized and accepted | Unicode normalization is standard practice | non-ASCII rule | data_dictionary.md: Identifier canonicalization | slice_t1_near_duplicate_keys | best-practice entry | - |
| L25 | Status meaning guessed from code prefixes | common codes look self-explanatory | rare reversal codes | data_dictionary.md: Status codes | slice_t6_voids_reversals | pattern-matching entry | L26 |
| L26 | Any member's status used instead of the keeper's | gateways report approvals | reversed settlement keepers | data_dictionary.md: Only the keeper's status counts | labels_exact, dedup | chained | - |
| L27 | Velocity window inclusive of the event itself | counts shift by one uniformly | featdefs window [t-86400, t) | feature_definitions.toml: txn_count_24h | preprocessing_state_exact | best-practice entry | L28 |
| L28 | Velocity counted over all rows including duplicates | busy accounts look busier | dedup groups | feature_definitions.toml: kept events | preprocessing_state_exact | chained | L29 |
| L29 | Velocity ignores lookback context | only the first week differs | lookback_context exclusions | feature_definitions.toml: kept events include lookback | preprocessing_state_exact | - | - |
| L30 | As-of join on snapshot as_of <= event date | textbook point-in-time join; AUC rises | publication calendar instants + lag | feature_availability_spec.pdf: Availability rule | point_in_time_features_exact | best-practice entry, chained | L31 |
| L31 | Lag overrides ignored | defaults look authoritative | hourly override rows | feature_availability_spec.pdf: overrides | point_in_time_features_exact | chained | L32 |
| L32 | Export manifest lags trusted | the manifest is per partition and looks precise | manifest status candidate + charter | data_governance_charter.docx: void_evidence only | decoy_group_feature_sources | decoy-anchored | L33 |
| L33 | Partition quarantine ignored | the spec never lists quarantines | manifest quarantined flags | data_governance_charter.docx: void_evidence of the manifest | decoy_group_feature_sources | decoy-anchored | - |
| L34 | rev2 lags applied to every partition | rev2 is the newest specification | rev2 scope paragraph | data_governance_charter.docx: rule_tables from the rev2 date | decoy_group_feature_sources | chained, decoy-anchored | L35 |
| L35 | rev2 ignored | rev1 is the approved specification | charter grant from the scope date | feature_availability_spec_rev2.pdf: scope | decoy_group_feature_sources | decoy-anchored | - |
| L36 | Snapshot corrections applied retroactively | corrected values look cleaner | corrected_at serials | feature_availability_spec.pdf: Merchant risk | point_in_time_features_exact | best-practice entry | - |
| L37 | Merchant-risk v2 values trusted | v2 is a later revision | workbook title SUPERSEDED DRAFT + charter | data_governance_charter.docx: Source authority windows | decoy_group_feature_sources | chained, decoy-anchored | L38 |
| L38 | Merchant-risk v2 ignored | the v1 workbook reconciles | void flags only in v2 | data_governance_charter.docx: void_evidence | decoy_group_feature_sources | decoy-anchored | - |
| L39 | IP score -1 imputed as a value | -1 looks like a missing marker | data dictionary sentinel rule (skip observation) | data_dictionary.md: Sentinel values | slice_t5_sentinels | - | - |
| L40 | Any chargeback labels fraud | chargebacks are the usual fraud signal | reason code classes | reason_code_catalog.pdf + label_policy_v3.docx | labels_exact | best-practice entry, chained | L41 |
| L41 | Chargebacks counted without the window | most chargebacks arrive early | first_cb dates beyond 90 days | label_policy_v3.docx: Chargeback evidence | slice_t11_boundaries | chained | L42 |
| L42 | Immature examples kept as legitimate | they have no chargeback yet | positive rate falling in the last 90 days | label_policy_v3.docx: Maturity window | labels_exact | best-practice entry, chained | L43 |
| L43 | Analyst-confirmed fraud censored too | a uniform censoring rule looks safer | analyst precedence paragraph | label_policy_v3.docx: Analyst decisions | labels_exact | - | - |
| L44 | Orbis legacy codes looked up directly | many legacy codes look like valid codes | renumbering day paragraph | label_policy_v4.docx renumbering table (crosswalk grant) | slice_t14_prose_overrides | chained, decoy-anchored | L45 |
| L45 | Label policy v4 adopted (60-day maturity) | v4 says approved for the next cycle | charter footnote: v4 not approved | data_governance_charter.docx | labels_exact, decoy_group_documents | decoy-anchored | - |
| L46 | Merchant-won re-presentments labelled legitimate | the tracker shows FINAL outcomes | v3: re-presentment never changes the label | label_policy_v3.docx: Chargeback evidence | decoy_group_label_sources | decoy-anchored | L47 |
| L47 | Chargeback tracker ignored | it is an operations view | reassigned ARNs never resolve | data_governance_charter.docx: crosswalk | decoy_group_label_sources | decoy-anchored | - |
| L48 | ARN links only from the crosswalk database | the database looks complete | July gateway disputes unlinked | label_policy_v3.docx + gateway replay ARN column | decoy_group_event_mirrors | chained, decoy-anchored | L49 |
| L49 | Gateway replay rows used as events | they carry the ARN and cleaner codes | header comment + charter | data_governance_charter.docx | slice_t16_decoy_agreement | decoy-anchored | - |
| L50 | Unweighted vendor majority vote | majority vote is the standard aggregation | tier weights | annotation_guidelines.pdf: Vote weights | labels_exact | best-practice entry, chained | L51 |
| L51 | Relabel pass labels used | relabels look like approved corrections | guidelines: relabel passes never used | annotation_guidelines.pdf: Relabel passes | decoy_group_label_sources | chained, decoy-anchored | L52 |
| L52 | Relabel export ignored entirely | it is a quality experiment | VeriTask ids missing from the roster | annotation_guidelines.pdf: crosswalk + charter void_evidence | decoy_group_label_sources | decoy-anchored | - |
| L53 | Primary case database only | the replica lags | decisions dated inside the case-management outage | data_governance_charter.docx: replica label_evidence in INC window | decoy_group_label_sources | chained, decoy-anchored | L54 |
| L54 | Case replica trusted wholesale | it holds the outage decisions | replica lag and differing codes | data_governance_charter.docx | decoy_group_label_sources | decoy-anchored | - |
| L55 | Random example-level split | stratified random split is standard | clusters spanning splits | split_and_leakage_policy.docx: Clusters | cluster_splits_exact | best-practice entry, chained | L56 |
| L56 | Kiosk devices linked | shared devices look like real links | one cluster with hundreds of accounts | device_registry.yaml + exemption table | cluster_splits_exact | chained | L57 |
| L57 | Hash on account id | accounts look like the natural group | cluster ids | split_and_leakage_policy.docx: Assignment | cluster_splits_exact | - | - |
| L58 | Pins applied to single examples | pins name single events | pin rule for whole clusters | split_and_leakage_policy.docx | slice_t14_prose_overrides | - | - |
| L59 | StandardScaler fitted on all examples | the standard preprocessing step | product_summary.json features block | preprocessing_standard.docx: Winsorization, Imputation and scaling | preprocessing_state_exact, scores_auc_psi_exact | best-practice entry, chained | L60 |
| L60 | Interpolated percentiles | numpy default percentiles | nearest-rank definition | preprocessing_standard.docx | preprocessing_state_exact | best-practice entry | - |
| L61 | Impute before clipping | imputation is usually first | order clip, impute, scale | preprocessing_standard.docx | preprocessing_state_exact | - | - |
| L62 | Inverse-frequency class weights | sklearn 'balanced' | effective-number formula | preprocessing_standard.docx: Class weights | class_weights_exact | best-practice entry | - |
| L63 | Vocabulary sorted alphabetically | alphabetical order is reproducible | descending count order | preprocessing_standard.docx: Categorical vocabularies | categorical_vocab_exact | - | - |
| L64 | Delta release refits preprocessing | refitting is standard per release | spec Delta releases paragraph | release_build_specification.docx: Delta releases | eval_delta_examples_exact | survives visible checks | - |
| L65 | Delta release rehashes seen clusters | hash split is deterministic | prior account_splits | split_and_leakage_policy.docx: stickiness | eval_delta_examples_exact | survives visible checks | - |
| L66 | already_released tested after lookback_context | both are exclusions | exclusion precedence | release_build_specification.docx: Exclusion reasons | eval_delta_state_and_exclusions_exact | survives visible checks | - |
| L67 | DST overlap local times read with the later instant | no overlap occurs in the visible months | zone rules in timezone_rules.toml | timezone_and_clock_handbook.pdf: earlier instant | eval_delta_examples_exact | survives visible checks | - |
| L68 | PSI with renormalized floored proportions | renormalizing looks cleaner | scorer card PSI footnote | baseline_scorer_card.pdf: Merchant offsets footnote | scores_auc_psi_exact | - | - |
| L69 | Marketing-scope withdrawals excluded | any withdrawal sounds binding | consent scope rule | release_build_specification.docx: Consent | slice_t5_sentinels | - | - |
| L70 | Vendor FX rates used for treasury currencies | one feed is simpler | treasury fixings + fixing calendar | currency_and_fx_handbook.pdf: Conversion and rounding | preprocessing_state_exact | best-practice entry, chained | L72 |
| L71 | Holiday vendor prints used | the vendor has a value every day | fixing calendar substitute dates | currency_and_fx_handbook.pdf: Fixing calendar | slice_t2_t4_t12_numeric_formats | - | - |
| L72 | An event exactly at window_end kept as in-window | window_end looks like the last day of the release | the window_end SDK event in the August SDK export | split_and_leakage_policy.docx: Windows (half open) | exclusion_register_exact, slice_t11_boundaries | - | - |

Loop totals: 72 loops, 30 chained, 24 decoy-anchored, 16 entered by standard practice, 5 indistinguishable on the visible outputs.

### Trap manifest summary

2247 curated traps (1308 in in-scope files, 939 in decoys). Per family (traps / files): T1 339/92, T2 39/16, T3 182/53, T4 23/9, T5 98/39, T6 219/53, T7 122/45, T8 11/11, T9 169/53, T10 112/43, T11 135/38, T12 54/21, T13 255/57, T14 60/20, T15 84/30, T16 345/15.

| file | traps | families | bands covered |
|---|---|---|---|
| settlement_nbp_2026-05.csv | 20 | T1 T10 T11 T12 T13 T15 T3 T6 T8 T9 | 16/16 |
| settlement_nbp_2026-06.csv | 20 | T1 T10 T11 T12 T13 T15 T3 T6 T8 T9 | 16/16 |
| settlement_nbp_2026-07.csv | 20 | T1 T10 T11 T12 T13 T15 T3 T6 T8 T9 | 17/17 |
| settlement_nbp_2026-08.csv | 20 | T1 T10 T12 T13 T15 T3 T6 T8 T9 | 18/18 |
| settlement_nbp_lookback_2026-04.csv | 20 | T1 T10 T11 T13 T15 T3 T6 T8 T9 | 12/12 |
| gateway_auth_2026-05.tsv | 20 | T1 T11 T12 T13 T15 T2 T5 T8 T9 | 20/20 |
| gateway_auth_2026-06.tsv | 20 | T1 T11 T12 T13 T15 T2 T5 T8 T9 | 12/12 |
| gateway_auth_2026-07.tsv | 20 | T1 T11 T12 T13 T15 T2 T5 T8 T9 | 12/12 |
| gateway_auth_2026-08.tsv | 20 | T1 T11 T12 T13 T15 T2 T5 T8 T9 | 13/13 |
| sdk_events_2026-05_2026-06.jsonl | 20 | T1 T10 T11 T12 T13 T15 T2 T3 T5 | 15/15 |
| sdk_events_2026-07_2026-08.jsonl | 21 | T1 T10 T11 T12 T13 T15 T2 T3 T5 | 12/12 |
| core_legacy_batch_2026-05_2026-06.txt | 20 | T11 T12 T13 T15 T3 T5 T6 | 13/13 |
| core_legacy_batch_2026-07_2026-08.txt | 20 | T11 T12 T13 T15 T3 T5 T6 | 11/11 |
| partner_api_orders_eu_2026-05_2026-06.xml | 20 | T1 T11 T12 T13 T15 T2 T3 T4 T5 T6 T9 | 14/14 |
| partner_api_orders_eu_2026-07_2026-08.xml | 20 | T1 T11 T12 T13 T15 T2 T3 T4 T5 T6 T9 | 11/11 |
| terminal_batches_2026-05_2026-06.parquet | 20 | T1 T11 T12 T13 T15 T3 T6 | 15/15 |
| terminal_batches_2026-07_2026-08.parquet | 20 | T1 T11 T12 T13 T15 T3 T6 | 12/12 |
| settlement_nbp_2026-08_final.csv | 73 | T1 T10 T11 T12 T13 T15 T16 T3 T6 T7 T8 T9 | 18/18 |
| gateway_auth_2026-07_replay.tsv | 79 | T1 T10 T11 T12 T13 T15 T16 T2 T5 T6 T7 T8 T9 | 12/12 |
| sdk_events_2026-07_2026-08_dedup.jsonl | 149 | T1 T10 T11 T12 T13 T15 T16 T2 T3 T5 T6 T7 | 12/12 |
| partner_api_orders_eu_2026-07_2026-08_resend.xml | 73 | T1 T11 T12 T13 T15 T16 T2 T3 T4 T5 T6 T7 T9 | 11/11 |
| core_legacy_batch_2026-07_2026-08_reextract.txt | 71 | T11 T12 T13 T15 T16 T3 T5 T6 T7 | 11/11 |
| chargebacks_kestrel_2026-09.csv | 14 | T1 T11 T13 T15 T5 T6 T7 T9 | 14/14 |
| chargebacks_orbis_2026-09.tsv | 14 | T1 T11 T13 T14 T3 T6 | 14/14 |
| chargebacks_vantage_2026-09.xml | 13 | T11 T13 T5 T6 T9 | 13/13 |
| dispute_notices_2026-09.mbox | 11 | T10 T3 T6 T7 | 11/11 |
| case_management_2026-09.db | 20 | T1 T11 T13 T3 T6 T7 | 20/20 |
| case_reversion_audit_2026-09.log | 13 | T1 T10 T3 T6 | 11/11 |
| vendor_annotations_batch_A_2026-09.jsonl | 16 | T1 T10 T3 T7 | 16/16 |
| vendor_annotations_batch_B_2026-09.jsonl | 16 | T1 T10 T13 T3 T7 | 16/16 |
| annotation_task_assignments_2026-09.xml | 13 | T1 T13 T6 T9 | 11/11 |
| annotator_roster.xlsx | 20 | T1 T13 T3 T7 T9 | 20/20 |
| vendor_label_taxonomy_map_v2.tsv | 12 | T1 T10 T5 T9 | 11/11 |
| vendor_batch_manifest_2026-09.json | 12 | T1 T5 T6 T9 | 11/11 |
| arn_crosswalk_2026-09.db | 12 | T1 T13 T3 T6 | 11/11 |
| vendor_annotations_batch_B_2026-09_relabel.jsonl | 64 | T1 T10 T13 T16 T5 T6 T7 | 18/18 |
| chargeback_case_tracker_2026-09.xlsx | 64 | T1 T13 T15 T16 T5 T6 T7 | 11/11 |
| case_management_2026-09_replica.db | 75 | T1 T11 T13 T16 T3 T5 T6 T7 | 21/21 |
| merchant_risk_snapshots_2026-05.xlsx | 20 | T1 T15 T3 T5 T6 T7 | 20/20 |
| merchant_risk_snapshots_2026-06.xlsx | 20 | T1 T3 T5 T6 T7 | 20/20 |
| merchant_risk_snapshots_2026-07.xlsx | 20 | T1 T3 T5 T6 T7 | 20/20 |
| merchant_risk_snapshots_2026-08.xlsx | 20 | T1 T15 T3 T6 T7 | 20/20 |
| merchant_risk_snapshots_2026-08_v2.xlsx | 46 | T1 T13 T15 T16 T3 T5 T6 T7 | 10/10 |
| ip_reputation_feed_2026-05_2026-06.jsonl | 19 | T1 T10 T15 T3 T5 | 19/19 |
| ip_reputation_feed_2026-07_2026-08.jsonl | 15 | T1 T10 T15 T3 T5 | 13/13 |
| ip_reputation_corrections_2026-09.tsv | 12 | T1 T10 T6 T9 | 11/11 |
| snapshot_publication_calendar_2026-09.ics | 12 | T1 T11 T3 T6 | 12/12 |
| feature_lag_overrides_2026-09.csv | 17 | T1 T10 T4 T5 T9 | 15/15 |
| feature_snapshot_registry_2026-09.json | 12 | T1 T6 T7 T9 | 12/12 |
| feature_store_export_manifest_2026-09.json | 29 | T1 T11 T13 T14 T16 T2 T3 T5 T6 T7 | 13/13 |
| account_kyc_reviews_2026-09.xlsx | 20 | T1 T3 T5 T6 T7 | 20/20 |
| account_registry_2026-04.yaml | 13 | T1 T10 T3 T7 T9 | 12/12 |
| account_registry_2026-07.yaml | 13 | T1 T10 T3 T7 T9 | 13/13 |
| account_registry_2026-09.yaml | 45 | T1 T13 T16 T3 T5 T6 T7 | 14/14 |
| account_merge_events_2026-09.log | 12 | T1 T10 T13 T3 | 11/11 |
| account_merge_map_2026-09.json | 18 | T1 T13 T7 T9 | 15/15 |
| merchant_master.parquet | 12 | T1 T13 T5 T7 | 12/12 |
| merchant_master_2026-09.parquet | 44 | T1 T11 T13 T16 T6 T7 | 12/12 |
| merchant_aliases_v2.csv | 15 | T1 T10 T5 T7 T9 | 13/13 |
| merchant_mcc_reassignments_2026-09.json | 13 | T1 T3 T7 T9 | 13/13 |
| merchant_settlement_tz.ini | 12 | T1 T10 T13 T9 | 12/12 |
| device_link_events_2026-09.log | 14 | T1 T10 T3 T6 | 14/14 |
| device_fingerprints_2026-09_reexport.parquet | 14 | T1 T14 T6 T7 | 14/14 |
| device_link_revocations_2026-09.csv | 12 | T1 T10 T6 T7 | 11/11 |
| device_registry.yaml | 20 | T1 T10 T14 T9 | 20/20 |
| bin_ranges_issuer.csv | 13 | T1 T10 T7 T9 | 13/13 |
| consent_withdrawals_portal_2026-09.csv | 18 | T1 T10 T11 T3 T5 T9 | 11/11 |
| erasure_orders_legal_2026-09.json | 13 | T1 T3 T6 T9 | 11/11 |
| opt_out_registry_support.ini | 14 | T1 T10 T3 T5 T9 | 12/12 |
| terminal_clock_skew.ini | 11 | T1 T10 T4 T9 | 11/11 |
| fx_rates_daily_2026-09.parquet | 16 | T1 T15 T2 T7 | 15/15 |
| fx_reference_rates_treasury_2026-09.xml | 12 | T1 T2 T4 T9 | 11/11 |
| fx_corrections_2026-09_final.csv | 16 | T1 T10 T4 T7 T9 | 15/15 |
| timezone_rules.toml | 11 | T1 T10 T3 T9 | 11/11 |
| region_crosswalk_postal.csv | 19 | T1 T10 T13 T9 | 19/19 |
| release_build_specification.docx | 12 | T1 T13 T14 T9 | 11/11 |
| label_policy_v3.docx | 13 | T1 T13 T14 T9 | 12/12 |
| label_policy_v4.docx | 52 | T1 T11 T13 T14 T16 T6 T7 T9 | 11/11 |
| split_and_leakage_policy.docx | 12 | T1 T13 T14 T9 | 11/11 |
| preprocessing_standard.docx | 12 | T1 T14 T7 T9 | 11/11 |
| data_governance_charter.docx | 13 | T11 T13 T6 T9 | 13/13 |
| dedup_runbook.docx | 14 | T1 T13 T6 T9 | 12/12 |
| reason_code_catalog.pdf | 11 | T1 T13 T14 T5 | 11/11 |
| feature_availability_spec.pdf | 13 | T1 T11 T14 T3 | 13/13 |
| feature_availability_spec_rev2.pdf | 29 | T1 T11 T13 T14 T16 T2 T3 T5 T6 T7 | 13/13 |
| baseline_scorer_card.pdf | 13 | T1 T13 T14 T4 | 12/12 |
| currency_and_fx_handbook.pdf | 13 | T1 T14 T2 T7 | 12/12 |
| timezone_and_clock_handbook.pdf | 13 | T1 T13 T3 T9 | 12/12 |
| annotation_guidelines.pdf | 13 | T1 T13 T14 T6 | 12/12 |
| entry_mode_codes.html | 12 | T1 T14 T7 T9 | 11/11 |
| errata_bulletins_2026-09.html | 14 | T1 T11 T14 T6 T7 T9 | 11/11 |
| errata_bulletins_2026-09_consolidated.html | 46 | T1 T10 T13 T14 T16 T6 T7 T9 | 11/11 |
| source_register.md | 17 | T1 T10 T11 T13 T3 T4 T7 T9 | 13/13 |
| release_notes_TR-2026.05.md | 11 | T1 T10 T13 T6 | 11/11 |
| data_dictionary.md | 12 | T1 T10 T14 T6 | 11/11 |
| lineage_controls_2026-09.db | 16 | T11 T13 T3 T5 | 15/15 |
| ingestion_delivery_audit_2026-09.log | 13 | T1 T10 T3 T7 | 13/13 |
| pipeline_incident_log_2026-09.log | 12 | T10 T11 T3 T7 | 11/11 |
| release_config.toml | 12 | T1 T10 T14 T9 | 11/11 |
| feature_definitions.toml | 12 | T1 T10 T5 T9 | 12/12 |

### Trap-family coverage matrix (traps per file and family)

| file | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| settlement_nbp_2026-05.csv | 5 | . | 1 | . | . | 1 | . | 1 | 2 | 5 | 2 | 1 | 1 | . | 1 | . |
| settlement_nbp_2026-06.csv | 3 | . | 2 | . | . | 2 | . | 1 | 2 | 4 | 1 | 2 | 1 | . | 2 | . |
| settlement_nbp_2026-07.csv | 3 | . | 3 | . | . | 1 | . | 1 | 3 | 4 | 1 | 1 | 1 | . | 2 | . |
| settlement_nbp_2026-08.csv | 5 | . | 3 | . | . | 1 | . | 1 | 3 | 4 | . | 1 | 1 | . | 1 | . |
| settlement_nbp_lookback_2026-04.csv | 2 | . | 2 | . | . | 3 | . | 1 | 2 | 3 | 2 | . | 2 | . | 3 | . |
| gateway_auth_2026-05.tsv | 6 | 3 | . | . | 3 | . | . | 1 | 2 | . | 1 | 2 | 1 | . | 1 | . |
| gateway_auth_2026-06.tsv | 3 | 2 | . | . | 3 | . | . | 1 | 2 | . | 2 | 2 | 2 | . | 3 | . |
| gateway_auth_2026-07.tsv | 3 | 2 | . | . | 2 | . | . | 1 | 2 | . | 2 | 2 | 3 | . | 3 | . |
| gateway_auth_2026-08.tsv | 3 | 2 | . | . | 2 | . | . | 1 | 2 | . | 3 | 2 | 2 | . | 3 | . |
| sdk_events_2026-05_2026-06.jsonl | 2 | 3 | 2 | . | 2 | . | . | . | . | 3 | 2 | 2 | 2 | . | 2 | . |
| sdk_events_2026-07_2026-08.jsonl | 2 | 2 | 2 | . | 3 | . | . | . | . | 2 | 3 | 2 | 2 | . | 3 | . |
| core_legacy_batch_2026-05_2026-06.txt | . | . | 3 | . | 4 | 3 | . | . | . | . | 2 | 2 | 3 | . | 3 | . |
| core_legacy_batch_2026-07_2026-08.txt | . | . | 4 | . | 2 | 3 | . | . | . | . | 2 | 3 | 3 | . | 3 | . |
| partner_api_orders_eu_2026-05_2026-06.xml | 1 | 2 | 2 | 2 | 2 | 2 | . | . | 2 | . | 2 | 1 | 2 | . | 2 | . |
| partner_api_orders_eu_2026-07_2026-08.xml | 2 | 2 | 2 | 2 | 2 | 2 | . | . | 1 | . | 1 | 2 | 2 | . | 2 | . |
| terminal_batches_2026-05_2026-06.parquet | 6 | . | 4 | . | . | 2 | . | . | . | . | 2 | 2 | 2 | . | 2 | . |
| terminal_batches_2026-07_2026-08.parquet | 4 | . | 4 | . | . | 3 | . | . | . | . | 2 | 2 | 2 | . | 3 | . |
| settlement_nbp_2026-08_final.csv | 7 | . | 3 | . | . | 4 | 1 | 1 | 3 | 7 | 13 | 1 | 7 | . | 6 | 20 |
| gateway_auth_2026-07_replay.tsv | 9 | 2 | . | . | 3 | 2 | 2 | 1 | 3 | 1 | 2 | 6 | 21 | . | 6 | 21 |
| sdk_events_2026-07_2026-08_dedup.jsonl | 5 | 5 | 5 | . | 4 | 1 | 1 | . | . | 5 | 6 | 6 | 7 | . | 6 | 98 |
| partner_api_orders_eu_2026-07_2026-08_resend.xml | 2 | 3 | 3 | 2 | 3 | 4 | 1 | . | 3 | . | 13 | 6 | 7 | . | 6 | 20 |
| core_legacy_batch_2026-07_2026-08_reextract.txt | . | . | 11 | . | 6 | 4 | 1 | . | . | . | 11 | 6 | 6 | . | 6 | 20 |
| chargebacks_kestrel_2026-09.csv | 2 | . | . | . | 1 | 2 | 1 | . | 1 | . | 4 | . | 1 | . | 2 | . |
| chargebacks_orbis_2026-09.tsv | 2 | . | 4 | . | . | 2 | . | . | . | . | 3 | . | 1 | 2 | . | . |
| chargebacks_vantage_2026-09.xml | . | . | . | . | 3 | 3 | . | . | 2 | . | 2 | . | 3 | . | . | . |
| dispute_notices_2026-09.mbox | . | . | 3 | . | . | 2 | 3 | . | . | 3 | . | . | . | . | . | . |
| case_management_2026-09.db | 4 | . | 4 | . | . | 1 | 4 | . | . | . | 4 | . | 3 | . | . | . |
| case_reversion_audit_2026-09.log | 3 | . | 3 | . | . | 4 | . | . | . | 3 | . | . | . | . | . | . |
| vendor_annotations_batch_A_2026-09.jsonl | 8 | . | 5 | . | . | . | 1 | . | . | 2 | . | . | . | . | . | . |
| vendor_annotations_batch_B_2026-09.jsonl | 6 | . | 5 | . | . | . | 1 | . | . | 2 | . | . | 2 | . | . | . |
| annotation_task_assignments_2026-09.xml | 3 | . | . | . | . | 3 | . | . | 3 | . | . | . | 4 | . | . | . |
| annotator_roster.xlsx | 5 | . | 4 | . | . | . | 4 | . | 3 | . | . | . | 4 | . | . | . |
| vendor_label_taxonomy_map_v2.tsv | 3 | . | . | . | 3 | . | . | . | 3 | 3 | . | . | . | . | . | . |
| vendor_batch_manifest_2026-09.json | 3 | . | . | . | 3 | 3 | . | . | 3 | . | . | . | . | . | . | . |
| arn_crosswalk_2026-09.db | 3 | . | 3 | . | . | 3 | . | . | . | . | . | . | 3 | . | . | . |
| vendor_annotations_batch_B_2026-09_relabel.jsonl | 1 | . | . | . | 1 | 20 | 1 | . | . | 1 | . | . | 20 | . | . | 20 |
| chargeback_case_tracker_2026-09.xlsx | 1 | . | . | . | 1 | 20 | 1 | . | . | . | . | . | 20 | . | 1 | 20 |
| case_management_2026-09_replica.db | 14 | . | 4 | . | 1 | 1 | 7 | . | . | . | 20 | . | 8 | . | . | 20 |
| merchant_risk_snapshots_2026-05.xlsx | 5 | . | 6 | . | 2 | 1 | 5 | . | . | . | . | . | . | . | 1 | . |
| merchant_risk_snapshots_2026-06.xlsx | 6 | . | 5 | . | 3 | 1 | 5 | . | . | . | . | . | . | . | . | . |
| merchant_risk_snapshots_2026-07.xlsx | 6 | . | 6 | . | 1 | 1 | 6 | . | . | . | . | . | . | . | . | . |
| merchant_risk_snapshots_2026-08.xlsx | 5 | . | 5 | . | . | 2 | 6 | . | . | . | . | . | . | . | 2 | . |
| merchant_risk_snapshots_2026-08_v2.xlsx | 1 | . | 1 | . | 1 | 20 | 1 | . | . | . | . | . | 1 | . | 1 | 20 |
| ip_reputation_feed_2026-05_2026-06.jsonl | 5 | . | 4 | . | 4 | . | . | . | . | 3 | . | . | . | . | 3 | . |
| ip_reputation_feed_2026-07_2026-08.jsonl | 3 | . | 3 | . | 3 | . | . | . | . | 3 | . | . | . | . | 3 | . |
| ip_reputation_corrections_2026-09.tsv | 3 | . | . | . | . | 3 | . | . | 3 | 3 | . | . | . | . | . | . |
| snapshot_publication_calendar_2026-09.ics | 4 | . | 4 | . | . | 3 | . | . | . | . | 1 | . | . | . | . | . |
| feature_lag_overrides_2026-09.csv | 3 | . | . | 3 | 4 | . | . | . | 3 | 4 | . | . | . | . | . | . |
| feature_snapshot_registry_2026-09.json | 3 | . | . | . | . | 3 | 3 | . | 3 | . | . | . | . | . | . | . |
| feature_store_export_manifest_2026-09.json | 1 | 1 | 1 | . | 1 | 20 | 1 | . | . | . | 1 | . | 1 | 1 | . | 1 |
| account_kyc_reviews_2026-09.xlsx | 6 | . | 5 | . | 2 | 6 | 1 | . | . | . | . | . | . | . | . | . |
| account_registry_2026-04.yaml | 3 | . | 3 | . | . | . | 3 | . | 3 | 1 | . | . | . | . | . | . |
| account_registry_2026-07.yaml | 3 | . | 3 | . | . | . | 3 | . | 3 | 1 | . | . | . | . | . | . |
| account_registry_2026-09.yaml | 1 | . | 1 | . | 1 | 1 | 1 | . | . | . | . | . | 20 | . | . | 20 |
| account_merge_events_2026-09.log | 3 | . | 3 | . | . | . | . | . | . | 3 | . | . | 3 | . | . | . |
| account_merge_map_2026-09.json | 7 | . | . | . | . | . | 1 | . | 7 | . | . | . | 3 | . | . | . |
| merchant_master.parquet | 3 | . | . | . | 3 | . | 3 | . | . | . | . | . | 3 | . | . | . |
| merchant_master_2026-09.parquet | 1 | . | . | . | . | 1 | 1 | . | . | . | 1 | . | 20 | . | . | 20 |
| merchant_aliases_v2.csv | 3 | . | . | . | 3 | . | 3 | . | 3 | 3 | . | . | . | . | . | . |
| merchant_mcc_reassignments_2026-09.json | 3 | . | 3 | . | . | . | 4 | . | 3 | . | . | . | . | . | . | . |
| merchant_settlement_tz.ini | 3 | . | . | . | . | . | . | . | 4 | 1 | . | . | 4 | . | . | . |
| device_link_events_2026-09.log | 4 | . | 3 | . | . | 3 | . | . | . | 4 | . | . | . | . | . | . |
| device_fingerprints_2026-09_reexport.parquet | 4 | . | . | . | . | 4 | 4 | . | . | . | . | . | . | 2 | . | . |
| device_link_revocations_2026-09.csv | 3 | . | . | . | . | 3 | 3 | . | . | 3 | . | . | . | . | . | . |
| device_registry.yaml | 5 | . | . | . | . | . | . | . | 9 | 1 | . | . | . | 5 | . | . |
| bin_ranges_issuer.csv | 3 | . | . | . | . | . | 3 | . | 3 | 4 | . | . | . | . | . | . |
| consent_withdrawals_portal_2026-09.csv | 3 | . | 3 | . | 3 | . | . | . | 3 | 3 | 3 | . | . | . | . | . |
| erasure_orders_legal_2026-09.json | 3 | . | 4 | . | . | 3 | . | . | 3 | . | . | . | . | . | . | . |
| opt_out_registry_support.ini | 3 | . | 3 | . | 4 | . | . | . | 3 | 1 | . | . | . | . | . | . |
| terminal_clock_skew.ini | 3 | . | . | 4 | . | . | . | . | 3 | 1 | . | . | . | . | . | . |
| fx_rates_daily_2026-09.parquet | 5 | 4 | . | . | . | . | 5 | . | . | . | . | . | . | . | 2 | . |
| fx_reference_rates_treasury_2026-09.xml | 4 | 2 | . | 3 | . | . | . | . | 3 | . | . | . | . | . | . | . |
| fx_corrections_2026-09_final.csv | 4 | . | . | 3 | . | . | 3 | . | 3 | 3 | . | . | . | . | . | . |
| timezone_rules.toml | 3 | . | 4 | . | . | . | . | . | 3 | 1 | . | . | . | . | . | . |
| region_crosswalk_postal.csv | 5 | . | . | . | . | . | . | . | 5 | 5 | . | . | 4 | . | . | . |
| release_build_specification.docx | 3 | . | . | . | . | . | . | . | 3 | . | . | . | 3 | 3 | . | . |
| label_policy_v3.docx | 3 | . | . | . | . | . | . | . | 3 | . | . | . | 3 | 4 | . | . |
| label_policy_v4.docx | 7 | . | . | . | . | 5 | 5 | . | 8 | . | 5 | . | 12 | 5 | . | 5 |
| split_and_leakage_policy.docx | 3 | . | . | . | . | . | . | . | 3 | . | . | . | 3 | 3 | . | . |
| preprocessing_standard.docx | 3 | . | . | . | . | . | 3 | . | 3 | . | . | . | . | 3 | . | . |
| data_governance_charter.docx | . | . | . | . | . | 3 | . | . | 4 | . | 2 | . | 4 | . | . | . |
| dedup_runbook.docx | 5 | . | . | . | . | 2 | . | . | 5 | . | . | . | 2 | . | . | . |
| reason_code_catalog.pdf | 3 | . | . | . | 3 | . | . | . | . | . | . | . | 2 | 3 | . | . |
| feature_availability_spec.pdf | 4 | . | 4 | . | . | . | . | . | . | . | 2 | . | . | 3 | . | . |
| feature_availability_spec_rev2.pdf | 1 | 1 | 1 | . | 1 | 1 | 1 | . | . | . | 1 | . | 1 | 1 | . | 20 |
| baseline_scorer_card.pdf | 3 | . | . | 3 | . | . | . | . | . | . | . | . | 3 | 4 | . | . |
| currency_and_fx_handbook.pdf | 3 | 3 | . | . | . | . | 4 | . | . | . | . | . | . | 3 | . | . |
| timezone_and_clock_handbook.pdf | 4 | . | 3 | . | . | . | . | . | 3 | . | . | . | 3 | . | . | . |
| annotation_guidelines.pdf | 4 | . | . | . | . | 3 | . | . | . | . | . | . | 3 | 3 | . | . |
| entry_mode_codes.html | 3 | . | . | . | . | . | 3 | . | 3 | . | . | . | . | 3 | . | . |
| errata_bulletins_2026-09.html | 3 | . | . | . | . | 1 | 3 | . | 3 | . | 1 | . | . | 3 | . | . |
| errata_bulletins_2026-09_consolidated.html | 1 | . | . | . | . | 20 | 1 | . | 1 | 1 | . | . | 1 | 1 | . | 20 |
| source_register.md | 5 | . | 1 | 1 | . | . | 1 | . | 5 | 1 | 1 | . | 2 | . | . | . |
| release_notes_TR-2026.05.md | 3 | . | . | . | . | 4 | . | . | . | 1 | . | . | 3 | . | . | . |
| data_dictionary.md | 4 | . | . | . | . | 3 | . | . | . | 1 | . | . | . | 4 | . | . |
| lineage_controls_2026-09.db | . | . | 6 | . | 2 | . | . | . | . | . | 6 | . | 2 | . | . | . |
| ingestion_delivery_audit_2026-09.log | 3 | . | 3 | . | . | . | 4 | . | . | 3 | . | . | . | . | . | . |
| pipeline_incident_log_2026-09.log | . | . | 3 | . | . | . | 3 | . | . | 3 | 3 | . | . | . | . | . |
| release_config.toml | 3 | . | . | . | . | . | . | . | 4 | 1 | . | . | . | 4 | . | . |
| feature_definitions.toml | 4 | . | . | . | 3 | . | . | . | 4 | 1 | . | . | . | . | . | . |

### Expert time estimate

- Reading the register, specification, charter, policies and handbooks; building a rule map: 5 h
- Writing parsers for 19 formats (fixed width, mbox, ics, sqlite, parquet, xlsx 1900/1904, docx/pdf tables): 6 h
- Time normalization: offsets, epochs, local zones with DST rules, terminal skew, serials; reconciling partition controls: 4 h
- Identifier resolution (merges, legacy crosswalk, aliases), errata, replay, dedup and keeper rules: 4 h
- Label resolution: three chargeback networks, ARN linkage and reassignment, notices, cases with replica window, votes: 5 h
- Point-in-time features with publication schedules, outages, lags, corrections, voids and quarantines: 4 h
- Clusters, salted splits, pins; train-only fitting, vocabularies, class weights, scoring, AUC and PSI: 3 h
- Delta-release mode, determinism, falsification against invariants, decoy triage and re-runs: 3 h
- Total: 34 hours, about four working days for a senior ML data engineer.

## Provenance

```yaml
uuid: 9f5486ac-ace6-5767-85e3-14ebb268f410
instance_id: 9f5486ac-ace6-5767-85e3-14ebb268f410
task_name: terminal-bench/9f5486ac-ace6-5767-85e3-14ebb268f410
solve_sh_sha256: 62a5938d43ddbb08480a2f3357dbf06bab2d9467b93691636da35fd782962880
solve_py_sha256: 0394dc22cf20dd7977b03765ab27e504bc6f10db4caf61f5969458606f6adfc5
generator_sources_sha256: 8f1d813dcec1dcf87ee8cac8c48f32841b41ffb12de136115cc925a4452ea2ae  # GENERATOR_SHA256 in tests/test_output.py
language: python
golden_score_channel_a: 1.0  # tests-only oracle runs
```
