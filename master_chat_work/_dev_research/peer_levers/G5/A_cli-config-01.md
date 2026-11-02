# A: cli-config-01. Is the low score genuine?

Recorded: overall 66.07, tests 45.78, rubric 86.36 (1 run, claude-opus-5, judge openai/gpt-5.6-sol, mode `individual`).

**Verdict: PARTLY (the tests channel is mostly ARTEFACT).** Of the 45 positive test points lost, about 5 are a genuine but contestable agent miss (spine env scope). The other 40 come from a spec/test contradiction (29), a source-text grep (3), and output types or ordering that are never stated plus a cascade (8). None of the 6 judge points lost are genuine: both criteria grade rules that are stated nowhere.

## 1. Harness health
- `result.json`: `exception_info` None. The agent ran ~13.8 min of its 7200 s budget (task.toml:35 `timeout_sec = 7200.0`). No step limit was hit: 46 trajectory steps, the last one a final message.
- `verifier/test-stdout.txt` holds only the `reward: 0.6607` line. No traceback, no `Permission denied`/`Errno 13`, no `No such file`, no collection or import errors, no skips.
- `ctrf.json`: 32 tests, 12 passed. The 5 negatives are reported as "failed", which means they did not fire. The positive total is 83 and 38 were earned = 45.78, which matches the recorded score.

## 2. Did the verifier grade real outputs? (reproduced locally)
I imported `tests/test_output.py` with a no-op `rewardkit` stub, pointed `OUT` at `trajectories/.../artifacts/app/out/`, and ran every `_check` that does not run the tool. The pass/fail set matched ctrf exactly. Each failure shows a wrong VALUE. None comes from a missing file or a crash. The cause of each wrong value:

| failed check (wt) | cause | genuine? |
|---|---|---|
| config_matches_policy (5) | Test `wanted_config()` replays only `env == "base"` ops (test_output.py L410-415). The agent replayed the valid ops of every env. A local base-only replay gives {rekey 30576, max_sessions 915, retry 0, hs 2200, mode audit-seal} = test. An all-env replay gives {21845, 422, 1, 13336, strict-seal} = agent config.json. | GENUINE but contestable: the env filter is never stated for the spine (see B). |
| aggregates_match 5, csv 3, tsv 1, xml 3, ini 1, env 3, md 1, txt 1, zone_totals 3, corpus_index 5, posture 3 (29) | Test `triples()` strips each field (`line.strip()`, `part.strip()`, L187-200) and the oracle solve.py strips too (L117-123, 138-143, 190, 204, 212). The spec says the opposite: contract L44-51 "`str(int(value)) == value` evaluated on the exact field bytes ... This rejects: ... surrounding spaces", L67 "Comparisons are exact and byte-literal", instruction L12 "on the raw field bytes. Reject ... surrounding spaces". The agent followed the spec. Example: c42 tsv row `core\t 12\tactive` is counted by the test and rejected by the agent. A byte-exact parser reproduces 11 of the 14 agent diffs; the other 3 (xmlnest, ini, props) are the same mechanism. The agent measured both readings (trajectory step 28: `c16_ssh_keybits exact=158(158) strip=162(162)`) and chose exact. | ARTEFACT (spec-test contradiction) |
| validation_report_correct (5) | The test needs `checks.command_failures == []` and `checks.rejected_ops` == the list of seqs (L579-593). The agent wrote 0 and 2113 (counts). Instruction L18 lists key names only, with no types. aggregate_total also cascades from the strip artefact. | ARTEFACT (hidden schema + cascade) |
| summary_correct (3) | The test needs `profiles == [core, edge, dmz, mgmt]` (L595-607). The agent wrote them sorted [core, dmz, edge, mgmt]. Instruction L19 gives no order. aggregate_total also cascades. | ARTEFACT (hidden order + cascade) |
| cli_repaired (3) | `assert "sort_keys=True" in source_text()` (L646-648) is a literal text grep. The agent's cli.py passes `"sort_keys": True` through a kwargs dict, and its JSON bytes are correct (manifest_correct passed). | ARTEFACT (brittle source grep) |

Shift lever: the test shift is `R % 97` only (L406-407). The instruction (L11) and the oracle (solve.py L305-309, L339) use `R%97 + J%31`. The agent used 25. Expected aggregates are **identical for every shift from 17 to 31** (local probe), so this inconsistency costs nothing. It also means the claim that "a single misclassified journal op is observable in every one of the fifty aggregates" (instruction L11) is false for the shipped data.

## 3. Near-zero tests?
No. Tests are 45.78. No single gate zeroes everything, but one shared reduction (the field-trim reading) fails 29 points across 11 checks (a cascade).

## 4. Judge
`score.json`: 14 criteria, positive total 44, 38 earned. The judge read the trajectory (`atif-trajectory`) and gave per-criterion justifications.
- #1 (3) "inspects the local CLI source, schema file, and failing command behaviour before editing": the agent never ran the broken CLI before it rewrote cli.py (steps 6 extract → 14-16 overwrite). The agent really skipped this, but no instruction or contract sentence asks for it (grep for "before edit", "failing", "observe" found nothing). **HIDDEN RULE.**
- #11 (3): requires naming "a concrete journal operation whose misclassification would shift every one of the fifty aggregates by one". The agent stated R=21845, J=2113 and the shift but named no op. Naming an op is never requested, and the property is false for this data (aggregates do not move for shifts 17-31). The oracle could meet it only by narration. **HIDDEN + JD-7 doubtful.**

## 5. Permission setup
tests/test.sh: `chown root:root /logs/verifier; chmod 755 /logs/verifier; chmod -R go-rwx /tests; exec rewardkit /tests --workspace /app ...`. The grader reads /app/out as root. It runs the agent CLI as `nobody` via `setpriv --reuid=nobody`, from a 0o755 temp extract with 0o644 files (test_output.py L123, L437-446, L464-471). There is no route to our Errno 13 bug, and none was observed.
