# XREF, dispatch-plan-reoptimization

Values copied across bundle files. INFERRED marks a value taken from the oracle run rather than read from a file.

```json
{"entries": [
 {"key": "corrected total objective (oracle shipped run)", "value": "446527364", "files": ["tests/judge.toml", "solution/TRUTH.md", "tests/test_output.py"], "retired": []},
 {"key": "published faulty objective", "value": "724451671", "files": ["solution/TRUTH.md", "tests/test_output.py"], "retired": []},
 {"key": "total setup cost (INFERRED from oracle objective.json)", "value": "19229000", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "total holding cost (INFERRED from oracle objective.json)", "value": "31756967", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "production lots opened (INFERRED, optimal_plan.jsonl rows)", "value": "75 production lots", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "uncovered units", "value": "33012", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "K14 item setup fallback", "value": "41000", "files": ["environment/data/runbook_params.yaml", "solution/TRUTH.md"], "retired": []},
 {"key": "control setup default", "value": "default_setup_cents: 96000", "files": ["environment/data/runbook_params.yaml"], "retired": []},
 {"key": "setup fallback rule", "value": "item_defaults", "files": ["environment/data/handbook_ops_v9.md", "environment/data/runbook_params.yaml", "solution/TRUTH.md", "solution/solve.py"], "retired": ["takes the runbook fallback"]},
 {"key": "lot tie rule wording", "value": "moving back", "files": ["environment/data/handbook_ops_v9.md"], "retired": ["schedule whose production\nperiod is earlier in fiscal order wins"]},
 {"key": "tests positive total", "value": "101", "files": ["solution/TRUTH.md"], "retired": []},
 {"key": "tests channel weight 0.5/101", "value": "0.0049504950495049506", "files": ["tests/reward.toml"], "retired": ["0.005494505494505495"]},
 {"key": "judge channel weight 0.5/16 (6cd567a)", "value": "0.03125", "files": ["tests/reward.toml"], "retired": ["0.02631578947368421", "0.00641025641025641", "0.027777777777777776", "0.023809523809523808"]},
 {"key": "judge positive total", "value": "(16)", "files": ["solution/TRUTH.md"], "retired": ["(19)", "(18)", "(21)"]},
 {"key": "data file count", "value": "data_files: 55", "files": ["solution/TRUTH.md"], "retired": ["cache.txt"]},
 {"key": "code quality criterion", "value": "r9_solver_code_quality", "files": ["tests/judge.toml"], "retired": []},
 {"key": "retired v0 checks", "value": "shipped_artifacts_match_contract", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": ["all_artifacts_exist", "negative_hardcoded_sample_answers", "negative_embedded_visible_records", "solver_has_python_shebang_and_exec_bit", "hidden_perturbation_recomputes", "reusable_regenerates_elsewhere", "artifact_encoding_is_canonical"]},
 {"key": "litellm pin", "value": "litellm==1.105.0", "files": ["tests/Dockerfile"], "retired": []},
 {"key": "judge mode", "value": "mode = \"batched\"", "files": ["tests/judge.toml"], "retired": []},
 {"key": "author", "value": "ayush.sah@ethara.ai", "files": ["task.toml"], "retired": []},
 {"key": "per-run time limit", "value": "400", "files": ["instruction.md", "tests/test_output.py"], "retired": []},
 {"key": "writes-outside negative", "value": "negative_writes_outside_output_dir", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "shell negative", "value": "negative_network_dependency_or_shell_cheat", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "read scope negative", "value": "negative_reads_outside_input_dir", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "shipped rejected_rows (oracle data_quality.json, rejected_records.csv rows; cc4bb7f, graded by tests only, judge R11/R12 name no figure, 77e8554 R11/R12 rewritten as code order and trajectory check)", "value": "1002", "files": ["solution/TRUTH.md"], "retired": []},
 {"key": "shipped out_of_scope_rows (INFERRED, oracle data_quality.json; cc4bb7f, graded by tests only)", "value": "1835", "files": [], "retired": []},
 {"key": "shipped retired_item rows (INFERRED, oracle rejected_records.csv; cc4bb7f)", "value": "151", "files": [], "retired": []},
 {"key": "shipped retired_item rows above cutoff 8140 (INFERRED, oracle rejected_records.csv joined to effective_seq; the a2 trap rows; cc4bb7f)", "value": "28", "files": [], "retired": []},
 {"key": "plan cutoff", "value": "plan_sequence_cutoff: 8140", "files": ["environment/data/runbook_params.yaml"], "retired": []},
 {"key": "sweep out of scope rule", "value": "counts sweep rows that survive rejection", "files": ["environment/data/handbook_ops_v9.md"], "retired": []},
 {"key": "sweep order criterion R11 deleted (6cd567a, QC v6 JD-8: settled by tests)", "value": "eleven judge criteria", "files": ["solution/TRUTH.md"], "retired": ["r11_solver_rejects_before_out_of_scope", "r11_sweep_rejects_before_out_of_scope", "twelve judge criteria"]},
 {"key": "retired row above cutoff check criterion (judge w3, 77e8554)", "value": "r11_checks_retired_row_above_cutoff", "files": ["tests/judge.toml"], "retired": ["r12_rejected_count_from_rejection_artifact", "r12_checks_retired_row_above_cutoff", "id = \"R12\""]},
 {"key": "baked answer negative (77e8554 merge)", "value": "negative_shipped_results_baked_into_solver", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "tests check count (77e8554)", "value": "registers 35", "files": ["solution/TRUTH.md"], "retired": ["registers 36"]},
 {"key": "retired items with demand rows above cutoff (INFERRED, oracle; 77e8554)", "value": "K07 and K19", "files": ["solution/TRUTH.md"], "retired": []},
 {"key": "item scope rule in oracle (6cd567a DS-20, solve side)", "value": "== \"retired\"", "files": ["solution/solve.py"], "retired": ["elif item_status[code] != \"active\":"]},
 {"key": "cutoff settling clause (6cd567a IN-16)", "value": "never counted as rejected because of the cutoff", "files": ["environment/data/handbook_ops_v9.md"], "retired": ["It is counted as out of scope."]},
 {"key": "write_input counted by writes negative (6cd567a TS-16)", "value": "(\"write_outside\", \"write_input\")", "files": ["tests/test_output.py"], "retired": ["e[\"kind\"] == \"write_outside\" for e in events"]},
 {"key": "R6 constraint label (6cd567a JD-15)", "value": "# instruction.md:9: \"All money is integer United States cents.\"", "files": ["tests/judge.toml"], "retired": []},
 {"key": "certificate wording (6cd567a DS-22)", "value": "five check keys", "files": ["solution/TRUTH.md", "environment/data/handbook_ops_v9.md"], "retired": []},
 {"key": "R8 carved from solver writes (6cd567a AL-28 side effect of TS-16)", "value": "by any means other than running its solver.py", "files": ["tests/judge.toml"], "retired": ["path under /app/data.\""]}
]}
```
