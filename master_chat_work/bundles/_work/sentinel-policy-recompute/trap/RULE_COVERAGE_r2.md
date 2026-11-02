# RULE_COVERAGE sentinel-policy-recompute (Harden round 2, P = 44)

Mutants: `WORK/rule_mutants.py` (one exact edit each to the oracle cli.py; m1-m7 recreate QC v3 Gate 05). Scores: `WORK/trap/after_h2_mutants.txt` (local_score.py, tests channel). Paths under `environment/data/`. Previous table: `WORK/trap/RULE_COVERAGE_v3r3.md`.

| rule | file:line | mutant | score | tests failed |
|---|---|---|---|---|
| N1 override_allowance keyed by region (catalog region) | quota_limits.cfg:6-8, override_precedence.conf:6 | m2 counted per tenant; m2b never enforced; m2c one counter for every row | 0.477 / 0.477 / 0.545 | region_hard, policy, curve, trace (+ mutation_allowance for m2, m2b) |
| N2 timeout_ms_delta unit by version cutover | units_reference.txt:6-7, override_deltas.json:6 | m3 read raw; m3b unit from rev | 0.659 / 0.659 | cutover_hard, policy, trace |
| N3 window admit count | override_precedence.conf:5-6, effective_windows.xml admit | m15 never enforced; m16 drawn by the resolved tenant only | 0.477 / 0.477 | admit_hard, policy, curve, trace, mutation_risk |
| draw_order: a row refused by either draws neither | override_precedence.conf:6 | m17 region refusal draws an admit; m18 window refusal draws a region unit | 0.659 / 0.659 | policy, curve, trace |
| half-open window | override_precedence.conf:3 | m4 inclusive end | 0.659 | policy, curve, trace |
| row version | override_precedence.conf:4 | m5 row version dropped | 0.659 | policy, curve, trace |
| window version | override_precedence.conf:4 | m14 window version dropped | 0.591 | policy, curve, trace, mutation_risk |
| status | override_precedence.conf:2 | m7 status dropped (closed in r2 by hidden-c row `OV-K042-cs`; before: 0 tests failed) | 0.591 | policy, curve, trace, mutation_risk |
| clamp order | clamp_rules.txt:2-4 | m6 clamp before multiply | 0.932 | mutation_allowance |
| per-term rounding | risk_weight_rounding.txt:2-3 | m1 rounded once on the sum | 0.818 | curve, mutation_risk |
| effective version | policy_version_map.json:2 | m9 latest version, instant ignored | 0.182 | all six hidden w5, both mutations |
| tier = role_level | convergence_spec.txt:6 | m10 tier one below role_level | 0.295 | three _hard, policy, curve, both mutations |
| B9 vs B7 | boot_manifest.toml:3-4, bundle_ledger.jsonc:2-3, migration_notice.yml:2 | m11 B9 read as active | 0.182 | all six hidden w5, both mutations |
| client claimed version | request_corpus.json:5, policy_version_map.json:2 | m12 v205 used | 0.182 | all six hidden w5, both mutations |
| controls over every stored row | override_deltas.json:11 | m13 stored controls trusted | 0.886 | trace |
| every applied row adds its deltas | override_deltas.json:10, clamp_rules.txt:2, risk_weight_rounding.txt:2 | m8 first passing row only | 0.364 | cutover_hard, admit_hard, policy, curve, trace, mutation_risk |

Rules uncovered: 0 (status was the one gap after the r2 corpora; closed with a hidden case).
