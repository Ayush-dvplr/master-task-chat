# PAUSED: condition 1 conflicts with conditions 2 and 4 (ed621c7, 04:50 IST)

## Done since the go (04:33)
- Backup of the pushed bundle at `WORK/pushed_0de116d29fdb/` (diff -rq empty).
- BUNDLE swapped to the QL bytes (diff -rq against ql_bundle empty before the add-on).
- `_visible_test_removed` add-on: module-level `Assign`/`Expr` statements and the bodies of
  `setUpModule`/`tearDownModule` are now watched. Replay (`WORK/ql1/bypass_replay.py`):
  setUpModule SkipTest True, module assign `unittest.skip(...)(InvoiceCase)` True, module expr skip
  True, tearDownModule SkipTest True, unchanged file False, the agent's own @skipIf test False.
  On the QL bytes alone both bypasses gave False.
- Docker on the QL bytes plus add-on (exe_copy tests-only copy,
  `/tmp/opencode-logs/tariff-ql1-f0b-20261029T043733-b127`, ALL_DONE 04:39:38): oracle 1.0, nop 0.0.
  TRUTH sha lines still match solve.sh and solve.py (no edit to solution/).

## Why I stopped before building F1 + F2
The QL-run agent's final package (`OUT/agent_program/`, from run_1 artifacts) is exact:
Fraction money, half-even cents, plain string id order, first id list walk, balance clamp, statements
for accounts in vouchers.csv (report.py:227-240, core.py:120-140). Differential fuzz
(`WORK/ql1/fuzz_agent.py`, log `WORK/ql1/fuzz40.log`): the 7 hidden corpora reseeded 40 times,
280 invoice documents and 277 statement documents, 0 divergences from the test reference
(3 seeds skipped by the generator). Its only loss is CRASH: the ledger corpora kill it with
rc -9 at about 6 s (out of memory under the declared 4096 MB) before the 10 s limit.

So every point this program can lose is CRASH or TIMEOUT. That gives:

| plan | agent tests | its loss | split W/T/C (% of positive) | cond 1 (C+T <= 30%) | cond 2 (<= 60) | cond 4 final (judge mid 21.4) |
|---|---|---|---|---|---|---|
| now (QL bytes) | 81.35 | 91/488 | 0 / 0 / 18.6 | pass | FAIL | 51.4 |
| F1 only (r3 to hidden scale) | 62.7 | 182/488 | 0 / ~0 / 37.3 | FAIL | FAIL | 42.1 |
| F1 + F2 (DIAGNOSIS plan) | 45.7 | 364/670 | 0 / ~0 / 54.3 | FAIL | pass | 33.5 |
| crash capped at 30% | 70.0 | 30% | 0 / 0 / 30 | pass | FAIL | 45.7 |

Condition 2 needs this program to lose at least 40%; condition 1 allows at most 30% of that by
CRASH/TIMEOUT, so at least 10% must be WRONG output. An exact program gives WRONG output only on a
rule it misreads; on every stated rule it agrees with the reference (fuzz above). A new WRONG lever
would need new rule text (condition 5 forbids) or an unstated rule (LEVER_RULES section 8 hole).
No build satisfies conditions 1, 2 and 4 together; building F1 + F2 would only confirm the table.

## Options for the master
1. Lift the condition 1 cap for this bundle to about 55% CRASH/TIMEOUT on lever checks (v3.5 and
   v3.7 count hidden-scale loss when shipped inputs are fast, the limit is stated and each lever
   corpus has its own call; all three hold). Then I build F1 + F2 + 3 probes as in DIAGNOSIS.md:
   predicted final 33.5.
2. Keep the 30% cap: the best this agent can reach is tests 70, final about 45.7, which misses the
   < 40 gate. Ship the QL bytes plus add-on as they are, or retire the task.
3. Allow one new stated rule built to fail Opus. Risky: the agent read every stated rule right the
   first time, so a WRONG loss cannot be predicted from this run.

State of BUNDLE now: QL bytes plus the add-on, oracle 1.0, nop 0.0, valid to ship as is.
