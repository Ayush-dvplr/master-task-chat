# Template rewrite session (setup plan v1), written 23 Oct 2026 08:40 IST. HOLD: start only after cohort 7cbd9f5 passes the gate on a real trajectory.

Board id: assigned by the master chat at start (replace `[[SHA]]` before pasting).

=== PASTE BELOW ===

You are rewriting the master chat's prompt templates and records to the approved setup plan. Board id: `[[SHA]]`. Rename this session to `[[SHA]]` first, using the same opencode db command as the other issued prompts.

Read in full first:
- `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/SETUP_PLAN_v1.md` (Parts 1-4, all APPROVED);
- `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/LEVER_PLAN_v1.md`;
- `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/` (every file, plus CHANGELOG.md);
- cohort's `HARDEN_REPORT.md` and `STACKING_CHECK.md` under `master_chat_work/20261023_cohort-retention-reconciliation/harden_r2/`. These are the proven pilot; copy what worked.

Rules:
- Never edit the harness clone, the QC kit, the Anubis repo, `QC assigned/`, `my tasks/`, or any bundle.
- No git writes.
- Never overwrite a template: add new version files and a CHANGELOG line for each.
- Keep the board-id rename, compaction rules, result json (sha = board id), oracle x3 (kit asks x5) and the clash rules exactly as they are.

Deliverables:
1. `master_chat_tasks/knowledge/LEVER_RULES_v1.md`: L1-L7, W1-W7, G1-G7, J1-J5, and the STACKING_CHECK + reflex gate (≤ 0.20), taken from LEVER_PLAN_v1 plus the pilot's lessons. Templates point to it by path; they never paste it.
2. New template versions, as Part 1 lists:
   - P2 build v2;
   - P9 harden v2 (with the 4-cause root-cause section);
   - P12 fix v2 (no fix may undo a lever or add a giveaway; reflex re-run after fixes; compensate if > 0.20);
   - P3 hardness check v2 (replay gate);
   - new P13 blind-solve v1 (read-only; sees only a copy of instruction.md + environment/; writes its program once; self-checks on shipped data; stops);
   - `_COMMON_RULES` gains W1 as a hard rule.
   P11 is unchanged.
3. `master_chat_tasks/registry/peer_tasks.json` plus `master_chat_tasks/tools/peer_manifest.py`:
   - commands: `check <dir>` lists new or changed tasks; `add`; `show`;
   - `root_sha` = sha256 over the sorted relative paths and contents of every file in the task folder;
   - fill it for the 20 tasks in `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Pass@1_New/`, with verdicts and patterns from `_dev_research/peer_levers/G1..G5/result_*.json`.
4. Add L1-L7 to `registry/levers.json` (peer evidence, rule file, reflex score per task, trajectory result per task, status), and mark CR-1..CR-5 and V0-1..V0-8 `leaked`. Keep the existing entries.
5. Add `valid` / `artefact_reason` to `registry/scores.jsonl`, by appending correction lines only (never rewrite old lines): cohort 58.67, vendor 52.41 and the district-heat timeout are invalid (permission bug / timeout).
6. `OUT/REWRITE_REPORT.md` in `master_chat_work/20261023_template_rewrite/`: every file created or changed, with one line each, plus `result_[[SHA]].json` (`{"sha":"[[SHA]]","status":"DONE","files":[...]}`, which must parse).

Final reply (8 lines max): files written, template versions, peer_manifest self-test output (`check` on Pass@1_New must list 0 new tasks), report path.
