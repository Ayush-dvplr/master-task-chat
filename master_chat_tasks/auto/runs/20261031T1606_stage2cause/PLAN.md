# PLAN for this auto run (written by the master from Ayush's words; wins over AUTO_POLICY.md)

Until: 17:30 IST
Paid runs: 0
Workers/harness/Docker: 5 / 1 / Docker by dockfree.py (START=yes before every container)
Budget: no paid runs in this run
Wind-down: none
Last spawn: 17:00 (Ayush: no long sessions started after 17:00; whatever is left continues in a later auto run)
Ayush's words (verbatim):
> can you do this in auto mode now : 1. Find the real cause
> (16:05) save opus claude as much you can by using the codex or opencode gpt options ... 5:30 pm today and later whatever is raning we will do later , stop running long prompts sessions after 5 pm

Models (Ayush 16:05 answers): replays + scorer = opencode `openai/gpt-6.1-sol` (`auto.py spawn ... --model openai/gpt-6.1-sol`); the 3 blinds = Opus (default, true calibration of our blind); no kiro; CAUSE_REPORT draft = `codex exec -s read-only` in a later run, master checks key numbers.

Step 1 of the NO CORE plan (master 31 Oct ~15:50): find why Opus loses points on the lowest stage-2 tasks, and whether our blind sessions fail where Opus failed.

## Do, in this order
1. Spawn the five issued sessions (prompts in `master_chat_tasks/prompts/issued/_stage2_calib/`):
   - `3d517b2` replay A1 (GPT) (billing 59417607, PM2.5 98ed74c1, royalty 75407a55) -> `master_chat_work/20261031_stage2_calib/replay_A1/`
   - `4e9d595` replay A2 (GPT) (pension 9bb234eb, spectrum fa7c65bd) -> `master_chat_work/20261031_stage2_calib/replay_A2/`
   - `d830ccb` blind billing, `5c1644a` blind PM2.5, `de212ed` blind pension (Opus) (BLIND_DIRs in `_runs/20261031/stage2-calib/blind_dirs.json`)
2. Blind DONE: check the program and `work/result_<sha>.json` exist and parse; board done.
3. All three blinds DONE: master writes the scorer prompt (`_stage2_calib/<ts>_score_blinds.md`): for each blind, a scratch copy of the stage-2 task whose `solution/solve.sh` copies the blind program to the path the instruction names and runs it exactly as the instruction says, `harbor run --agent oracle` (dockfree first), tests score, then the same instrumented per-check labels as the replay sessions, and a table blind vs Opus per check (lost by both / only Opus / only blind). Spawn it with `--model openai/gpt-6.1-sol`, only if before 17:00; else leave it for the later run.
4. Replay DONE: check `result_<sha>.json` parses, replay tests within 0.5 of recorded (else note why); board done.
5. All of 3d517b2, 4e9d595 and the scorer DONE (likely a later run): `codex exec -s read-only` drafts, master checks and writes `master_chat_work/20261031_stage2_calib/CAUSE_REPORT.md`: why Opus loses (share by cause, test and judge), whether our blind is calibrated (blind vs Opus tests per task), the copyable mechanisms that pass our QC kit, and the decisions for Ayush (plan steps 2-4: which task to twin, gate change, judge target). Put the decisions in REPORT.md Needs Ayush.
6. A worker STALL or doom loop: one continue message; a second one -> note it in REPORT.md and leave it.

## At 17:30
- `auto.py stop`. Sessions still running keep going on their own; REPORT.md lists them under Still running at stop; nothing is aborted.

## Do not
- Push, commit, paid runs, or `auto.py harness`.
- Edit rule files, templates, knowledge, GOALS or policy (findings go into the report only).
- Edit, move or delete anything under `anubis-stage-2/` (sessions work on scratch copies).
- Open or spawn hangar-check-replan `af5dddf` or depot-charge-plan `154f570` (held: Ayush has not answered question 2).
- Touch pushed, parked, dropped or killed tasks.
- Docker prune.

## Ayush 16:12 rule (applies to every GPT prompt from now on)
Every prompt or message sent to an opencode session on a GPT model must contain the line: "Strictly do not run subagents (no task, agent or background-agent tools). Do all work yourself in this main chat."
