You are studying 3 accepted peer tasks to learn what a task that passed the team QC and scored under the gate looks like, and how far our own bundles are from it. Board id: `6c287ec`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261024T1145_peer-qc-aditya.md`.

Why (Ayush, 24 Oct, Q57): our tasks loop through QC rounds and Opus still scores 100 on most. Teammates use the same QC kit and the PL accepts only zero findings. Aditya Patel's 3 tasks in `Pass@1_New` were accepted and scored 50-67. We want to know (a) does the live kit really give them zero findings, (b) where Opus lost points, (c) what design choices made that possible, (d) which of those our templates forbid or never use.

## Rules that survive compaction
- First thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 6c287ec`. If it fails, note it and carry on. Run it again at the very end.
- Tools are always available; never claim otherwise without a real call and its quoted error.
- After every compaction: run `TZ=Asia/Kolkata date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- READ ONLY on: the peer folders, the harness clone, the QC kit, every bundle, `QC/`, `master_chat_tasks/`. Work on COPIES in `/tmp/peer_qc-<YYYYMMDDTHHMM>/`. Never run `harbor run` or anything that calls a model or uploads. Docker only through `precheck.sh` (it builds from a copy); remove your own images at the end.
- Do the work yourself. No subagents.
- Every claim cites file:line, a command with its quoted output, or a trajectory step. Unconfirmed = UNVERIFIED.

## Inputs
- Peer tasks (QL Dinshi_Jain, author Aditya Patel): `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Pass@1_New/Dinshi_Jain/Aditya Patel/{detbench-release-gate-eval, estate-manifest-consolidation, kvec-meter-settlement-reconciliation}/`. Each has instruction.md, task.toml, environment/, solution/, tests/, Output/logs/pass-summary.json (scores 61.62 / 67.39 / 50.23), Output/trajectory/, trajectories/claude-opus-5.
- Precheck (live kit 71a653b2 + our gap checks): `"/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/precheck.sh" <bundle copy>`.
- Loss table: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/loss.py" "<peer task>/Output"` (tested, works on this layout).
- Kit check list: `master_chat_work/20261024_process/qc_reverse/A/checks.json` (302 checks with pass conditions) and `A/LEVER_COMPAT.md`.
- Our side (all updated 24 Oct 13:40 from the six delivered-task reads; compare against these, and against `master_chat_work/20261024_process/final_delivery/SYNTHESIS.md`): `master_chat_tasks/prompts/templates/_COMMON_RULES_v3.md`, `P2_build_v3.md`, `master_chat_tasks/knowledge/LEVER_RULES_v1.md`, `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md`, and two of our bundles for contrast: `Terminal_2.0_Harbor_Harness/Tasks_INPUT/dispatch-plan-reoptimization` (tests 67.33, judge 85.7) and `Tasks_INPUT/cohort-retention-reconciliation` (100/100/100).
- Earlier peer mining (20 tasks, older samples, QC failed): `master_chat_work/_dev_research/peer_levers/GROUP_SUMMARY.md` and `LEVER_PLAN_v1.md`. Do not redo it; say where these 3 agree or disagree with it.
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/peer_qc`

## Phase 1: kit verdict (per task)
Copy each task to scratch, run precheck.sh, save the full output as `OUT/precheck/<slug>.txt`. Table: task | fails | minors | warns | our gap-check hits | test count | criteria count. If any finding appears, quote it and judge whether it is a real defect, a kit false positive, or a gap check of ours that is stricter than the kit.

## Phase 2: where Opus lost points (per task)
Run loss.py, save as `OUT/loss/<slug>.txt`. For every lost or fired item: what the agent did wrong, citing the trajectory step, and the cause class: GENUINE computation trap / AMPLIFICATION (one bug billed across many tests) / AMBIGUITY (spec does not settle it) / HIDDEN RULE (rule not stated) / CONDUCT (judge criterion on process) / ARTEFACT (harness, timeout, env). Quote the instruction line that settles each GENUINE item, or say none exists.

## Phase 3: design anatomy
Per task: instruction length and structure, how rules are stated, data shape (files, decoys, hidden tiers), test design (weights, how many tests one bug touches, hidden vs visible), judge criteria (count, weights, conduct vs output, negatives), solution size. Then one table: design choice | which tasks use it | points it produced | does a kit check permit it (checks.json id) | do our v3 templates allow it (file:line) | adopt / adapt / avoid.

## Phase 4: deliverables
- `OUT/PEER_QC.md`: Phases 1-3, then `## What we change` with at most 8 concrete template or playbook edits, each naming the file and line it would change and the evidence row behind it. No edits made by you.
- `OUT/result.json`: {"board": "6c287ec", "status": "done|partial", "kit_zero_findings": {slug: bool}, "loss_classes": {slug: {class: points}}, "adopt": [..], "avoid": [..], "unverified": [..]}.
- Final reply: 5 lines max, with the OUT path.
