# XREF data-product-config-compiler (harden r1, e317de1)

Values that must agree across bundle files; retired values must appear nowhere in the bundle.
Run: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" "<BUNDLE>" "<WORK>/XREF.md"`.

```json
{"entries": [
  {"key": "task name", "value": "data-product-config-compiler", "files": ["task.toml", "solution/TRUTH.md"], "retired": []},
  {"key": "contract path", "value": "/app/data/config_contract.md", "files": ["instruction.md"], "retired": []},
  {"key": "tool archive", "value": "/app/out/tool.zip", "files": ["instruction.md", "tests/judge.toml"], "retired": []},
  {"key": "config document", "value": "config.json", "files": ["instruction.md", "environment/data/config_contract.md", "tests/test_output.py", "solution/solve.py"], "retired": []},
  {"key": "dev profile", "value": "profile_dev.json", "files": ["instruction.md", "environment/data/config_contract.md", "tests/test_output.py", "tests/judge.toml"], "retired": []},
  {"key": "prod profile", "value": "profile_prod.json", "files": ["instruction.md", "environment/data/config_contract.md", "tests/test_output.py", "tests/judge.toml"], "retired": []},
  {"key": "validation report", "value": "validation_report.json", "files": ["instruction.md", "environment/data/config_contract.md", "tests/test_output.py", "tests/judge.toml"], "retired": []},
  {"key": "summary document", "value": "summary.json", "files": ["instruction.md", "environment/data/config_contract.md", "tests/test_output.py", "tests/judge.toml"], "retired": []},
  {"key": "NL-1 defined term", "value": "Assignment of an owner on date D", "files": ["environment/data/config_contract.md", "solution/TRUTH.md"], "retired": ["The rows of one owner never overlap"]},
  {"key": "NL-1 owners.csv shape", "value": "no two rows of one owner share an", "files": ["environment/data/config_contract.md"], "retired": []},
  {"key": "NL-3 cap key", "value": "quota_cap", "files": ["environment/data/config_contract.md", "environment/data/schema_registry.json", "solution/solve.py", "tests/test_output.py", "tests/judge.toml"], "retired": []},
  {"key": "NL-3 re-share sentence", "value": "The units given back are handed out again by largest", "files": ["environment/data/config_contract.md"], "retired": ["by the same rule"]},
  {"key": "NL-4 digits", "value": "one or more of the digits 0 to 9", "files": ["environment/data/config_contract.md"], "retired": []},
  {"key": "NL-4 passed over", "value": "is passed over, and the key", "files": ["environment/data/config_contract.md"], "retired": []},
  {"key": "LV-ENUM type reason", "value": "the value does not have the key's type", "files": ["environment/data/config_contract.md"], "retired": ["a JSON boolean for an integer key", "a number with a fraction or exponent"]},
  {"key": "tests pip line", "value": "RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0", "files": ["tests/Dockerfile"], "retired": []},
  {"key": "judge mode", "value": "mode = \"batched\"", "files": ["tests/judge.toml"], "retired": []},
  {"key": "R13 check line", "value": "R13", "files": ["tests/judge.toml", "solution/solve.py"], "retired": []},
  {"key": "R14 check line", "value": "R14", "files": ["tests/judge.toml", "solution/solve.py"], "retired": []},
  {"key": "R15 check line", "value": "R15", "files": ["tests/judge.toml", "solution/solve.py"], "retired": []},
  {"key": "tests weight", "value": "0.004166666666666667", "files": ["tests/reward.toml"], "retired": []},
  {"key": "judge weight", "value": "0.013513513513513514", "files": ["tests/reward.toml"], "retired": []}
]}
```

## Lessons for the master
- Retiring the old sentence text in XREF catches a stale TRUTH.md before QC does | no change: xref_check already scans every text file.
