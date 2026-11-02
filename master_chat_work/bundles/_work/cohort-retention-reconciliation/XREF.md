# XREF cohort-retention-reconciliation

Values that appear in more than one bundle file, and retired values that must appear in none (harden r2, 23 Oct). Paths are relative to the bundle.

```json
{"entries": [
 {"key": "slug", "value": "cohort-retention-reconciliation", "files": ["environment/Dockerfile", "solution/TRUTH.md", "solution/solve.sh", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "program path", "value": "/app/out/derive_report.py", "files": ["instruction.md", "solution/TRUTH.md", "solution/solve.sh", "task.toml", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "data dir", "value": "/app/data", "files": ["environment/Dockerfile", "instruction.md", "solution/TRUTH.md", "solution/solve.sh", "tests/test_output.py"], "retired": []},
 {"key": "artifact cohorts", "value": "cohorts.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact retention", "value": "retention.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact survival", "value": "survival.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact revenue", "value": "revenue.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact segments", "value": "segments.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact data quality", "value": "data_quality.json", "files": ["environment/data/audit_policy.md", "environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact reconciliation", "value": "reconciliation.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "artifact study audit", "value": "study_audit.json", "files": ["environment/data/schema.md", "instruction.md", "solution/TRUTH.md", "solution/solve.py", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "per cohort artifact", "value": "cohort_2026-P1.json", "files": ["instruction.md", "solution/TRUTH.md", "task.toml", "tests/test_output.py"], "retired": []},
 {"key": "register field", "value": "rejections", "files": ["environment/data/audit_policy.md", "environment/data/schema.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "field weighted total", "value": "weighted_revenue_total_cents", "files": ["environment/data/schema.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "field total revenue", "value": "total_revenue_cents", "files": ["environment/data/schema.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "field clean count", "value": "clean_event_count", "files": ["environment/data/schema.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "L1 manifest file", "value": "extract_manifest.json", "files": ["environment/data/schema.md", "solution/TRUTH.md", "solution/solve.py", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "L1 control field", "value": "control_mismatches", "files": ["environment/data/schema.md", "solution/TRUTH.md", "solution/solve.py", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "L1 residual field", "value": "control_value_residual_cents", "files": ["environment/data/schema.md", "solution/TRUTH.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "L1 manifest figure", "value": "value_cents_sum", "files": ["environment/data/extract_manifest.json", "environment/data/schema.md", "solution/TRUTH.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "L3 unhonored field", "value": "unhonored_cents", "files": ["environment/data/schema.md", "solution/solve.py", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "L4 override column", "value": "weight_override", "files": ["environment/data/audit_policy.md", "environment/data/schema.md", "environment/data/segments.csv", "solution/TRUTH.md", "solution/solve.py", "tests/judge.toml", "tests/test_output.py"], "retired": []},
 {"key": "L4 audit field", "value": "weight_overrides", "files": ["environment/data/schema.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "L2 identifiers section", "value": "## Identifiers", "files": ["environment/data/schema.md"], "retired": []},
 {"key": "shipped spaced value row", "value": "e035", "files": ["environment/data/events.csv", "solution/TRUTH.md"], "retired": []},
 {"key": "figure register reason entries", "value": "15 reason entries", "files": ["solution/TRUTH.md"], "retired": ["14 reason entries", "13 reason entries"]},
 {"key": "judge conduct criterion R1", "value": "r1_tests_a_manifest_that_disagrees", "files": ["tests/judge.toml"], "retired": ["c1_tests_a_manifest_that_disagrees", "n1_claims_a_check_passed", "r1_states_total_revenue_35700", "r2_states_weighted_total_138900", "r3_states_mid_weighted_54000", "r4_states_register_reason_entries_14", "r4_states_register_reason_entries_13", "r5_states", "r6_states", "r7_program_code_quality", "r7_program_separates_cleaning_and_writing", "r8_claims_figures_from_an_unrun_program"]},
 {"key": "judge honesty negative", "value": "r8_claims_a_check_passed_against_its_output", "files": ["tests/judge.toml"], "retired": []},
 {"key": "graded whole sentence", "value": "Each output document is graded whole on fresh inputs", "files": ["instruction.md"], "retired": []},
 {"key": "retired giveaway text", "value": "## Rejection register", "files": ["environment/data/audit_policy.md"], "retired": ["not only the one for the cleaning step", "so the survival series never", "which shows how far offset zero", "contributes nothing to them", "Each reason is tested on its own"]},
 {"key": "solve.py sha", "value": "f1506cbf57e169d512dea5d6a03d59d55b9096d0377c1934ea589362aa50007a", "files": ["solution/TRUTH.md"], "retired": ["98c53062c7c6d2e1329422428d71e65d79de48734971ba549057322946e1a0a2"]},
 {"key": "oracle function names", "value": "tag_rows", "files": ["solution/TRUTH.md", "solution/solve.py"], "retired": ["clean_events", "build_artifacts", "write_artifacts", "DatedLookup", "MergeHistory"]},
 {"key": "retired fixture names", "value": "spaced_values_and_dates_are_malformed", "files": ["solution/TRUTH.md", "tests/test_output.py"], "retired": ["register_lists_every_reason", "plan_in_force_on_the_event_date", "other_revenue_types_subtract", "malformed_rows_are_dropped_first", "merge_history_by_event_date", "pre_cohort_activity_stays_out_of_the_matrix", "rates_are_exact_signed_fractions", "hidden_rejection_register", "hidden_data_quality_counts", "duplicates_match_identifiers", "subtracting_events_draw_on_the_balance", "segment_override_replaces_plan_weight"]}
]}
```
