# XREF - outage-window-replan (P12 fix v1, 20552cf)

Values that must agree across bundle files. Checked by `master_chat_tasks/tools/xref_check.py <bundle> WORK/XREF.md`.

```json
{"entries": [
 {"key": "task name", "value": "outage-window-replan", "files": ["task.toml", "solution/TRUTH.md"]},
 {"key": "program path", "value": "/app/out/derive_report.py", "files": ["instruction.md", "task.toml", "solution/solve.sh"]},
 {"key": "program file name", "value": "derive_report.py", "files": ["tests/test_output.py"]},
 {"key": "run limit", "value": "60 seconds", "files": ["instruction.md", "solution/TRUTH.md"]},
 {"key": "objective pair", "value": "[risk_days, moved]", "files": ["instruction.md", "environment/data/docs/output_schema.md"]},
 {"key": "register", "value": "docs/RULES.md", "files": ["instruction.md", "solution/TRUTH.md"]},
 {"key": "reward test weight", "value": "0.005434782608695652", "files": ["tests/reward.toml"]},
 {"key": "reward judge weight (0.5/36 after R17)", "value": "0.013888888888888888", "files": ["tests/reward.toml"], "retired": ["0.014285714285714285"]},
 {"key": "run limit in tests (TS-19)", "value": "_RUN_SECONDS = 60", "files": ["tests/test_output.py"], "retired": ["_RUN_SECONDS = 90"]},
 {"key": "contract docs in every corpus (CL-7)", "value": "_SHIPPED_DOCS", "files": ["tests/test_output.py"]},
 {"key": "process group kill (TS-24)", "value": "start_new_session=True", "files": ["tests/test_output.py"]},
 {"key": "R9 clause dropped (JD-8)", "value": "handlers_act_on_errors", "files": ["tests/judge.toml"], "retired": ["a missing or malformed declared input stops the run"]},
 {"key": "objective pair criterion (AL-2)", "value": "gives_objective_pair", "files": ["tests/judge.toml"]},
 {"key": "write-only criterion (AL-2)", "value": "write only under /app/out and temporary directories", "files": ["tests/judge.toml"]},
 {"key": "TRUTH digests heading (DS-27)", "value": "Digests:", "files": ["solution/TRUTH.md"], "retired": ["Digests after the last edit", "Not yet measured on the harness", "no calibration trial has been run yet"]},
 {"key": "keywords (IN-12)", "value": "maintenance-planning", "files": ["task.toml"]}
]}
```
