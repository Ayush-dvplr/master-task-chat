# master_chat_tasks: records of Ayush's task-creation master chat

The master chat is an advisor. It answers "what next?" with the next step, the session that should run it, and a prompt written to an `.md` file. All heavy work (building, QC, runs, research, big reads) runs in new sessions. Only the master chat writes here, and since 24 Oct 11:26 (plan v1) only through the tools below.

## Read order after any compaction
1. `README.md` (this file) and `GOALS.md`.
2. `python3 tools/status.py`: stage and scores of every task (`status.py <slug>` for one). Answer any task question from this, never from memory.
3. `python3 tools/pending.py list`: every open step, question, reminder, running job. List open questions older than 12 h to Ayush at his next turn (U7).
4. `python3 tools/board.py show <sha>` for any session Ayush names (`done: <sha>`).
5. `knowledge/INDEX.md`, then `knowledge/KNOWLEDGE.md`. Read INDEX before proposing any research (U5). Then `prompts/issued/_adhoc/20261101_route1_notes.md` section R0 (lever order v3.8, 2 Nov; overrides older lever text everywhere, incl. line 31 below).
6. The last 10 lines of `decisions.jsonl`. ALL of `feedback.jsonl`. ALL `lessons.jsonl` lines with `"kind": "master_process"`: `python3 -c "import json;[print(d['ist'],d['lesson']) for d in map(json.loads,open('lessons.jsonl')) if d.get('kind')=='master_process']"`. Then the last 10 other lessons.
7. `master_chat_work/_dev_research/pipeline_v4/PLAN.md` (pipeline v4, Ayush "proceed" 27 Oct; wins where it differs), `master_chat_work/20261024_process/MASTER_UPGRADE_PLAN_v1.md` (approved 24 Oct 11:26) and `state.json` (config and standing rules only).

Then re-check live state before acting: `git -C Terminal_2.0_Harbor_Harness rev-parse HEAD` against `state.json`, and the files of any task in progress. Run `TZ=Asia/Kolkata date` before writing any time.

## Tools (the only write path)
| Tool | Does |
|---|---|
| `tools/issue.py SLUG KIND DRAFT OUT` | Issues a session prompt: refuses past caps (2 fix rounds per QC, 2 QC rounds, harden after PASS, drop rule at 3 edit rounds, parked/killed/dropped, 8-session time box) unless `--override "<Ayush verbatim>"`; writes the prompt file, board row, pending item; prints the handoff (board sha + step + clickable link only). |
| `tools/intake.py SHA` / `intake.py --job SLUG` | Checks a finished session (OUT folder, result.json) or a harness job (scores, staged path, staged vs bundle diff, author-note grep, gate, kill rule); `--apply` writes board, pending, scores, registry. |
| `tools/precheck.sh BUNDLE` | Live kit scripts + exe_copy + grep gaps + author-note grep + test/criterion counts (no cap) + v4 stage-2 checks (TRUTH line cites, judge type/target; TS-13 multi-file and JD-5 warns; SELF_CHECKS.md note). Every build and fix session runs it until `PRECHECK CLEAN`. |
| `tools/trajectory_readout.py RUN_DIR --out TRIP.md` | Section T read-out of one harness run from reward-details.json: lost/skipped/easy items, TIMEOUT/CRASH/WRONG split, FALSE_CLAIM; empty TRIP table the master fills. |
| `tools/loss.py SLUG` | Points lost per check and per hidden input from a harness job. Replaces hand P14 attribution. |
| `tools/status.py set SLUG k=v ...` | Task stage and scores (`registry/tasks.json`). Stages: build probe harden qc fix qc_pass gate_runs pl_ready parked killed dropped. |
| `tools/pending.py`, `tools/board.py`, `tools/name_session.py` | Open items; session board (BOARD.md is generated); session naming. |
| `auto/auto.py` | Auto mode (replaces night mode, Ayush 26 Oct): `start --until HH:MM --plan PLAN.md --label L` (adopts running board rows), `resume` (after reboot/closed terminal/limit), `adopt SHA`, `spawn SHA PROMPT`, `send SHA TEXT`, `harness BUNDLE`, `status`, `stop`. While on, follow `auto/AUTO_POLICY.md` + the run's `PLAN.md` and keep the run's `REPORT.md` current (`auto/LATEST` = current run folder `auto/runs/<ts>_<label>/`). `[AUTO WATCHER]` messages stand in for Ayush. Old night runs: `auto/runs/20261025_0048_night/`. |

After any write, view the result (table or list) before saying it is done.

## Pipeline (v4, Ayush "proceed" 27 Oct; replaces plan v1 probe-first order)
[2 Nov v3.8: lever order = route-1 notes R0 / LEVER_RULES 1C v3.8 bullet; primary lever must be lost by the careful exact program; misread-rule levers are extras; scale TIMEOUT counts with no cap; the WRONG-only wording below is superseded] Design (proven lever LEVER_RULES_v3 1C; kill test in Docker only, `--memory 4g --cpus 2`, perl alarm; every strong solver loses by WRONG output or hidden-scale timeout/crash under LEVER_RULES v3.5) -> stop DESIGN READY -> build + stage-2 self-checks (`precheck.sh` clean, WORK/SELF_CHECKS.md) -> 3 fresh P13 blind reads (>= 10% positive test points lost; v3.5 hidden-scale loss counts) -> QC full once (P11 v3), fix-all under guard rules G1-G7 (P12 v4, QC_FIX_PLAYBOOK_v3) -> QC recheck with carry-over (P11 v3 MODE recheck) -> 0 fails = **freeze** (tree sha) -> **1 harness run** on the frozen bytes -> gate met (tests<100, rubric<100, overall<70) = push. Gate missed: no re-run on the same bytes; `trajectory_readout.py` + KNOWLEDGE.md section T -> fix prompt -> recheck -> 1 new run. No harden after QC PASS. Count cap option A (over 35 = warn). Honesty negative -3 in every judge. Regrade diagnostic only. Templates: `_COMMON_RULES_v5`, P2 v5, P9 v4, P11 v3, P12 v4. Harness: one Docker task at a time, max 2 Docker-heavy jobs on the Mac.

## Rules for every intake and ruling
- **U3** Every lesson gets `template_change: file:line` or `no change: reason`.
- **U4** No KEEP/FIX ruling without the kit line (`qc_reverse/A/checks.json`) and the side-effect row (`qc_reverse/B/FIX_SIDE_EFFECTS.md`).
- **U9** Every plan states the harness runs it needs.
- **U12** Stop at the first QC PASS. No harden after PASS.
- **U13** Before fixing a new finding, diff the cited lines against the previous QC copy. Unchanged and passed last round = reviewer noise: KEEP with the diff as evidence, row into `knowledge/FP_DOSSIER.md`, and pass the defence file to the next reviewer.
- **U14** Keep every QC report copy; never prune.
- Every input from another session is verified on disk first, then recorded (intake.py), then answered. Copy each session's "Lessons for the master" into lessons.jsonl.

## Layout
| Path | Holds | Write pattern |
|---|---|---|
| `GOALS.md`, `state.json` (config + standing rules only) | current truth | overwrite |
| `board.json` -> `BOARD.md` | sessions | board.py / issue.py |
| `pending.db` | open steps, questions, reminders, running jobs, with history | pending.py |
| `registry/tasks.json` | one entry per task, pipeline block | status.py |
| `registry/scores.jsonl` | one line per run (probe, gate_run, run) | intake.py --apply |
| `decisions.jsonl` | `{ist, who, decision, verbatim}` | append |
| `lessons.jsonl` | `{ist, kind, surprise, lesson, changed}` | append |
| `feedback.jsonl` | `{ist, verbatim, class, action}` | append |
| `knowledge/` | see INDEX.md | overwrite on upstream change |
| `registry/levers.json`, `ideas.jsonl` | lever bank, ChatGPT ideas | overwrite / append |
| `prompts/templates/` | `_COMMON_RULES` + P1..P15, versioned, CHANGELOG.md | new version file per bump |
| `prompts/issued/<slug>/`, `issued/_adhoc/` | filled prompts | issue.py |
| RETIRED, read-only | `open_questions.json` (closed questions to 24 Oct), `log.jsonl` (events to 24 Oct) | none |

Outside this folder: session outputs `master_chat_work/<YYYYMMDD>_<topic>/`; bundles `Tasks_INPUT/<slug>/` (harness input) and `master_chat_work/bundles/`; scratch `/tmp/<slug>-<step>-<ts>/`.

## What gets stored
Only rules, decisions, state changes, failures and lessons, scores, levers and ideas. Never chat summaries or raw session output. Mark guesses UNVERIFIED. IST times from `date`. No secrets.

## Self-improvement
- After every score event: `intake.py --job --apply`, `loss.py`, then `levers.json`.
- A surprise gets a lessons.jsonl line (U3). If it changes a prompt: new template version + CHANGELOG line.
- If 3 tasks leak or fail the same way, change the template, not the weights.

## Hard rules
- Allowed repos: Terminal_2.0_Harbor_Harness, Anubis_Tasks_Samples, beta-task-generator, Finalized_Tasks_RFP, read-only git only. Ayush runs every pull, commit and push.
- Never edit the generator, the QC kit, `QC assigned/` or `my tasks/` without his explicit "proceed".
- When two authorities conflict, report it to Ayush; never pick one.
- Handoff to Ayush = board sha + step + clickable file:/// link only (feedback 24 Oct 10:10).
- Long jobs run in the background with logs in `/tmp/opencode-logs/<task>-<ts>/`.

## Process lessons (Ayush 08:47 23 Oct)
Every failure of MY OWN process goes to `lessons.jsonl` with `"kind": "master_process"`, and every corrective remark from Ayush goes verbatim to `feedback.jsonl`, in the same turn.
