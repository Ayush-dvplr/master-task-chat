# BLIND_REPORT 16ab9fc — sentinel-policy-recompute (P13)

Session rename: `name_session.py 16ab9fc` gave `codex: no match` and `opencode: ['ses_e85d05eefffeVNP8OuNuN1rhkd']`. The opencode session is listed, so the rename is treated as done.

## Files read, in order
1. environment/instruction.md
2. environment/data listing (57 entries)
3. tool.zip, extracted to work/x: README.md, cli.py, schema.json
4. output_field_spec.txt, report_field_spec.txt, validation_rules.json, determinism_rules.txt
5. boot_manifest.toml, bundle_ledger.jsonc, principal_role_index.yaml, principal_alias_table.jsonc, legacy_override_table.ini, legacy_policy_memo.pdf, stale_version_rules.txt, migration_notice.yml
6. policy_version_map.json, request_corpus.json, effective_windows.xml, superseded_windows.xml, effective_instant_examples.xml
7. override_deltas.json (conventions, rows, controls), override_precedence.conf, units_reference.txt
8. risk_weight_rounding.txt, clamp_rules.txt, convergence_spec.txt, reconciliation_rules.conf
9. quota_limits.cfg, tenant_catalog.xml, numeric_constants.env, defaults.json, config_schema.json, env_overrides.json, sample_config_dev.json, sample_config_prod.json
10. Context and decoy files: audit_field_spec.yml, bundle_checksums.ini, cache_policy.ini, engine_settings.cfg, env_overrides.yaml, forbidden_keys.env, gateway_settings.conf, glossary.txt, policy_digest_index.ini, policy_migrations.yaml, role_level_ladder.txt, permission_matrix.xml, role_scope_matrix.xml, service_accounts.xml
11. After the first compaction: threshold_overrides.json, alias_table.json, tenant_multiplier_table.xlsx, tenant_region_multipliers.xlsx, operation_risk.xlsx, and the parquet schemas (base_parameters, threshold_tier_curve, tier_boundaries, resource_catalog)
12. Step 5 only: BLIND_DIR.judge.md

## Timing
- Start: 03:18 IST.
- First full write of app/tool/cli.py and app/build.py: about 03:23 IST, so **5 minutes** to first write.

## Self-check (CHECKS.md lines 1-9): PASS
- The build ran with rc 0 and ok=true.
- Exactly the 7 named outputs exist, with the shapes from output_field_spec.
- report config_sha256 equals sha256(config.json).
- A hand recompute from the parquet rows matches max_records 285, retry_limit 3, timeout_ms 2250 and contribution 63.
- All 14 ledger controls are ok.
- A second run was byte-identical, and the zip layout matches the original.
- Coverage limits: only the shipped corpus was run, with no perturbed or edge corpora. pyarrow was absent, so only the stdlib parquet fallback ran.
- Crash fixed: no (no crash happened). There was no logic rework after the self-check.

## Judge estimate (JUDGE_ESTIMATE.md)
- lower **3 / 40**, upper **17 / 40**. No negatives fired.
- 6 process criteria were not performed (R1-R6): running the shipped tool first, the window-end corpus, the half-rounding corpus, the mult_bps rerun, the role_level rerun and the missing-input run.
- R12 also fails: FINAL_REPLY.md does not give full /app/out paths.

## Lessons for the master
- Run the shipped tool once before the first edit, and log the failing output (R1). Also log each named defect with the 3.12 change or the file it contradicts (R10).
- Self-check needs perturbed corpora: effective instant on a window end, a risk term landing on .5, changed mult_bps, changed role_level, and one declared input deleted (R2-R6). Logging the shipped data alone scores little.
- Wrap every declared-input read so a missing or malformed file exits non-zero with the file name (R11).
- The final answer must list each artifact by its full /app/out/... path (R12).
- Recompute the converged threshold and the prod max_records with a separate script, and log both comparisons (R8, R9).
