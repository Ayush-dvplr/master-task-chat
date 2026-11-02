# XREF cold-chain-backbone-quote

Build 57a2dd7, wave 1 harden 678c839 (P-1 span hint removed, far-reaching books; P-5 judge rebuild), Law-1 fix 25c745d (fresh books 8 to 10 cold rooms), cap-60 build b223662 (held-out far-reaching books wide_4 to wide_10). Values that must agree across files, and strings retired by wave 1 that must appear in no text file.

```json
{"entries": [
  {"key": "G5 sentence", "value": "Each output document is graded whole on fresh books, and only an exact match counts.", "files": ["instruction.md"], "retired": []},
  {"key": "limit sentence", "value": "Limit: the command must finish a book within 4 seconds per project in it plus", "files": ["environment/ci/api_contract.md"], "retired": ["at most 52 sites including the depot", "at most 95 links and at most 17 cold rooms", "Links with the depot at one end have no span limit", "joins positions more than 4 apart"]},
  {"key": "test limit", "value": "SECONDS_PER_PROJECT = 4", "files": ["tests/test_output.py"], "retired": []},
  {"key": "span rule retired", "value": "E_NO_NETWORK", "files": ["environment/ci/api_contract.md", "tests/test_output.py", "solution/solve.py"], "retired": ["E_BAD_SPAN", "SPAN = 4", "_spanning_links", "the last four positions"]},
  {"key": "wide checks", "value": "wide_networks_feasible", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "wide summary check", "value": "wide_books_summary", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "reward weights", "value": "test_output = 0.0025, judge = 0.015625", "files": ["tests/reward.toml"], "retired": ["test_output = 0.004629629629629629", "test_output = 0.0045871559633027525"]},
  {"key": "judge J4", "value": "/app/repo/src/task/core.py", "files": ["tests/judge.toml", "task.toml"], "retired": []},
  {"key": "missing file code", "value": "E_MISSING_FILE", "files": ["environment/ci/api_contract.md", "tests/judge.toml", "tests/test_output.py", "solution/solve.py"], "retired": []},
  {"key": "fresh book cold rooms", "value": "8 to 10 cold rooms", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": ["16 or 17 cold rooms", "rng.randint(16, 17)", "16 <= len(P[\"terms\"]) <= 17"]},
  {"key": "metadata check", "value": "archived_package_metadata", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
  {"key": "final reply ask", "value": "list the projects of the current book that the command rejects, with their codes.", "files": ["instruction.md"], "retired": ["finds each project's network", "split into functions of one purpose each and its handling of a project with no network", "more than 20 cold rooms", "\"stdlib\""]},
  {"key": "held-out wide books", "value": "HELD_WIDE_BOOKS", "files": ["tests/test_output.py"], "retired": []},
  {"key": "positive test weight", "value": "positive weight total 200", "files": ["solution/TRUTH.md"], "retired": ["positive weight total 109", "points of 109"]},
  {"key": "package name", "value": "task", "files": ["environment/ci/api_contract.md", "environment/repo/pyproject.toml", "tests/test_output.py"], "retired": []}
]}
```
