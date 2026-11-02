# FINAL_REPLY 16ab9fc (frozen 03:26 IST)

## What was built
- Repaired `sentinel-ctl` at `/app/tool/cli.py` (local: `app/tool/cli.py`), with README.md and schema.json unchanged from data/tool.zip. Fixes: `SafeConfigParser` -> `ConfigParser` (Python 3.12), deterministic JSON (sort_keys, indent 2, trailing newline), `active_bundle_id` (B7) instead of `latest_bundle_id` (B9), effective version from `policy_version_map.json` (client `claimed_version` ignored), half-open windows, full selection/draw rules from `override_precedence.conf` (active/reinstated, window+version match, admit and region allowance units, requires, reissued ids, aliases, carry), timeout_pool sharing plus the 1000 ms running floor, round_half_up scale then min(cap), `tier == role_level` lookup, curve-report divisor search with fallback divisor 10, iteration to epsilon 0, unresolved -> null. export-report drops `config_path`. Uses pyarrow when available and a stdlib parquet reader otherwise. Also reads xlsx shared strings.
- Driver `app/build.py` runs the tool for resolve, init, 5x set and validate (config), then init+set+validate for each profile, then export-report. It also writes a deterministic tool.zip (same members, stored, 1980 timestamps, 0644), summary.json and validation_report.json.

## Where each artifact was written (/app/out = out/)
config.json, report.json, tool.zip, profile_dev.json, profile_prod.json, validation_report.json, summary.json. That is exactly 7 files (CHECKS 2).

## Checked (CHECKS.md lines 1-9)
- Build rc=0 with ok=true and no command failures. Exactly 7 outputs.
- I recomputed the policy by hand from the parquet base rows (CHECKS 7) and it matches.
- report config_sha256 equals sha256(config.json) (CHECKS 6).
- A second run gave byte-identical outputs (CHECKS 8). The zip layout matches the original (CHECKS 9).
- All 14 ledger controls are ok.

## Key figures
- config: max_records 285, retry_limit 3, timeout_ms 2250, mode strict-local, profile TASK, producer sentinel-policyd, container policy-bundle, checksum crc32, trailer sentinel:policy:TASK:2c016d65.
- Resolved principal: K042 / t-atlas, active bundle B7, effective_version v100, applied_overrides [OV-K042-auth], client_version_ignored true.
- threshold: tier 4, base 40, contribution 63, iterations [40,50,51,51], converged 51 = risk_threshold.
- dev profile: 275/4/2125 (TASK-dev). prod profile: 310/3/2500 (TASK-prod).
- summary: artifact_count 7, input_count 56.
- report: ok true, 8 commands all rc 0, config_sha256 af64452c3277d5a2fbceff1e99f39cf06276da660d9a7fc43de1ef831dd70b8e.
- rejected_branches: B9, B1, legacy_override_table.ini, superseded_windows.xml, principal_alias_table.jsonc, legacy_policy_memo.pdf, ignored client versions, non-applied K042 rows.

## Known limits
- pyarrow was absent locally, so only the stdlib parquet path was exercised.
- rejected_branches is verbose (one entry per ignored client version).
- No corpus other than the shipped data was tested.
