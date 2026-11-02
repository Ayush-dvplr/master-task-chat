You are reworking ONLY the judge of ONE Harbor 0.24 bundle: `dispatch-plan-reoptimization`. Board id: `cc4bb7f`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/dispatch-plan-reoptimization/P12_judge_r1.md`.

## Rules that survive compaction
- First thing: rename this session to `cc4bb7f`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" cc4bb7f
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `WORK/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step. Read files in pieces of at most 50 KB (`tests/test_output.py` is about 17,000 lines; read it by line range, never whole; the agent's `solver.py` is 1,775 lines).
- Read first, in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES_v2.md`, then `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md`, `QC_RULINGS.md` and `QC_FIX_PLAYBOOK.md` (same folder). Then the live kit's judge rules (JD-* checks and the judge caps / weight / negative-total rules) under `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`; record `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` once.
- Scope lock: edit ONLY `tests/judge.toml` in BUNDLE, plus the WORK files that describe the judge (QC_DEFENCE.md, XREF.md, LEVERS.md, TRUTH.md judge lines if any, LOG/TODO). Never edit `instruction.md`, `environment/`, `solution/` code, `tests/test_output.py`, goldens, the generator in `WORK/build/`, `reward.toml` or `task.toml`. If a fix seems to need any of them, stop and write it under "Lessons for the master".
- Criterion weights are only 1, 3 or 5 (negatives -1, -3, -5). Never 2 or 4.
- Never commit, push, pull or open a PR. Never edit the harness clone, the QC kit, `QC/copies/`, `QC assigned/` or `my tasks/`. No Docker in this round.
- Lock: take `mkdir /tmp/opencode-logs/locks/dispatch-plan-reoptimization.lock` before any bundle edit and remove it at the end (if it exists: `sleep 200`, retry, max 30 minutes, then report).
- At the very end, run the rename command once more.

## Inputs
- BUNDLE (edit only tests/judge.toml): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/dispatch-plan-reoptimization` (tree hash before this round e931391c733f: `find . -type f | sort` then shasum over paths and contents, first 12).
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/dispatch-plan-reoptimization`
- Real attempt 2 run (Claude Opus 5, 76.52 overall / tests 67.33 / rubric 85.71, judge 18/21 positive points): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_dispatch-plan-reoptimization/traj_a2/job/trajectory/claude-opus-5/Run 1/` (`agent/trajectory.json`, `verifier/`, `report.json`, `judge_response.txt`, the agent's `/app/out` files if present).
- Previous rounds: `master_chat_work/20261022_dispatch-plan-reoptimization/{harden_r1,p12_r1,p12_r2,p12_r3}` and QC reports under `/Users/mac/Desktop/Terminal Bench/QC/reports/dispatch-plan-reoptimization/` (latest v4, board 3a23fca).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_dispatch-plan-reoptimization/judge_a2`

## Why this round (master's analysis; verify every number yourself before you rely on it)
- overall = 0.5 x tests + 0.5 x rubric. The tests channel works: the agent lost 32.67 test points to ONE natural trap. Its `sweep()` (solver.py about lines 1280-1312) tests "above the cutoff" before the rejection reasons, so 28 demand rows of retired items (K07, K19; for example `dmd_block_a2.tsv` U000356, effective_seq 8422) were counted as out of scope instead of rejected `retired_item`. Agent: out_of_scope_rows 1863, rejected_rows 974. Oracle: 1835 and 1002. The agent's other shipped artifacts are byte-identical to the oracle's; only `data_quality.json`, `rejected_records.csv`, `reconciliation.txt` (`rejected_rows=`) and `audit_summary.md` (`- rejected_rows:`) differ. Rule: `handbook_ops_v9.md` about lines 329-339 ("rejection and accounting sweep ... first reason in that order ... totals.out_of_scope_rows counts sweep rows that survive rejection, carry effective_seq, and sit above the cutoff") and section 5 about line 80 (a retired item is rejected `retired_item`).
- The judge did not see the trap. R1-R5 are "states figure X" criteria (17 of 21 positive points) on reply figures the trap does not touch (objective, setup, holding, lots, shortfall), so the rubric scored 85.71 and the overall passed 70. For the overall to fall below 70 at tests 67.33, the rubric must be below 72.67.
- Goal: a judge that pays for the work the task is about (the accounting sweep and the audit artifacts it feeds) and no longer pays most of its points for echoing figures the agent's own program printed. Same task, same instruction, same tests.

## Master's directions
1. Recompute the shipped-set oracle figures yourself: run `solution/solve.py` with `APP_ROOT` set to a temp dir that holds a `data` symlink to `environment/data` (it writes `APP_ROOT/out/solver.py` and runs it), and read `data_quality.json`, `rejected_records.csv` (count of `retired_item` rows, and how many of those carry an effective_seq above the cutoff), `reconciliation.txt` and `audit_summary.md`. Diff against the agent's files from the a2 run. Use only figures you produced; quote the command and output in OUT/JUDGE_REWORK.md.
2. Keep R1 (objective, w5), R6, R7, R8, R9, R10 as they are unless the live kit flags them. Lower R2, R3, R4, R5 to weight 1 each (reply figures the task asks for, but not where the difficulty lives); set their `importance` annotation to whatever the live kit pairs with weight 1.
3. Add criteria that grade the accounting sweep and its audit artifacts on the shipped set, each atomic (one fact), observable in the trajectory or in the agent's `/app/out` files (say which `evaluation_target`), and traceable to an instruction sentence ("publish the corrected plan with its audit artifacts"; "the operating contract ... and the shape of every artifact are written out inside the export set") and to the handbook line it rests on. Suggested shape, adjust to the live kit:
   - one w5 criterion: the shipped `data_quality.json` reports 1002 rejected rows and 1835 out-of-scope rows (if the kit treats two figures as compound, split into a w3 and a w3, or w5 + w1);
   - one w3 criterion: `rejected_records.csv` gives reason `retired_item` to every demand row of a retired item, including those whose effective_seq is above the cutoff (state the count you computed);
   - optional w1 or w3: `reconciliation.txt` and `audit_summary.md` carry the same rejected-row count as `data_quality.json`.
   Judge text lives in `tests/` and is not shown to the agent, so naming the sweep order inside a criterion is allowed; never put it in `instruction.md` or the data.
4. If the live kit forbids a judge criterion that re-checks a figure the tests already check, use the behaviour form instead (for example "the agent's solver.py applies every rejection reason before it counts a row as out of scope"), quote the rule, and explain the choice.
5. Check the live kit's caps (criterion count, positive and negative totals, negative-total vs positive-total rule) and state the numbers after the change.

## Phases
### Phase A: paper judge before and after (no Docker)
1. Score the a2 trajectory against the CURRENT judge by hand (pass/fail per criterion with a quoted line); it must reproduce 18/21. If it does not, stop and report why.
2. Score the a2 trajectory against the NEW judge by hand, the same way. Then score a reference reply: a run identical to a2 but with the trap fixed (oracle artifacts; the a2 reply with the corrected counts; a2's solver.py code quality). Compute both rubrics and both overalls (a2: tests 67.33; reference: tests 100).
3. Targets: a2 rubric low enough that the overall is below 70 with at least 3 points to spare (rubric at most 66); reference overall at least 85; no criterion that a correct agent can fail for reasons outside its control (judge cannot see a file, wording too strict). If a target is missed, adjust weights inside {1,3,5} or the criteria and redo Phase A; max 2 tries, then stop with `PAUSED: <reason>` and the numbers.
4. Also score the a2 trajectory under each new criterion as a skeptical judge would: would `gpt-5.6-sol` reading `trajectory.json` actually see the figure (was the file printed or written in a tool call)? If not, pick an evaluation_target it can see.

### Phase B: apply and check
1. Edit `tests/judge.toml` only. Keep ids stable for unchanged criteria; new ids continue the sequence (R11, R12, ...). Each new criterion gets a `#` comment naming its instruction sentence and handbook file:line.
2. Update WORK: QC_DEFENCE.md (one entry per new criterion and for the weight change), XREF.md (every new figure: 1002, 1835, the retired-row count, with files), LEVERS.md (judge column). Run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/xref_check.py" "<BUNDLE>" "<WORK>/XREF.md"`: 0 findings.
3. Run the live kit's judge-related QC scripts / checks on BUNDLE: 0 FAIL. Run `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/stacking_check.py" "<BUNDLE>"`. Confirm `git diff --no-index` style: the only bundle file changed is `tests/judge.toml` (list file hashes before and after).
4. Tests are untouched, so oracle / owner / nop / reflex / trap survival are unchanged: say so with the tree hash of every file except judge.toml matching the before hash list. No Docker.

## Deliverables
- `OUT/JUDGE_REWORK.md`: oracle figures (command + output), agent vs oracle diff, criterion table before and after (id, text, weight, target, instruction sentence, handbook line), Phase A paper scores (a2 old, a2 new, reference new, with quoted evidence per criterion), overall projections, caps, QC script results, xref result, files changed. Last: `## Lessons for the master` (max 5 lines).
- `OUT/PL_NOTE.md`: anything QC may question about the new criteria, with the reply. Short, plain words.
- `OUT/result_cc4bb7f.json`: {"sha":"cc4bb7f","slug":"dispatch-plan-reoptimization","step":"P12_judge","status":"DONE|PAUSED","criteria_before":10,"criteria_after":N,"positive_total":N,"negative_total":N,"a2_rubric_old":x,"a2_rubric_new":x,"a2_overall_new":x,"reference_rubric_new":x,"reference_overall_new":x,"oracle_figures":{"rejected_rows":N,"out_of_scope_rows":N,"retired_item_rows":N,"retired_above_cutoff":N},"qc_fail":0,"xref_findings":0,"files_changed":["tests/judge.toml"],"tree_sha":"<first 12>","report":"<path>"}. It must parse.

Final reply (8 lines max): criteria before/after, weights changed, a2 rubric old -> new and projected overall, reference projected overall, caps, QC scripts result, report path. Next step: master issues the P11 QC rerun, then trajectory attempt 3 via the harness queue.
