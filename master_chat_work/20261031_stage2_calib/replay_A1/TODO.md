# Replay A1 Progress

Session rename attempted first: `name_session.py 3d517b2` returned `NOT RENAMED: no session starts with this board id`.
Original task trees are read-only. No subagents, web, git, or host package installs.

- [x] billing 1: Inventory recorded tests, weights, judge reasons, and pass_summary agreement.
- [x] billing 2: Trace checks, hidden inputs, comparators, and swallowed exceptions.
- [x] billing 3: Run scratch oracle and captured-artifact replay; compare scores.
- [x] billing 4: Run field-level diagnostics in verifier image.
- [x] billing 5: Write attributed test loss rows.
- [x] billing 6: Write judge loss rows with trajectory references.
- [x] billing 7: Write mechanism card and QC fit.
- [x] pm25 1: Inventory recorded tests, weights, judge reasons, and pass_summary agreement.
- [x] pm25 2: Trace checks, hidden inputs, comparators, and swallowed exceptions.
- [x] pm25 3: Run scratch oracle and captured-artifact replay; compare scores.
- [x] pm25 4: Run field-level diagnostics in verifier image.
- [x] pm25 5: Write attributed test loss rows.
- [x] pm25 6: Write judge loss rows with trajectory references.
- [x] pm25 7: Write mechanism card and QC fit.
- [x] royalty 1: Inventory recorded tests, weights, judge reasons, and pass_summary agreement.
- [x] royalty 2: Trace checks, hidden inputs, comparators, and swallowed exceptions.
- [x] royalty 3: Run scratch oracle and captured-artifact replay; compare scores.
- [x] royalty 4: Run field-level diagnostics in verifier image.
- [x] royalty 5: Write attributed test loss rows.
- [x] royalty 6: Write judge loss rows with trajectory references.
- [x] royalty 7: Write mechanism card and QC fit.
- [x] Synthesis: Validate CSV attribution totals, findings, result JSON, and cleanup.

Validation passed: 46 failed test checks, 66 non-double-counted cause rows, 32 judge rows; raw losses 230 tests and 138 judge. All six successful test-only Harbor runs verified, all three replay criterion vectors match recorded values, and all oracles score 100%. Diagnostic and separation evidence retained. All own containers removed; three diagnostic verifier image tags removed; no scratch file exceeds 5 MB. Original/captured snapshot equality checked for 96 files. What-if computational root causes beyond recorded expected/actual figures remain explicitly INFERRED in FINDINGS.md.
