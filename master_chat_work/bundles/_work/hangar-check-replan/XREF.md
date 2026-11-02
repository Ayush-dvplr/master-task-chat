# XREF hangar-check-replan (dabfeb4 QC v4 repair totals)

```json
{"entries": [
 {"key": "task name", "value": "hangar-check-replan", "files": ["task.toml", "solution/TRUTH.md", "environment/Dockerfile"]},
 {"key": "plan order (IN-12)", "value": "three-term order with start and finish tie-breaks", "files": ["task.toml"], "retired": ["four-term order"]},
 {"key": "probe script (DS-22)", "value": "/tmp/oracle_checks/probes.py", "files": ["solution/solve.sh", "solution/TRUTH.md"], "retired": ["solution/probes.py"]},
 {"key": "test positive total", "value": "0.5/344", "files": ["solution/TRUTH.md"], "retired": ["0.5/129", "0.5/130", "0.5/137", "0.5/242", "0.5/230"]},
 {"key": "judge positive total", "value": "0.5/39", "files": ["solution/TRUTH.md"], "retired": ["0.5/42"]},
 {"key": "reward weights", "value": "test_output = 0.0014534883720930232, judge = 0.01282051282051282", "files": ["tests/reward.toml"]},
 {"key": "split checks (TS-13)", "value": "shipped_data_quality", "files": ["tests/test_output.py"], "retired": ["shipped_plan_rows_and_rejections", "_plan_fields"]},
 {"key": "missing-input check (JD-16 R10)", "value": "program_stops_on_a_missing_input", "files": ["tests/test_output.py"]},
 {"key": "AL-2 negative", "value": "negative_writes_outside_out_dir", "files": ["tests/test_output.py", "solution/TRUTH.md"]},
 {"key": "deferred list source (JD-8)", "value": "/app/out/policy_audit.json marks deferred", "files": ["tests/judge.toml"]},
 {"key": "error stop sentence", "value": "names the file", "files": ["environment/data/docs/data_conventions.md", "tests/judge.toml"]}
,
 {"key": "Word form folders (harden_r1)", "value": "h15", "files": ["tests/test_output.py"]}
]}
```
