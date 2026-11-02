# RULE_TRACE sentinel-policy-recompute (t1, 26 Oct 2026)

Every branch of the test reference (tests/test_output.py `evaluate`, `build_from_spec`, `pooled_deltas`, `unit_reader`, `ledger_controls`) traced to its stated sentence. Line numbers: environment/data files and tests/test_output.py after t1. No generator branch is without a sentence.

| rule id | sentence file:line | generator branch | tests |
|---|---|---|---|
| R01 active bundle B7, not latest B9 | boot_manifest.toml:3-4, bundle_ledger.jsonc:2-3, migration_notice.yml:2-3 | ACTIVE_BUNDLE, trace active_bundle | trace doc, all hidden w5 |
| R02 principal from role_key of the active bundle | bundle_ledger.jsonc:2, principal_role_index.yaml | PARAM_KEY, TENANT | all hidden |
| R03 retired alias table not used | principal_alias_table.jsonc:2 | PARAM_KEY K042 (not K118) | all hidden |
| R04 effective version from effective_from | policy_version_map.json:2 | EFFECTIVE_VERSION v100 | all hidden |
| R05 client claimed version ignored | request_corpus.json:5, policy_version_map.json:2 | client_version_ignored True | trace doc |
| R06 select active status only | override_precedence.conf:2 | evaluate:562 status | policy, curve, trace |
| R07 half-open window | override_precedence.conf:3 | evaluate:548 in_window | policy, curve, trace |
| R08 row and window carry effective version | override_precedence.conf:4 | evaluate:548-549 | policy, curve, trace |
| R09 window admit count | override_precedence.conf:5, effective_windows.xml admit | evaluate:571-574 admit_left | admit_hard, policy |
| R10 draw in ascending seq, refused draws neither unit | override_precedence.conf:6 | evaluate:557-576 draw | policy, curve, trace |
| R11 requires: applied earlier in the same draw (Q4, new) | override_precedence.conf:7, override_deltas.json:11 | evaluate:566-569 | requires_order_hard w5, rare_rule_pairs w3 |
| R12 timeout pool share and reshare | override_precedence.conf:8, effective_windows.xml timeout_pool, override_deltas.json:12 | pooled_deltas | timeout_pool_hard, policy, mutation_pool |
| R13 apply to base_parameters | override_precedence.conf:9, base_parameters.parquet | BASE_* constants | all hidden |
| R14 allowance keyed by region of tenant | quota_limits.cfg:7, tenant_catalog.xml region | evaluate:529-531, 570-573 | region_hard, policy |
| R15 allowance range 1 to 6 | quota_limits.cfg:6 | check_bounds allowance | generator bound |
| R16 timeout stored seconds, ms = seconds * 1000 | units_reference.txt:2-4, reconciliation_rules.conf:2 | evaluate:601 | all hidden |
| R17 delta unit by version cutover | units_reference.txt:6-7 | unit_reader | cutover_hard, policy, trace |
| R18 running timeout floor 1000 in seq order (Q1, new) | units_reference.txt:8-9 | evaluate:606-611 | running_timeout_floor_hard w5, rare_rule_pairs w3 |
| R19 after_delta = base + every applied max_records_delta | clamp_rules.txt:2 | evaluate:595, 599 | policy |
| R20 scaled = round_half_up(after_delta * mult_bps / 1000) | clamp_rules.txt:3, tenant_multiplier_table.xlsx mult_bps | scaled | policy |
| R21 max_records = min(cap, scaled) | clamp_rules.txt:4, tenant_multiplier_table.xlsx max_records_cap | evaluate:599 | policy, mutation_allowance |
| R22 risk terms = base + every applied risk_delta | risk_weight_rounding.txt:2 | evaluate:597, 612 | curve |
| R23 per-term rounding | risk_weight_rounding.txt:3 | evaluate:612 | curve, mutation_risk |
| R24 iteration rule and seed | convergence_spec.txt:4-5, reconciliation_rules.conf:3 | evaluate:613-619 | curve |
| R25 epsilon 0, max 64 iterations | convergence_spec.txt:2-3 | evaluate:614-616 | curve |
| R26 tier = role_level of resolved principal | convergence_spec.txt:6, threshold_tier_curve.parquet | TIER, BASE_THRESHOLD | curve |
| R27 rows in ascending seq, seq unique | override_deltas.json:5 | build_from_spec reseq 10 + 3 i | all generated |
| R28 value ranges | override_deltas.json:9 | check_bounds | generator bound |
| R29 every applied row adds its deltas | override_deltas.json:12 | evaluate:594-600 | policy, curve |
| R30 alias of a principal for part of a window (Q3, new) | override_deltas.json:4 | evaluate:538-544 principal_of | principal_alias_span_hard w5, rare_rule_pairs w3 |
| R31 reissued override_id: highest seq only (Q2, new) | override_deltas.json:6 | evaluate:552-555, 564-565 | reissued_override_hard w5, rare_rule_pairs w3 |
| R32 carried clause of a superseded row (Q5, new) | override_deltas.json:13 | evaluate:587-598 carried | superseded_carry_hard w5, rare_rule_pairs w3 |
| R33 controls over every stored row | override_deltas.json:14 | ledger_controls, evaluate:629-635 | trace doc (hidden-b corrupt), all w5 full trace |
| R34 output documents and fields | output_field_spec.txt:4, 14-16 | config_doc, TRACE_KEYS | every document test |
| R35 config keys, checksum, trailer, profile | output_field_spec.txt:18-49, config_schema.json, defaults.json | config_doc | cli_init, policy |
| R36 one stored rev per row, 1 or 2 | override_deltas.json:7 | check_bounds rev 2 | generator bound (neutral) |

Count: 36 stated rules across 20 files (boot_manifest.toml, bundle_ledger.jsonc, migration_notice.yml, principal_role_index.yaml, principal_alias_table.jsonc, policy_version_map.json, request_corpus.json, override_precedence.conf, effective_windows.xml, quota_limits.cfg, tenant_catalog.xml, units_reference.txt, reconciliation_rules.conf, clamp_rules.txt, tenant_multiplier_table.xlsx, risk_weight_rounding.txt, convergence_spec.txt, threshold_tier_curve.parquet, override_deltas.json, output_field_spec.txt) in 11 formats (toml, jsonc, yml, yaml, json, conf, xml, cfg, txt, xlsx, parquet).

## Test-hardening t2 (27 Oct 2026)

| rule id | sentence file:line | generator branch | tests |
|---|---|---|---|
| R38 seq unique across rows and reports | override_deltas.json:5 | build_from_spec reports seq 11 + 3 * at | all t2 corpora |
| R39 statuses; withdrawn passes no selection; reinstated adds deltas of last earlier active row; none -> no selection (never generated, check_bounds) | override_deltas.json:14, override_precedence.conf:2 | evaluate reinstated_from / deltas_of; chain() planter | reinstated_chain_hard, rare_state_pairs_hard |
| R40 reports: curve (seq, role, converged) and reset; a reset withdraws every curve report at a lower seq | override_deltas.json:15 | evaluate standing; attach_reports withdrawn + resets | curve_reset_hard, rare_state_pairs_hard |
| R41 divisor fixed by the standing curve reports, each recomputed for its role; iteration_divisor when none stand | convergence_spec.txt:7 | evaluate witness_amount, fit_set, divisor | unique_divisor_fit_hard, rare_state_pairs_hard |
| R42 divisor range 6 to 14 | reconciliation_rules.conf:3 | DIVISORS = range(6, 15) | unique_divisor_fit_hard |
| R43 unresolved: iterations only the seed, converged and risk_threshold null | convergence_spec.txt:7, output_field_spec.txt:14-15 | evaluate divisor None branch | unique_divisor_fit_hard (utie-a/b), rare_state_pairs_hard (combo2-b) |

## Test-hardening t3 (27 Oct 2026)

| rule id | sentence file:line | generator branch | tests |
|---|---|---|---|
| R44 spare rows (withdrawn; superseded without carry; earlier row of a reissued id; never the protected source of a reinstated id) | override_deltas.json:17 | spare_seqs; plant_repair spare flag | ledger_repair_spare_hard, _tie_hard, _reconciles_hard |
| R45 repair reconciles row count and both sums with controls; empty set counts | override_deltas.json:17 | build_from_spec `_cut` / skew; repair_document | ledger_repair_reconciles_hard |
| R46 smallest total absolute timeout in ms | override_deltas.json:17, units_reference.txt:6-7 | repair_document cost | ledger_repair_cheapest_hard, _unit_hard |
| R47 equal totals -> seq list first compared one by one | override_deltas.json:17 | plant_repair tie flag | ledger_repair_tie_hard, _cheapest_hard |
| R48 no repair -> null; keys = mismatched tenants | override_deltas.json:17, output_field_spec.txt:17 | null tenant (skew +1) | ledger_repair_reconciles_hard and every whole-doc R check |
| R49 resolve writes ledger_repair.json, within 60 s | output_field_spec.txt:4, instruction.md:5 | run_resolve optional read; run_repaired_cli timeout 60 | every R check |
