# HARDEN_REPORT ed621c7: tariff-engine-audit-repair, round _ql1 (status PAUSED)

## Outcome
PAUSED: go conditions 1 (crash/timeout loss <= 30% of positive test weight) and 2/4 (agent's own package tests <= 60, predicted final <= 35) cannot hold together. Details and options: [PAUSED.md](PAUSED.md). Diagnosis: [DIAGNOSIS.md](DIAGNOSIS.md).

## Done in this round
- F0 backup: BUNDLE (pushed 0de116d29fdb) copied to WORK/pushed_0de116d29fdb/ (diff -rq empty).
- F0 swap: BUNDLE replaced by the QL bytes (ql_bundle, tree dfd8e457d203), diff -rq empty.
- F0 add-on: `_visible_test_removed` now also watches module-level Assign/Expr nodes and setUpModule/tearDownModule bodies. Replay (WORK/ql1/bypass_replay.py): setUpModule raise SkipTest fires, module assign `InvoiceCase = unittest.skip(..)(InvoiceCase)` fires, module expr skip fires, tearDownModule fires, unchanged file does not fire, agent's own @skipIf test does not fire. QL original: none fire.
- Docker on QL bytes + add-on (exe_copy tests-only copy, /tmp/opencode-logs/tariff-ql1-f0b-20261029T043733-b127, ALL_DONE 04:39:38): oracle 1.0, nop 0.0. TRUTH sha lines match solve.sh and solve.py.
- Differential fuzz of the agent's final package vs the test reference (WORK/ql1/fuzz_agent.py, fuzz40.log): 280 invoice documents + 277 r3 statement documents over 40 reseeds of all 7 corpora, 0 divergences. The agent is exact on every stated rule; its only loss mode is CRASH (OOM) at hidden scale.

## Why it stops
| design | agent tests | WRONG | TIMEOUT | CRASH | predicted final (judge mid 21.4) |
|---|---|---|---|---|---|
| now (QL bytes + add-on) | 81.35 | 0 | 0 | 18.6% | 51.4 |
| F1 only | 62.7 | 0 | 0 | 37.3% | 42.1 |
| F1 + F2 (planned) | 45.7 | 0 | 0 | 54.3% | 33.5 |
| F1 + F2 capped at 30% crash/timeout | 70.0 | 0 | 0 | 30.0% | 45.7 |
No WRONG stage exists for this agent without a new rule sentence or a hole (Never 6, LEVER_RULES section 8, go condition 5).

## Not run
Phase 2 (F1, F2, F3 probes), kill table, cost table, STACKING_CHECK, precheck, QC scripts, validator, oracle x3 / owner / stub / forgery, Tasks_INPUT sync. BUNDLE is left valid (oracle 1.0, nop 0.0) at tree 8f7de2fe6f22.

## Lessons for the master
- A cap on crash/timeout loss plus a tests <= 60 target needs a WRONG stage; check the agent program for any divergence before issuing a scale-only harden | template_change: prompts/templates P9 go block (ask for a fuzz of the agent package first)
- exe_copy.py must build the Docker copy; a raw copy with judge.toml errors with RewardFileNotFoundError | no change: round notes G already say exe_copy
- Read-out tool labels OOM as WRONG | template_change: tools/trajectory_readout.py (no reason text -> UNKNOWN)
