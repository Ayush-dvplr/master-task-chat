# P13 Blind-solve (reflex program), template v1 (23 Oct 2026)

New (SETUP_PLAN_v1 Part 1.3 Q1 = a, Part 3.3). Produces the reflex program for a task that has no valid trajectory. One per task, after the build or fix round, before any trajectory. Model: the closest available to the trajectory agent claude-opus-5 (Q6 = a). The build/fix session (or P3 v2) scores the program against the tests; this session never sees them.

Master steps before issuing:
1. Make the blind copy: `TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)`; `mkdir -p "/tmp/blind/[[SLUG]]-$TS"`; `cp -Rp "<BUNDLE>/instruction.md" "<BUNDLE>/environment" "/tmp/blind/[[SLUG]]-$TS/"`. Nothing else is copied (no tests/, solution/, task.toml, notes). Fill `[[BLIND_DIR]]` with the literal path.
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
- Read ONLY files inside `[[BLIND_DIR]]`. Never open, list or search anything outside it: no `master_chat_work/`, `master_chat_tasks/`, bundles, `QC_*`, `/tmp` outside BLIND_DIR, the harness clone, the Anubis repo, or any `tests/` or `solution/` folder anywhere. No web lookups. No subagents.
- No Docker, no harbor, no pip, no git. Python 3 standard library only.

## Task
- `[[BLIND_DIR]]/instruction.md` is the task. `[[BLIND_DIR]]/environment/` holds its Dockerfile and data.
- Path mapping: where the instruction says `/app/data`, use `[[BLIND_DIR]]/environment/data`; where it says `/app/out` (or another `/app/...` output), use `[[BLIND_DIR]]/out/...`; put the program(s) the instruction asks for under `[[BLIND_DIR]]/app/` with the file names it names. Keep the interface (arguments, input and output paths) exactly as the instruction states, so the same program can later be run at `/app`.

## Steps (tick each in `[[BLIND_DIR]]/work/TODO.md`)
1. Read `instruction.md` and every file it points to, as you judge necessary.
2. Write your solution program once, completely.
3. Self-check on the shipped data only: run it, check that every output the instruction names exists and has the stated shape, and check any totals or controls the files themselves define. If the run crashes, you may fix the crash once; do not rework logic after the self-check.
4. Stop. Do not iterate further, do not build extra test inputs, do not polish.

## Deliverables
- The program(s) under `[[BLIND_DIR]]/app/` and its outputs under `[[BLIND_DIR]]/out/`.
- `[[BLIND_DIR]]/work/BLIND_REPORT.md`: files read in order, minutes to first full write, what the self-check covered and its result, any crash fixed, and last `## Lessons for the master` (max 5 lines; e.g. what in the instruction was unclear).
- `[[BLIND_DIR]]/work/result_[[SHA]].json`: {"sha":"[[SHA]]","slug":"[[SLUG]]","step":"P13","status":"DONE|BLOCKED","program":["<paths>"],"outputs":N,"self_check":"PASS|FAIL","crash_fixed":true|false,"report":"<path>"}. It must parse.

Final reply (5 lines max): status, program paths, self-check result, report path.
