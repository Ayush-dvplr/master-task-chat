# Self-discovery research (read-only), issued 22 Oct 2026 22:36 IST. Board id: `d161afa`

You are mining everything this project has already learned about building Harbor 0.24 Terminal-Bench tasks that frontier agents (claude-opus-5) fail, plus every error, conflict and process failure along the way. You change nothing outside OUT. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022T2235_self_discovery.md`.

## Survival rules
- First: rename this session to `d161afa`:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '%Board id: \`d161afa\`%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); opencode db "UPDATE session SET title='d161afa' WHERE id='$SID'"
- Tools are always available; never claim otherwise without a real `date` call and its quoted error. After every compaction: run `date`, re-read this file, then `OUT/PROGRESS.md`, and continue from the first unticked source. Copy this section into any compaction summary.
- Read files in pieces of at most 50 KB. Trajectories are large: read them in slices by step, never whole.
- Read-only everywhere except OUT. No git writes, no Docker, no harbor runs. Never open `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214`.
- Write findings to OUT as you go (one source at a time), tick PROGRESS.md.

OUT = `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/self_discovery/`

## Goal
Produce evidence-backed rules for making tasks where a careful frontier agent scores about 0.10-0.20 on tests (pass line this phase: tests <100, rubric <100, overall <70%), without hidden rules, volume, arithmetic, puzzles or formatting tricks, and that pass the PL QC. Also: every error, conflict and process failure, so the process stops repeating them.

## Sources (in this order; list each in PROGRESS.md)
1. Records: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/` — `lessons.jsonl`, `log.jsonl`, `decisions.jsonl`, `feedback.jsonl`, `registry/{levers.json,scores.jsonl,ideas.jsonl,tasks.json}`, `knowledge/KNOWLEDGE.md`, `prompts/issued/_adhoc/20261022_round_notes.md`, `prompts/issued/_adhoc/20261022_converted_batch_notes.md`.
2. Prior study: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_lowscore-study/SYNTHESIS.md` and `levers_found.json` (do not redo it; extend and test its 13 rules against the newer evidence).
3. Our round outputs: every `DIAGNOSIS.md`, `HARDEN_REPORT.md`, `REBUILD_REPORT.md`, `RECHECK*.md`, `RECHECK_FIX.md`, `PL_NOTE.md`, `recheck.json` under `/Users/mac/Desktop/Terminal Bench/master_chat_work/2026102*/`, and every `_work/<slug>/{LEVERS.md,QC_DEFENCE.md,DESIGN.md}` under `master_chat_work/bundles/_work/`.
4. QC reports: `/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/qc_report/*/v*.md`, `/Users/mac/Desktop/Terminal Bench/QC assigned/qc_report/*/` (v*, triage*, fixplan*), and `QC assigned/converted_tasks_report/*.md`. Count which check IDs fail most, which were false positives, which fixes made tasks easier.
5. Real trajectories (claude-opus-5), the main new evidence: `/Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/*/trajectory/claude-opus-5/Run 1/` (agent/trajectory.json, verifier/ctrf.json, verifier/reward.json) and anything under `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/jobs/`. For each task: score; the steps where the agent found each rule; how it self-checked (visible examples, recomputing shipped outputs, reading tests-like files, brute-force search); where it lost points; whether any loss was a bundle bug (permissions, timeouts) rather than difficulty.
6. Live QC kit, for rule wording only: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (read-only).

## Deliverables (OUT)
1. `FINDINGS.jsonl`: one line each: {"id":"F-NN","kind":"lever_held|lever_leaked|agent_behaviour|qc_false_positive|qc_rule_trap|bundle_bug|process_failure|conflict|tooling","claim":"","evidence":[{"path":"","line_or_step":"","quote":""}],"tasks":[],"confidence":"high|medium|low","proposed_rule":"","rule_target":"P2|P4|P9|P11|P12|round_notes|QC_DEFENCE|none"}.
2. `AGENT_PLAYBOOK.md`: how claude-opus-5 actually solves these tasks (ordered habits with step quotes) and, for each habit, the task property that defeats it legitimately.
3. `LEVER_TABLE.md`: every lever seen, family (A-F per registry/levers.json), tasks, held/leaked count, why, and a verdict keep/fix/retire.
4. `CONFLICTS.md`: every contradiction between our rules, QC rules, PL answers and real results, with both quotes.
5. `RULES_PROPOSED.md`: at most 25 rules, ranked by evidence strength, each with the findings it rests on and the exact template/section it would change. Mark which of the 13 study rules are confirmed, weakened or contradicted.
6. `result_d161afa.json`: {"sha":"d161afa","status":"DONE","findings":N,"rules_proposed":N,"sources_read":N,"sources_skipped":[...]}.

Never invent evidence: every claim needs a quoted path + line or trajectory step. Mark guesses UNVERIFIED.

Final reply (8 lines max): counts by kind, the top 5 proposed rules in one line each, sources skipped and why, OUT path.
