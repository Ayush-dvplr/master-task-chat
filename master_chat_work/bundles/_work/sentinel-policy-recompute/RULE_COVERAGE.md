# RULE_COVERAGE sentinel-policy-recompute (Harden round 3, P = 52)

Mutants: `WORK/rule_mutants.py` (one exact edit each to the oracle cli.py; m19-m24 added for N4). Scores: OUT harden_r3/local/rule_mutants.txt (local_score.py, tests channel). Paths under `environment/data/`. Round 2 table: WORK/trap/RULE_COVERAGE_r2.md.

| rule | file:line | mutant | score | tests failed |
|---|---|---|---|---|
| N4 timeout pool, shared again across the rows that held 100 or more | override_precedence.conf:7, effective_windows.xml timeout_pool, override_deltas.json:10 | m19 pool ignored; m20 fits test taken again; m21 first share kept; m22 only dropped ms shared; m23 no drop; m24 resolved key only | 0.692 each | timeout_pool_hard, policy, mutation_risk, mutation_pool |
| N1 override_allowance keyed by region | quota_limits.cfg:6-8, override_precedence.conf:6 | m2 per tenant; m2b never enforced; m2c one counter | 0.558 / 0.558 / 0.615 | region_hard, policy, curve, trace (+ mutation_allowance for m2, m2b) |
| N2 timeout_ms_delta unit by version cutover | units_reference.txt:6-7, override_deltas.json:6 | m3 raw; m3b unit from rev | 0.712 / 0.712 | cutover_hard, policy, trace |
| N3 window admit count | override_precedence.conf:5-6, effective_windows.xml admit | m15 never enforced; m16 resolved tenant only | 0.558 / 0.558 | admit_hard, policy, curve, trace, mutation_risk |
| draw_order: a row refused by either draws neither | override_precedence.conf:6 | m17; m18 | 0.712 / 0.712 | policy, curve, trace |
| half-open window | override_precedence.conf:3 | m4 inclusive end | 0.712 | policy, curve, trace |
| row version | override_precedence.conf:4 | m5 | 0.712 | policy, curve, trace |
| window version | override_precedence.conf:4 | m14 | 0.654 | policy, curve, trace, mutation_risk |
| status | override_precedence.conf:2 | m7 | 0.654 | policy, curve, trace, mutation_risk |
| clamp order | clamp_rules.txt:2-4 | m6 clamp before multiply | 0.788 | timeout_pool_hard, mutation_allowance, mutation_pool |
| per-term rounding | risk_weight_rounding.txt:2-3 | m1 | 0.846 | curve, mutation_risk |
| effective version | policy_version_map.json:2 | m9 | 0.154 | all seven hidden w5, mutations |
| tier = role_level | convergence_spec.txt:6 | m10 | 0.250 | four _hard, policy, curve, mutations |
| B9 vs B7 | boot_manifest.toml:3-4, bundle_ledger.jsonc:2-3, migration_notice.yml:2 | m11 | 0.154 | all seven hidden w5, mutations |
| client claimed version | request_corpus.json:5, policy_version_map.json:2 | m12 | 0.154 | all seven hidden w5, mutations |
| controls over every stored row | override_deltas.json:11 | m13 | 0.904 | trace |
| every applied row adds its deltas | override_deltas.json:10, clamp_rules.txt:2, risk_weight_rounding.txt:2 | m8 first passing row only | 0.308 | cutover_hard, admit_hard, timeout_pool_hard, policy, curve, trace, mutation_risk |

Rules uncovered: 0.

# Test-hardening round t1 (26 Oct 2026), P = 80

Old mutants re-run on the t1 oracle and tests (rule_mutants.py; log OUT harden_t1/local/mutants.log); each still fails at least one check. New rules: the readings of COST_TABLE.md t1 act as mutants.

| mutant | rule | score | tests failed |
|---|---|---|---|
| m1 | per-term rounding | 0.5500 | hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_threshold_curve_document_matches(5), mutation_risk_delta_moves_only_contribution(3) |
| m2 | N1 region allowance (counted per tenant) | 0.7125 | hidden_region_allowance_hard(5), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_allowance_cut_drops_later_override(3) |
| m2b | N1 region allowance (never enforced) | 0.7125 | hidden_region_allowance_hard(5), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_allowance_cut_drops_later_override(3) |
| m2c | N1 region allowance (one counter for every row) | 0.6250 | hidden_region_allowance_hard(5), hidden_reissued_override_hard(5), hidden_requires_order_hard(5), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m3 | N2 unit cutover (timeout_ms_delta read raw) | 0.4625 | hidden_unit_cutover_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m3b | N2 unit cutover (unit taken from rev) | 0.8125 | hidden_unit_cutover_hard(5), hidden_policy_resolved_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m4 | half-open window (end inclusive) | 0.6250 | hidden_running_timeout_floor_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m5 | row version (row version check dropped) | 0.8125 | hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m6 | clamp order (clamp before multiply) | 0.5750 | hidden_timeout_pool_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_rare_rule_pairs_hard(3), mutation_allowance_cut_drops_later_override(3), mutation_pool_cut_reshares_timeout(3) |
| m7 | status (status check dropped) | 0.4875 | hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3) |
| m8 | first-only override (one override per key) | 0.2625 | hidden_unit_cutover_hard(5), hidden_window_admit_hard(5), hidden_timeout_pool_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| m9 | effective version (latest version, instant ignored) | 0.1000 | hidden_region_allowance_hard(5), hidden_unit_cutover_hard(5), hidden_window_admit_hard(5), hidden_timeout_pool_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_allowance_cut_drops_later_override(3), mutation_pool_cut_reshares_timeout(3) |
| m10 | tier = role_level (tier read one below role_level) | 0.1625 | hidden_region_allowance_hard(5), hidden_unit_cutover_hard(5), hidden_window_admit_hard(5), hidden_timeout_pool_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_allowance_cut_drops_later_override(3), mutation_pool_cut_reshares_timeout(3) |
| m11 | B9 vs B7 (latest bundle B9 read as active) | 0.1000 | hidden_region_allowance_hard(5), hidden_unit_cutover_hard(5), hidden_window_admit_hard(5), hidden_timeout_pool_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_allowance_cut_drops_later_override(3), mutation_pool_cut_reshares_timeout(3) |
| m12 | client claimed version (v205 used as effective version) | 0.1000 | hidden_region_allowance_hard(5), hidden_unit_cutover_hard(5), hidden_window_admit_hard(5), hidden_timeout_pool_hard(5), hidden_running_timeout_floor_hard(5), hidden_reissued_override_hard(5), hidden_principal_alias_span_hard(5), hidden_requires_order_hard(5), hidden_superseded_carry_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_allowance_cut_drops_later_override(3), mutation_pool_cut_reshares_timeout(3) |
| m13 | controls (stored controls trusted) | 0.9375 | hidden_dependency_trace_document_matches(5) |
| m14 | window version (window version check dropped) | 0.7750 | hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3) |
| m15 | N3 window admit (never enforced) | 0.7125 | hidden_window_admit_hard(5), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3) |
| m16 | N3 window admit (drawn by the resolved tenant only) | 0.7125 | hidden_window_admit_hard(5), hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5), mutation_risk_delta_moves_only_contribution(3) |
| m17 | draw_order (region refusal still draws an admit) | 0.8125 | hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m18 | draw_order (window refusal still draws a region unit) | 0.8125 | hidden_policy_resolved_document_matches(5), hidden_threshold_curve_document_matches(5), hidden_dependency_trace_document_matches(5) |
| m19 | N4 timeout pool ignored | 0.7375 | hidden_timeout_pool_hard(5), hidden_principal_alias_span_hard(5), hidden_policy_resolved_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| m20 | N4 fits test taken again on the second share | 0.8000 | hidden_timeout_pool_hard(5), hidden_policy_resolved_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| m21 | N4 first share kept, pool not shared again | 0.8000 | hidden_timeout_pool_hard(5), hidden_policy_resolved_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| m22 | N4 only the dropped milliseconds shared again | 0.8000 | hidden_timeout_pool_hard(5), hidden_policy_resolved_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| m23 | N4 no row dropped below 100 | 0.8000 | hidden_timeout_pool_hard(5), hidden_policy_resolved_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| m24 | N4 pool shared by the resolved key's rows only | 0.7000 | hidden_timeout_pool_hard(5), hidden_principal_alias_span_hard(5), hidden_rare_rule_pairs_hard(3), hidden_policy_resolved_document_matches(5), mutation_risk_delta_moves_only_contribution(3), mutation_pool_cut_reshares_timeout(3) |
| q1-sum, q1-final | Q1 running timeout floor (units_reference.txt:8-9) | 0.9000 | hidden_running_timeout_floor_hard(5), hidden_rare_rule_pairs_hard(3) |
| q2-none | Q2 reissued override_id (override_deltas.json:6) | 0.9000 | hidden_reissued_override_hard(5), hidden_rare_rule_pairs_hard(3) |
| q3-none / q3-nospan | Q3 principal alias span (override_deltas.json:4) | 0.9000 / 0.9375 | hidden_principal_alias_span_hard(5) (+ hidden_rare_rule_pairs_hard(3) for q3-none) |
| q4-none, q4-anyorder | Q4 requires order (override_precedence.conf:7, override_deltas.json:11) | 0.9000 | hidden_requires_order_hard(5), hidden_rare_rule_pairs_hard(3) |
| q5-none / q5-any | Q5 superseded carry (override_deltas.json:13) | 0.9000 / 0.9375 | hidden_superseded_carry_hard(5) (+ hidden_rare_rule_pairs_hard(3) for q5-none) |

Rules uncovered: 0.

# Test-hardening round t2 (27 Oct 2026), P = 98

New rules: the readings of COST_TABLE.md t2 act as mutants (WORK/t2_levers.py, log WORK/t2_levers3.log); every row fails at least one check.

| mutant | rule | score | tests failed |
|---|---|---|---|
| u-none | U divisor fixed by reports (convergence_spec.txt:7) | 0.9184 | hidden_unique_divisor_fit_hard(5), hidden_rare_state_pairs_hard(3) |
| u-firstfit | U uniqueness / unresolved verdict | 0.9184 | hidden_unique_divisor_fit_hard(5), hidden_rare_state_pairs_hard(3) |
| u-firstreport | U every standing report | 0.9184 | hidden_unique_divisor_fit_hard(5), hidden_rare_state_pairs_hard(3) |
| d1-none | D1 reset withdraws earlier reports (override_deltas.json:15) | 0.9184 | hidden_curve_reset_hard(5), hidden_rare_state_pairs_hard(3) |
| d1-first | D1 every reset (the last one decides) | 0.9184 | hidden_curve_reset_hard(5), hidden_rare_state_pairs_hard(3) |
| d2-none | D2 reinstated selects (override_precedence.conf:2) | 0.9184 | hidden_reinstated_chain_hard(5), hidden_rare_state_pairs_hard(3) |
| d2-own | D2 deltas of the earlier active row (override_deltas.json:14) | 0.9184 | hidden_reinstated_chain_hard(5), hidden_rare_state_pairs_hard(3) |
| d2-first | D2 last earlier active row | 0.9184 | hidden_reinstated_chain_hard(5), hidden_rare_state_pairs_hard(3) |
| q1-sum .. q5-none | Q1-Q5 (t1) | 0.8878 each | own owned check(5), rare_rule_pairs(3), rare_state_pairs(3) |

Old mutants m1-m24: their checks and corpora are unchanged (28 old corpora give identical documents), so each still fails at least one check. Rules uncovered: 0.

# Test-hardening round t3 (3022cae), P = 131

R readings of COST_TABLE.md t3 act as mutants (WORK/t3_levers.py, log WORK/t3_levers_local.log); every row fails at least one check. Old mutants m1-m24 rerun on the t3 tests: WORK/rule_mutants_t3.log.

| mutant | rule | score | tests failed |
|---|---|---|---|
| r-none | R45/R49 ledger_repair.json written | 0.7863 | all six R checks |
| r-greedy | R46 smallest total cost | 0.7863 | all six R checks |
| r-records | R45 all three figures reconcile | (generator: rbig own reading) | cheapest (rbig corpora differ) |
| r-tie-last | R47 tie-break | 0.9008 | cheapest(5), tie(5), rare_repair_pairs(3) |
| r-unit | R46 cost in ms (cutover) | 0.9008 | cheapest(5), unit(5), rare_repair_pairs(3) |
| r-q2 | R44 later row of same id -> spare | 0.9008 | tie(5), spare(5), rare_repair_pairs(3) |
| r-q5 | R44 carry rows not spare | 0.9008 | tie(5), spare(5), rare_repair_pairs(3) |
| r-d2 | R44 reinstated source not spare | 0.9008 | tie(5), spare(5), rare_repair_pairs(3) |
| (null) | R48 no repair -> null | every R corpus has a null tenant; r-greedy/r-none fail | reconciles(5) |
| fresh | Q1-Q5, U, D1, D2 readings | 0.8779 / 0.9008 | hidden_fresh_state_corpora_hard(5) plus earlier checks |
