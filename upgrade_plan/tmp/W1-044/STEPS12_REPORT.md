STEPS 1 AND 2 REPORT (rollout steps 1 and 2, tags mc2-v2.1 and mc2-v2.2). Helper W1-044, 4 Nov 2026 14:45 IST.

Worktree W = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2 (branch mc2-v2).
Test folder T = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2_test (simulated ROOT with the step 0 data copy).
Nothing was pushed, no branch was checked out, nothing in /home/user/master-task-chat was changed except this folder. Full outputs: upgrade_plan/tmp/W1-044/logs/.

1. COMMITS AND TAGS (in W only)

mc2-v2.1  6fc6ae5f6ebb73a0b802c85089b4d85b34ee2d25  "mc2-v2.1: rollout step 1 (settings, rules, fix map, history move)"
mc2-v2.2  37f2a6d732afcdfb90cd0cc7a9d4bffff3546808  "mc2-v2.2: rollout step 2 (state card, read order, prompts, DCP and opencode files)"
Both on top of mc2-v2.0 (8d1c963e). Author Claude <noreply@anthropic.com>, both attribution lines at the end of each message. git status is clean after the second commit.

2. STEP 1 FILES (mc2-v2.1, 17 files, 426 insertions, 31 deletions)

1. master_chat_tasks/settings.json (new). The drafts/P1 settings with the _note no longer saying DRAFT, plus:
   a. paths: root null (never stored; tools compute ROOT as the folder holding SYSTEM_VERSION), records, work, runs, harness, kit "Terminal_2.0_Harbor_Harness/Input_Bundle_QC", all relative to ROOT, with a _note.
   b. upgrade: backup_dir "../mc2_backup" (relative to ROOT), old_root "/Users/mac/Desktop/Terminal Bench", known_bundle "" (Ayush sets it), with a _note.
   c. system block exactly as drafted. Valid JSON (parsed by python json and by upgrade.py).
2. master_chat_tasks/RULES_IN_FORCE.md and master_chat_tasks/knowledge/BUILD_RULES.md: byte copies of the drafts.
3. master_chat_tasks/knowledge/FIX_MAP.md and knowledge/REGRESSION_CHECK.md: byte copies from tmp/W1-030.
4. History move (git mv, so history is kept): LEVER_RULES_v1.md, LEVER_RULES_v2.md, LEVER_RULES_v3.6_snapshot.md, KNOWLEDGE_v3.6_snapshot.md, QC_FIX_PLAYBOOK.md (v1), QC_FIX_PLAYBOOK_v2.md, PLAN_v1.md into master_chat_tasks/knowledge/history/. New history/README.md: "history only, never read by the master". .gitignore: the line master_chat_tasks/knowledge/history/ removed; git check-ignore confirms none of the history files is ignored.
5. knowledge/INDEX.md: the six existing rows point at history/<name> with "moved to history/ in mc2-v2.1"; a row for history/QC_FIX_PLAYBOOK.md (v1 had no row) and one for history/ itself; LEVER_RULES_v3 row says history/LEVER_RULES_v3.6_snapshot.md; new rows for ../RULES_IN_FORCE.md, ../settings.json, BUILD_RULES.md, FIX_MAP.md, REGRESSION_CHECK.md; intake/ row marked "system folder of how to docs, kept in git; decided mc2-v2.1".
6. master_chat_tasks/tools/upgrade.py:
   a. ROOT is found as the nearest folder above the file holding SYSTEM_VERSION (fallback two folders up); --root still wins.
   b. Settings required from v2.1: missing or invalid is a FAIL (checked: moving settings.json away gives FAIL "settings missing"). New settings checks: paths.root must be null, every other paths value must be relative, WARN when paths.kit, upgrade.old_root or upgrade.known_bundle is empty.
   c. upgrade.old_root is read from settings (--old still overrides) for the idle check and for the SYSID scan text. If the old board is not reachable the WARN says so and live rows stay FAIL.
   d. backup_dir, known_bundle and paths.kit resolve against ROOT, not the current folder (before, "../mc2_backup" would have resolved against the shell's folder).
   e. BUILD_RULES.md is looked for in knowledge/. knowledge/history removed from DATA_RECORDS; a comment says history and intake are system folders.
   f. status prints the kit and old root and whether they are reachable.
7. SYSTEM_VERSION: version = v2.1.

3. STEP 2 FILES (mc2-v2.2, 13 files)

1. master_chat_tasks/tools/state_card.py (new) from drafts/P1/state_card.py v2. Changes: docstring (no DRAFT), settings.json and RULES_IN_FORCE.md read from master_chat_tasks/ (the --root default, so the draft paths already matched the new places), header shows "mc2 v2.2" from ROOT/SYSTEM_VERSION, QC KIT line falls back to ROOT/<paths.kit> when the snapshot's source path is not there, a live row that is also live on the old board (settings upgrade.old_root, read only) gets "OLD SYSTEM: finishes there; then carry_over.py --slug <slug>", time from datetime.now(IST) instead of the deprecated utcnow. Card written to master_chat_tasks/STATE_CARD.md, already in .gitignore with STATE_CARD.prev.json.
2. master_chat_tasks/tools/card_hook.py (new): refresh() runs state_card.py in a child process; a missing script, non zero exit, timeout or any exception prints one WARNING line to stderr and returns; nothing goes to stdout (issue.py parses pending.py's stdout for the new id). defer() lets issue.py and intake.py stop their child tools from rebuilding, then they rebuild once at the end. MC2_CARD_OFF=1 switches it off.
3. Hooks: issue.py (after the prompt, board row and pending item are written), intake.py (only with --apply), status.py (set), pending.py (add, set, done, drop; not list, md, show). Each tool loads card_hook.py by file path inside try/except, so even a missing card_hook.py only prints a warning.
4. master_chat_tasks/tools/tests/test_state_card.py (new, 10 tests): card builds under the limit with the protect block, rules, header version and the OLD SYSTEM flag on the right row only; hard limit gives LEFT OUT with the rules still first; missing rules named; status.py set and pending.py add rebuild the card; pending.py add stdout stays one line; a read command does not build; missing state_card.py, a state_card.py that exits 5 and a missing card_hook.py never break the write; a deferred child skips.
5. master_chat_tasks/README.md: the old "Read order after any compaction" section (lines 5 to 15, including the line 14 git check) replaced by MASTER_RECOVERY.md part A; new section "Compact and restore prompts" with parts E and B word for word (title lines, part E intro and prompt, part B prompt); the pipeline paragraph (old gates 100/100/70, count cap 35, WRONG only wording) replaced by one line pointing at STATE_CARD.md, RULES_IN_FORCE.md and knowledge/BUILD_RULES.md; a tools table row for state_card.py. Part A was adapted in three places, see problem 2.
6. ROOT/.opencode/dcp.jsonc = drafts/P1/tasks.dcp.jsonc ("enabled": false) and ROOT/master_chat_tasks/.opencode/dcp.jsonc = drafts/P1/master.dcp.jsonc (manualMode). Only the leading // comment lines changed (no longer "DRAFT, not applied"; layering UNVERIFIED until the Mac check); the JSON bodies are byte identical to the drafts (diff checked).
7. ROOT/opencode.jsonc: only "$schema". Comments say UNVERIFIED (Q78), that it sets no model, plugin, provider, permission, agent or compaction key so ROOT runs on the global config as the old folder does, that runner and model choices live in settings.json (planned master model, plugin set and blind runner listed as comments only), and that the DCP layering is UNVERIFIED until the G1 check, rollback git checkout mc2-v2.1.
8. upgrade.py: release text v2.2; new check "opencode and DCP files" (the three files exist, parse as JSONC, the task file has enabled and the master file manualMode; WARN before v2.2, FAIL after) in preflight and recheck; the card check builds in a ROOT shaped copy (SYSTEM_VERSION beside master_chat_tasks); test_state_card.py added to the self tests.
9. SYSTEM_VERSION: version = v2.2.

4. CHECKS (TMPDIR in T; T/ROOT refreshed from W before each step by logs/refresh_root.sh: removes the files of the previous tag, copies every tracked and new file, leaves DATA alone)

1. Step 1, upgrade.py status: v2.1, settings present, rules present, kit and old root "not reachable here", 773 record files.
2. Step 1, preflight (plain, settings as committed): exit 1 BLOCKED, only on "no session running": the 2 running rows copied from the old board (dabfeb4, ffd3a8e) because /Users/mac/Desktop/Terminal Bench does not exist in this container. PASS SYSTEM_VERSION, rules files, tool self tests (18 files, carry_over 6 OK, dockfree 5 OK), backup. WARN settings (known_bundle empty only), template SYSID scan (17 templates, step 3), kit_watch and card not delivered yet.
3. Step 1, preflight with settings upgrade.old_root pointed at /home/user/master-task-chat in the test copy only (stand in for the Mac's old folder, restored afterwards and compared byte equal with W): exit 0 READY, both rows WARN "old system session, finishes there". This is what plain preflight should print on the Mac.
4. Step 2, card on T/ROOT data: first build 7652 B (7.5 KB, 8 news lines, open items and uniqueness LEFT OUT to stay under 8 KB); second build 7570 B (7.4 KB, news 0, every section in, 57 lines). Both under the 8 KB hard limit, over the 6 KB target. Cards: logs/STATE_CARD_mc2_test.md and logs/STATE_CARD_mc2_test_second.md.
5. Step 2, self tests: test_state_card.py 10 OK; test_carry_over.py 6 OK; test_dockfree.py 5 OK. test_issue_lint.py 7 passed (copy with dir="/tmp" pointed at T/tmp; exercises issue.py with the hook). test_upgrade_tools.py A1Issue and A3Status classes all pass, 5 A2Intake tests fail on the missing ROOT/Terminal_2.0_Harbor_Harness (jobs/, Tasks_INPUT/), A4Repackage not run (the tool writes /tmp/repack-*, outside my folders). test_e3_e6_tools.py 4 passed, 3 fail on the missing harness scripts. The temporary test copies were deleted.
6. Step 2, upgrade.py backup then preflight (plain): exit 1, the same single FAIL as in 2 (old root not reachable here). PASS SYSTEM_VERSION, rules, state card builds (7.5 KB, hard 8 KB), opencode and DCP files, tool self tests (20 files compile, --help state_card and carry_over, 3 test files OK), backup (775 record files, now with the card and its snapshot).
7. Step 2, preflight --old /home/user/master-task-chat and plain preflight with the simulated settings old_root: both exit 0 READY, git commands for mc2-v2.3 printed. The card built with the simulated old_root marks both rows OLD SYSTEM.
8. Step 2, recheck --from mc2-v2.1: exit 3 WAITING on the cold recovery test (prompt printed) and the known bundle; PASS version, card, opencode files.
9. Not possible here: the cold recovery test and the G1 and G3 checks (need opencode on the Mac).

5. PROBLEMS AND OPEN POINTS

1. Plain preflight on this container cannot be READY, since upgrade.old_root names a Mac folder; on the Mac it reads the old board and turns the copied rows into WARN (shown with the simulated path). If Ayush runs ROOT without the old folder reachable, preflight blocks until he gives --old or those rows end and carry_over.py runs.
2. MASTER_RECOVERY.md part A was not copied word for word (the task asked word for word only for E and B). Three changes: "knowledge/BUILD_RULES.md" (its new place); point 3d "knowledge/FIX_MAP.md and knowledge/QC_FIX_PLAYBOOK_v3.md (current version only), then knowledge/REGRESSION_CHECK.md", because knowledge/QC_FIX_PLAYBOOK.md is now the v1 history file; point 4 names knowledge/history/. Point 3c still names knowledge/PATTERNS.md, which does not exist in ROOT (it is in upgrade_plan/knowledge/); it needs copying or a different pointer.
3. FOLD_PLAN.md part 1 also says to rename QC_FIX_PLAYBOOK_v3.md to QC_FIX_PLAYBOOK.md and LEVER_RULES_v3.md to LEVER_RULES.md, and to move prompts/templates/_COMMON_RULES_v5_v3.6_snapshot.md and master_chat_work/_dev_research/pipeline_v4/PLAN_v3.6_snapshot.md. Not done (outside the list I was given; the template snapshot belongs with P10 in step 3, the PLAN snapshot is in master_chat_work, which is DATA). Many old templates and CHANGELOG lines name the moved files by old path; the current templates only mention them in history notes, so nothing current breaks, but P2_build_v2 to v4 and older _COMMON_RULES now point at missing paths.
4. The card is 7.4 to 7.5 KB on this data: under 8 KB but over the 6 KB target; on a first build (no snapshot) the news section pushed open items and uniqueness out. The rules block alone is 3.9 KB.
5. Part B says "Read master_chat_tasks/STATE_CARD.md" while the master starts from ROOT/master_chat_tasks (Q108), where the path is STATE_CARD.md. Kept word for word; the master will most likely find it, but the cold test should watch for it.
6. board.py is not hooked (only the four named tools). A board.py set run by hand (for example issued to running) leaves the card stale until the next hooked write or a manual state_card.py; the read order says to regenerate when older than 1 hour.
7. RULES_IN_FORCE.md and BUILD_RULES.md copied as drafted; BUILD_RULES.md LIMITS still says "4x" and "Oracle runs 3" and "at most 6" what if figures, with the PL ANSWERS line at the end replacing them. Layered by the draft's own design, but the same file states two values.
8. README keeps other old lines that later steps own: the issue.py row "refuses past caps" (step 3), /tmp/opencode-logs and /tmp/<slug> paths (SYSID, step 3), "max 2 Docker heavy jobs" was in the replaced paragraph and is gone.
9. Whether opencode writes into ROOT/.opencode (for example plugin caches) is not known; if it does, those files show as untracked in git status until .gitignore lists them. Check on the Mac with git status --porcelain after the first session.
10. The DCP layering and the protectTags behaviour on tool output stay UNVERIFIED (G1, MASTER_RECOVERY part C, Q121).
11. Tests that hardcode dir="/tmp" (test_upgrade_tools.py, test_e3_e6_tools.py, test_issue_lint.py) and the harness tests need the Mac with the harness clone in ROOT.

6. COMMANDS FOR AYUSH (nothing here was run; upgrade.py never runs git)

A. Publish (from W, after reading the diff git diff mc2-v2.0 mc2-v2.2):
   git push origin mc2-v2 mc2-v2.1 mc2-v2.2
B. On the Mac, per step (ROOT at mc2-v2.0 or mc2-v2.1):
   python3 master_chat_tasks/tools/upgrade.py backup
   python3 master_chat_tasks/tools/upgrade.py preflight          (reads upgrade.old_root from settings now)
   then the commands it prints, then upgrade.py recheck --from <old tag> --to <new tag>.
C. Step 2 by hand on the Mac: start the master from ROOT/master_chat_tasks (title mc2-master), /dcp must show manual; a task session at ROOT must show no DCP notice; paste part B for the cold test; git status --porcelain must print nothing. If the nearest DCP file does not win: git checkout mc2-v2.1.
D. Set upgrade.known_bundle in settings.json to a QC passed bundle (a commit in mc2-v2, Ayush's choice) so recheck can run the dry precheck.
