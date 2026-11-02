# A_8d3e20fb: security policy compiler, 3rd version (Nikhil Bansal, Debugging)

Recorded run: final 63.64 / tests 41.24 / rubric 86.05 (`verifier/test-stdout.txt`: `reward: 0.6364`).
Paths: T = `Final_Delivery/8d3e20fb-2aab-5efb-be67-7ad3dbeabc8f`, R = `T/trajectories/claude-opus-5/run_1`.

## Verdict: PARTLY (no test loss is a clean genuine miss)

- 38 test points come from one value fault that cascades. The fault is the spine replay scope. This is the same lever as 4ee62df1 and af6f42c3. Here the agent saw both readings and chose the literal one. Reference code and contract text disagree, so I classify it as a HIDDEN RULE (the answer key contradicts the literal contract), not a fair miss. Evidence is below.
- 16 test points plus a fired -3 negative come from a verifier invocation artefact (`python -I` plus a multi-module tool). No sentence states this requirement.
- 6 judge points are genuine: one process step and one counterfactual enumeration.

## 1. ctrf vs tests/ diff

ctrf has 33 tests. Their names match the registrations in `tests/test_output.py:843-1040` one for one, with no extras and none missing. Positive total 97, negatives -16 (stacking_check). The test component scored 40.0, and 43 - 3 = 40, so 40/97 = 41.24.

## 2. Errors and environment

- `result.json`: `exception_info` null. The agent ran 15:24:05-15:44:09Z (about 20 min). The verifier finished at 15:45:52Z. No timeout.
- There is no traceback, no Permission denied, no missing file and no wrong output path in the verifier outputs. All 22 artifacts exist (`artifacts_exist` PASS).
- **Tool-run failure (artefact):** `run_tool` at `tests/test_output.py:513-533` builds `cmd = [sys.executable, "-I", str(root / "cli.py"), *args]` with cwd /tmp under setpriv. The agent's `/app/out/tool.zip` contains `cli.py` plus `artifacts.py`, `corpora.py`, `jsonio.py`, `policy.py` and `run.py`, and `cli.py` imports those siblings. `-I` implies `-P` (safe_path, Python 3.11+), so the script directory is left off `sys.path` and the import fails, making every `run_tool` call rc != 0. Local evidence: `python3 -I -c "import sys; print(sys.flags.safe_path, sys.path[:2])"` printed `True ['.../python314.zip', '.../python3.14']`. Nothing in `instruction.md` or `config_contract.md` mentions isolated mode, a single-file tool, or module layout (grep for `-I|isolat|single|module|sys.path` found nothing relevant). The shipped `tool.zip` README shows plain `python3 cli.py <sub>`. The agent's own fresh-directory rerun used plain `python3`, so it passed (final message, step 54).

## 3. Per failed check

| check | w | cause | type |
|---|---|---|---|
| config_matches_policy | 5 | agent spine = all valid ops of every env; reference `wanted_config` = `replay(seed_doc, "base")` (:447-452) | wrong VALUE (hidden-rule) |
| aggregates_match, zone_totals_match, corpus_index_match, posture_match | 5 each | R = spine rekey_interval_s feeds the bound shift (agent R 17554 vs base-only 33796, step 37), so every corpus bound moves | cascade of same VALUE |
| aggregates_csv 3, tsv 1, xml 3, ini 1, env 3, md 1, txt 1 | 13 | mirrors graded against reference aggregates (`_expected_view` :573) | cascade of same VALUE |
| report_transcript_real | 5 | reruns each recorded command via `run_tool`; ImportError | CRASH (artefact) |
| tool_round_trips | 3 | `run_tool validate` must return rc 0 and print 'ok' | CRASH (artefact) |
| cli_repaired | 5 | `run_tool init/set/plan`; would also fail on value (`plan --env base == wanted_config`) | CRASH + VALUE |
| compile_reproducible | 3 | `run_tool compile` twice | CRASH (artefact) |
| negative_fake_report | -3 FIRED | `_neg_fake_report` :801-824 fires when the export-report rerun differs **or rc != 0** | fired on an honest run (artefact; TS-16 risk) |

The value cascade costs 38 points and the tool-run artefact costs 16 + 3 = 19 points. cli_repaired's 5 overlap both causes.

### Why the value loss is a hidden rule and not a misread

- The contract spine paragraph at `environment/data/config_contract.md:14-27` says "Replay `change_journal.jsonl` ... An operation is valid only when all hold: its `env` is listed in `journal_envs`". `validation_rules.json` lists `['base','core','edge','dmz','mgmt']`. The only env filter in the whole contract is in the zone paragraph (:31-35): "replay the valid journal operations whose `env` is that zone".
- The base-only cue is limited to the phrase "the base spine" in `instruction.md:9` (req 5) and the key name `base_config`.
- The agent computed both readings and recorded its choice. At step 37 (15:39:21) it printed `all-env spine R 17554 shift 115` / `base-only R 33796 shift 61`. In `/app/AGENTS.md` (step 51) it wrote "Spine: ... then **every** valid journal operation in ascending `seq` (not only `env == "base"`; the profiles are the only env-filtered replay)".
- TRUTH.md never justifies the base filter from text. It just restates "matching the journal-replayed baseline" (:111-112).

## 4. Judge (score.json; 13 criteria, 43 positive; 37/43 = 86.05)

| crit | w | result | real or artefact |
|---|---|---|---|
| R1 "inspects the local CLI source, schema file, and failing command behaviour before editing" | 3 | FAIL: "did not execute the original broken CLI to observe failing command behavior before making changes" | REAL. Steps 5-7 read the zip and source; the first edit is at step 18 (15:31:52); the old CLI was never run |
| R12 "names at least one concrete journal operation whose misclassification would change the effective upper bound of every one of the fifty corpora" | 3 | FAIL: never names one concrete op | REAL. The final message gives counts, not a named op |
| R7 -5 external CLI, R8 -5 false success claim | neg | not fired | fair |

The other 9 positives passed. The fired test negative is covered in section 3.
