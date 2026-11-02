# LEVERS (b7c42a8f, teammate task, written by P12 7b203bc on 30 Oct)

No designed levers are on record (no DESIGN.md / LEVERS.md from the author). The task's difficulty, as
measured, is the set of graded items the saved opus-5 run (27 Oct, replayed on current tests 30 Oct
17:30) lost for a WRONG VALUE (all ten files were delivered, so no loss is for a missing file).

## Test checks lost for a wrong value (BEFORE replay, current tests, 12/67 earned)
| check | w | saved run's wrong value (artifacts/app/out) |
|---|---|---|
| development_spine_exact | 5 | ledger backbone differs (157 rows vs 158; 80 rows unresolved reinsurer; paid totals 40762412 vs 24968133) |
| ibnr_carryforward_exact | 5 | spine differs (alae / ceded / ibnr per row) |
| lob_cycle_capacity_and_fill_exact | 5 | cell remainder / capacity view differs |
| program_reproduces_unseen_extract_alpha | 5 | extract A digests differ |
| program_reproduces_unseen_extract_beta | 5 | extract B digests differ |
| treaty_cession_walk_exact | 5 | layer view differs (39/38/80 layer split vs reference) |
| row_order_permutation_changes_nothing | 3 | A_perm digests differ from sealed A |
| paid_to_date_dollars_exact | 3 | paid/ultimate/ceded per row differ |
| outcome_and_reason_vocabulary_exact | 3 | outcome/reason view differs |
| data_quality_source_counts_exact | 3 | cross_source_collapsed 119 vs 155, unknown_reinsurer_rows 80 vs 1, out_of_horizon_rows 0 vs 5 |
| data_quality_anomaly_tallies_exact | 3 | duplicate_conflicting 818 vs 155, fold_disambiguated 114 vs 155, gap_shifted 1 vs 0, log_continuations 0 vs 2 |
| treaty_layer_breakdown_exact | 3 | layer totals differ |
| summary_claim_counts_exact | 3 | claims_admitted 157 vs 158, claims_dropped_late 0 vs 5 (claims_retracted 10 vs sealed 0) |
| chain_ladder_development_exact | 3 | per-cycle development differs |
| ledger_order_exact | 1 | order view differs |

## Judge criteria lost for a wrong value (saved reward-details, 13/65 earned)
| criterion | w | why lost |
|---|---|---|
| R1-R14 | 3 each | closing figures (3015547, 0, 8, 2404196, 0, 184, 217, 80, 0, 0, 0, 0, 16, 0) match neither old nor reference values |
| R15 | 1 | no executed per-LOB cross-check against treaty_working.json |
| R19 | 3 | no CLM-00011 paid value reported |
| R20 | 3 | named tallies without source files |
| R21 | 1 | no RE-0412 worked example |
| R23 | 1 | did not walk the three allocation steps; claimed no capacity binds |
| R27 | 1 | overclaim ("every settled observation contradicts excess_only") |

## Rule families behind those losses (trap-survival variants, harness/variants.py)
| lever | single wrong reading | graded where |
|---|---|---|
| L1 governing paid column | reads column 7 (last header occurrence) instead of column 4 | backbone, spine, dollars, extracts |
| L2 clash-cover attachment | per-claim individual retention | layers, layer_breakdown, spine, extracts |
| L3 admission instant | keeps rows recorded after 2033-01-15T00:00:00Z | dq source counts, summary counts, ledgers |
| L4 cutover precedence | one precedence table across the cutover | backbone/dollars, extracts |
| L5 reinsurer epochs | ignores epoch_boundary (#1 only) | backbone, order, treaty by reinsurer |
| L6 chain-ladder bounds | unclipped development factor | ultimate, spine, chain_ladder_development |
| L7 remainder tie-break | remainder step ignores unmet ordering | cells, spine, extracts |

## 841c07e (QC v4) trap survival
Variants re-run on the fixed tests (runs/trap_v4_after, P 64): L1 39 -> 39, L2 21 -> 21, L3 41 -> 41, L4 45 -> 45, L5 19 -> 19, L6 22 -> 22, L7 0 -> 0. Every lever keeps 100%. Fix effects: G03-1/G05-1 none on every lever; G04-1 none; G04-2 none (settlement is pro_rata / duration_matched on shipped, A and B; no lever variant touches it).

## dbe00fc (QC v5) trap survival
Variants re-run on the fixed tests (runs/trap_v6_after, P 64): L1 39 -> 42, L2 21 -> 21, L3 41 -> 41, L4 45 -> 45, L5 19 -> 19, L6 22 -> 22, L7 0 -> 0. Every lever keeps at least 100%; L1 also loses hidden_extract_outcomes_exact now (A's ALAE moves under excess_only). Fix effects: AL-27 none on L2-L7, harder on L1; JD-5 none on every lever.
