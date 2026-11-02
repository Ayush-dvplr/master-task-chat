# Upgrade 2: Ayush's request (30 Oct 2026, evening) and open questions

Status: PROMPT ANSWERS IN (30 Oct ~20:30); writing session prompts. Nothing is built or changed. Order agreed: list items -> Ayush answers prompt questions -> master writes research/analysis session prompts -> sessions run -> master writes one plan -> Ayush answers the remaining questions -> plan verification -> build only after "proceed". Rule for the whole upgrade: nothing may degrade what works today.

## A. What Ayush asked for (his words condensed, one item each)

| # | Item | Ayush's words (gist) |
|---|---|---|
| U1 | Large context without memory loss; proper decisions | "handle large context without memory loss, proper decisions" |
| U2 | Fresh-chat bootstrap | a new chat given one prompt becomes as capable as this master: knows decision powers, state, rules |
| U3 | Folder restructure | a session prompt that decides how to restructure; root is disorganised; periodic cleanup of what is no longer needed |
| U4 | Git repo for the master's own folders | master can push/pull its own repo; the other root folders must not be pushed |
| U5 | Auto mode improvements + speed process | build on SPEED_PLAN_v1 (on hold) |
| U6 | Master decisions review | "there are few decisions of yours" to improve |
| U7 | QC kit updates handled ASAP | when the QC kit changes, rules/prompts update quickly |
| U8 | Learn from a directory of good tasks | Ayush will name it; some failed due to errors; analyse how they passed/failed, what fixes broke ("fix map": what a fix fixed and what it broke) |
| U9 | Task building method | generator made tasks easy (flagged before); find rigid, repeatable ways; target final < 35 when needed |
| U10 | Levers | new levers untested; weightage; find as many proven levers as possible |
| U11 | Codex and Claude CLI as workers/researchers | can the master run Codex directly and take its output; same for Claude CLI; check Claude usage |
| U12 | External deep research | use Gemini Deep Research / ChatGPT research for new levers (prompts for Ayush to paste) |
| U13 | Self-upgrade guard | master cannot change its own rules without Ayush; signing (public/private key) or a script Ayush runs |
| U14 | Time and token research | "time and token ... without the output flag" (meaning to confirm, Q-P6) |
| U15 | Database | proper SQLite store; running terminals write a JSON file next to it, never the DB; master merges on "done" |
| U16 | Missing information | write down what is missing; answer at the end before the full plan |

## B. Checks done now (evidence)

- Codex CLI: `/Users/mac/.local/bin/codex`, codex-cli 0.163.0, `codex login status` = "Logged in using ChatGPT". Has `codex exec` (non-interactive, prompt from arg or stdin, `-m` model, `-s` sandbox, `resume`). So the master can run Codex directly from bash and read its output. Not yet test-run (uses Ayush's ChatGPT quota).
- Claude Code CLI: `/Users/mac/.local/bin/claude`, 2.1.314, `claude -p` print mode with `--output-format` json/stream-json. `claude auth status`: logged in, subscriptionType "max", email **sugamcorporate@gmail.com** (org "sugamcorporate@gmail.com's Organization"). See Q-P5.
- Claude usage on disk (~/.claude/stats-cache.json, last computed 24 Oct only): 19 sessions, 29,958 messages; model claude-opus-5-5 output 12.8 M tokens, cache read 2.53 B, cache write 45.6 M. Live plan limits are not in that file (the `/usage` screen inside claude shows them).
- Gemini CLI: not installed.
- Root folders now: Aakrsh tasks, Anubis_Tasks_Samples (4.3 G), QC (272 M), QC assigned, Terminal_2.0_Harbor_Harness (2.5 G), _tmp_master_tasks_20261020T2214 (120 M), anubis-stage-1 (2.1 G), anubis-stage-2 (1.2 G), beta-task-generator, converted tasks backup, harness_master_tasks, help others, job-search-skill, master_chat, master_chat_tasks (9 M), master_chat_work (1.8 G), research. ("Shubhi Tasks" and "Input Bundle Generator New", used earlier, are not at the root now.)

## C. Master's first self-assessment (to be tested by the sessions, not trusted)

1. Memory: state lives in many places (registry/tasks.json, board.json, pending.db, decisions.jsonl, feedback.jsonl, lessons.jsonl, open_questions.json, REPORT.md files, compressed chat). After compaction the master rebuilds from memory summaries; no single "current state" file exists. Candidate: one generated STATE.md + one DB, read on every start.
2. Decisions: recent misses with evidence: cold-chain go froze judge.toml while asking pred <= 35 (30 Oct 12:00, admitted); QC prompt note said oracle once (schema v14 slip); Nikhil fix prompt said shipped data byte-identical while also allowing data fixes; paid_run_cap read first digit; trajectory_readout labelled timeouts WRONG.
3. Speed: measured 35% of worker time waiting for Ayush/master, 23% in sleep/poll loops, Docker idle 43% of samples (MEASURE.md).
4. Build method: 5 of the last new builds on stated-rule levers were parked; what worked: hidden larger instances (P-3), held-out conventions (warrant), gated large graphs (schema). Several gates were met only with crash/timeout-share exceptions (tariff 60%, schema 70%, cold-chain 60%, outage 100%).
5. Writes: several tools write the same JSON files; concurrent sessions can race (no lock on registry/board).

## D. Open questions (answer at the end, before the full plan)

Prompt-part questions are asked now (Q-P*); the rest wait.

- Q-P1 Which research/analysis sessions to write (proposed list in chat).
- Q-P2 Path of the "good tasks" directory for U8.
- Q-P3 Git repo: which remote (new private GitHub repo?), which folders go in.
- Q-P4 Who runs research sessions: Ayush opens opencode sessions as today, or the master runs `codex exec` / `claude -p` itself.
- Q-P5 Claude CLI is logged in as sugamcorporate@gmail.com (Max). Is that the account to use?
- Q-P6 Meaning of "time and token ... without the output flag".
- Q-L1 Cleanup: what may be deleted, after how long (jobs/, /tmp copies, QC copies, old bundles, sessions DB)?
- Q-L2 Signing: who holds the private key, which files are "protected" (rules, prompts templates, AUTO_POLICY, tools)?
- Q-L3 Database: which records move in (registry, board, pending, decisions, feedback, scores)? Keep JSON copies for reading?
- Q-L4 Target score bands per task type (below 35 when?).
- Q-L5 Lever weightage: what share of points a lever must carry; which exceptions (crash/timeout share) become rules vs stay per-task.
- Q-L6 Gemini/ChatGPT research: does Ayush paste prompts and bring back answers, or install Gemini CLI?
- Q-L7 Budget: how much Codex/Claude quota the research may use.
- Q-L8 Speed plan (SPEED_PLAN_v1, on hold): merge into this upgrade?

## E. Answers so far (30 Oct ~20:30, Question tool)

- Q-P1 sessions: all nine (S1 memory + bootstrap, S2 folders + cleanup + git, S3 database + write inbox, S4 task study passed/failed + fix map, S5 build method + generator review, S6 auto mode + speed + decisions audit, S7 Codex/Claude CLI as workers + usage, S8 self-upgrade guard, S9 external deep-research prompts).
- Q-P2 good-tasks folder: `anubis-stage-2`.
- Q-P3 git: new private GitHub repo.
- Q-P4 runner: master runs `codex exec` itself.
- Q-P5 Claude CLI: "i change the login among my friends" -> the Claude CLI account rotates; treat its quota as unknown; no heavy claude -p use without asking.
- Q-P6 (U14): "research such that the upgrade takes less token and time without any tradeoff to quality of task if possible" -> token/time efficiency is a cross-cutting goal for every session and for the plan.

## F. Codex live test (30 Oct, master)

`codex exec -s read-only --skip-git-repo-check --ephemeral -c model_reasoning_effort=low -o last.txt "<count files in master_chat_tasks>" < /dev/null` -> rc 0, 12 s, answer 16 (correct), model gpt-6-sol, 7,146 tokens. Notes: needs `< /dev/null` (else waits on stdin); macOS has no `timeout` command; default config model gpt-6-sol, reasoning xhigh (override per run with -c).
