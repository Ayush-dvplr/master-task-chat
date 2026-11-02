# P12 fix of QC v4, sentinel-policy-recompute (board 279f9d5)

Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute`
QC report: `/Users/mac/Desktop/Terminal Bench/QC/reports/sentinel-policy-recompute/v4.md`
Session lookup: `name_session.py 279f9d5` printed `codex: no match` and `opencode: ['ses_e84f4c642ffeVoN0zvrb5cV4Ud']`; the sha itself was not shown in that output.

Files changed: `instruction.md`, `tests/judge.toml`, `solution/TRUTH.md`, `task.toml`. Not touched: environment/data, generators, hidden corpora, ledger_repair, `tests/test_output.py` (sha `abcf8dae...` unchanged), `solution/solve.py` (sha `1fb297ed...` unchanged), `solution/solve.sh`.

## Finding 1, AL-2 (instruction.md:7): FIXED
- before: "Produce the two environment profiles at `/app/out/profile_dev.json` and `/app/out/profile_prod.json` through the same tool."
- after: "Produce the two environment profiles at `/app/out/profile_dev.json` and `/app/out/profile_prod.json`."
- before: "... timestamps, uuids, or seeds. Write nothing under `/app/out` except the artifacts named here. In your final response, ..."
- after: "... timestamps, uuids, or seeds. In your final response, ..."
- TRUTH.md Out of bounds trimmed to match: "hand-writing `config.json` or the profiles" -> "hand-writing `config.json`"; the "extra files under `/app/out`;" entry removed.

## Finding 2, IN-8, and Finding 3, JD-5 (tests/judge.toml:143-144, R11): FIXED
- before: name `r11_cli_handlers_act_and_inputs_named`, description "The agent leaves /app/tool/cli.py in which every exception handler acts on the error it catches by raising, logging and exiting non-zero, or recording it in an output, and a missing or malformed declared input stops the run with a message naming the file."
- after: name `r11_cli_handlers_act_on_errors`, description "The agent leaves /app/tool/cli.py in which every exception handler acts on the error it catches by raising, logging and exiting non-zero, or recording it in an output."
- weight 5 unchanged; id R11 unchanged; old name referenced nowhere else in the bundle.
- solve.sh: has no R11 text (it only echoes artifact paths), so no change. TRUTH.md R11 summary (:344) now "R11 every exception handler in the repaired `cli.py` acts on the error it catches (5);" and ordered plan step 3 (:401-402) now "with every exception handler acting on the error it catches (rubric R11)".

## Finding 4, DS-27 (solution/TRUTH.md taxonomy): FIXED
- Lever tags and labels removed from item headers, for example:
  - :20 before "1. (focal) (N1, region override allowance, stateful group counter)" -> after "1. Region override allowance."
  - :30 before "2. (focal) (N2, unit by version cutover, L1 as amplifier)" -> after "2. Timeout unit by version cutover."
  - :39 "3. (focal) (N3, window admit count, ...)" -> "3. Window admit count."
  - :51 "4. (focal, the counted lever this round) (N4, window timeout pool, H7 re-entry)" -> "4. Window timeout pool."
  - :68-86 "4a..4e. (quiet, t1) (Q1..Q5, ...)" -> "4a. Running timeout floor.", "4b. Reissued override.", "4c. Principal alias span.", "4d. Requires order.", "4e. Carried clause."
  - :92 "5. (graded noise) (L7, per-item rounding)" -> "5. Per-term risk rounding."
  - :97 "6. (amplifier) (L1, honest control)" -> "6. Ledger controls."
  - items 7 to 17: "(drift)", "(focal)" and "(trap)" labels removed.
- Corpus section headers: "(t1; ... no other quiet rule fires)" -> "Generated corpora for rules 4a to 4e (... no other rule of 4a to 4e fires)"; "(t2; ...)" -> "Generated corpora for the curve reports and reinstated rows (...)"; "(t3; ...)" -> "Generated corpora for the ledger repair (...)".
- before (:240): "`WORK/UNIQUENESS.md` lists every fitting divisor of each corpus."
- after (:241-242): "Of the candidate divisors 6 to 14, the standing curve reports fit only 14 on `udecoy-a/b`, only 10 on `d1-a/b` and only 12 on `combo2-a`; both 13 and 14 fit on `utie-a`, `utie-b` and `combo2-b`." (facts copied from the work-folder UNIQUENESS.md)
- "lever" wording -> "rule" (:268, :270, :275, :298). No figure changed; remaining hits for N1/Q1/D1 style strings are corpus ids (`n1-a`, `q1-a`, `d1-a`) that name test variants.
- Provenance (:452-454) still true: shasum of solve.py `1fb297ed...`, test_output.py `abcf8dae...`, tool.zip `7fd26ac3...` matches the recorded values.

## Finding 5, AL-17 (task.toml:22 verifier timeout): FIXED
- before: `timeout_sec = 2700.0`
- after: `timeout_sec = 4200.0`
- Arithmetic (counted by wrapping `run_repaired_cli` in a local oracle grading run): 58 `resolve` runs plus 27 other CLI runs (5 init, 20 set, 2 validate), each capped at 60 s, run one at a time under `_GRADE_LOCK`.
  - worst case resolve: 58 x 60 s = 3480 s
  - corpus generation plus all other checks: the whole local tests pass took 23.9 s (resolve 9.4 s, init/set/validate 1.5 s), and the Docker verify step in harden_t3 took 23-24 s; budget 24 s
  - 3480 + 24 = 3504 s; 4200 s leaves 696 s for the judge channel and a slower host. The old 2700 s covered only 44 resolve runs at the cap.

## Finding 6, TS-13 (tests/test_output.py:1956, registered :2009): KEPT
- Reason: splitting the weight-1 aggregate check would change test weights and the score scale that two probes have already measured.

## Finding 7, IN-L2 (instruction.md:3): FIXED
- before: "traversing the dependency chain in its documented order rather than"
- after: "traversing the dependency chain in the order each file points to the next rather than"

## Gates (each run once)
- precheck.sh: rc 0, last line `PRECHECK CLEAN` (tests 34, judge criteria 15).
- QC kit: structure_qc rc 0, 0 FAIL (17 pass, 1 warn: X1 binary files skipped, same as before); instruction_qc rc 0 PASS; tests_qc rc 0 PASS; judge_qc rc 0 PASS.
- Local oracle: `oracle_local.py` solve exit 0, then `local_score.py`: `SCORE 1.0000 (131/131)`. Run in a temp venv (pyarrow 26.0.0, harbor-rewardkit 0.2.1). `tests/__pycache__` removed.
- Docker and harbor are installed, but no Docker or harbor run was done in this step, because the gate asked for a local oracle run only.
- Tasks_INPUT sync: the 4 changed files copied with `cp -p`; `diff -rq` between bundle and Tasks_INPUT is empty.
