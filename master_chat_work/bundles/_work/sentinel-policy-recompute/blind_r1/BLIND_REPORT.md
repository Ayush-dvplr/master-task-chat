# BLIND_REPORT ecb5b69 — sentinel-policy-recompute

Session rename: the name_session.py output was `codex: no match` / `opencode: ['ses_e86c3287cffevqq2xbYzwASFT8']`. It listed the opencode session, so the rename worked there.
Start: 22:53 IST. First full write of the program: cli.py at about 22:57–22:58, so minutes_to_first_write = 5. The driver was written at 22:59.

## Files read in order
1. instruction.md
2. environment/Dockerfile
3. environment/data listing and data/tool.zip, extracted to work/x: README.md, cli.py, schema.json
4. boot_manifest.toml, bundle_ledger.jsonc, stale_version_rules.txt, migration_notice.yml, principal_role_index.yaml, principal_alias_table.jsonc, legacy_override_table.ini
5. base_parameters.parquet, threshold_tier_curve.parquet (with its schema metadata), tier_boundaries.parquet, resource_catalog.parquet
6. convergence_spec.txt, reconciliation_rules.conf, clamp_rules.txt, risk_weight_rounding.txt, units_reference.txt, override_precedence.conf
7. override_deltas.json, effective_windows.xml, superseded_windows.xml, policy_version_map.json, quota_limits.cfg, tenant_catalog.xml
8. tenant_multiplier_table.xlsx, tenant_region_multipliers.xlsx, operation_risk.xlsx
9. config_schema.json, defaults.json, env_overrides.json/.yaml, sample_config_dev/prod.json, validation_rules.json, determinism_rules.txt
10. output_field_spec.txt, report_field_spec.txt
11. Context and noise files: glossary, cache_policy, engine_settings, gateway_settings, forbidden_keys.env, numeric_constants.env, policy_digest_index.ini, bundle_checksums.ini, audit_field_spec.yml, role_level_ladder.txt, threshold_overrides.json, request_corpus.json
12. Judge file (step 5 only)

## Environment note
The system python3 was 3.14 without pyarrow, and the prompt named no venv. I created `work/venv` (uv, Python 3.12.15, pyarrow==18.1.0) to match the Dockerfile.

## Programs
- app/tool/cli.py (the repaired sentinel-ctl), with README.md and schema.json kept as shipped
- app/build_artifacts.py, the driver. Its defaults are /app/data, /app/tool, /app/out and /app/work, and it sends resolve's scratch output to /app/work/resolve so that out/ holds only the 7 artifacts.
- The program is delivered into out/ as out/tool.zip, the only out/ path the instruction names for it.

## Self-check (shipped data only)
- **Run:** the build exited rc 0 and out/ holds exactly the 7 artifacts.
- **Checks:** every validation_report check is true, the report.json sha256 equals the hash of config.json, and summary has 56 inputs.
- **Archive:** the tool.zip layout matches the original.
- **Ledger:** the controls for all 14 tenants are ok.
- **Hand recompute:** max_records 285, timeout 2250, retry 3 and risk 51 all match.
- **Determinism:** the rerun gave byte-identical results.
- **Forbidden content:** the grep found only the OOXML namespace string inside cli.py, which the original tool also has.

Result: PASS. No crash occurred, so none was fixed.

## Judge estimate
lower 5/40 = 0.125; upper 19/40 = 0.475; process criteria not performed: 7.

## Lessons for the master
- Most of the weight is on process (6 of 15 rows ask for corpora I built myself, such as boundary, half, multiplier, role_level and missing-file runs). The blind protocol forbids extra test inputs, so these rows are lost by design.
- R1 and R10 reward running and naming the shipped crash before editing. The instruction never asks for that, so they are invisible to a first-contact engineer.
- The instruction does not say where resolve's three files should go. "Write nothing under /app/out" forces a scratch dir that is never named; I chose /app/work.
- R11 expects named-file errors for missing or malformed inputs. The instruction only says that resolve "must work on any corpus with the same layout".
- Ambiguity: threshold_curve.converged could be a bool or the converged value; I wrote the value, as the instruction says "converged value".
