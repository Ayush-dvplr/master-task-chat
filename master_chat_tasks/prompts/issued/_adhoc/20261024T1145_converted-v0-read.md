You are reading the real Opus v0 runs of 3 converted tasks to decide, per task, whether it can reach the gate with a small fix or should be dropped. Board id: `a1ab2d0`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261024T1145_converted-v0-read.md`.

Why (plan v1 rec 4, approved 24 Oct 11:26): no reruns and no blind harden. Read the failures first. Gate on 2 real runs: tests < 100, rubric < 100, overall < 70 (overall = mean of tests % and rubric %). Kill rule: tests >= 95 on a real run -> drop unless a new computation trap is designed.

Current v0 numbers (master's loss.py, 24 Oct 11:45):
| task | reward | tests | judge |
|---|---|---|---|
| caldermoor-commitment-closure | 0.8722 | 99/133 = 74.44% | 95/95 = 100% |
| numeric-reduction-benchmark-forge | 0.874 | 83/84 = 98.81% | 38/50 = 76% (one negative fired -3) |
| season-ladder-settlement | 0.8209 | 95/148 = 64.19% | 49/49 = 100% |

## Rules that survive compaction
- First thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" a1ab2d0`. If it fails, note it and carry on. Run it again at the very end.
- Tools are always available; never claim otherwise without a real call and its quoted error.
- After every compaction: run `TZ=Asia/Kolkata date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- READ ONLY on everything: bundles, harness clone, QC kit, `QC/`, `master_chat_tasks/`. No Docker, no `harbor run`, nothing that calls a model. You write only in OUT.
- Do the work yourself. No subagents.
- Every claim cites file:line, a command with quoted output, or a trajectory step. Unconfirmed = UNVERIFIED.

## Inputs (per slug)
- Bundle: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Tasks_INPUT/<slug>/`
- Run: `Terminal_2.0_Harbor_Harness/jobs/<slug>/` (logs/, trajectory/claude-opus-5/...). Check `logs/job-config.json` staged path; if it is under the OLD `Harbor_Harness/Terminal_2.0_Harbor_Harness/.kiro-staged-tasks/`, the master already confirmed the only diff is `.kiro-staged-from` + task.toml allowed_hosts, so the score is valid.
- Loss table: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/loss.py" <slug>` (save output to `OUT/loss/<slug>.txt`).
- Rules: `master_chat_tasks/prompts/templates/_COMMON_RULES_v3.md` (Judge rules section, Score conventions), `master_chat_tasks/knowledge/LEVER_RULES_v1.md` (updated 24 Oct 13:40: section 1b Opus-habit bank H1-H6, G10 cost table, J1 at most 6 what-if figures that solve.py prints, J3 mandatory honesty negative, J4 exactly one concrete code-quality criterion, J8 no criterion restating a test-graded method), `master_chat_work/20261024_process/final_delivery/SYNTHESIS.md` (what the delivered tasks that scored under 70 did), `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md`, kit checks `master_chat_work/20261024_process/qc_reverse/A/checks.json`.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/converted_read`

## Per task
1. Every lost or fired item from loss.py: what the agent did, trajectory step, cause class GENUINE (computation the spec settles) / AMBIGUITY / HIDDEN RULE / AMPLIFICATION / ARTEFACT. Quote the instruction line that settles each GENUINE item, or say none.
2. Run-to-run risk: which GENUINE losses look stable (a real misunderstanding repeated in code) and which are luck (a one-off slip). The gate needs 2 runs.
3. Judge from probe (A5): list behaviours the trajectory shows the agent did NOT do but a careful engineer would (for example never tested an edge input the spec names, never checked its output against a stated invariant, a claim in the final message its own output contradicts). Each becomes a candidate criterion: id, text, weight, the oracle evidence that a good solve does it, the trajectory step proving Opus missed it, and the kit checks it must pass (JD ids). Conduct criteria only if the oracle path shows the behaviour (v3 Judge rules).
3b. Lever check (LEVER_RULES section 1 + G10): name the task's levers, say whether each is a stated single-reading rule, and which H1-H6 habit it uses. Estimate each lever's cost alone as a share of test points from the loss table (no Docker). Name any H1-H6 lever the shipped data already supports in a rarely joined field.
4. Arithmetic: with tests held at the v0 value, the rubric % needed for overall < 70, and whether your candidate criteria get there without touching tests. Then the minimal fix list (judge only, or judge + named test/data change) and its expected QC cost (which kit checks it touches, from checks.json).
5. Verdict: FIX (list, at most 1 fix round + 1 QC), or DROP (why). numeric-reduction is tests 98.81 so the kill rule applies unless you name a new computation trap that the shipped data settles; say which.

## Deliverables
- `OUT/READ.md`: one section per task with the 5 items, then a summary table task | verdict | expected tests | expected rubric | expected overall | fix size.
- `OUT/result.json`: {"board": "a1ab2d0", "status": "done|partial", "tasks": {slug: {"verdict": "FIX|DROP", "loss_classes": {..}, "candidate_criteria": [..], "expected": {"tests": n, "rubric": n, "overall": n}}}, "unverified": [..]}.
- Final reply: 5 lines max, with the OUT path.
