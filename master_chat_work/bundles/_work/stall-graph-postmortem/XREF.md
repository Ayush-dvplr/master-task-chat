# XREF stall-graph-postmortem (harden r1 Phase 2)

Values that must agree across files. Checked with
`python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" <BUNDLE> <WORK>/XREF.md`.

```json
{"entries": [
 {"key": "slug", "value": "stall-graph-postmortem", "files": ["task.toml", "tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "program path", "value": "/app/out/derive_report.py", "files": ["instruction.md", "task.toml", "solution/solve.sh", "solution/TRUTH.md"], "retired": []},
 {"key": "time budget seconds", "value": "21600", "files": ["instruction.md", "task.toml"], "retired": []},
 {"key": "tests weight 0.5/142", "value": "0.0035211267605633804", "files": ["tests/reward.toml"], "retired": []},
 {"key": "judge weight 0.5/27", "value": "0.018518518518518517", "files": ["tests/reward.toml"], "retired": ["0.013513513513513514"]},
 {"key": "self-check stage", "value": "self-check", "files": ["solution/solve.sh", "solution/TRUTH.md"], "retired": []},
 {"key": "solve.py sha256", "value": "cc0fb50e1f45c44758784e70ec4e8ea90ce91427328b01e15a48e4fcff7fa884", "files": ["solution/TRUTH.md"], "retired": ["8e9ee7fd4c6cd2abcb6ac6910329d1bd55e6c17b131c2be01b3b86052ac41534"]},
 {"key": "later capture bound", "value": "its own copies of the side tables", "files": ["instruction.md", "environment/data/calibration-and-controls.md"], "retired": ["beside the same side tables"]},
 {"key": "positive test total", "value": "142", "files": ["solution/TRUTH.md"], "retired": []},
 {"key": "region file", "value": "region_West.json", "files": ["instruction.md", "task.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "segment file", "value": "segment_public.json", "files": ["instruction.md", "task.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "quality file", "value": "data_quality.json", "files": ["instruction.md", "task.toml", "solution/TRUTH.md", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "control file", "value": "control-slice-figures.json", "files": ["solution/solve.py", "tests/test_output.py", "solution/solve.sh"], "retired": []},
 {"key": "last control id", "value": "CTRL-K", "files": ["environment/data/calibration-and-controls.md", "environment/data/control-slice-figures.json", "solution/solve.py", "tests/test_output.py"], "retired": []},
 {"key": "verifier pip line", "value": "RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0", "files": ["tests/Dockerfile"], "retired": []},
 {"key": "judge model", "value": "gpt-5.6-sol", "files": ["tests/judge.toml"], "retired": []}
]}
```
