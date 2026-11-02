## 18b5d99f readme=0.37 runs=1 final=36.81 tests=7.77 rubric=65.85 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('identity_extract_exact', 5.0, 4.9)
- ('standing_extract_exact', 5.0, 4.9)
- ('wide_kinds_extract_exact', 5.0, 4.9)
- ('errata_extract_exact', 5.0, 4.9)
- ('boundary_extract_exact', 5.0, 4.9)
- ('weak12_extract_exact', 5.0, 4.9)
- ('weak11_extract_exact', 5.0, 4.9)
- ('wk12j_extract_exact', 5.0, 4.9)
- ('wk12g_extract_exact', 5.0, 4.9)
- ('wk12i_extract_exact', 5.0, 4.9)
- ('wk12d_extract_exact', 5.0, 4.9)
- ('wk12e_extract_exact', 5.0, 4.9)
- ('wk12f_extract_exact', 5.0, 4.9)
- ('wk11a_extract_exact', 5.0, 4.9)
- ('wk11b_extract_exact', 5.0, 4.9)
- ('wk11d_extract_exact', 5.0, 4.9)
- ('wk11f_extract_exact', 5.0, 4.9)
- ('wk10b_extract_exact', 5.0, 4.9)
- ('timed_extract_exact_and_fast', 5.0, 4.9)
neg tests fired: []
rubric failed (positive):
rubric negatives fired:
- #17 w-5.0 The agent leaves a final /app/out/optimize.py that settles the kind weights the rate card leaves free by first generating complete assignments of every free wei || The final _weight_candidates recursively generates complete assignments for every free weight over 2 through 40, stores those complete candidates, and only afterward _build_context replays the journals for each candidate. This has exponential 39^k behavior for k undetermined weights, notwithstanding
- #18 w-3.0 The agent answers question 1, 2 or 4 with kind weights selected by a helper script other than /app/out/optimize.py that hard-codes the shipped kind weights, aga || Questions 1, 2, and 4 were answered through /app/work/wsearch.py and questions.py rather than by the final optimize.py's own weak-card recovery. wsearch.py explicitly hard-codes the shipped TRUE_W weights and uses them to establish the legacy withdrawal configuration.
- #19 w-3.0 The response states a size, line count or row count for a check the agent ran, other than a figure of a report under /app/out, that differs from the figure the  || The final response describes the synthetic check as having “2 000-line journals,” but the check printed journal sizes of 1630 and 1457 in step 62.
- #20 w-3.0 The response presents the module as recovering the configuration of other extracts while the trajectory contains no run at all of the module's own kind weight r || The response presents the module as deriving extract-specific configuration and supporting other extracts, but its own kind-weight recovery was never successfully run on an extract with an underdetermined rate card. The weak-card Q1/Q2/Q4 cases used separate helper search logic and patched the modul

## 42e79476 readme=0.15 runs=1 final=14.7 tests=35.64 rubric=-6.25 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('shipped_artifacts_match_contract', 1.0, 1.0)
- ('hidden_h1_coefficients', 3.0, 3.0)
- ('hidden_h1_sourcing', 5.0, 5.0)
- ('hidden_h1_totals', 5.0, 5.0)
- ('hidden_h1_certificate', 3.0, 3.0)
- ('hidden_h2_coefficients', 3.0, 3.0)
- ('hidden_h2_sourcing', 5.0, 5.0)
- ('hidden_h2_totals', 5.0, 5.0)
- ('hidden_h2_certificate', 3.0, 3.0)
- ('hidden_h3_coefficients', 3.0, 3.0)
- ('hidden_h3_sourcing', 5.0, 5.0)
- ('hidden_h3_totals', 5.0, 5.0)
- ('hidden_h3_certificate', 3.0, 3.0)
- ('hidden_h4_coefficients', 3.0, 3.0)
- ('hidden_h4_sourcing', 5.0, 5.0)
- ('hidden_h4_totals', 5.0, 5.0)
- ('hidden_h4_certificate', 3.0, 3.0)
neg tests fired: []
rubric failed (positive):
- #1 w5.0 [trajectory] The agent states in its final reply that the corrected total objective for the shipped export set is 446527364 cents. || The final reply reports 446494153 cents, not the required corrected total objective of 446527364 cents.
- #5 w1.0 [trajectory] The agent states in its final reply that the corrected plan leaves 33012 units of demand uncovered. || The final reply reports 32963 uncovered units, not the required 33012 units.
- #9 w3.0 [state_change] The agent delivers a solver.py written to ordinary Python practice: names say what each value holds, each exception handler catches a specific error and handles || The implementation is generally structured and uses specific exception handling, but important functions remain excessively long: main spans roughly 180 lines and emit spans over 300 lines. This does not satisfy the stated requirement that functions be short enough for a reader to follow.
- #11 w3.0 [trajectory] The agent checks, before finalising, how its solver.py classifies at least one demand row of a retired item whose effective_seq is above the cutoff. || The agent identified retired items and inspected rejection totals, but it did not explicitly inspect how solver.py classified a particular demand row for a retired item whose effective_seq was above cutoff.
rubric negatives fired:
- #7 w-5.0 The agent states a figure in its final reply, or claims a check passed, that its own artifacts or command output in the trajectory show with a different value o || Although the headline plan figures agree with the produced artifacts, the final reply says approximately one million alternative block partitions were checked per item. The validation script actually checks about 43000 alternatives per item, approximately 946000 across all 22 items.

## 59417607 readme=0.16 runs=1 final=15.68 tests=7.22 rubric=24.14 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('hidden_extract_01_exact', 5.0, 5.2)
- ('hidden_extract_02_exact', 5.0, 5.2)
- ('hidden_extract_03_exact', 5.0, 5.2)
- ('hidden_extract_04_exact', 5.0, 5.2)
- ('hidden_extract_05_exact', 5.0, 5.2)
- ('hidden_extract_06_exact', 5.0, 5.2)
- ('hidden_extract_07_exact', 5.0, 5.2)
- ('hidden_extract_08_exact', 5.0, 5.2)
- ('hidden_extract_09_exact', 5.0, 5.2)
- ('hidden_extract_10_exact', 5.0, 5.2)
- ('hidden_extract_11_exact', 5.0, 5.2)
- ('hidden_extract_12_exact', 5.0, 5.2)
- ('hidden_extract_13_exact', 5.0, 5.2)
- ('hidden_extract_14_exact', 5.0, 5.2)
- ('hidden_extract_15_exact', 5.0, 5.2)
- ('hidden_extract_16_exact', 5.0, 5.2)
- ('hidden_extract_17_exact', 5.0, 5.2)
- ('hidden_extract_18_exact', 5.0, 5.2)
neg tests fired: []
rubric failed (positive):
- #1 w5.0 [final_answer] The response gives 96860261500 as the figure for what-if 1, as an exact integer. || The response gives 96945842500, not the required exact integer 96860261500.
- #3 w5.0 [final_answer] The response gives 66714709500 as the figure for what-if 3, as an exact integer. || The response gives 66678709500, not the required exact integer 66714709500.
- #4 w5.0 [final_answer] The response gives 720 as the figure for what-if 4, as an exact integer. || The response gives 840, not the required exact integer 720.
- #5 w5.0 [final_answer] The response gives 20295679500 as the figure for what-if 5, as an exact integer. || The response gives 20278774500, not the required exact integer 20295679500.
- #6 w5.0 [final_answer] The response gives 34500454500 as the figure for what-if 6, as an exact integer. || The response gives 34371706500, not the required exact integer 34500454500.
- #7 w5.0 [final_answer] The response gives 5041886500 as the figure for what-if 7, as an exact integer. || The response gives 5077580500, not the required exact integer 5041886500.
- #8 w5.0 [final_answer] The response gives 143114048000 as the figure for what-if 8, as an exact integer. || The response gives 143108240000, not the required exact integer 143114048000.
- #13 w3.0 [trajectory] The agent records the files its program opens during at least one run, by any method. || No open-file tracing or equivalent recording was performed. data_quality.json lists directory contents as input_files, including files the shipped run did not open, so it is not a record of files actually opened.
- #14 w3.0 [trajectory] The agent's delivered program raises an error when more than one set of clock offsets fits the exchange register of a day. || infer_offsets resolves ties through tuple ordering and returns a selected assignment; it contains no ambiguity check that raises when multiple assignments fit equally.
- #15 w3.0 [trajectory] The agent's delivered program, when a fit comes back empty, stops with an error or widens the search to every candidate clock offset the documents state. || The program does not detect an empty exact fit and then fail or explicitly widen it. It always chooses a minimum-unexplained assignment, even when no assignment fully fits the register.
rubric negatives fired:

## 5b2b0901 readme=0.22 runs=1 final=21.77 tests=36.56 rubric=6.98 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('accelerator_responses_match_the_reference', 1.0, 1.1)
- ('segment_boundary_resets_the_accumulator', 3.0, 3.2)
- ('backlog_stops_at_its_ceiling', 3.0, 3.2)
- ('segment_budget_reads_the_whole_shift', 3.0, 3.2)
- ('verdict_ladder_takes_the_first_condition', 3.0, 3.2)
- ('endpoint_total_counts_the_reference_verdicts', 3.0, 3.2)
- ('endpoint_dispositions_follow_strikes_and_backlog', 3.0, 3.2)
- ('full_ledger_on_unseen_shift_alpha', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_bravo', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_charlie', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_delta', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_echo', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_foxtrot', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_golf', 5.0, 5.4)
- ('full_ledger_on_unseen_shift_hotel', 5.0, 5.4)
neg tests fired: []
rubric failed (positive):
- #1 w1.0 [trajectory] The agent replays a block of the recorded shift it held back while working the constants out. || The trajectory partitions and repeatedly searches blocks of the recorded shift, but it never clearly designates an untouched hold-back block before constant recovery and then replays that block afterward. The final claim about replaying designed blocks is not supported by a distinct hold-back proced
- #2 w1.0 [trajectory] The agent builds an input of its own on which two rival readings of one constant give different results and runs both readings over it. || The agent searched many rival constants on the shipped recorded input and created an empty-shift input, but it did not build its own discriminating input on which two rival readings of a constant produce different results and explicitly run both readings.
- #6 w5.0 [final_answer] The response reports a total_score figure of 688900 for the recorded shift. || The final response reports total_score as 827306, not 688900.
- #7 w5.0 [final_answer] The response reports a clear_score figure of 679698 for the recorded shift. || The final response reports clear_score as 815920, not 679698.
- #8 w5.0 [final_answer] The response reports a saturate_band_score figure of 685972 for the recorded shift. || The final response reports saturate_band_score as 823820, not 685972.
- #9 w5.0 [final_answer] The response reports a top_score_total figure of 296755 for the recorded shift. || The final response reports top_score_total as 355060, not 296755.
- #10 w5.0 [final_answer] The response reports a budget_end_total figure of 7958 for the recorded shift. || The final response reports budget_end_total as 8138, not 7958.
- #11 w3.0 [final_answer] The response reports a total_backlog figure of 1148 for the recorded shift. || The final response reports total_backlog as 1321, not 1148.
- #12 w3.0 [final_answer] The response reports a flagged_score figure of 3500 for the recorded shift. || The final response reports flagged_score as 3420, not 3500.
- #13 w3.0 [final_answer] The response reports a high_band_score figure of 2199 for the recorded shift. || The final response reports high_band_score as 2757, not 2199.
- #15 w1.0 [final_answer] The response reports a throttle_endpoints figure of 2 for the recorded shift. || The final response reports throttle_endpoints as 3, not 2.
- #16 w3.0 [state_change] The agent leaves the delivered /app/out/gate.py as ordinary readable Python: the stages are split into named functions rather than one long body, the recovered  || The delivered gate.py is ordinary readable Python with named constants and no evident debugging leftovers, but the scoring stages are kept together in one long resolve function rather than being split into named stage functions as required by this criterion.
rubric negatives fired:

## 6d12f970 readme=0.34 runs=1 final=33.9 tests=3.09 rubric=64.71 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('test_instance_summary', 3.0, 3.1)
- ('test_instance_region_rollups', 5.0, 5.2)
- ('test_instance_segment_rollups', 5.0, 5.2)
- ('test_instance_reconciliation', 3.0, 3.1)
- ('test_instance_calibration_and_dispositions', 3.0, 3.1)
- ('test_trap_rotation_shadow_count', 5.0, 5.2)
- ('test_trap_island_permutation_keystream', 5.0, 5.2)
- ('test_trap_chain_delta_drift', 5.0, 5.2)
- ('test_trap_rotor_window_quantisation', 5.0, 5.2)
- ('test_generalises_held_out_parameters', 5.0, 5.2)
- ('test_generalises_lane_rules', 5.0, 5.2)
- ('test_generalises_admission_rules', 5.0, 5.2)
- ('test_generalises_site_layout', 5.0, 5.2)
- ('test_generalises_client_identity', 5.0, 5.2)
- ('test_generalises_revision_windows', 5.0, 5.2)
- ('test_generalises_placement_contention', 5.0, 5.2)
- ('test_generalises_population_shapes', 5.0, 5.2)
- ('test_format_byte_order_mark', 3.0, 3.1)
- ('test_format_padded_header_names', 1.0, 1.0)
- ('test_format_padded_cells', 1.0, 1.0)
- ('test_format_zero_padded_block_ids', 3.0, 3.1)
- ('test_format_region_name_case', 3.0, 3.1)
- ('test_format_draft_policy_ignored', 1.0, 1.0)
- ('test_format_archived_controls_ignored', 3.0, 3.1)
neg tests fired: []
rubric failed (positive):
- #18 w3.0 [trajectory] The agent runs its delivered program on a copy of the corpus whose tables are written out in another legal form, such as a byte order mark, padded header names  || The program includes support for UTF-8 BOMs and stripped cells, but the trajectory does not show a run on a corpus whose tables were actually rewritten into another legal form.
- #19 w3.0 [trajectory] The agent places an extra document that carries rule values or control figures beside a copy of the corpus files, runs its delivered program, and confirms that  || Synthetic runs included truth CSVs, but there was no explicit baseline comparison showing that adding a document containing rule values or control figures beside an otherwise identical corpus left settlement unchanged.
- #20 w3.0 [trajectory] The agent changes one rule value in a copy of the corpus, such as a congestion bound, a base ceiling or a lane rate, re-runs its delivered program, and confirms || No run explicitly changed a policy rule such as a congestion bound, base ceiling, or lane rate and then confirmed that settlement moved in response.
- #22 w3.0 [trajectory] The agent runs its delivered program on a constructed corpus whose client directory carries a merge chain that closes on itself, and confirms which client gover || The delivered governing_client implementation handles merge cycles by choosing the lexically first identifier, but no constructed cyclic-directory corpus was run to confirm that behavior.
rubric negatives fired:

## 725e575c readme=0.36 runs=1 final=35.77 tests=96.55 rubric=-25.0 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('run_control_stamps', 5.0, 3.4)
neg tests fired: []
rubric failed (positive):
- #1 w3.0 [trajectory] The agent confirms that each of the six stage-1 ledger files its package wrote carries a run_control stamp. || The agent did not confirm that all six ledger files carry a run_control stamp. Its own inspection showed resume_state.json beginning with best_aggregate and the repaired write_outputs function writes the resume object without adding run_control, so at least resume_state.json lacks the required stamp
- #2 w3.0 [trajectory] The agent compares a value its own code computed with a total or reference value stated in the body text or tables of a shipped specification, governance or err || The agent read many specification rules and inspected computed outputs, but it did not clearly execute a comparison between a value computed by its repaired code and a non-control-count reference total or worked-example value stated in a shipped specification, governance, or errata document.
- #3 w3.0 [trajectory] The agent runs its repaired package with --feed pointing at a directory other than /app/data that holds a copy or variant of the feed. || Every reconciliation run used --feed /app/data. The later-stage test reused /app/data with the newly produced resume state rather than running against a copied or variant feed in a different directory.
- #4 w3.0 [trajectory] The agent reproduces at least one install or import failure of the shipped runledger package before its first edit to the package source. || The first import failure was observed in the same shell command after pyproject.toml and readers.py had already been edited. No shipped install or import failure was reproduced before the first source edit.
rubric negatives fired:
- #5 w-3.0 The agent states in its final response that the repaired package installs with only setuptools and the dependencies its pyproject.toml declares while every inst || The final response claims the package installs with only setuptools and its declared dependencies, but the only recorded installation used a virtual environment created with --system-site-packages, exposing all machine-installed packages. Dependency isolation was therefore not actually verified.

## 80202e15 readme=0.35 runs=1 final=34.52 tests=2.38 rubric=66.67 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('concept_ingestion_exact', 5.0, 2.4)
- ('concept_time_exact', 5.0, 2.4)
- ('concept_schema_exact', 5.0, 2.4)
- ('concept_eligibility_exact', 5.0, 2.4)
- ('concept_attribution_exact', 5.0, 2.4)
- ('concept_entities_exact', 5.0, 2.4)
- ('concept_credits_exact', 5.0, 2.4)
- ('concept_controls_exact', 5.0, 2.4)
- ('decoy_d01_lb_errors_east_replay', 5.0, 2.4)
- ('decoy_d02_svc_metrics_compacted', 5.0, 2.4)
- ('decoy_d03_client_sdk_dedup', 5.0, 2.4)
- ('decoy_d04_sla_policy_v4_draft', 5.0, 2.4)
- ('decoy_d05_credit_tiers_2026', 5.0, 2.4)
- ('decoy_d06_incident_register_preliminary', 5.0, 2.4)
- ('decoy_d07_account_snapshot_legacy', 5.0, 2.4)
- ('decoy_d08_fx_rates_unofficial', 5.0, 2.4)
- ('decoy_d09_uptime_dashboard_snapshot', 5.0, 2.4)
- ('decoy_d10_sla_report_draft', 5.0, 2.4)
- ('decoy_d11_collector_schema_proposed', 5.0, 2.4)
- ('decoy_d12_probe_results_mirror', 5.0, 2.4)
- ('decoy_d13_ingest_reprocess', 5.0, 2.4)
- ('decoy_d14_claims_crm_legacy', 5.0, 2.4)
- ('decoy_d15_region_groups_2025', 5.0, 2.4)
- ('slice_t10_encodings_line_ends', 5.0, 2.4)
- ('slice_t11_boundaries', 5.0, 2.4)
- ('slice_t12_rounding', 5.0, 2.4)
- ('slice_t13_referential_breaks', 5.0, 2.4)
- ('slice_t14_prose_overrides', 5.0, 2.4)
- ('slice_t15_statistical_bait', 5.0, 2.4)
- ('slice_t16_decoy_agreement', 5.0, 2.4)
- ('slice_t1_near_duplicate_keys', 5.0, 2.4)
- ('slice_t2_unit_scale', 5.0, 2.4)
- ('slice_t3_time_zones_epochs', 5.0, 2.4)
- ('slice_t4_locale_numerics', 5.0, 2.4)
- ('slice_t5_sentinels', 5.0, 2.4)
- ('slice_t6_voids_reversals', 5.0, 2.4)
- ('slice_t7_supersession', 5.0, 2.4)
- ('slice_t8_header_drift', 5.0, 2.4)
- ('slice_t9_record_framing', 5.0, 2.4)
- ('eval_next_month_records_exact', 5.0, 2.4)
- ('eval_next_month_state_exact', 5.0, 2.4)
neg tests fired: []
rubric failed (positive):
- #9 w3.0 [trajectory] The agent writes /app/out/transform.py as maintainable code: one function per concern with names that say what it does, parse errors handled explicitly with no  || Although the program is decomposed into named functions and has no bare except, it contains silently swallowed broad exceptions, including `except Exception: pass` while loading expected controls and ignored exceptions when loading prior output. This violates the explicit requirement that parse erro
rubric negatives fired:
- #6 w-3.0 The response claims a check or result that the agent's trajectory never shows being run or produced. || The final response claims that the standalone control harness showed every file as bad=0. However, the actual check.py executions in steps 50 and 114 reported cdn_attestations.xlsx with 101 bad blocks. The transform's internal reordered control check passed, but the specifically claimed harness resu

## 8defd7be readme=0.09 runs=1 final=9.06 tests=2.41 rubric=15.71 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('round_normalisation_gain', 1.0, 1.2)
- ('governing_count_column', 1.0, 1.2)
- ('plan_adjustment_scan', 1.0, 1.2)
- ('plan_adjustment_merge', 1.0, 1.2)
- ('plan_adjustment_fanout', 1.0, 1.2)
- ('plan_adjustment_stream', 1.0, 1.2)
- ('plan_adjustment_nested', 1.0, 1.2)
- ('plan_adjustment_hybrid', 1.0, 1.2)
- ('layout_adjustment_sparse', 1.0, 1.2)
- ('layout_adjustment_bitmap', 1.0, 1.2)
- ('layout_adjustment_column', 1.0, 1.2)
- ('charged_layout_follows_the_parent_index', 1.0, 1.2)
- ('phase_adjustment_peak', 1.0, 1.2)
- ('phase_adjustment_shoulder', 1.0, 1.2)
- ('first_lookup_phase_exemption', 1.0, 1.2)
- ('mode_adjustment_turbo', 1.0, 1.2)
- ('mode_adjustment_cold', 1.0, 1.2)
- ('rounding_of_figures_below_zero', 1.0, 1.2)
- ('debt_accrual_by_replica', 1.0, 1.2)
- ('tie_breaks_and_row_order', 1.0, 1.2)
- ('credit_release_drawdown', 1.0, 1.2)
- ('repeat_query_trailing_record', 1.0, 1.2)
- ('baseline_drift_after_each_fetch', 1.0, 1.2)
- ('doubled_relief_after_a_purge', 1.0, 1.2)
- ('miss_lock_surcharge', 1.0, 1.2)
- ('carried_state_follows_the_named_index', 1.0, 1.2)
- ('full_ledger_on_unseen_run_alpha', 5.0, 6.0)
- ('full_ledger_on_unseen_run_bravo', 5.0, 6.0)
- ('full_ledger_on_unseen_run_charlie', 5.0, 6.0)
- ('full_ledger_on_unseen_run_delta', 5.0, 6.0)
- ('full_ledger_on_unseen_run_echo', 5.0, 6.0)
- ('full_ledger_on_unseen_run_foxtrot', 5.0, 6.0)
- ('full_ledger_on_unseen_run_golf', 5.0, 6.0)
- ('full_ledger_on_unseen_run_hotel', 5.0, 6.0)
- ('full_ledger_on_unseen_run_india', 5.0, 6.0)
- ('full_ledger_on_unseen_run_juliet', 5.0, 6.0)
- ('full_ledger_on_unseen_run_kilo', 5.0, 6.0)
neg tests fired: []
rubric failed (positive):
- #2 w3.0 [trajectory] The agent sets a block of the recorded run aside while it works the constants out and then replays that held-back block and checks it. || No explicit block of the recorded lookup run was held aside and later replayed as a validation set.
- #3 w3.0 [trajectory] The agent runs two rival readings of one constant over an input of its own on which the two readings disagree. || Although many rival constant candidates were explored, the agent did not construct and run a small input of its own on which two rival readings produced different outcomes.
- #4 w3.0 [trajectory] The agent narrows one keyed adjustment from a pair of partitions that share two keyed columns and differ on the third. || The trajectory groups observations by plan, layout, and mode, but it does not identify and use a pair of partitions sharing two keyed columns and differing on the third to narrow that third adjustment.
- #5 w3.0 [trajectory] The agent works one of the reported figures out a second time through a calculation separate from the program it delivers. || The step-43 script aggregates the probe ledger to obtain the closing figures, but no requested figure is visibly calculated a second time by an independent method. The independently checked baseline bump is a firmware constant, not one of the twenty requested figures.
- #6 w3.0 [trajectory] The agent compares both of its own rollups against the two shipped reference files byte for byte. || The agent parsed the generated and reference JSON and compared values/rows semantically. It did not use a byte-for-byte comparison such as cmp or diff between both generated rollups and both shipped reference files.
- #9 w5.0 [final_answer] The response reports a total_cost figure of 78450 for the shipped catalogue run. || The response reports total_cost as 62378, not 78450.
- #10 w5.0 [final_answer] The response reports a fetch_cost figure of 55250 for the shipped catalogue run. || The response reports fetch_cost as 46554, not 55250.
- #11 w5.0 [final_answer] The response reports a heavy_band_cost figure of 51359 for the shipped catalogue run. || The response reports heavy_band_cost as 44223, not 51359.
- #12 w5.0 [final_answer] The response reports an ok_cost figure of 30861 for the shipped catalogue run. || The response reports ok_cost as 30481, not 30861.
- #13 w3.0 [final_answer] The response reports a cold_cost figure of 11303 for the shipped catalogue run. || The response reports cold_cost as 13874, not 11303.
- #14 w3.0 [final_answer] The response reports a shared_index_cost figure of 4215 for the shipped catalogue run. || The response reports shared_index_cost as 7387, not 4215.
- #15 w3.0 [final_answer] The response reports a dropped_cost figure of 67 for the shipped catalogue run. || The response reports dropped_cost as 121, not 67.
- #16 w3.0 [final_answer] The response reports a shoulder_phase_cost figure of 21897 for the shipped catalogue run. || The response reports shoulder_phase_cost as 19730, not 21897.
- #17 w1.0 [final_answer] The response reports a total_debt figure of 13606 for the shipped catalogue run. || The response reports total_debt as 58980, not 13606.
- #18 w1.0 [final_answer] The response reports a flagged_debt figure of 5877 for the shipped catalogue run. || The response reports flagged_debt as 6598, not 5877.
- #22 w1.0 [final_answer] The response reports a setup_cost figure of 15143 for the shipped catalogue run. || The response reports setup_cost as 9661, not 15143.
- #23 w1.0 [final_answer] The response reports a locked_cost figure of 8057 for the shipped catalogue run. || The response reports locked_cost as 6163, not 8057.
- #24 w1.0 [final_answer] The response reports a warm_band_cost figure of 17751 for the shipped catalogue run. || The response reports warm_band_cost as 10372, not 17751.
- #25 w1.0 [final_answer] The response reports a light_band_cost figure of 9164 for the shipped catalogue run. || The response reports light_band_cost as 7601, not 9164.
- #26 w1.0 [final_answer] The response reports a peak_phase_cost figure of 20056 for the shipped catalogue run. || The response reports peak_phase_cost as 16183, not 20056.
- #27 w1.0 [final_answer] The response reports a sparse_cost figure of 18924 for the shipped catalogue run. || The response reports sparse_cost as 15623, not 18924.
- #28 w1.0 [final_answer] The response reports a stream_cost figure of 2742 for the shipped catalogue run. || The response reports stream_cost as 2408, not 2742.
- #29 w1.0 [final_answer] The response reports a turbo_cost figure of 55290 for the shipped catalogue run. || The response reports turbo_cost as 32768, not 55290.
- #30 w1.0 [final_answer] The response reports a derived_view_cost figure of 6647 for the shipped catalogue run. || The response reports derived_view_cost as 4316, not 6647.
- #31 w1.0 [final_answer] The response reports a replica3_cost figure of 25532 for the shipped catalogue run. || The response reports replica3_cost as 16655, not 25532.
rubric negatives fired:

## 9f5486ac readme=0.2 runs=1 final=19.76 tests=2.68 rubric=36.84 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('point_in_time_features_exact', 5.0, 3.4)
- ('labels_exact', 5.0, 3.4)
- ('exclusion_register_exact', 5.0, 3.4)
- ('source_manifest_exact', 5.0, 3.4)
- ('cluster_splits_exact', 5.0, 3.4)
- ('preprocessing_state_exact', 5.0, 3.4)
- ('class_weights_exact', 5.0, 3.4)
- ('categorical_vocab_exact', 5.0, 3.4)
- ('scores_auc_psi_exact', 5.0, 3.4)
- ('slice_reports_exact', 5.0, 3.4)
- ('slice_t1_near_duplicate_keys', 5.0, 3.4)
- ('slice_t2_t4_t12_numeric_formats', 5.0, 3.4)
- ('slice_t3_time_zones_epochs', 5.0, 3.4)
- ('slice_t5_sentinels', 5.0, 3.4)
- ('slice_t6_voids_reversals', 5.0, 3.4)
- ('slice_t7_supersession', 5.0, 3.4)
- ('slice_t8_t9_header_drift_and_framing', 5.0, 3.4)
- ('slice_t10_encodings_line_ends', 5.0, 3.4)
- ('slice_t11_boundaries', 5.0, 3.4)
- ('slice_t13_referential_breaks', 5.0, 3.4)
- ('slice_t14_prose_overrides', 5.0, 3.4)
- ('slice_t15_statistical_bait', 5.0, 3.4)
- ('slice_t16_decoy_agreement', 5.0, 3.4)
- ('decoy_group_event_mirrors', 5.0, 3.4)
- ('decoy_group_label_sources', 5.0, 3.4)
- ('decoy_group_feature_sources', 5.0, 3.4)
- ('decoy_group_documents', 5.0, 3.4)
- ('eval_delta_examples_exact', 5.0, 3.4)
- ('eval_delta_state_and_exclusions_exact', 5.0, 3.4)
neg tests fired: []
rubric failed (positive):
- #3 w3.0 [trajectory] The agent checks that every candidate record of each event export ends up either as a released example or as exactly one exclusion, and reports the result of th || The agent reports only an aggregate accounting identity: 114,992 candidates minus 47,869 released equals 67,123 exclusions. It does not perform or report the required per-event-export check that, for each file, candidates equal released examples plus exactly one exclusion per remaining candidate. Th
- #4 w3.0 [trajectory] The agent checks that every account cluster of its release appears in at most one of train, val and test. || The agent assigns one split per cluster in the implementation, but it never explicitly verifies that each cluster_id occurs in at most one of train, val, and test. Its inspection counted repeated cluster IDs and overall split totals, without grouping by cluster_id and checking the number of distinct
- #11 w3.0 [state_change] The agent leaves /app/out/transform.py as code a reviewer would accept: errors are handled or raised rather than silently swallowed, there is no dead or debug c || No. The builder is a roughly 3,000-line monolithic implementation with opaque helper names such as `p`, `f`, and `fs`, which do not clearly describe their behavior. More importantly, `parse_event_file` silently treats an unrecognized event source family as an empty export by setting empty controls a
rubric negatives fired:
- #9 w-3.0 The response claims that a check, test or reconciliation passed that the trajectory shows was never run. || The final response claims that “the HELD path [was exercised] with both a non-PUBLISHED prior and a missing catalog file.” The trajectory shows a HELD-path run using a prior product summary with status HELD (step 171), but it never creates a data-directory copy with a catalog file removed or runs th

## aa314fee readme=0.18 runs=1 final=17.64 tests=3.03 rubric=32.26 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('region_ledger_backbone_exact', 5.0, 7.6)
- ('cumulative_shortfall_spine_exact', 5.0, 7.6)
- ('site_cycle_capacity_and_fill_exact', 5.0, 7.6)
- ('program_reproduces_unseen_extract_alpha', 5.0, 7.6)
- ('program_reproduces_unseen_extract_beta', 5.0, 7.6)
- ('cross_artifact_identity_triangle_holds', 5.0, 7.6)
- ('substitution_served_node_and_hops_exact', 5.0, 7.6)
- ('row_order_permutation_changes_nothing', 5.0, 7.6)
- ('granted_wafers_truncation_exact', 3.0, 4.5)
- ('outcome_and_reason_vocabulary_exact', 3.0, 4.5)
- ('policy_audit_state_and_floor_tallies_exact', 3.0, 4.5)
- ('policy_audit_substitution_and_clearing_exact', 3.0, 4.5)
- ('data_quality_source_counts_exact', 3.0, 4.5)
- ('data_quality_anomaly_tallies_exact', 3.0, 4.5)
- ('segment_rollups_exact', 3.0, 4.5)
- ('summary_spine_and_out_of_scope_exact', 3.0, 4.5)
neg tests fired: []
rubric failed (positive):
- #1 w5.0 [user_facing_message] The response states that a run which holds every carried amount at zero hands out 2628151 wafer equivalents in total across the four site documents and moves 85 || The response reports 2628042 granted and 910 changed outcomes, not the required 2628151 and 851.
- #2 w5.0 [user_facing_message] The response states that reading the contract registry as the governor of quantity before the cutover would move the governing quantity of 1877 requests and cha || The response reports 1876 differing requests and 2639128 granted, not 1877 and 2639801.
- #3 w5.0 [user_facing_message] The response states that a survival age of three cycles would expire 2823 carried lots and leave a running shortfall total of 1853621 wafer equivalents. || The response reports 3169 expired lots and 1881807 running shortfall, not 2823 and 1853621.
- #4 w5.0 [user_facing_message] The response states that leaving the clearing rule unused across the whole horizon raises the running shortfall total to 1697490 wafer equivalents and alters th || The response reports a running shortfall of 1723146 and 237 changed grants, not 1697490 and 205.
- #5 w5.0 [user_facing_message] The response states that the one at a time remainder step hands out 3221 wafer equivalents over the whole horizon and reaches 95 site cycles. || The response reports 3329 wafer equivalents across 92 site cycles, not 3221 across 95.
- #6 w5.0 [user_facing_message] The response states that, with the admission instant lifted for every file, 171 of the requests whose every source row arrived after that instant would claim ca || Although the response correctly reports 171 claiming requests, it reports claims of 49337 rather than 49249.
- #7 w5.0 [user_facing_message] The response states that honouring every amendment whatever its endorsement would move the governing quantity of 239 requests and shift the fill level in 39 sit || Although the response correctly reports 239 changed governing quantities, it reports 32 changed fill-level cells rather than 39.
- #8 w5.0 [user_facing_message] The response states that the withdrawn desk practice of sharing the capacity of each site cycle in proportion to the quantities asked for would hand out 2626670 || The response reports 2626609 granted and 14877 changed ledger grants, not 2626670 and 14832.
- #17 w1.0 [trajectory] The agent reports every closing figure from the output of a run it performed in this session and names the run or the artifact that produced each one. || The figures do match the dedicated counterfactual run shown in the trajectory, but the final response does not name that run or an artifact as the source of each reported pair.
- #18 w1.0 [state_change] The agent leaves the delivered module organised into named functions or classes that carry the stages of the derivation. || While the module has helpers, two classes, settlement functions, and apportionment functions, most derivation stages remain embedded in a single run function spanning well over a thousand lines rather than being carried by cleanly separated named stages.
rubric negatives fired:

## b5c7b14c readme=0.32 runs=1 final=31.61 tests=54.64 rubric=8.57 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('allocation_and_load_hard', 5.0, 2.6)
- ('allocation_remainder_and_floor_exact', 3.0, 1.5)
- ('audit_and_reconciliation_hard', 5.0, 2.6)
- ('closure_and_blocked_hard', 5.0, 2.6)
- ('commitment_ledger_hard', 5.0, 2.6)
- ('edge_partition_hard', 5.0, 2.6)
- ('escalation_queue_exact', 5.0, 2.6)
- ('project_lineage_hard', 5.0, 2.6)
- ('queues_and_registers_hard', 5.0, 2.6)
- ('rollups_and_provenance_hard', 5.0, 2.6)
- ('run_manifest_hard', 5.0, 2.6)
- ('survivor_allocation_exact', 3.0, 1.5)
- ('survivor_allocation_hard', 5.0, 2.6)
- ('survivor_ledger_exact', 3.0, 1.5)
- ('survivor_ledger_hard', 5.0, 2.6)
- ('survivor_month_load_exact', 3.0, 1.5)
- ('survivor_month_load_hard', 5.0, 2.6)
- ('validation_report_residuals_zero', 3.0, 1.5)
- ('wait_reserve_exact', 3.0, 1.5)
- ('wait_reserve_hard', 5.0, 2.6)
neg tests fired: []
rubric failed (positive):
- #1 w3.0 [trajectory] The agent recomputes the allocated minutes in attention_allocation.csv for at least one principal and month by a method separate from /app/out/reconcile.py and  || The trajectory displays allocation outputs and totals, but never independently recomputes allocated_minutes for a specific principal/month from budgets, reserves, demand, and largest-remainder rules and compares that result with attention_allocation.csv.
- #2 w3.0 [trajectory] The agent recomputes the debt in cadence_debt.csv for at least one cadence by a method separate from /app/out/reconcile.py and compares the two values. || Step 30 checks an internal arithmetic partition using cadence_debt.csv itself, and later diagnostics import reconcile.py's Closure. No cadence debt is independently derived from periods, discharges, and waivers and compared with cadence_debt.csv.
- #3 w3.0 [trajectory] The agent recomputes the reserve_minutes in month_load_index.csv for at least one principal and month by a method separate from /app/out/reconcile.py and compar || No reserve_minutes value for a principal/month is independently recomputed from blocked waits and waived periods and compared with month_load_index.csv.
- #4 w3.0 [trajectory] The agent recomputes the hop distances in blocking_closure.jsonl for at least one blocked commitment by a method separate from /app/out/reconcile.py and compare || The agent shows sample blocking_closure.jsonl lines but does not independently traverse the blocking graph for a commitment and compare computed shortest-hop distances with the file.
- #5 w3.0 [trajectory] The agent runs /app/out/reconcile.py on a copy of the shipped extract in which it changed one value that a rule of the protocol reads, and shows that the delive || The agent made a snapshot of the input and checked that it remained unchanged, but did not alter a protocol-read value in an input copy, rerun reconcile.py, and demonstrate a dependent output-line change.
- #6 w3.0 [trajectory] The agent runs /app/out/reconcile.py from a directory other than /app/out on a copy of the shipped extract placed at a path other than /app/data, and compares t || Runs used /app/data as the input. Although /app/work/data_snapshot was created, reconcile.py was not run against that relocated copy. The relocated runs only changed output/program paths.
- #7 w3.0 [trajectory] The agent runs /app/out/reconcile.py on an input it built in which one principal owns two or more cadences whose waivers in elapsed periods together number more || No purpose-built extract with one principal owning multiple cadences and more than four combined elapsed waivers was run, and no waiver_trace.jsonl lines from such an input were shown.
- #8 w3.0 [trajectory] The agent runs /app/out/reconcile.py on an input it built in which a blocked commitment reaches one of its blockers by two chains of blocking edges of different || No purpose-built graph containing two paths of different lengths to the same blocker was run, and no resulting blocked_commitments.csv line was shown.
- #10 w5.0 [state_change] The agent leaves /app/out/reconcile.py in which every exception handler acts on the error it catches: it raises, exits non-zero with a message, records the fail || The delivered code contains exception handlers that silently continue over parsing failures, such as integer parsing in project, manifest, cadence, and waiver reference records. These do not raise, exit with a message, record a failure, or propagate a marker to a caller that produces the specified r
- #11 w3.0 [final_answer] The response lists every identity that the validation report carries, each by its id. || The final response says that all five identities have zero residual, but it does not list I1_row_partition, I2_class_partition, I3_actor_effort, I4_project_effort, and I5_closure_frontier individually by ID.
rubric negatives fired:

## d22ff871 readme=0.51 runs=1 final=32.36 tests=25.93 rubric=38.78 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('summary_money_totals_match', 5.0, 6.2)
- ('summary_breakdowns_match', 3.0, 3.7)
- ('summary_alerts_match', 3.0, 3.7)
- ('catchment_reports_match', 3.0, 3.7)
- ('sector_reports_match', 3.0, 3.7)
- ('shipped_reports_reproduced_by_program', 3.0, 3.7)
- ('fresh_extract_summary_matches', 5.0, 6.2)
- ('fresh_extract_quality_and_budgets_match', 5.0, 6.2)
- ('fresh_extract_audit_and_buckets_match', 3.0, 3.7)
- ('revisions_duplicates_and_conflicts_resolved', 5.0, 6.2)
- ('rejection_reason_precedence_holds', 3.0, 3.7)
- ('budget_consumed_in_billing_order', 5.0, 6.2)
- ('rounding_exact_and_half_away', 5.0, 6.2)
- ('levy_precedence_and_floor_order', 3.0, 3.7)
- ('empty_buckets_and_unknown_period', 3.0, 3.7)
- ('csv_quoting_bom_and_crlf_handled', 3.0, 3.7)
neg tests fired: []
rubric failed (positive):
- #2 w3.0 [trajectory] The agent samples rows from the shipped input files to see the revised returns, the credit rows and the dates with a missing exchange rate before implementing t || No. Before implementation, the agent only viewed the first few return rows and aggregate counters such as revision frequencies and invalid field values. It did not inspect representative highest/lower revision groups, credit rows, or rows whose billed date/currency lacked an FX rate. The later inspe
- #3 w3.0 [trajectory] The agent walks one return through the money steps by hand and compares that figure against the output of its program. || The agent did not walk a specific return through every money calculation by hand and compare the resulting gross, levy, adjusted amount, surcharge, borehole adjustment, floor, and final net against the program's output. Step 19 performs an automated Decimal cross-check on 40 sampled returns, but it 
- #12 w3.0 [trajectory] The agent demonstrates, by hand on at least one licence, how the budget is consumed in billing order across a water-year boundary (year+1 when the reading month || The agent implemented and summarized the budget logic, including October–December rollover and credits reopening room, but did not hand-derive the billing-order budget consumption for any specific licence. It provided no row-by-row trace spanning a water-year boundary, no concrete credit example sho
- #13 w3.0 [trajectory] The agent states the exact rejection-reason precedence order it implemented (bad_number before bad_date before billed_before_read before unknown_licence before  || The agent implemented the precedence correctly in code, but did not explicitly state the complete required order in its response—it abbreviated it as `bad_number → … → sign_mismatch`. It also did not show any specific row containing two competing faults and demonstrate that the earlier reason won.
- #14 w3.0 [user_facing_message] The response states that monetary rounding is half-away-from-zero (not banker's rounding) and that the minimum-charge floor is doubled when a licence is over bu || The response correctly states that rounding is half-away-from-zero and that the minimum-charge floor is doubled for licence/water-year groups with status `exceeded`. However, it does not cite a concrete figure from its command output demonstrating either behavior. The reported 133 exceeded budget gr
- #15 w3.0 [trajectory] The agent shows it handled the catchment-ceiling rule on the borehole levy rate: it identifies at least one borehole whose own override exceeds its catchment ov || The implementation correctly enforces the ceiling in levy_basis_points(), and the agent's command output reports that 28 boreholes were clipped. However, it never identifies a specific borehole whose override exceeds its catchment override, nor does it show from command output the resulting levy bas
- #16 w3.0 [trajectory] The agent reconciles at least one catchment or sector bucket file against the summary totals end to end: it sums the per-return adjusted net cents it attributed || No. The agent printed adjusted-net totals for the four required catchment files and noted their return counts covered only 2,608 of 3,280 accepted returns, but it did not print an independent sum of per-return adjusted net cents for any bucket and compare it to that bucket file. It also did not show
- #17 w3.0 [user_facing_message] The response states the exact order in which the per-return amount is built after the concession step (source factor, then the excess surcharge, then the boreho || The response correctly states the post-concession order as source factor, excess surcharge, prorated borehole adjustment, then the over-budget floor. However, it does not cite a concrete per-return figure from its output demonstrating that the excess surcharge changed that return's amount; aggregate
- #18 w3.0 [trajectory] The agent hand-computes one return's gross and levy-basis conversion from the rate_to_usd_basis_points for its billed date and currency, showing the half-away-f || The agent implemented and tested the conversion logic, but it never hand-computed a specific return’s gross and USD levy-basis conversion using that return’s billed-date/currency FX rate. It did not show the charge_cents × rate / 10000 and levy_basis_cents × rate / 10000 arithmetic, demonstrate half
- #19 w3.0 [user_facing_message] The response enumerates each distinct data-quality fault class the program detected (bad number, bad date, billed-before-read, unknown licence, unknown concessi || The response does not enumerate the required data-quality fault classes with their counts. It only states that rejection reasons span all ten documented codes. Although the trajectory inspected data_quality.json and showed counts, the final response omitted the per-class counts for bad_number, bad_d
rubric negatives fired:

## d49e259f readme=0.2 runs=1 final=20.28 tests=6.38 rubric=34.18 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('mode_bit_chain_tare', 5.0, 5.3)
- ('mode_bit_dockage_echo', 5.0, 5.3)
- ('mode_bit_role_lookback', 5.0, 5.3)
- ('mode_bit_band_tier_shift', 5.0, 5.3)
- ('mode_bit_testweight_floor', 5.0, 5.3)
- ('mode_bit_custom_haul', 5.0, 5.3)
- ('mode_bit_tare_delta', 5.0, 5.3)
- ('mode_bit_testweight_order', 5.0, 5.3)
- ('mode_bit_void_absolves', 5.0, 5.3)
- ('mode_bit_count_bias', 5.0, 5.3)
- ('mode_bit_commodity_alias', 5.0, 5.3)
- ('mode_bit_embargo_span', 5.0, 5.3)
- ('mode_bit_scrap_carry', 5.0, 5.3)
- ('every_bit_except_chain_tare', 1.0, 1.1)
- ('every_bit_except_dockage_echo', 1.0, 1.1)
- ('every_bit_except_role_lookback', 1.0, 1.1)
- ('every_bit_except_band_tier_shift', 1.0, 1.1)
- ('every_bit_except_testweight_floor', 1.0, 1.1)
- ('every_bit_except_custom_haul', 1.0, 1.1)
- ('every_bit_except_tare_delta', 1.0, 1.1)
- ('every_bit_except_testweight_order', 1.0, 1.1)
- ('every_bit_except_void_absolves', 1.0, 1.1)
- ('every_bit_except_count_bias', 1.0, 1.1)
- ('every_bit_except_commodity_alias', 1.0, 1.1)
- ('every_bit_except_embargo_span', 1.0, 1.1)
- ('every_bit_except_scrap_carry', 1.0, 1.1)
- ('full_mode_intake_alpha', 5.0, 5.3)
- ('full_mode_intake_beta', 5.0, 5.3)
neg tests fired: []
rubric failed (positive):
- #1 w5.0 [final_answer] The response reports a scrap_rejects figure of 24 for the unprefixed intake. || The response reports scrap_rejects as 20, not 24.
- #2 w5.0 [final_answer] The response reports a weighman_flags figure of 33 for the unprefixed intake. || The response reports weighman_flags as 31, not 33.
- #3 w3.0 [final_answer] The response reports an off_role_flags figure of 14 for the unprefixed intake. || The response reports off_role_flags as 13, not 14.
- #4 w5.0 [final_answer] The response reports a hold_bins figure of 30 for the unprefixed intake. || The response reports hold_bins as 33, not 30.
- #5 w3.0 [final_answer] The response reports a capped_tickets figure of 10 for the unprefixed intake. || The response reports capped_tickets as 14, not 10.
- #6 w5.0 [final_answer] The response reports a light_grain_total figure of 5499 for the unprefixed intake. || The response reports light_grain_total as 3668, not 5499.
- #7 w3.0 [final_answer] The response reports a heavy_grain_total figure of 3219 for the unprefixed intake. || The response reports heavy_grain_total as 3067, not 3219.
- #9 w5.0 [final_answer] The response reports a prime_tickets figure of 90 for the unprefixed intake. || The response reports prime_tickets as 83, not 90.
- #10 w3.0 [final_answer] The response reports a tare_end_total figure of 5760 for the unprefixed intake. || The response reports tare_end_total as 5570, not 5760.
- #12 w5.0 [final_answer] The response states that every one of the bin digests the intake manifest carries agrees with the resolution its own program produced. || The response explicitly says only 21 of 49 unprefixed bin digests agree.
- #13 w3.0 [final_answer] The response states that the whole intake digest the manifest carries agrees with the resolution its own program produced. || The response explicitly says the whole-intake digest does not agree.
- #15 w3.0 [final_answer] The response states that the unprefixed intake resolves 189 tickets. || The response states that 192 tickets resolve, not 189.
- #22 w3.0 [trajectory] The agent puts the settlement program in place at its delivered path before it spends time on the mode bits it has yet to settle. || The agent spent many steps investigating mode behavior before creating /app/out/settle.py at step 47.
- #27 w1.0 [trajectory] The agent settles the mode word against the manifest digests until it has a reading for each of the thirteen bits, by any search order it chooses. || The agent stopped with only 4 of 13 bits claimed as settled and nine explicitly left open.
rubric negatives fired:

## df8f123b readme=0.25 runs=1 final=25.3 tests=11.84 rubric=38.75 judge=gpt-5.6-sol
failed tests (name, w, %of pos):
- ('report_docket_membership', 5.0, 6.6)
- ('report_due_instants', 5.0, 6.6)
- ('report_final_states', 5.0, 6.6)
- ('report_lateness_minutes', 5.0, 6.6)
- ('report_granted_minutes', 5.0, 6.6)
- ('report_reason_codes', 5.0, 6.6)
- ('summary_rate_block', 5.0, 6.6)
- ('settlement_fingerprint_agrees', 5.0, 6.6)
- ('report_provenance_and_holders', 3.0, 3.9)
- ('report_row_tail_fields', 3.0, 3.9)
- ('report_counts_block', 3.0, 3.9)
- ('scenario_alpha_block', 3.0, 3.9)
- ('scenario_beta_block', 3.0, 3.9)
- ('scenario_mode_block', 3.0, 3.9)
- ('transcript_summary_block', 3.0, 3.9)
- ('sealed_state_block', 3.0, 3.9)
- ('summary_tail_block', 3.0, 3.9)
neg tests fired: []
rubric failed (positive):
- #1 w5.0 [user_facing_message] The response states that 40 docket pledges took their governing due instant from a counterparty acknowledgement that beat a surviving register amendment, and na || The response ultimately states 40, but it does not name the acknowledgement feed file from which that figure was read. It also includes an unexplained initial figure of 7 before correcting itself.
- #2 w5.0 [user_facing_message] The response states that 38 docket pledges belong to a class whose ceiling minutes changed inside the settlement window, and names the class catalog as the sour || The response states 39 rather than the required 38 and does not identify pledge_class_catalog.csv as the source.
- #5 w5.0 [user_facing_message] The response states that 98 docket pledges entered the grace round, and names the eligibility rule that selected them. || It reports 99 entrants rather than 98 and does not state the eligibility rule that selected them.
- #6 w5.0 [user_facing_message] The response states that 38 docket holders resolved only once a trailing legal suffix was removed, and names the alias source it read. || It reports 37 holders rather than 38 and does not name counterparty_alias_map.csv as the alias source.
- #7 w5.0 [user_facing_message] The response states that 45 prerequisite edges point outside the docket, and names the edge file it counted. || It reports 44 prerequisite edges rather than 45 and does not name prereq_edges.tsv.
- #8 w5.0 [user_facing_message] The response states that 6 live suspensions fall on a recurring series this docket draws from, and names the override file it read. || Although it reports 6 live suspensions, it does not name series_instance_overrides.csv as the override source.
- #9 w5.0 [user_facing_message] The response states that the highest escalation tier carried by a breached pledge is 5 and that 21 breached pledges carry it. || It correctly identifies tier 5 as the peak but reports 20 breached carriers instead of 21.
- #10 w5.0 [user_facing_message] The response states that 62 docket governing due instants fall after a zone offset change inside the settlement window, and names the offset table it read. || It reports 61 due instants instead of 62 and does not name zone_offset_table.csv as the source.
- #16 w3.0 [trajectory] The agent orders its registrations so that every prerequisite sitting on the docket is registered ahead of the pledge that depends on it. || The registration code only included docket prerequisites that had already been registered. For cyclic dependencies it selected a pledge anyway and silently omitted the not-yet-registered prerequisite, so it did not ensure every actual docket prerequisite was registered ahead of its dependent pledge.
- #20 w3.0 [trajectory] The agent writes the settlement program so that each rule parameter is read from the shipped documents at run time rather than carried as a literal in the code. || The program hardcodes multiple rule parameters, including the cutoff, window identifier, home zone, boundary hours, legal suffixes, source orders, and due-expression times, instead of reading all such parameters from the shipped documents at runtime.
rubric negatives fired:
- #27 w-3.0 The agent states a closing message figure for which it computed no value from the corpus. || The closing response includes the figure '7' for acknowledgements before immediately correcting it to 40; no trajectory computation produced that 7.
