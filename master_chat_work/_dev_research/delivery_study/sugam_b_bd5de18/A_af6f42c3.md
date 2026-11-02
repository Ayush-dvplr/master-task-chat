# A — af6f42c3 (sealb-ctl security policy compiler)

Recorded: overall 69.5 / tests 45.83 / rubric 93.18 (`trajectories/claude-opus-5/pass_summary.json`, `run_1/report.json`).

## Verdict: PARTLY
A genuine misreading (which journal ops build the spine) cascades into every corpus bound. On top of that, a name-format gate in one helper (`_agent_agg`) zeroes 13 consistency-only points that the agent's files actually meet, and two unstated value types also fail `validation_report`.

## Artefact screen (clean)
- `result.json`: exception_info null. Agent 13:44-14:13Z (29 min), verifier 14:17-14:34Z. No timeout.
- `verifier/test-stdout.txt` holds only `reward: 0.6951`. No traceback, no Permission denied.
- All 22 artifacts are present in `artifacts/app/out/`. `artifacts_exist`, `artifacts_are_regular_files` and the tool round-trip, compile and determinism tests passed (report.json).
- The five negatives were not triggered (polarity-inverted, `tests/test_output.py:8-9`).

## Failed checks (52 of 96 positive points lost)
| check | w | cause | kind |
|---|---|---|---|
| config_matches_policy | 5 | spine replays valid ops from ALL envs; the reference uses only `env == "base"` | wrong VALUE (hidden scope) |
| zone_totals_match | 3 | effective bound shift 25 instead of 26 | wrong VALUE, cascade (INFERRED: zone totals carry no names, so only a value can fail) |
| aggregates_{plain,symbol,structured} | 15 | key-set gate + shift cascade | GATE + VALUE |
| aggregates_{csv,tsv,xml,ini,env,md,txt} | 13 | key-set gate only: the views equal the agent's own aggregates.json byte for byte | GATE |
| corpus_index_match | 5 | names carry the extension; `eligible_rows` likely shifted | GATE + VALUE (INFERRED) |
| posture_match | 3 | `max_corpus` name has the extension, plus totals | GATE + VALUE |
| validation_report_correct | 5 | `_agent_agg` gate; `command_failures` 0 vs `[]`; `rejected_ops` 2113 (a count) vs a list | GATE + unstated type |
| summary_correct | 3 | `aggregate_total` goes through the `_agent_agg` gate | GATE (INFERRED: the other fields match the contract) |

### Lever 1: spine scope (genuine)
- Reference `tests/test_output.py:420-425`: `wanted_config` = `replay(seed_doc, "base")`. `:408`: `if op["env"] == env and op_ok(op, rules)`.
- Contract `environment/data/config_contract.md:14-27` (spine): "Replay `change_journal.jsonl` … An operation is valid only when all hold: its `env` is listed in `journal_envs`" (journal_envs = base, core, edge, dmz, mgmt) "… Apply valid operations as events in `seq` order, last valid wins per key". It has no env filter. Only the profiles paragraph (`:35`) filters: "replay the valid journal operations whose `env` is that zone". `instruction.md:9` says "Generate the base spine". `solution/TRUTH.md:39` says "compiled base `rekey_interval_s`". No sentence says the spine uses only `env == "base"`, so this is a HIDDEN RULE (scope by omission, implied only by the word "base" and the parallel with the zone sentence).
- Agent step #11 (t+2.4 min): `for r in rows: if not valid(r): continue … cfg[k]=r['value']` with no env filter. It printed `R 21845`. The final claim (step #36) says "spine R = rekey_interval_s 21845 → corpus shift 20 + 5 = 25".
- My recomputation from `environment/data` (my own code, not task code): the base-only replay gives `{'mode':'audit-seal','max_sessions':915,'retry_budget':0,'handshake_timeout_ms':2200,'rekey_interval_s':30576}`, shift 30576%97 + 2113%31 = 26. The all-env replay gives exactly the agent's config (422/1/13336/21845/strict-seal), shift 25. The rejected set is identical (2113 = 2113, no difference either way).
- Why `profiles_match` (5) still PASSED: every zone profile is rebuilt by replaying that zone's ops on top (`:428-437`). With 9000 ops, the zone replays overwrite every key that differed. So a wrong spine stays invisible in the profiles.

### Lever 2: corpus name gate (artefact-like, not stated)
- `tests/test_output.py:554-558` `_agent_agg`: `assert set(agg) == set(wanted_aggregates())`. Keys are `f"c{idx + 1:02d}_{slug}"` with no extension (`:155-162`). Every view, index, summary and validation test calls `_agent_agg()` (`:603-627`, `:637`, `:666`, `:681`).
- Contract `config_contract.md:166`: "`aggregates.json`: an object mapping each corpus name to its derived integer." The contract table column headed `corpus` lists `c01_cve_severity.csv`, `c05_key_age_days.colon`, … (`:84-90`), and `summary.inputs` is defined as base file names. The stem form appears only as the keys of `validation_rules.json` `corpus_bounds`. Two readings fit the visible text.
- The agent used the stem to look up bounds (agent `cli.py:433` `stem = name.rsplit(".", 1)[0]`) but keyed the output by the full file name, following the contract table.
- Evidence that this gate alone cost points: I rebuilt all six text views from the agent's `aggregates.json` exactly as `_expected_view` (`:582-599`) does, and every one matched (`csv True … txt True`). Those 13 points are lost only to the key-set assert.

### Unstated types in validation_report
- `tests/test_output.py:664-665`: `checks["command_failures"] == []` and `checks["rejected_ops"] == load("rejected_ops.json")["rejected"]` (lists).
- Contract `:190-193` names `command_failures` and `rejected_ops` but gives no type. The agent wrote `0` and `2113`. This is the QC_RULINGS TS-19 "silent value type" shape.

## Tests < 30?
No. Tests = 45.83 (44/96).

## Points split (my attribution)
- Genuine VALUE: config 5 + zone_totals 3 + families 15 + posture 3 = 26 (the families and posture would fail on the shift even with correct names; INFERRED, because the gate prevents direct confirmation).
- GATE only: views 13 + summary 3 = 16.
- Mixed (gate + value or type): corpus_index 5 + validation_report 5 = 10.
