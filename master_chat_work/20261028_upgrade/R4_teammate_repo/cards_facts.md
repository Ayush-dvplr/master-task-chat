## 59417607 (transform.py) steps=57
- first create: (14, 5.3, 'create'); runs: 4 (first (17, 6.5, 'run'), last (51, 22.2, 'run')); edit/other: 5
- TRUTH:8 1. (focal) Clock offset recovery per exchange day (the spine). Getting it wrong fails every `hidden_extract_NN_exact` check, because every hidden extract carries an offset change. The one-offset-per-handset reading and the per-day
- TRUTH:9 2. (focal) Amendments issued before the completion instant have no effect, and an amendment issued exactly at it has effect. Ignoring the test fails 15 of 18 hidden checks (`hidden_extract_01`, `02`, `04` to `07`, `09` to `11`, `1
- TRUTH:10 3. (focal) Allowance credit tie-break: among one client's eligible closings with the same completion instant, the lower closing reference is credited first. Every hidden extract plants such ties where the allowance runs out; rever

## aa314fee (derive_report.py) steps=62
- first create: (30, 12.7, 'create'); runs: 3 (first (33, 18.1, 'run'), last (60, 27.5, 'run')); edit/other: 4
- TRUTH:7 1. (focal) The shared fill level. Capacity is handed out by raising one level across every claiming request of a site cycle after the committed minimums are paid, so the grant of any request depends on the claims of all the others
- TRUTH:8 2. (focal) The carried shortfall. An unmet claim becomes a lot that attaches to the same identity and site, survives a withheld number of cycles, is cut before the current quantity when a ceiling binds, is discharged oldest first 
- TRUTH:9 3. (focal) The two withheld rules. Neither the governor of quantity before the July cutover nor the survival age of a carried lot is stated anywhere in the contract. Each has to be settled by testing the candidate readings against
- TRUTH:10 4. (drift) The single conversion stage. `rounding_rules.md` section 2 describes a conversion that rounds at every substitution hop; `errata_2031-07.md` replaces that section with one conversion for the whole walk. Rounding per hop
- TRUTH:11 5. (drift) The duplicate column title. Every order book part carries two columns titled `quantity`. The first governs. A dictionary reader keeps the second, which agrees with the first on roughly four rows in five. Defeats the bac
- TRUTH:12 6. (trap) Admission by recorded instant. Rows recorded after `2032-01-10T00:00:00Z` are evidence of nothing, including capacity revisions, ceilings, exceptions, state events and amendment notices. Defeats `data_quality_source_coun
- TRUTH:13 7. (trap) Identity across epochs. A reused customer identifier carries two epochs with different segments, and the two epochs share no ceiling, no commitment and no carried lot. Defeats `segment_rollups_exact` and `cross_artifact_
- TRUTH:14 8. (trap) The substitution walk. A request for an unqualified node walks the cheapest edge in force at the cycle start, at most three hops, and two nodes close a cycle between them. The shortest path to any qualified node is a dif
- TRUTH:15 9. (trap) Endorsement of amendments. A notice counts only when it was recorded after the row it amends and an approver holding that scope endorsed it at the audit instant, across three rotated log files whose stamps carry a per si
- TRUTH:16 10. (trap) The state machine. Events apply by ascending version rather than file order, a stale version is ignored, an illegal move leaves the state unchanged and still counts, and only an approved request claims capacity while he
- TRUTH:7 1. (focal) The shared fill level. Capacity is handed out by raising one level across every claiming request of a site cycle after the committed minimums are paid, so the grant of any request depends o
- TRUTH:8 2. (focal) The carried shortfall. An unmet claim becomes a lot that attaches to the same identity and site, survives a withheld number of cycles, is cut before the current quantity when a ceiling bind
- TRUTH:9 3. (focal) The two withheld rules. Neither the governor of quantity before the July cutover nor the survival age of a carried lot is stated anywhere in the contract. Each has to be settled by testing 
- TRUTH:10 4. (drift) The single conversion stage. `rounding_rules.md` section 2 describes a conversion that rounds at every substitution hop; `errata_2031-07.md` replaces that section with one conversion for th
- TRUTH:11 5. (drift) The duplicate column title. Every order book part carries two columns titled `quantity`. The first governs. A dictionary reader keeps the second, which agrees with the first on roughly four
- TRUTH:12 6. (trap) Admission by recorded instant. Rows recorded after `2032-01-10T00:00:00Z` are evidence of nothing, including capacity revisions, ceilings, exceptions, state events and amendment notices. Def
- TRUTH:13 7. (trap) Identity across epochs. A reused customer identifier carries two epochs with different segments, and the two epochs share no ceiling, no commitment and no carried lot. Defeats `segment_rollu
- TRUTH:14 8. (trap) The substitution walk. A request for an unqualified node walks the cheapest edge in force at the cycle start, at most three hops, and two nodes close a cycle between them. The shortest path 

## 42e79476 (solver.py) steps=81
- first create: (29, 8.5, 'create'); runs: 12 (first (30, 8.6, 'run'), last (80, 21.2, 'run')); edit/other: 23
- TRUTH:17 1. (focal) The previous run used a sequence cutoff of `9999` rather than the
- TRUTH:22 2. (focal) The previous run read EUR denominated cost rows and EUR denominated
- TRUTH:27 3. (focal) The previous run never opened the capital programme workbook. It used
- TRUTH:33 4. (focal) The previous run charged carrying cost at `75` basis points against a
- TRUTH:40 5. (focal) The previous run applied a zero energy surcharge. The governing
- TRUTH:47 6. (drift) A seasoned planner reaches for a value to capital ratio greedy on the
- TRUTH:54 7. (trap) The row lifecycle log binds to ledger rows through `row_uid` across
- TRUTH:61 8. (trap) The planning horizon is ordered by the fiscal ordinal in the period
- TRUTH:66 9. (trap) A key with no live setup row takes the `setup_fallback_cents` its item
- TRUTH:74 10. (trap) Equal cost lot sizing schedules are compared by their production
- TRUTH:20 committed volume registers won rows they should never have won. Defeated by
- TRUTH:26 the highest at or below the cutoff. Defeated by `hidden_*_totals`.
- TRUTH:31 project committed volumes live only inside `capital_program.xlsx`. Defeated by
- TRUTH:39 Defeated by `hidden_*_plan` and `hidden_*_sourcing`.
- TRUTH:46 Defeated by `hidden_*_coefficients`.
- TRUTH:52 answer opens far fewer setups than lot for lot does. Defeated by
- TRUTH:59 void register is a decoy channel that must change nothing. Defeated by
- TRUTH:64 and only the ordering artifacts expose it. Defeated by

## df8f123b (report.json) steps=87
- first create: (72, 18.1, 'create'); runs: 0 (first None, last None); edit/other: 3
- TRUTH:10 1. (focal) Docket membership is read from origin instants rather than from the
- TRUTH:15 2. (focal) Source precedence is applied uniformly. The due_instant class ranks
- TRUTH:23 3. (focal) Precedence is read as recency first. The governing record comes from
- TRUTH:26 4. (drift) The grace round is run on lateness alone and the clamp is
- TRUTH:30 5. (drift) Prerequisite readiness is computed only among docket pledges. Forty
- TRUTH:33 6. (trap) The rate denominator counts every docket pledge. It counts only
- TRUTH:37 7. (trap) The boundary band is left unfiled. Five pledges miss the window by
- TRUTH:41 8. (trap) Waive events are sent straight to the interface. The channel policy
- TRUTH:14 251 pledges and no other number. Defeats report_docket_membership.
- TRUTH:21 carry no authority. Defeats report_due_instants and
- TRUTH:25 amendment loses to an earlier acknowledgement. Defeats report_due_instants.
- TRUTH:29 granted total away from 10228. Defeats report_granted_minutes.
- TRUTH:32 own evidence and their own state. Defeats report_final_states.
- TRUTH:36 gives 208 and a rate of 486 per thousand. Defeats summary_rate_block.
- TRUTH:39 what makes rejections_by_reason carry out_of_window 5. Defeats
- TRUTH:43 Defeats negative_channel_rule_ignored.

## 18b5d99f (optimize.py) steps=83
- first create: (22, 8.5, 'create'); runs: 3 (first (23, 8.9, 'run'), last (78, 30.6, 'run')); edit/other: 14

## 6d12f970 (derive_report.py) steps=93
- first create: (27, 13.3, 'create'); runs: 12 (first (35, 14.1, 'run'), last (88, 44.8, 'run')); edit/other: 31
- TRUTH:21 payload checksums while carrying wrong values. Defeats the four trap checks
- TRUTH:32 any order other than the order the manifest gives, drifts. Defeats
- TRUTH:39 locally because every rollup still balances. Defeats `test_instance_summary`
- TRUTH:47 later order onto relief capacity at the site penalty rate. Defeats
- TRUTH:55 residual at zero. Defeats `test_generalises_client_identity` and
- TRUTH:62 Defeats `test_instance_region_rollups`, `test_instance_segment_rollups` and
- TRUTH:70 Defeats `test_instance_region_rollups` and `test_generalises_lane_rules`.

## 80202e15 (transform.py) steps=137
- first create: (40, 7.5, 'create'); runs: 15 (first (71, 25.5, 'run'), last (134, 60.8, 'run')); edit/other: 15
- TRUTH:7 1. (focal) C1 Multi-collector ingestion: Six collectors overlap; per subscription and window the highest-precedence valid record wins, highest seq within a collector; replayed batches, voids (with RESTORE), tombstones, quarantined
- TRUTH:8 2. (focal) C2 Time normalization: Local ISO with offsets, epoch seconds and milliseconds, Excel 1900 serials (UTC) and 1904 serials (local), host-clock readings corrected by the measured skew in force, SDK device clocks replaced b
- TRUTH:9 3. (drift) C3 Ordered schema rollout: LB schema v1 counts 429 inside err_5xx; the version per host at each window is the highest-seq rollout or rollback event with ts <= window over the latest manifest revision of its wave, ignori
- TRUTH:10 4. (focal) C4 Eligibility: Active days, suspensions (log state machine plus active orders), approved planned maintenance after ics overrides and cancellations with notice at least five site business days ahead; exclusions with a f
- TRUTH:11 5. (drift) C5 Dependency attribution: A downstream bad window is attributed, not counted, when the same account owns an active upstream subscription in the region, the link is active at the window and a final incident on the upstr
- TRUTH:12 6. (focal) C6 Entity resolution: Account aliases then charter decisions in date order with chains, plan at month end with reverts and legacy codes, region aliases, regrouping effective mid-month, enrollment class and segment.
- TRUTH:13 7. (drift) C7 Credit computation: SLA version by pin or contract signature cutover, custom enterprise schedules unless revoked, tier selection, list price with platform-wide discount or approved override, proration, half-even mino
- TRUTH:14 8. (drift) C8 Controls and HELD gate: Per file, 100-record blocks with control sums of the first field's digits must match the highest-revision register row (companions in two decoys); any missing or mismatched file holds the whol
- TRUTH:15 9. (focal) All 100 data_quality.sources entries must be exact (records, control blocks, control result per file); concept_controls and the hidden-month state test grade them.
- TRUTH:16 10. (focal) Charter-designated sections of the fifteen draft, preliminary, snapshot, mirror, unofficial and proposed files are authoritative; the rest is bait.

## 9f5486ac (transform.py) steps=183
- first create: (95, 21.8, 'create'); runs: 12 (first (101, 30.8, 'run'), last (178, 76.4, 'run')); edit/other: 41
- TRUTH:7 1. (focal) Six transaction systems encode the same payment differently (offset ISO, epoch ms, local account time, local merchant time, terminal clock with skew); dedup and every partition control depend on normalizing them. Defeat
- TRUTH:8 2. (focal) Labels must be resolved from analyst cases, three chargeback networks and weighted vendor votes with maturity censoring. Defeated test: labels_exact.
- TRUTH:9 3. (focal) Merchant risk and IP reputation features must be joined point-in-time with publication schedules, outages, lags and corrections. Defeated test: point_in_time_features_exact.
- TRUTH:10 4. (focal) Splits must follow device-linked account clusters with exemptions, pins and salted hashing. Defeated test: cluster_splits_exact.
- TRUTH:11 5. (focal) Preprocessing, vocabularies and class weights are fitted on the train split only and frozen for delta releases. Defeated test: preprocessing_state_exact, eval_delta_examples_exact.
- TRUTH:12 6. (focal) The release is gated on lineage controls of all 100 files; one missing or mis-parsed file holds the release. Defeated test: every test (HELD outputs); the HELD branch itself is graded by held_release_when_catalog_file_m
- TRUTH:13 7. (focal) The builder must reproduce the hidden delta release exactly from the prior state it wrote itself. Defeated test: eval_delta_state_and_exclusions_exact.
- TRUTH:14 8. (drift) Robust scaling with nearest-rank quantiles replaces the textbook StandardScaler/interpolated percentiles. Defeated test: preprocessing_state_exact.
- TRUTH:15 9. (drift) Effective-number class weights replace inverse-frequency weights. Defeated test: class_weights_exact.
- TRUTH:16 10. (drift) Point-in-time availability uses publication instant plus lag, not the snapshot as_of date. Defeated test: point_in_time_features_exact.
- TRUTH:7 1. (focal) Six transaction systems encode the same payment differently (offset ISO, epoch ms, local account time, local merchant time, terminal clock with skew); dedup and every partition control depe
- TRUTH:12 6. (focal) The release is gated on lineage controls of all 100 files; one missing or mis-parsed file holds the release. Defeated test: every test (HELD outputs); the HELD branch itself is graded by he

## b5c7b14c (reconcile.py) steps=46
- first create: (25, 14.1, 'create'); runs: 4 (first (28, 14.7, 'run'), last (44, 20.1, 'run')); edit/other: 9
