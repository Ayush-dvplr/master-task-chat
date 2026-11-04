STEP 0 REPORT (rollout step 0, tag mc2-v2.0). Helper W1-043, 4 Nov 2026. Nothing committed, pushed, tagged or checked out.

Worktree W = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2 (branch mc2-v2, orphan, no commit yet).
Test folder T = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2_test (ROOT, mc2_backup, old_sim, logs, tmp).
Full command outputs: upgrade_plan/tmp/W1-043/logs/ (copied from T/logs).

1. WHAT CHANGED IN THE WORKTREE

1. master_chat_tasks/tools/upgrade.py (rewritten for the ROOT layout; sha256 14bbf32a)
   a. The drafts layout is gone. ROOT is --root or two folders above the file; tools in ROOT/master_chat_tasks/tools; settings in ROOT/master_chat_tasks/settings.json.
   b. Missing settings.json: WARN "settings missing ... defaults used" before v2.1, FAIL from v2.1. Defaults: system.id mc2, card hard 8 KB, backup folder ROOT/../mc2_backup.
   c. Stage aware: a part that a later step delivers is a WARN while the running version is older than that step and a FAIL after it (ARRIVES: settings and rules v2.1, state card v2.2, template_check v2.3, kit_watch v2.5, dockslot v2.7).
   d. Until template_check.py arrives, a built in SYSID scan reads the newest template of each family and counts lines that type the old root or a /tmp path without mc2. WARN before v2.3, FAIL after.
   e. New check SYSTEM_VERSION (system_id matches settings, version is vN.N).
   f. Tags are <system id>-<version> (mc2-v2.0); preflight --to defaults to the next step tag; recheck --to defaults to the running tag and FAILs when SYSTEM_VERSION is not the target; "mark stable" prints git branch -f mc2-stable <tag>.
   g. preflight --old OLD_ROOT (read only): a live board row copied from the old board and still live there is a WARN (old system session, finishes there); a copied row that ended in the old board is a FAIL with the carry_over.py command; a slug live in both systems is a WARN (Q154). Without --old every live row is a FAIL.
   h. Tool self tests: every Python file compiles, --help of the present tools, and the self contained tests test_carry_over.py and test_dockfree.py.
   i. DATA_RECORDS now matches .gitignore: adds master_chat_tasks/*.jsonl (glob), prompts/issued, prompts/drafts, auto/plans, knowledge/archive_md, knowledge/history; knowledge/intake removed (it is a system folder in the worktree and not in .gitignore). The backup check also FAILs on record files that are new since the backup. The work mirror skips master_chat_work/_upgrade.
   j. Never runs git (subprocess only runs python3 and bash precheck.sh); standard library only.
2. master_chat_tasks/tools/carry_over.py (new; sha256 57029ccf). Usage and rules in its docstring:
   a. --old OLD_ROOT (opened read only, pending.db with mode=ro), --new NEW_ROOT, --slug SLUG (repeatable) or --all-finished, --apply (default dry run).
   b. Reads the old registry/tasks.json entry, board.json rows, registry/scores.jsonl lines and pending.db items (items a board row of the slug points to by pending_id, and items whose text names the slug) plus their history rows.
   c. Merge: never deletes; objects merged key by key, lists joined, a differing value replaced only when the old timestamp is later (task: entry updated_ist, else pipeline.updated, else the file updated_ist; board: updated, else issued; pending: updated_ist). A registry entry the new system never touched (no board row of its own and no newer own timestamp) takes the old values. Scores: lines the new file lacks are appended. A pending id the new system already uses for another item is carried as <id>-old and the board row's pending_id follows it.
   d. Marks: "carried_from": "old system" and "carried_ist" on registry entries, board rows and score lines; pending items get a history row and a note suffix "[carried from old system <date>]".
   e. Refuses (exit 1, writes nothing) when the slug has a running or issued row in the NEW board that the old board does not have, or a running or issued row in the OLD board.
   f. On --apply: one line per slug in NEW master_chat_tasks/carry_over.jsonl (ignored by *.jsonl), JSON written atomically, BOARD.md rewritten through the new tools/board.py md. A second run carries nothing and logs nothing.
3. master_chat_tasks/tools/tests/test_carry_over.py (new; sha256 ddeb65b4): 6 tests on temporary OLD and NEW copies: dry run writes nothing; apply merges, marks, logs once and leaves OLD byte identical; newer new value kept; refusal when still running in old; refusal when live in new; --all-finished skips the running slug.
4. Removed the ignored master_chat_tasks/tools/__pycache__ left from the W1-039 copy. No other file changed.

2. COMMANDS RUN AND RESULTS (simulated ROOT = T/ROOT, backup = T/mc2_backup, TMPDIR = T/tmp)

Setup: T/ROOT made from the worktree files without .git (tar, since rsync is not installed in this container), then DATA copied from /home/user/master-task-chat/master_chat_tasks: registry/, board.json, BOARD.md, pending.db, state.json, GOALS.md, open_questions.json, the 4 *.jsonl files, prompts/issued, auto/runs, auto/plans, knowledge/fingerprints, knowledge/archive_md. 772 DATA files, 12 MB.

1. upgrade.py status: exit 0. mc2, v2.0 (tag mc2-v2.0, next mc2-v2.1); settings WARN missing, defaults used; backup folder T/mc2_backup; 772 record files; parts not yet delivered listed with their step; board live 3 (dabfeb4 hangar-check-replan, ffd3a8e sensor-network-lsq-correlated-adjustment, 420bf9a flood-repair-portfolio).
2. upgrade.py backup: exit 0. T/mc2_backup/20261104: 772 record files with MANIFEST.json; work mirror 1 file (master_chat_work/README.md).
3. upgrade.py preflight (no --old): exit 1, BLOCKED. PASS SYSTEM_VERSION, tool self tests (18 files compile, carry_over 6 tests OK, dockfree 5 tests OK), backup. WARN settings missing, rules not delivered, template SYSID scan (17 current templates type the old root or /tmp: for example P11_full_qc_v3 old root x16, P2_build_v5 x12), kit_watch and state card not delivered. FAIL no session running: the 3 running rows of the 2 Nov board copy.
4. upgrade.py preflight --old /home/user/master-task-chat: exit 0, READY. The 3 rows become WARN "old system session, finishes there"; the git switch commands are printed.
5. tools/registry_check.py: exit 0, 37 tasks, 0 fields with type drift. Again after the carry in 7: exit 0, 0 drift.
6. carry_over.py dry run, finished task cold-chain-backbone-quote: exit 0, "nothing to carry" (expected: the old records and the copy are the same snapshot). Running task flood-repair-portfolio: exit 1, "has not finished in the OLD system (420bf9a running)". --all-finished: 56 slugs checked, 0 to carry, 0 refused.
7. Realistic carry on a simulated old copy (T/old_sim: 420bf9a set done on 4 Nov 12:00, pending S443 done, one score line, registry status and pipeline.updated changed): dry run lists task fields 2, board row 1, score 1, pending item 1, history 2; --apply writes them with the marks, rewrites BOARD.md, one log line; a second --apply says "nothing to carry".
8. preflight --old T/old_sim after the carry: exit 1, BLOCKED by the backup check (5 record files changed and 1 new since the backup). That is correct: run backup again after carry_over. After backup: exit 0, READY (773 record files match; 2 old sessions WARN).
9. upgrade.py rollback --from mc2-v2.1 --to mc2-v2.0: prints checkout, recheck and the rsync dry run from T/mc2_backup/20261104/records/.
10. upgrade.py recheck --from mc2-v2.0: exit 3 WAITING (known bundle not given); state card, cold test and dockslot are WARN "not delivered yet".
11. Self tests: pytest (/root/.local/bin/pytest; python3 -m pytest is not importable here) on test_carry_over.py and test_dockfree.py: 11 passed. auto/tests/test_auto.py: 75 passed.
12. Not run: tools/tests/test_upgrade_tools.py, test_e3_e6_tools.py, test_issue_lint.py. They create folders with dir="/tmp" (outside the folders this helper may write) and need ROOT/Terminal_2.0_Harbor_Harness. They are collected fine (48 tests). Run them on the Mac once the harness clone is in ROOT.

3. GITIGNORE CHECK (step 4)

git check-ignore --stdin -v -n in the worktree over all 773 DATA files of the simulated ROOT (772 copied plus carry_over.jsonl): every one is ignored, 0 not ignored. Rules hit: prompts/issued/ 606, auto/runs/ 119, fingerprints/ 14, auto/plans/ 11, registry/ 7, *.jsonl 5, archive_md/ 5, and board.json, BOARD.md, pending.db, state.json, GOALS.md, open_questions.json 1 each. The 109 worktree system files are all untracked and none is ignored.

4. PROBLEMS FOUND

1. Old templates type the old root. 17 current templates type "/Users/mac/Desktop/Terminal Bench" or a /tmp path without mc2. A prompt issued from ROOT between step 0 and step 3 points sessions at the old folder, which works against "the new records are the truth from day 1". Proposal: issue no new task from ROOT until mc2-v2.3, or run steps 0 to 3 close together. tools/precheck.sh line 9 also types the old kit path (UPGRADE.md open point 3).
2. Copied live rows. The board copy holds 3 running rows of the old system; preflight without --old blocks on them. Step 1 settings should carry upgrade.old_root = the old folder so preflight tells them apart without the flag.
3. Pending ids are allocated in both systems from the same counter (next S444 in both). carry_over.py carries a clashing old item as <id>-old; worth one line in BUILD_RULES.md.
4. knowledge/intake: UPGRADE.md calls it DATA, but the worktree holds it as system files and .gitignore does not list it. I took it out of DATA_RECORDS to match the worktree. Needs a decision.
5. The step 0 copy list leaves out auto/LATEST, auto/SCHEDULED.log and .out, prompts/drafts, auto/TEST_REPORT.md and master_chat_work (2.2 GB). I suggest leaving LATEST and SCHEDULED in the old folder (they describe old auto runs); master_chat_work stays in the old folder and board results keep pointing there by absolute path.
6. carry_over.py writes tasks.json, board.json, scores.jsonl and pending.db directly; only BOARD.md goes through a tool (board.py md), since the old tools have no merge command. The plan text says "writes through the new tools".
7. Registry entries have no own updated timestamp; carry_over.py uses pipeline.updated or the file timestamp and the "untouched copy" rule. A field the old system changed without touching pipeline.updated, on a slug the new system also edited, is kept as the new value and reported as KEEP newer.
8. Order: carry_over.py changes records, so the day's backup must be taken again after it, or preflight blocks (shown in 8).
9. Names: PLAN_FINAL.md C2 says branches stable and v2; this step uses mc2-stable and mc2-v2 with tags mc2-v2.N. tmp/W1-039/UPGRADE.md still says tags v2.0 and "git branch -f stable".
10. ROOT has no harness clone yet (PLAN_FINAL.md C1); kit_watch, precheck and the harness tests need it.
11. Recheck at step 0 exits 3 because the known bundle is not set (settings upgrade.known_bundle, step 1).

5. GIT COMMANDS FOR LATER (Ayush runs every one; nothing here was run)

A. Release mc2-v2.0 (in the worktree, after Ayush reads the diff):
   cd "<worktree>"
   git status --short                         (only the 109 system files; no DATA)
   git add -A
   git commit -m "mc2-v2.0: rollout step 0 (old system files, SYSTEM_VERSION, .gitignore, upgrade.py, carry_over.py)"
   git branch mc2-stable mc2-v2
   git tag mc2-v2.0 mc2-v2
   git push origin mc2-v2 mc2-stable
   git push origin mc2-v2.0

B. On the Mac. ROOT and the backup names are proposals until Ayush names them.
   OLD="/Users/mac/Desktop/Terminal Bench"
   ROOT="/Users/mac/Desktop/mc2"
   git clone --branch mc2-stable --single-branch https://github.com/Ayush-dvplr/master-task-chat.git "$ROOT"
   cd "$ROOT" && cat SYSTEM_VERSION && git status --porcelain     (version = v2.0; status prints nothing)

C. Data copy, once (the old folder is only read):
   MO="$OLD/master_chat_tasks"; MN="$ROOT/master_chat_tasks"
   cp -Rp "$MO/registry" "$MN/registry"
   for f in board.json BOARD.md state.json GOALS.md open_questions.json; do cp -p "$MO/$f" "$MN/$f"; done
   sqlite3 "$MO/pending.db" ".backup '$MN/pending.db'"
   cp -p "$MO"/*.jsonl "$MN/"
   cp -Rp "$MO/prompts/issued" "$MN/prompts/issued"
   cp -Rp "$MO/auto/runs" "$MN/auto/runs"
   cp -Rp "$MO/auto/plans" "$MN/auto/plans"
   cp -Rp "$MO/knowledge/fingerprints" "$MN/knowledge/fingerprints"
   cp -Rp "$MO/knowledge/archive_md" "$MN/knowledge/archive_md"
   cd "$ROOT" && git status --porcelain        (must print nothing: every DATA file is ignored)

D. Checks after the copy:
   python3 master_chat_tasks/tools/upgrade.py status
   python3 master_chat_tasks/tools/upgrade.py backup                (writes /Users/mac/Desktop/mc2_backup/YYYYMMDD)
   python3 master_chat_tasks/tools/upgrade.py preflight --old "$OLD"
   python3 master_chat_tasks/tools/registry_check.py
   python3 master_chat_tasks/tools/tests/test_carry_over.py

E. Each time a task finishes in the old system:
   python3 master_chat_tasks/tools/carry_over.py --old "$OLD" --new "$ROOT" --slug <slug>            (dry run, read it)
   python3 master_chat_tasks/tools/carry_over.py --old "$OLD" --new "$ROOT" --slug <slug> --apply
   python3 master_chat_tasks/tools/upgrade.py backup

F. Rollback of step 0: delete ROOT (the old folder never changed).
