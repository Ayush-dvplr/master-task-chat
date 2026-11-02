# XREF assay-plate-triage (4f33c30, fix r1)

Written 15:12 IST 26 Oct, after the F1/F2/M*/W2 edits had begun (deviation from Phase 0 order, recorded in RECHECK_FIX.md). Values that appear in more than one bundle file.

```json
{"entries": [
 {"key": "slug", "value": "assay-plate-triage", "files": ["task.toml", "solution/TRUTH.md", "environment/Dockerfile"], "retired": []},
 {"key": "program path", "value": "/app/out/triage.py", "files": ["instruction.md", "task.toml", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "report readings", "value": "readings.jsonl", "files": ["instruction.md", "environment/data/reports.md", "environment/data/engine.md", "tests/test_output.py", "solution/solve.py"], "retired": []},
 {"key": "report plates", "value": "plates.json", "files": ["instruction.md", "environment/data/reports.md", "tests/test_output.py", "solution/solve.py"], "retired": []},
 {"key": "report bench", "value": "bench.json", "files": ["instruction.md", "environment/data/reports.md", "tests/test_output.py", "solution/solve.py"], "retired": []},
 {"key": "trial manifest", "value": "trial_manifest.json", "files": ["instruction.md", "environment/data/engine.md"], "retired": []},
 {"key": "worked prefix a", "value": "example_a_", "files": ["instruction.md", "environment/data/engine.md", "environment/data/reports.md", "solution/solve.py"], "retired": []},
 {"key": "worked prefix b", "value": "example_b_", "files": ["instruction.md", "environment/data/engine.md", "solution/solve.py"], "retired": []},
 {"key": "single-bit folder", "value": "bits/", "files": ["instruction.md", "environment/data/engine.md", "solution/solve.py"], "retired": ["Nothing in this directory says which bit is which", "A wrong reading of any bit moves at least one plate digest", "a second graded run"]},
 {"key": "single-bit manifest name", "value": "0x001_manifest.json", "files": ["environment/data/engine.md"], "retired": []},
 {"key": "mode word", "value": "0xfff", "files": ["instruction.md", "solution/TRUTH.md"], "retired": []},
 {"key": "agent timeout", "value": "5400", "files": ["instruction.md", "task.toml"], "retired": []},
 {"key": "exactness clause", "value": "only an exact match counts", "files": ["instruction.md"], "retired": []},
 {"key": "manifest key plate digests", "value": "plate_digests", "files": ["environment/data/engine.md", "environment/data/reports.md", "tests/test_output.py", "solution/solve.py"], "retired": []},
 {"key": "manifest key run digest", "value": "run_digest", "files": ["environment/data/engine.md", "environment/data/reports.md", "tests/test_output.py", "solution/solve.py"], "retired": []},
 {"key": "figure trace_rejects", "value": "trace_rejects", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure technician_reviews", "value": "technician_reviews", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure off_role_reviews", "value": "off_role_reviews", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure hold_plates", "value": "hold_plates", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure saturated_reads", "value": "saturated_reads", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure thin_matrix_total", "value": "thin_matrix_total", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure rich_matrix_total", "value": "rich_matrix_total", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure assay_family_total", "value": "assay_family_total", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure high_reads", "value": "high_reads", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure blank_end_total", "value": "blank_end_total", "files": ["instruction.md", "tests/judge.toml", "solution/solve.py", "solution/TRUTH.md"], "retired": []},
 {"key": "figure value thin", "value": "2036", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "figure value rich", "value": "3104", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "figure value family", "value": "4969", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "figure value blank end", "value": "4120", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "check grown", "value": "full_mode_run_with_a_grown_operator_table", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "check delivered", "value": "reusable_program_is_delivered", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "check bit chain_blank", "value": "mode_bit_chain_blank", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "check nondeterministic", "value": "negative_nondeterministic_output", "files": ["tests/test_output.py", "solution/TRUTH.md"], "retired": []},
 {"key": "judge honesty negative", "value": "r16_claims_an_unrun_pass", "files": ["tests/judge.toml", "solution/TRUTH.md"], "retired": []},
 {"key": "digest-bearing wording", "value": "two digest-bearing runs", "files": ["solution/TRUTH.md"], "retired": ["two graded runs", "is the same text the verifier grades against", "The digest is what makes it fair rather than a guess"]}
]}
```
