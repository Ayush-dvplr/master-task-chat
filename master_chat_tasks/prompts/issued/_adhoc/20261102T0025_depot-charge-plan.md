You are scoring, without a paid run, the program that paid attempt 2 of ONE Harbor 0.24 bundle, `depot-charge-plan`, delivered, to find any documented case it gets WRONG. No bundle edits. Board id: `af2d811`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261102T0025_depot-charge-plan.md`. Issued by the master on route 1 (Ayush 2 Nov 00:22: "A (recommended): score the a2 program offline").

## Rules that survive compaction
- First thing: rename this session to `af2d811`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" af2d811
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Strictly do not run subagents (no task/agent/background tools); do all work in this main chat.
- Last step before the final reply: run the rename again: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" af2d811`.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_depot-charge-plan/a2_score/TODO.md`, and continue from the first unticked item. Never re-run a finished Docker or fuzz block; check its log for ALL_DONE first. Copy this section word for word into any compaction summary.
- Keep `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_depot-charge-plan/a2_score/TODO.md` and `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_depot-charge-plan/a2_score/LOG.md` current after every step. Read files in pieces of at most 50 KB (tests/test_output.py and trajectory.json: grep, python extracts and line ranges, never print whole).
- Program runs: local python3 is fine for fuzz (wall cap `perl -e 'alarm N; exec @ARGV'`); any Docker run needs `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2` START=yes first. Poll with the early-exit loop of _COMMON_RULES_v5 rule 3. Kill your own child processes before you finish. Scratch and logs: `/Users/mac/Desktop/Terminal Bench/_runs/20261102/depot-charge-plan/a2score-<TS>/`.
- Read first: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261101_route1_notes.md` (R2 levers must be determinate from shipped docs; R3 trajectory items; R4 allowed forms) and `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md`.
- Never commit, push, pull or open a PR. Edit only OUT and the scratch folder. Never edit BUNDLE, Tasks_INPUT, the harness clone, the QC kit, `QC/`, `Output_RFP/`, `.kiro-run-*` or the Anubis repos (all read only).

## Inputs (read only)
- Frozen bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/depot-charge-plan/` (expect tree 205cb85281c7 = Tasks_INPUT; record it with `find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`). Shipped docs: environment/data/*.md (charging_rules.md is the rule book). Reference: solution/solve.py.
- a2 run: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Output_RFP/depot-charge-plan/trajectories/claude-opus-5/run_1/` - `artifacts/app/out/` (delivered derive_report.py + reports), `agent/trajectory.json` (66 steps), `verifier/reward-details.json` (tests 557/557, judge 10/44), `trajectory_usage.json` ($5.99).
- a1 for comparison: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_depot-charge-plan/harden_r3/gate_run_a1/`.
- Harden r3 tooling and report: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/depot-charge-plan/h3_a1/` (fuzz.py, kill.py, gen_core.py at `../gen_core.py`, datagen.py, check_exact.py), `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_depot-charge-plan/harden_r3/HARDEN_REPORT.md` and `TRIP.md` (a1 matched the reference on 1200 folders; only rule 11 'replaced by' split it; uplift generator gen_core.py:369-456).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_depot-charge-plan/a2_score`

## Master notes
1. a2 scored tests 100 (557/557, uplift lever included: it reads rule 11 as "replaced by", unlike a1's min()). Final 61.37 = 0.5 x 100 + 0.5 x 22.73. While tests are 100 the final cannot go under 50, so the only question is: is there any rule in the shipped docs that the a2 program applies WRONG on inputs the docs allow? If yes, that case planted in held-out folders is the harden r4 lever. If no, depot parks or goes off route 1.
2. a2 is a min-cost circulation program that fuzzed itself against brute force on about 180 tiny folders (trajectory). So look where its own fuzz could not reach: larger instances, rules its tiny generator never exercised, boundary dates/times, rounding, tie-breaks, reject paths, multi-line notices, roster/tariff version edges. Read its fuzz generator in trajectory.json to list what it never varied.
3. A WRONG case only counts if the shipped docs fix the answer (cite file:line) and the reference (solve.py) agrees with that reading. If the reference itself disagrees with the docs, report it as a reference bug, not a lever.

## Steps
1. OUT/TODO.md; record tree sha; copy a2 `artifacts/app/out/` into OUT/a2_out/ with sha256 of each file; confirm a2 on the shipped data matches the frozen expected documents.
2. Rule trace: for each numbered rule in charging_rules.md and every other shipped doc rule that changes an output, the a2 lines that apply it (derive_report.py:line) and whether its own fuzz varied it (trajectory step). OUT/A2_RULES.md, one row per rule.
3. Fuzz a2 vs reference with the harden r3 generators: every branch (shipped-like, hidden, hidden_reorder, large, uplift) 300 seeds each, then targeted generators for the rules step 2 marks as not varied by a2 (inputs must be allowed by the docs). Log seeds, MATCH/DIFF per document, seconds.
4. For each DIFF: minimal reproducer folder, the doc line that fixes the answer, which side is right, and whether a careful agent's brute-force fuzz would catch it.
5. Trajectory readout (route-1 R3): files never opened, shipped-fitted literals, where checking stopped, judge probes skipped (R1-R8, R18, R19 = 0) and why. OUT/TIMELINE.md max 60 lines.
6. OUT/A2_SCORE.md: DIFF list (or "none found in N folders"), candidate lever(s) with predicted a2 tests if planted, judge low/mid/high, predicted final; recommendation: harden r4 on route 1 / off route 1 (one new documented rule) / park, one line of cost each. No edits.

## Deliverables
- OUT/A2_RULES.md, OUT/TIMELINE.md, OUT/A2_SCORE.md, OUT/LOG.md, OUT/result_af2d811.json: {"sha":"af2d811","slug":"depot-charge-plan","step":"a2-score","status":"DONE|PAUSED","tree_sha":"<12>","folders_fuzzed":N,"diffs":N,"reference_bugs":N,"candidate_levers":["<rule file:line>"],"pred_a2_tests_if_planted":x,"pred_judge_low":x,"pred_judge_mid":x,"pred_judge_high":x,"pred_final":x,"recommendation":"route1_harden|off_route1|park","report":"<path>"}. It must parse.

Final reply (8 lines max): folders fuzzed and DIFFs; candidate lever(s) with doc line; reference bugs if any; predicted final if planted; recommendation; report path.
