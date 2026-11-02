You are reverse-engineering the Input Bundle QC kit from its SOURCE, to learn exactly what makes each check pass, what each check pressures, and which checks fight each other. Board id: `5087cd2`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261024T1004_qc_kit_reverse_A.md`.

Why (Ayush, 24 Oct): every task loops through QC rounds. Fixes for one finding create new findings, and hardening gets undone by QC. Before we design new levers we need a full map of the kit. A twin session (`ef7d851`, prompt `20261024T1004_qc_reports_mining_B.md`) is mining the 41 QC reports in parallel. Do NOT read or wait for its output; the master merges both.

## Rules that survive compaction
- First thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 5087cd2`. If it fails, note it and carry on. Run it again at the very end.
- Tools are always available; never claim otherwise without a real call and its quoted error.
- After every compaction: run `date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB.
- READ-ONLY study. Never edit the QC kit, the harness clone, any bundle, `QC/`, `QC assigned/` or `master_chat_tasks/`. Read-only git only. Write only to OUT and scratch.
- Running kit scripts is allowed only on a COPY of a bundle in scratch (`/tmp/qc_reverse_A-<YYYYMMDDTHHMM>/`), so you can confirm what a script really does. No Docker, no harbor runs, no network.
- Do the work yourself. No subagents.
- Every claim about the kit cites `file:line` and quotes the words. Something you did not confirm is labelled UNVERIFIED.

## Inputs
- KIT (the authority; Ayush confirmed 24 Oct): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (01-05 `*_QC.md`, `Final_checklist.md`, `Starter.md`, `structure_qc.py`, `tests_qc.py`, `judge_qc.py`, `instruction_qc.py`, `exe_copy.py`). Record `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` (expected `71a653b2...`) and `git log --oneline -- Input_Bundle_QC | head -30`.
- OLD COPY (18-19 Oct, for the change list only): `/Users/mac/Desktop/Terminal Bench/QC assigned/Input_Bundle_QC/`.
- Our current understanding (to check against the kit, not to trust): `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md`, `QC_RULINGS.md`, `LEVER_RULES_v1.md`, `qc_authoring_checklist_9b8229f6.md` (same folder), and `prompts/templates/_COMMON_RULES_v2.md` "Never" 6 and 8.
- Bundles to test scripts on (copy first): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/<slug>/` (use dispatch-plan-reoptimization and emberforge-vault-settlement).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/qc_reverse/A/`

## Phase 1: inventory every check
For EVERY check id in the kit (IN, DS, TS, JD, AL, CL, every Final_checklist item, and every rule a script enforces even without an id; about 150 known ids plus script-only rules), one row:
- `id`, `title`, `kit_file:line` (where defined), every other `file:line` that cites it.
- `owner`: `script` (name the function and line), `judgement` (a reviewer reads and decides), or `both`.
- `pass_condition`: the exact kit words that decide pass, quoted.
- `severity_rule`: what makes it fail vs minor vs warn, quoted. Also find and quote how the kit turns findings into the overall verdict (how many fails/minors make a FAIL).
- `reads`: the bundle files and artefacts it looks at (instruction.md, environment/data, tests/test_output.py, tests/judge.toml, solution/, TRUTH.md, oracle run, nop, stub, owner).
- `discretion`: any "use judgement", "if in doubt", "consider", "may" wording, quoted. These are where reviewers vary.
- `explicitly_not_required`: kit sentences that say what the check does NOT demand (like 01:45, 01:46), quoted.
- `local_precheck`: if it is script-owned or mechanical, the exact command or test we could run before sending a bundle to QC; else `none`.
Write `OUT/CHECK_INVENTORY.md` (table grouped by kit file) and `OUT/checks.json` (list of objects with exactly those keys; `id` is the join key the master uses).

## Phase 2: script truth
Run each script on the two bundle copies. For each script rule: what it actually computes (quote code lines), where the code is stricter or looser than the `.md` text, and any rule that exists only in code. Write `OUT/SCRIPT_RULES.md`.

## Phase 3: conflicts
List every pair or group of checks that pull in opposite directions, so that fixing one can trip the other. Examples to confirm or reject: IN-15/IN-16/DS-21 (state every graded rule, one reading) vs any lever built on unstated or blurred information; AL-27 (every stated rule triggered) vs TS-23 (check count); TS-26/JD-14 (pay once) vs whole-document cascades; JD-7 (oracle meets every criterion) vs judge criteria that track a trap (JD-8); TS-16 (negatives not honest-trippable) vs anti-hardcoding negatives; DS-4 (answer not recoverable from data) vs shipped boundary rows. For each: both kit quotes, the mechanism, and the narrow zone (if any) where both pass. Write `OUT/CONFLICTS.md` and add `conflicts_with: [ids]` to checks.json.

## Phase 4: lever compatibility
For each lever L1-L7 in LEVER_RULES_v1.md, plus three classes we have used: (a) withheld information, (b) blurred or ambiguous wording, (c) a trap that lives only in the computation or the hidden data. Give: the checks it pressures (ids), and a verdict LEGAL / ILLEGAL / CONDITIONAL with the kit lines that decide it and, for CONDITIONAL, the exact conditions. Write `OUT/LEVER_COMPAT.md`.

## Phase 5: our docs vs the kit
- Every QC_FIX_PLAYBOOK row and QC_RULINGS row: does the kit text still support it? Mark OK / WRONG / STALE with quotes.
- Diff the old copy against the live kit: every rule added, removed or reworded, one line each.
- Kit template defects that would fail any bundle built from them (known: `04_Judge_QC.md` R6 wording that is not tied to `/tests`, `/solution`, `/logs/verifier`). Write `OUT/DOC_CHECK.md`.

## Deliverables
`OUT/SUMMARY.md` (at most 60 lines): counts (checks by owner and kit file), the top 10 conflicts, the lever verdict table, the precheck commands we can automate, and "Lessons for the master". Also `OUT/result.json`: `{board:"5087cd2", kit_head, checks_total, by_owner:{script,judgement,both}, conflicts, lever_verdicts:{L1..L7,withheld,blurred,computation}, playbook_rows_wrong:[...], status:"done"}`.
End your final reply with: `Next session: board 5087cd2 done. Paste back: done : 5087cd2`.
