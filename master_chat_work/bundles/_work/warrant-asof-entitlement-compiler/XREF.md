# XREF: warrant-asof-entitlement-compiler (harden try 3)

Values that must agree across files, and retired wording that must be gone.

```json
{"entries": [
  {"key": "task slug", "value": "warrant-asof-entitlement-compiler", "files": ["task.toml"]},
  {"key": "tool name", "value": "warrant-ctl", "files": ["instruction.md", "solution/solve.py", "solution/TRUTH.md", "tests/test_output.py", "environment/data/cli_contract.md"]},
  {"key": "observation file", "value": "access_attestations.csv", "files": ["instruction.md", "environment/data/corpus_index.md", "solution/TRUTH.md"]},
  {"key": "conventions per corpus (instruction)", "value": "they belong to each corpus", "files": ["instruction.md"], "retired": ["the reviewer observations in `access_attestations.csv` are the only record of what the gateway did"]},
  {"key": "rerun promise", "value": "gateway conventions, people and records", "files": ["instruction.md"], "retired": ["with other zones, instants, configuration layers, people and records"]},
  {"key": "corpus_index observation sentence", "value": "The gateway conventions belong to the corpus, and its own observations are the record of them.", "files": ["environment/data/corpus_index.md"], "retired": ["The column is an observation; it is never an input to a profile."]},
  {"key": "contract clock clause", "value": "where that clock is a site's", "files": ["environment/data/time_rules.md"]},
  {"key": "closing message", "value": "names, for each convention left to the gateway, the reading the shipped observations show", "files": ["instruction.md"], "retired": ["exact integer or instant computed from this corpus"]},
  {"key": "runbook status", "value": "## Daily run", "files": ["environment/data/legacy_runbook.md"], "retired": ["It is reproduced in full because the first release was built to match it"]},
  {"key": "conv check first", "value": "conv_1_dev_profile_exact", "files": ["tests/test_output.py", "solution/TRUTH.md"]},
  {"key": "conv check last", "value": "conv_8_prod_profile_exact", "files": ["tests/test_output.py", "solution/TRUTH.md"]},
  {"key": "judge J4", "value": "r9_repaired_code_quality", "files": ["tests/judge.toml", "solution/TRUTH.md"]},
  {"key": "judge closing", "value": "r10_names_shipped_conventions", "files": ["tests/judge.toml", "solution/TRUTH.md"]},
  {"key": "gateway module", "value": "gateway.py", "files": ["solution/solve.py", "solution/TRUTH.md"]},
  {"key": "altered config check", "value": "altered_config_outputs_exact", "files": ["tests/test_output.py", "solution/TRUTH.md"]},
  {"key": "contract layout check", "value": "artifacts_contract_layout", "files": ["tests/test_output.py", "solution/TRUTH.md"]},
  {"key": "config split", "value": "config_heldout_resolution_exact", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": ["config_resolution_exact"]},
  {"key": "TRUTH repair route", "value": "Repair route:", "files": ["solution/TRUTH.md"], "retired": ["Reference authoring"]},
  {"key": "judge online lookup", "value": "r14_runs_online_lookup", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": ["r17_asserts_unchecked_convention", "r13_installs_or_goes_online"]}
]}
```
