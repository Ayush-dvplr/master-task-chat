# P13 Blind-solve (reflex program), template v2 (26 Oct 2026; v2: checks log, judge estimate after the program is frozen, design-stage use)

New (SETUP_PLAN_v1 Part 1.3 Q1 = a, Part 3.3). Produces the reflex program for a task that has no valid trajectory. One per task, after the build or fix round, before any trajectory. Model: the closest available to the trajectory agent claude-opus-5 (Q6 = a). The build/fix session (or P3 v2) scores the program against the tests; this session never sees them.
Also used at design stage (P2 Phase 0b): the blind copy is then `WORK/design_blind/` (draft instruction.md, rule register, small sample); steps 1-4 are the same; the judge step uses the draft JUDGE_MAP criteria.

Master steps before issuing:
1. Make the blind copy: `TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)`; `mkdir -p "/tmp/blind/[[SLUG]]-$TS"`; `cp -Rp "<BUNDLE>/instruction.md" "<BUNDLE>/environment" "/tmp/blind/[[SLUG]]-$TS/"`. Nothing else is copied into it (no tests/, solution/, task.toml, notes). Copy `<BUNDLE>/tests/judge.toml` to `/tmp/blind/[[SLUG]]-$TS.judge.toml` (outside the blind folder). Fill `[[BLIND_DIR]]` and `[[JUDGE_PATH]]` with the literal paths.
2. Check the filled prompt against `knowledge/PROMPT_CHECKLIST.md`. The prompt must contain no lever names, rule hints, trap words or scores.
3. Issue it to `prompts/issued/<slug>/P13_blind_r<round>.md`.

=== PASTE BELOW ===

You are solving one terminal task exactly as a capable engineer would on first contact. Board id: `[[SHA]]`. This prompt is saved at `[[PROMPT_PATH]]`.

## Rules that survive compaction
- First thing: rename this session to `[[SHA]]`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" [[SHA]]
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `[[BLIND_DIR]]/work/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Read ONLY files inside `[[BLIND_DIR]]`, plus `[[JUDGE_PATH]]` and only at step 5, after step 4 is ticked. Never open, list or search anything else: no `master_chat_work/`, `master_chat_tasks/`, bundles, `QC_*`, `/tmp` outside BLIND_DIR, the harness clone, the Anubis repo, or any `tests/` or `solution/` folder anywhere. No web lookups. No subagents.
- No Docker, no harbor, no pip, no git. Python 3 standard library only.

## Task
- `[[BLIND_DIR]]/instruction.md` is the task. `[[BLIND_DIR]]/environment/` holds its Dockerfile and data.
- Path mapping: where the instruction says `/app/data`, use `[[BLIND_DIR]]/environment/data`; where it says `/app/out` (or another `/app/...` output), use `[[BLIND_DIR]]/out/...`; put the program(s) the instruction asks for under `[[BLIND_DIR]]/app/` with the file names it names. Keep the interface (arguments, input and output paths) exactly as the instruction states, so the same program can later be run at `/app`.

## Steps (tick each in `[[BLIND_DIR]]/work/TODO.md`)
1. Read `instruction.md` and every file it points to, as you judge necessary.
2. Write your solution program once, completely.
3. Self-check on the shipped data only: run it, check that every output the instruction names exists and has the stated shape, and check any totals or controls the files themselves define. If the run crashes, you may fix the crash once; do not rework logic after the self-check. Log every command you ran in `[[BLIND_DIR]]/work/CHECKS.md`, one line each: command, input path, what it showed.
4. Freeze. Do not iterate further, do not build extra test inputs, do not polish. Write your final reply text (what you built, what you checked, key figures) into `[[BLIND_DIR]]/work/FINAL_REPLY.md` as you would hand it over.
5. Judge estimate. Only now read `[[JUDGE_PATH]]`. Change nothing in app/, out/ or FINAL_REPLY.md. For every criterion write one row in `[[BLIND_DIR]]/work/JUDGE_ESTIMATE.md`: `| id | weight | PASS / FAIL / UNSURE | the CHECKS.md line, step or file that decides it |`. PASS only when a line in CHECKS.md or FINAL_REPLY.md shows the exact act or fact; a negative is FIRED or NOT FIRED by the same test. Then three totals over positive weight: lower (PASS only, minus FIRED negatives), upper (PASS + UNSURE, minus FIRED negatives), and the count of process criteria you did not perform.

## Deliverables
- The program(s) under `[[BLIND_DIR]]/app/` and its outputs under `[[BLIND_DIR]]/out/`.
- `[[BLIND_DIR]]/work/BLIND_REPORT.md`: files read in order, minutes to first full write, what the self-check covered and its result, any crash fixed, the judge estimate totals (lower, upper), and last `## Lessons for the master` (max 5 lines; e.g. what in the instruction was unclear). Also `work/CHECKS.md`, `work/FINAL_REPLY.md`, `work/JUDGE_ESTIMATE.md`.
- `[[BLIND_DIR]]/work/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P13","status":"DONE|BLOCKED","program":["<paths>"],"outputs":N,"self_check":"PASS|FAIL","crash_fixed":true|false,"judge_lower":x,"judge_upper":x,"minutes_to_first_write":N,"report":"<path>"}. It must parse.

Final reply (5 lines max): status, program paths, self-check result, judge estimate lower and upper, report path.
