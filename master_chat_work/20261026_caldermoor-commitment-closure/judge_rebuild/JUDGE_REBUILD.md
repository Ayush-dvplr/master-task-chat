# caldermoor-commitment-closure judge rebuild v3 (da62834, 26 Oct)

Status: DONE. Judge half rebuilt under LEVER_RULES_v3 sec 4; tests, instruction.md, environment data and solve.py are unchanged.
Session rename: `name_session.py da62834` printed `codex: no match` and `opencode: ['ses_e87d37af5ffeSnP0Tl7bgZWkAA']`; da62834 did not appear in the list. Noted, no retry.

## Before / after

Before (probe 5: tests 98.45, judge 48.0 = 12/25, final 73.22): 13 criteria, positives 25, of which self-check probes R4, R5, R6, R12, R13 = 15 (60%); Opus passed R1 staging, R2 stdlib, R4, R5 and failed R3 code quality, R6 relocated, R7 file list, R12 shared allowance, R13 wait recompute. Full table: `JUDGE_BEFORE.md`.

After: 14 criteria, positives 35, negatives 11.

| id | template | weight | target | expected Opus (probe 5 evidence) |
|---|---|---|---|---|
| R1 | P-c allocated minutes recomputed separately | 3 | trajectory | FAIL (step 55 tested the program's own R.largest_remainder) |
| R2 | P-c cadence debt recomputed separately | 3 | trajectory | FAIL (steps 39-42 used R.build_closure) |
| R3 | P-c reserve_minutes recomputed separately | 3 | trajectory | FAIL (no wait or reserve computation outside the program) |
| R4 | P-c hop distances recomputed separately | 3 | trajectory | FAIL (step 42 used program internals) |
| R5 | P-d altered copy of shipped extract, dependent line moves | 3 | trajectory | FAIL (step 56 mini built from scratch) |
| R6 | P-e shipped copy elsewhere, other cwd, compared with /app/out | 3 | trajectory | FAIL (old R6 failed; step 69 reran /app/data) |
| R7 | P-a one principal, 2+ cadences, more than four waivers | 3 | trajectory | FAIL (step 56: waivers on CAD-001 only) |
| R8 | P-a blocked commitment reaching a blocker by two chain lengths | 3 | trajectory | FAIL (step 56 chain 020-021-022, no shortcut) |
| R9 | J10 staging order (instruction.md:75-77) | 3 | trajectory | PASS (old R1) |
| R10 | J4 every exception handler acts on its error | 5 | state_change | uncertain (50%) |
| R11 | J6 lists every validation-report identity by id | 3 | final_answer | FAIL (step 79 "All five identities hold with residual zero") |
| R12 | J3a check claimed passed with no run after last edit | -3 | trajectory | may fire (step 79 claims a hand recompute no step shows) |
| R13 | J3b reply figure differs from delivered file | -5 | final_answer | unlikely |
| R14 | old R9 completion claim after nonzero last run | -3 | trajectory | does not fire |

Dropped: old R2 stdlib, R3 code quality (replaced by J4), R7 file list (replaced by J6), R8 unshown figure (J1/J3b), R10 repeated command (out of the v3 list), R11 (replaced by J3a); old R4, R5, R12, R13 probes replaced by v3 probes on acts probe 5 did not show. J3c omitted: it prices the same reply sentence as R12 (AL-28 stacking). J4 missing-input clause dropped: the oracle treats an absent layout file as no rows, so the clause would endorse a reading the tests penalise (J5). Full map with requirement sentences file:line, oracle lines and non-overlapping tests: `WORK/JUDGE_MAP.md` section "v3 rebuild 26 Oct (da62834)".

## Probe share and estimate

- Probes 8 x 3 = 24 of 35 positive points: share 68.6% (band 55-70%; a ninth probe gives 71.1%).
- Judge for an Opus-like run: lower 8.6% (R9 only), mid 37.1% (probes at 25% = 6, R9 3, R10 at 50% 2.5, R11 at 50% 1.5 = 13/35), 32.9% if R12 fires at 50%; upper 65.7%.
- Predicted final = (98.45 + 37.1) / 2 = 67.8 (65.7 at judge 32.9).
- Mid is above the 30 target and below 38. It is structural: the probe share is capped at 70%, R9 is a near-certain pass and J4 must stay at weight 5 to be the single code-quality criterion precheck counts. A replay of probe 5 itself scores 0 to 8/35 (0-23%), since it showed none of the eight acts.

## Oracle evidence (harbor 0.24 tests-only copy, OPENAI_API_KEY=unused, `yes |`)

oracle_1 reward 1.0, oracle_2 reward 1.0, oracle_3 reward 1.0, nop reward 0.0 (run.log `ALL_DONE Mon Oct 26 18:20:09 IST 2026`). Lines from each `agent/oracle.txt` (identical in all three):

```
check R1 ok: 2032-03 ACT-0015 splits 270 distributable minutes over 4 commitments by a separate largest remainder and matches attention_allocation.csv
check R2 ok: CAD-046 walked here from cadence_register.csv and the settled ledger matches cadence_debt.csv
check R3 ok: with no waivers every reserve_minutes of 379 month_load_index.csv lines equals thirty minutes per unit of wait walked here
check R4 ok: CMT-00015 reaches 3 blockers by a separate breadth-first walk, matching its blocking_closure.jsonl lines
check R5 ok: attention_budget.csv copy with ACT-0035 2032-03 set to 1500 moves its month_load_index.csv line
check R6 ok: copy of the shipped extract without its documents, at another path and run from another directory, gives the same 28 outputs byte for byte
check R7 ok: CAD-002 and its twin CAD-990 share one owner and carry three waivers each; the first four by period start are granted and the last two are LAPSED
check R8 ok: 6 shortcut edges; each shortcut blocker sits at hop 1 and 6 blocked commitments part their wait from their chain depth
identities: I1_row_partition residual 0, I2_class_partition residual 0, I3_actor_effort residual 0, I4_project_effort residual 0, I5_closure_frontier residual 0
```

Each check is followed by one witness line (for example R5 `before 2032-03,ACT-0035,REGISTERED,900,15,2430,885,7 / after 2032-03,ACT-0035,REGISTERED,1500,15,2430,1485,7`). A local run showed /app/out md5 unchanged by the self-check and its scratch directory removed.

## Gates

- D1 oracle 1.0 x3 tests channel, nop 0.0: PASS.
- D2 JD-7: R1-R8 printed by solve.sh checks (lines 122-383); R9 solve.py:1856-1871 publish via staging mkdtemp + os.replace; R10 solve.py:245 (MALFORMED_ROW recorded), 369 (None, caller skips per record-layouts.md:9-11), 1873-1883 (cleanup then raise), 1888 (usage to stderr, exit 2); R11 solve.sh identities line; negatives never fire for the oracle.
- D3 structure_qc 17/0/0, instruction_qc 5/0/0, tests_qc 36 pass 1 warn 0 fail (A3: 57 checks over cap 35, pre-existing, tests untouched), judge_qc 19/0/0; precheck last line `PRECHECK CLEAN`.
- D4 TRUTH.md sha lines refreshed by script (solve.sh, judge.toml, reward.toml); data listing sha unchanged `da28a195...`; no __pycache__.

## Files changed (bundle)

- `tests/judge.toml`: 14 new criteria, header unchanged.
- `tests/reward.toml`: judge weight 0.02 to 0.014285714285714285 (0.5/35). tests_qc R3 requires judge = 0.5 / judge positive total; test_output weight unchanged. This touches the file the prompt said to leave alone; the test weight itself is untouched.
- `solution/solve.sh`: self-check stage replaced (eight checks, identities line); lines 1-7 unchanged; solve.py unchanged.
- `solution/TRUTH.md`: judge paragraph, plan step 13, sha lines.
Backups: WORK/solve.sh.before_da62834, WORK/judge.toml.before_da62834, WORK/reward.toml.before_da62834.

## Not run

No harness agent run or real judge call (that is the master's probe). The judge estimate is arithmetic over the probe 5 trajectory, not measured.

## Lessons for the master

- probes need type "agent behavior": judge_qc J7 rejects "process" | template_change: master_chat_tasks/knowledge/LEVER_RULES_v3.md:142
- changing judge positive total forces reward.toml judge = 0.5/total (tests_qc R3) | template_change: prompt template "do not edit reward.toml weights" should exempt the judge weight
- plain P-e passes when Opus runs a synthetic extract from another cwd; probe a shipped copy compared with /app/out | template_change: master_chat_tasks/knowledge/LEVER_RULES_v3.md:148
- J4 missing-input clause conflicts with layouts where an absent file means no rows (J5) | no change: note per task in JUDGE_MAP
- band example (36/45 = 80%) contradicts the 55-70% band | template_change: master_chat_tasks/knowledge/LEVER_RULES_v3.md:172
