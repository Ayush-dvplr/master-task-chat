You are drafting a report for the master chat. READ ONLY. Do not run Docker, harbor, git, pip, network, or any agent. Do not write files; your final message is the draft.

Read these, in full where short:
- /Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1/FINDINGS.md, CAUSES.csv, JUDGE_LOSS.csv, TASK_billing.md, TASK_pm25.md, TASK_royalty.md, result_3d517b2.json
- /Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A2/FINDINGS.md, CAUSES.csv, JUDGE_LOSS.csv, TASK_pension.md, TASK_spectrum.md, result_4e9d595.json
- /Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/score_blinds/FINDINGS.md, result_b366e00.json, CHECKS_*.csv
- Context on our own pipeline: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L5_stage2_study/PATTERNS.md

Write CAUSE_REPORT.md as Markdown (under 120 lines, plain short English, every number with its source file and field or line):
1. Line 1 `VERDICT: <one sentence>`.
2. Table per task (billing, pm25, royalty, pension, spectrum): recorded final/tests/judge, replay tests, oracle tests, lost test points by primary cause, top judge loss class.
3. Overall share of lost test points by cause (state the allocation rule used by each session and where A1 and the scorer disagree, e.g. PM2.5 LATENT-WRONG vs UNFAIR, and why).
4. Overall share of lost judge points by class.
5. Blind calibration: our blind vs Opus tests per task, both/only-Opus/only-blind counts; what it supports and what it does not.
6. Copyable mechanisms that pass our QC kit (with the QC kit file:line each session cited), ranked by evidence strength; for each: the evidence it really fails a careful agent (e.g. PM2.5 conforming no-step echo probes), and a one-paragraph recipe.
7. Not copyable, with the kit line it would fail.
8. Decisions for Ayush (the NO CORE plan steps 2-4): which mechanism/task to twin first, whether to keep the blind as the gate before a paid run, judge target, and what to measure in a pilot. Give a recommended option and one alternative for each.
Mark anything not directly supported by the files as INFERRED.
