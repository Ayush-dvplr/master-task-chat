# Master chat goals (registered 21 Oct 2026, 00:00 IST, from Ayush)

## Role
Advisor and prompt-writer for Ayush's Harbor 0.24 tasks. Heavy work runs in other sessions from my prompts. I decide what to store and keep it small.

## What I must handle
| # | Capability | Done means |
|---|---|---|
| G1 | Compaction | After any compaction, a fixed read order restores the exact state: no lost decisions, no re-asking. |
| G2 | Context hygiene | My own chat stays light: big reads go to other sessions, and I store only rules, decisions, state, failures and lessons. |
| G3 | Upstream changes | When the PL generator or QC changes (Ayush says so, or the fingerprint differs from the remote), I produce a diff prompt and update only what changed. Never hardcode QC or generator rules. |
| G4 | Build prompts | Paste-ready prompts to build a new task with the PL generator that passes the strict QC and hits the hardness target. |
| G5 | Fix and harden prompts | From a QC report, a raw trajectory, a pass_summary.json, or just a score plus "make it harder": a diagnosis and a paste-ready fix or harden prompt, like the beta generator's harden and feedback modes. |
| G6 | Records | Precise, deduplicated records in fixed formats. Appendable ones (scores, feedback, lessons) as JSONL; current-state ones as small JSON or MD. |
| G8 | ChatGPT idea prompts | Paste-ready ChatGPT prompts, mechanism-card style (beta Mode 4) but dynamic: the prompt carries the current lever bank, what held, what leaked, and settings already used. Rewritten after every batch. Every lever is measured per task (baseline it causes, real-run points lost on its checks) and its score kept in a lever bank. |
| G9 | Uniqueness | Each new task prompt is unique against MY OWN registry: new instruction, new data, new levers, plus some proven old levers. Never reuse the same full lever set, and never let tasks converge on one internal type (same archetype + same lever pattern + same task shape). Exploration is required: normally several new levers per task; exactly one new lever is a rare exception with a logged reason. (No check against Anubis/Finalized needed.) |
| G10 | Task tracking | One registry of every task built: idea, archetype, levers used, baseline table, every score (build run, after each fix, final 8 runs), what leaked, what was changed, with IST timestamps, session ids, prompt versions, generator/QC fingerprints, QC verdicts and fix rounds. |
| G11 | Hardness check | Rewritten 27 Oct (pipeline v4). Hardness comes from a proven test lever (LEVER_RULES_v3 1C P-1..P-3) whose kill test in Docker shows every strong generic solver losing by WRONG output, or by timeout/crash only on hidden scale under LEVER_RULES v3.5 (Law 1 amended 27 Oct 20:10, answer B). Measure = 3 fresh P13 blind reads losing >= 10% of positive test points (wrong output, or hidden-scale loss under v3.5). Proof = 1 real Opus run on our harness on the frozen QC-passed bytes. After every run the master reads the trajectory (KNOWLEDGE.md section T) and decides the next change. Difficulty comes from computation on hidden data, never from withheld rules. | [v3.6: Ayush 27 Oct 22:30, new gate tests < 85, rubric < 85, final < 50] See LEVER_RULES_v3 1C v3.6 bullet: a test lever now costs 25-40% of positive test points, and a plain first-write program and the all-but-one program aim at tests <= 75. Blind bar: each of the 3 fresh blind reads scores tests <= 80, its losses WRONG output or v3.5 hidden-scale loss. Judge: probe band with predicted probe mid 15-20. Overnight auto runs: the master may send "go" at DESIGN READY when the kill table passes (every generic solver and every blind program loses >= 15% of lever points, shipped inputs fast, reference <= 1/4 of the stated limit); otherwise Needs Ayush.
| G7 | Self-learning | Every score, every feedback from Ayush and every QC false positive becomes one lesson, applied to the next prompt. Patterns change the prompt templates, not just the notes. |

## Working rules for the discussion
- Do not just accept answers. If an answer conflicts with a report, the QC or an earlier answer, say so and ask again until it is clear.
- Inputs from Ayush are closed for now; he may add points later.

## Sequence
1. Register goals (this file).
2. Read every report and file built so far.
3. Question and discussion rounds until everything is clear.
4. Propose the final structure and process; Ayush approves or asks.
5. Build the final folder and process (move from temp into master_chat_tasks/, delete temp after OK).

## End outcome
- Self-improvement loop: scores per lever feed back into the idea prompt and builder prompt (which levers hold, which leak).
- Now: a working master-chat system (records, tools, prompt templates) for tasks that pass the kit QC with zero findings (dec 101) and score under the gate on 1 real run of the frozen QC-passed bytes (Ayush 27 Oct 17:17: "push needs only 1 run that is QC passed and under our gate score"): tests < 85, rubric < 85, overall < 50 (gate v3.6, Ayush 27 Oct 22:20 "new gate is test < 85 , rubrics < 85 and overall < 50"; was tests < 100, rubric < 100, overall < 70). (The old 0.10-0.20 / under-30% target is retired.)
- In 2 to 3 weeks: use the collected issues, lessons and idea bank to design Ayush's own generator for Harbor 0.24.

## Pipeline v4 (Ayush "proceed" 27 Oct; master_chat_work/_dev_research/pipeline_v4/PLAN.md)
Order: design (kill test, Law 1) -> build + stage-2 self-checks (precheck.sh) -> 3 blind reads -> QC full once, fix-all under G1-G7 -> QC recheck with carry-over -> freeze -> 1 harness run. No harden after QC PASS. A missed gate: no re-run on the same bytes; trajectory read-out, fix prompt, recheck, 1 new run. Count cap option A (over 35 checks = warn, never merge to reach it). Honesty negative -3 in every judge. Regrade diagnostic only. Auto-mode QC may run harbor oracle/nop (2 oracle + 1 nop).
