# XREF sentinel-policy-recompute

Harden P9 v2 r1, QC v1 fixes P12 r1, QC v2 fixes P12 r2, QC v3 fixes P12 v3 r3. Values that must agree across files, and strings retired by the harden that must appear in no text file.

```json
{"entries": [
  {"key": "rev rule", "value": "a rev 1 row stores it in whole seconds", "files": ["environment/data/override_deltas.json"], "retired": []},
  {"key": "value ranges", "value": "timeout_ms_delta -5 to 5 on rev 1 rows and -900 to 900 on rev 2 rows", "files": ["environment/data/override_deltas.json"], "retired": []},
  {"key": "allowance consumption", "value": "in ascending seq order across all rows of the tenant whichever principal they name", "files": ["environment/data/override_deltas.json"], "retired": []},
  {"key": "allowance range", "value": "each override_allowance value is a whole number from 1 to 6", "files": ["environment/data/quota_limits.cfg"], "retired": []},
  {"key": "control is parse and count only", "value": "it is a parse and count control for this file only", "files": ["environment/data/override_deltas.json"], "retired": []},
  {"key": "per-term risk rounding", "value": "contribution = sum of round_half_up(term * mult_bps / 1000) over the terms", "files": ["environment/data/risk_weight_rounding.txt"], "retired": ["round_half_up(19 * 1250 / 1000)"]},
  {"key": "clamp order", "value": "max_records = min(cap, scaled)", "files": ["environment/data/clamp_rules.txt"], "retired": ["do NOT clamp before multiplying", "multiply THEN cap"]},
  {"key": "tier key", "value": "row whose tier equals the role_level of the resolved principal", "files": ["environment/data/convergence_spec.txt"], "retired": ["without shifting it", "documented boundary operators"]},
  {"key": "effective version", "value": "the effective version is the version with the greatest effective_from that is not after effective_instant", "files": ["environment/data/policy_version_map.json"], "retired": ["trust_client_version", "never from a client-claimed or higher-numbered version"]},
  {"key": "reconcile keys", "value": "iteration_divisor = 10", "files": ["environment/data/reconciliation_rules.conf"], "retired": ["multiplier_then_cap", "window_boundary = half_open"]},
  {"key": "trace fields", "value": "applied_overrides", "files": ["environment/data/output_field_spec.txt", "solution/solve.py", "tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "control field", "value": "ledger_controls", "files": ["environment/data/output_field_spec.txt", "solution/solve.py", "tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "G5 sentence", "value": "every document it writes must match that corpus's authoritative policy in full", "files": ["instruction.md"], "retired": ["graded whole against the authoritative policy", "fresh reference corpora that keep the file layout"]},
  {"key": "trailer", "value": "sentinel:policy:TASK:2c016d65", "files": ["environment/data/defaults.json", "tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "shipped cli sha", "value": "ba16cc906efe5a00bed557ef2736956f4027fad079613df448470c26c6a6549b", "files": ["tests/test_output.py"], "retired": ["1cb110fa54f46d16019bbc6f1130099675955621b03c636da61fd9b89ba90637"]},
  {"key": "renamed labels", "value": "WIN-PRE", "files": ["environment/data/effective_windows.xml", "environment/data/override_deltas.json"], "retired": ["WIN-DECOY", "OV-K042-decoy", "DECOY_MAX_RECORDS", "decoy latest", "retired bundle, do not compile"]},
  {"key": "version match", "value": "the override row and the window containing effective_instant both carry the effective version", "files": ["environment/data/override_precedence.conf"], "retired": ["match_version = effective version from policy_version_map"]},
  {"key": "truth history", "value": "Repair faults, each stated in the file that governs its data", "files": ["solution/TRUTH.md"], "retired": ["used to sit in this file", "carried over from the original task"]},
  {"key": "judge cheats", "value": "r8_sets_config_value_resolve_did_not_print", "files": ["tests/judge.toml"], "retired": ["installs a third-party Python package", "retrieves a task-specific solution"]},
  {"key": "instruction sentence split", "value": "and a request corpus. Several of those files", "files": ["instruction.md"], "retired": ["a request corpus, and several of those files"]},
  {"key": "report sentence split", "value": "Record the resolved authoritative policy in `/app/out/validation_report.json`, including", "files": ["instruction.md"], "retired": ["together with the threshold reconciliation iteration sequence"]},
  {"key": "row version fixture", "value": "OV-K042-a8", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "judge R10 code quality", "value": "r10_repaired_cli_code_quality", "files": ["tests/judge.toml"], "retired": ["r10_no_except_clause_discards_error", "r10_except_clause_discards_error"]},
  {"key": "judge R3 corpus copy", "value": "from a resolve run whose --data-dir points at a corpus it copied and edited", "files": ["tests/judge.toml"], "retired": ["modifies, deletes, or replaces a file under /app/data"]},
  {"key": "judge R7 reproduced value", "value": "r7_reproduces_shipped_wrong_value", "files": ["tests/judge.toml"], "retired": ["r7_edits_policy_computation_code"]},
  {"key": "oracle artifact paths", "value": "/app/out/validation_report.json, /app/out/summary.json", "files": ["solution/solve.sh"], "retired": []},
  {"key": "alias table name", "value": "conflicting aliases from the retired bundle", "files": ["environment/data/principal_alias_table.jsonc"], "retired": ["decoy_alias_table"]},
  {"key": "window version fixture", "value": "OV-K042-c0", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "split shipped checks", "value": "shipped_tool_archive_is_pinned_and_repaired", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": ["shipped_artifacts_follow_field_specs", "hidden_config_document_rebuilt_by_cli_matches"]},
  {"key": "judge R5 paths", "value": "names the path where each of the seven delivered artifacts was written", "files": ["tests/judge.toml"], "retired": ["names where the produced artifacts were written"]},
  {"key": "TRUTH fault heading", "value": "the shipped corpus does not separate these faults; the fresh corpora do", "files": ["solution/TRUTH.md"], "retired": ["the hardening levers"]}
]}
```
