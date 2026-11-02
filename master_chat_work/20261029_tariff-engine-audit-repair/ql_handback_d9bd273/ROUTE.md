# ROUTE (d9bd273): lower_score

REQUEST = `lower_score` (zip `REQUEST.md`). Ayush 02:33: "Take his edits, QC, harden, run <40." The OK to lower the score is given (Q2 a). C1 (one new paid run) is the only open question, see CONFLICTS.md.

## Chosen route: lower_score, with trajectories -> P9 v4 from TRIP_ql.md
1. **P9 v4 harden.** Input: `OUT/TRIP_ql.md`, a regrade of our trial 6107faf5 on his bytes.
   - Start bytes: frozen `0de116d29fdb` (TASKS_INPUT) plus ALL of his hunks, i.e. the zip bundle excl. trajectories/, tree `dfd8e457d203`. Copy from `/tmp/ql-tariff-engine-audit-repair-20261029T0359/x/tariff-engine-audit-repair/` without `trajectories/`.
   - Take:
     - solution/solve.py Q431-574 and solution/TRUTH.md Q128-138 + Q323. The oracle generalisation matches brute force on 3000 cases. The sha line matches the file.
     - tests `_check_missing_source` Q7931-7946. It is stricter and grades a stated order, `api_contract.md:22-24`.
     - tests `_visible_test_removed` Q7963-7992. Take it with a small add-on (G-guard): also watch module-level `FunctionDef` named `setUpModule`/`tearDownModule`, and module-level `Assign`/`Expr` nodes, for the skip names. This closes the two bypasses shown in CHANGES.md and keeps his fix for agent-added tests.
   - Drop: nothing. The Q7949 blank line is harmless.
   - Harden targets, i.e. what his run shows the agent already gets right (TRIP_ql.md "Which bytes"): every invoice family on all 7 hidden corpora (subtotals, credits/totals, lines, energy, standing, all quiet-rule account families), the base statements (due/redeemed/feasible, 91 points), missing_source, two_runs, regression rows and corrected tests, and judge R8/R12/R13.
   - What already bites: the 21 `*_ledger_statement_*` criteria (91 points, WRONG and silent) and judge R1-R7, R11.
   - To reach final < 40 under the v3.7 targets (`LEVER_RULES_v3.md:90`: tests <= 60, blind <= 65, judge mid <= 20): the tests share has to fall by about 21+ points at the current judge level. INFERRED: final = 0.5 x tests + 0.5 x rubric, since (81.35 + 27.27) / 2 = 54.31.
   - Harden rules: Law-1 (WRONG only, no timeout/crash on shipped data), and no W1/IN-17 text in instruction/contract.
2. **P11 v3 full QC** on the hardened bytes. Not recheck mode, because tests/, solution/ and the oracle changed. Oracle must be 1.0 (UNVERIFIED on his bytes, no Docker here). TRUTH `solve_py_sha256` must be checked by script (`_COMMON_RULES_v5.md:38`).
3. **Freeze**, then **ASK** Ayush for C1. Then **1 run** (`_COMMON_RULES_v5.md:66`, `LEVER_RULES_v3.md:236,241`). Push only when that run meets tests < 85, rubric < 85, final < 40.

Next prompt to issue: **P9 v4** (harden) for tariff-engine-audit-repair, with `TRIP=OUT/TRIP_ql.md`, `START_BYTES=zip bundle excl. trajectories (dfd8e457d203) + _visible_test_removed add-on`, `PREV_COPY=/Users/mac/Desktop/Terminal Bench/QC/copies/f054899/tariff-engine-audit-repair`.

## Other routes (not chosen, and why)
- `trajectory_only`:
  - TRIP gives tests 81.35 < 85 PASS, rubric 27.27 < 85 PASS, final 54.31 < 40 FAIL, so gate v3.7 FAILS.
  - The trajectory does not cover his bytes: the agent ran on frozen 0de116d29fdb, and only the verifier ran on his edits.
  - Ruled out: the gate fails, and tests/ changed.
- `regrade_only`: not allowed, because tests/test_output.py changed (the rule in this prompt). For the record, the inputs would be:
  - the staged task: TASKS_INPUT + his 3 files + the run's staging lines;
  - the source trial: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/jobs/tariff-engine-audit-repair/trajectory/claude-opus-5/Run 1` (UNVERIFIED path existence);
  - the Output_RFP files it would replace: `trajectories/claude-opus-5/{pass_summary.json, run_1/{config,report,result}.json, run_1/verifier/*}`.
  It would still score about 54 > 40.
- `qc_fix`: P11 v3 MODE recheck with PREV_COPY = LAST_QC_COPY, then P12 v4. Ruled out: it does not lower the score, and the request is lower_score.

## Lessons for the master
- A QL "trajectory" can be a regrade of OUR transcript on his bytes. Check `config.json` `source_trial.action` before reading scores as a new run.
- A judge-only flip (R13) moved final by 4.5 points with no judge file change. Judge noise is around ±1 criterion (3/33), so plan the harden margin below 40 with that in mind.
- A narrowed anti-cheat check can be a fix and a hole at once. Replay old vs new on mutated visible tests in /tmp before taking it.
