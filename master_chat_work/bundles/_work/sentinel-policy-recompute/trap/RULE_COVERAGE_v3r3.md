# RULE_COVERAGE sentinel-policy-recompute (P12 v3 r3, AFTER tests, P = 33)

Mutants: `WORK/rule_mutants.py` (one cli.py edit each on the oracle tool; QC v3 Gate 05 m1-m7 recreated as cli.py edits, m8-m14 added). Scores: `WORK/trap/after_v3r3_scores.txt` (local_score.py, tests channel). Paths under `environment/data/`.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| convention 3 units (rev 1 seconds x1000) | override_deltas.json:6 | m3 rev 1 not x1000; m3b \|v\|<100 read as seconds | hidden_policy(5), hidden_trace(5) |
| convention 6 allowance (tenant-wide, seq order) | override_deltas.json:9, quota_limits.cfg:6-7 | m2 consumed by K042 rows only; m2b never enforced | hidden_policy(5), hidden_curve(5), hidden_trace(5), mutation_allowance(3) |
| half-open window | override_precedence.conf:3 | m4 inclusive end | hidden_policy, hidden_curve, hidden_trace, mutation_risk, mutation_allowance (21) |
| row version | override_precedence.conf:4 | m5 row version dropped | hidden_policy, hidden_curve, hidden_trace (15) |
| window version | override_precedence.conf:4 | m14 window version dropped (closed in v3r3 by hidden-c row `OV-K042-c0`; before: 0 tests failed) | hidden_policy, hidden_curve, hidden_trace (15) |
| status | override_precedence.conf:2 | m7 status check dropped | hidden_policy, hidden_curve, hidden_trace, mutation_risk (18) |
| clamp order | clamp_rules.txt:4 | m6 clamp before multiply | mutation_risk(3), mutation_allowance(3) |
| per-term rounding | risk_weight_rounding.txt:3 | m1 rounded once on the sum | hidden_curve(5), mutation_risk(3) |
| effective version | policy_version_map.json:2 | m9 latest version, instant ignored | hidden_policy, hidden_curve, hidden_trace, mutation_risk, mutation_allowance (21) |
| tier = role_level | convergence_spec.txt:6 | m10 tier one below role_level | hidden_policy, hidden_curve, mutation_risk, mutation_allowance (16) |
| B9 vs B7 | boot_manifest.toml:3-4, bundle_ledger.jsonc:2-3, migration_notice.yml:2 | m11 B9 read as active | hidden_policy, hidden_curve, hidden_trace, mutation_risk, mutation_allowance (21) |
| client claimed version | request_corpus.json:5, policy_version_map.json:2 | m12 v205 used | hidden_policy, hidden_curve, hidden_trace, mutation_risk, mutation_allowance (21) |
| controls | override_deltas.json:11 | m13 stored controls trusted | hidden_trace(5) |
| cumulative deltas (every passing row) | override_deltas.json:9 | m8 first passing row only | hidden_policy, hidden_curve, hidden_trace (15) |

Rules uncovered: 0 (window version was the one gap; fixed with a hidden case, no row left empty).
