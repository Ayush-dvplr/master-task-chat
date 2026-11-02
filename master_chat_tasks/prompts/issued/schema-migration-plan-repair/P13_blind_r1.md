You are solving one terminal task exactly as a capable engineer would on first contact. Board id: `cee149a`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/schema-migration-plan-repair/P13_blind_r1.md`.

## Rules that survive compaction
- First thing: rename this session to `cee149a`:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '%Board id: \`cee149a\`%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='cee149a' WHERE id='$SID'"; opencode session list | head -5
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/work/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Read ONLY files inside `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4`. Never open, list or search anything outside it: no `master_chat_work/`, `master_chat_tasks/`, bundles, `QC_*`, `/tmp` outside BLIND_DIR, the harness clone, the Anubis repo, or any `tests/` or `solution/` folder anywhere, except the repository's own `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/environment/repo/tests/`, which is part of the task. No web lookups. No subagents.
- No Docker, no harbor, no pip, no git. Python 3 standard library only.

## Task
- `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/instruction.md` is the task. `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/environment/` holds its Dockerfile and data.
- Path mapping: where the instruction says `/app/repo`, use `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/environment/repo` and repair it in place; where it says `/app/ci`, use `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/environment/ci`; where it says `/app/out`, use `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/out`. Leave `/app/...` paths inside the repository code and the output files exactly as the contract states (do not bake `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4` into them), so the same repository and outputs can later be checked at `/app`. Running the repository's visible tests with the standard library is allowed.

## Steps (tick each in `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/work/TODO.md`)
1. Read `instruction.md` and every file it points to, as you judge necessary.
2. Make your repair once, completely, and write the outputs.
3. Self-check on the shipped data only: run it, check that every output the instruction names exists and has the stated shape, and check any totals or controls the files themselves define. If the run crashes, you may fix the crash once; do not rework logic after the self-check.
4. Stop. Do not iterate further, do not build extra test inputs, do not polish.

## Deliverables
- The repaired repository in `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/environment/repo/` and every output the instruction names under `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/out/`.
- `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/work/BLIND_REPORT.md`: files read in order, minutes to first full write, what the self-check covered and its result, any crash fixed, and last `## Lessons for the master` (max 5 lines; e.g. what in the instruction was unclear).
- `/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/work/result_cee149a.json`: {"sha":"cee149a","slug":"schema-migration-plan-repair","step":"P13","status":"DONE|BLOCKED","program":["/tmp/blind/schema-migration-plan-repair-20261023T145400-92d4/environment/repo"],"outputs":N,"self_check":"PASS|FAIL","crash_fixed":true|false,"report":"<path>"}. It must parse.

Final reply (5 lines max): status, program paths, self-check result, report path.
