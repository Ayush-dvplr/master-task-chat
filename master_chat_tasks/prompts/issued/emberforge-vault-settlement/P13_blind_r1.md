You are solving one terminal task exactly as a capable engineer would on first contact. Board id: `1cd546e`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/emberforge-vault-settlement/P13_blind_r1.md`.

## Rules that survive compaction
- First thing: rename this session to `1cd546e`:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '%Board id: \`1cd546e\`%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='1cd546e' WHERE id='$SID'"; opencode session list | head -5
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/work/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Read ONLY files inside `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750`. Never open, list or search anything outside it: no `master_chat_work/`, `master_chat_tasks/`, bundles, `QC_*`, `/tmp` outside BLIND_DIR, the harness clone, the Anubis repo, or any `tests/` or `solution/` folder anywhere. No web lookups. No subagents.
- No Docker, no harbor, no pip, no git. Python 3 standard library only.

## Task
- `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/instruction.md` is the task. `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/environment/` holds its Dockerfile and data.
- Path mapping: where the instruction says `/app/data`, use `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/environment/data`; where it says `/app/out` (or another `/app/...` output), use `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/out/...`; put the program(s) the instruction asks for under `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/app/` with the file names it names. Keep the interface (arguments, input and output paths) exactly as the instruction states, so the same program can later be run at `/app`.

## Steps (tick each in `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/work/TODO.md`)
1. Read `instruction.md` and every file it points to, as you judge necessary.
2. Write your solution program once, completely.
3. Self-check on the shipped data only: run it, check that every output the instruction names exists and has the stated shape, and check any totals or controls the files themselves define. If the run crashes, you may fix the crash once; do not rework logic after the self-check.
4. Stop. Do not iterate further, do not build extra test inputs, do not polish.

## Deliverables
- The program(s) under `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/app/` and its outputs under `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/out/`.
- `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/work/BLIND_REPORT.md`: files read in order, minutes to first full write, what the self-check covered and its result, any crash fixed, and last `## Lessons for the master` (max 5 lines; e.g. what in the instruction was unclear).
- `/tmp/blind/emberforge-vault-settlement-20261023T144112-9750/work/result_1cd546e.json`: {"sha":"1cd546e","slug":"emberforge-vault-settlement","step":"P13","status":"DONE|BLOCKED","program":["<paths>"],"outputs":N,"self_check":"PASS|FAIL","crash_fixed":true|false,"report":"<path>"}. It must parse.

Final reply (5 lines max): status, program paths, self-check result, report path.
