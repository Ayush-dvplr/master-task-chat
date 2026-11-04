E2E REPORT (helper W1-046, end to end verifier, 4 Nov 2026 about 16:00 IST). Report only: nothing delivered was edited, nothing was committed, pushed, tagged or checked out in /home/user/master-task-chat (git status there is clean).

Scratch folder E = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/e2e
Mapping: ~/Desktop/mc2_upgrade = E/mc2_upgrade, /Users/mac/Desktop/mc2_root = E/mc2_root, /Users/mac/Desktop/mc2_backup = E/mc2_backup, "/Users/mac/Desktop/Terminal Bench" = E/old (master_chat_tasks copied in full, master_chat_work only README.md because it is 2.2 GB, Terminal_2.0_Harbor_Harness/Input_Bundle_QC from git archive origin/main, kit 487b4697).
Python: python3 was a shim to /usr/bin/python3.12 (3.12.3) for every run; sqlite3 CLI is not installed here, so a stand in did the ".backup" with Python's sqlite3 backup API. Shell: bash (zsh is not installed; zsh behaviour was emulated where it matters, see problem 1).
Logs (E paths shortened to E): upgrade_plan/tmp/W1-046/logs/. runprinted.sh there is how printed commands were pasted literally (one bash, each exit code recorded).

PROBLEMS

1. BREAKS. Where: the git commands preflight prints (upgrade.py git_switch_commands, every step). What happens: three of the printed lines carry trailing "# ..." comments. In zsh, which is the macOS default shell, "#" is NOT a comment at the interactive prompt unless setopt interactivecomments is on (Oh My Zsh turns it on, a plain zsh does not). Then the words become arguments:
   git status --porcelain '#' must print nothing: no uncommitted system edits   -> exit 0 and prints NOTHING even on a dirty tree (the words act as pathspecs). Shown on a clone with SYSTEM_VERSION edited: plain status printed " M SYSTEM_VERSION", the zsh form printed nothing. So the safety check silently passes.
   git fetch origin --tags '#' brings the new tag from GitHub   -> "fatal: couldn't find remote ref #", exit 128.
   git tag before-x '#' marks the version you run now (mc2-v2.0), local only   -> "fatal: too many arguments", exit 128 (in real zsh the "(mc2-v2.0)," word may even be a glob error first).
   The rollback lines "# Only if the failed version ..." give "zsh: command not found: #" (harmless but alarming).
   Suggested fix: print comments on their own line above each command (or drop them), or tell Ayush once to run setopt interactivecomments; never put a comment after git status.

2. BREAKS. Where: upgrade.py check_precheck (line 676 at mc2-v2.5) with the mc2-v2.3 precheck.sh. What happens: the regex ^KIT="([^"]+)" now matches the new line 11 of precheck.sh (KIT="${PRECHECK_KIT:-$(python3 -c '...)}") and captures a shell expression, which is "not present", so the dry precheck is a FAIL and recheck prints the rollback commands. Any known bundle triggers it from mc2-v2.3 on.
   Command: python3 master_chat_tasks/tools/upgrade.py recheck --from mc2-v2.2 --to mc2-v2.3 --known-bundle E/kb/anubis-stage-2/0024bce9-2e9b-5b41-bac1-393f51254d9b
   Output: FAIL  dry precheck on a known bundle / precheck.sh reads the kit at a fixed path ${PRECHECK_KIT:-$(python3 -c 'import json,os,sys; m=sys.argv[1]; k=(json.load(open(os.path.join(m,, not present / VERDICT: RECHECK FAILED. Roll back with these commands
   Suggested fix: resolve the kit the way precheck.sh does (settings paths.kit relative to ROOT, PRECHECK_KIT override) or only apply the fixed path test when the captured value has no "$"; add a self test that runs check_precheck against the shipped precheck.sh.

3. BREAKS. Where: no delivered instruction puts the harness into ROOT (delivery/README.md, STEP0_REPORT.md B to F, NEXT.md). STEP0_REPORT problem 10 and STEPS345 problem 9 only mention it. What happens in ROOT without ROOT/Terminal_2.0_Harbor_Harness:
   a. precheck.sh (from mc2-v2.3 it reads settings paths.kit) runs all four kit scripts against a missing folder: every script exit 2, "PRECHECK: findings", with no message that the kit is missing (logs/s3_precheck_nokit.txt). At mc2-v2.2 it still used the old kit path and worked on the Mac, so mc2-v2.3 is a regression for every build and fix session.
   b. kit_watch.py check and card: "kit_watch: kit folder not found: E/mc2_root/Terminal_2.0_Harbor_Harness/Input_Bundle_QC", exit 2. kit_watch.py save (NEXT.md item 2) would fail the same way unless --kit is given.
   c. Issued prompts (P11 sample and my real issue) tell the session "QC kit (live, read-only): [[ROOT]]/Terminal_2.0_Harbor_Harness/Input_Bundle_QC" and git -C "[[ROOT]]/Terminal_2.0_Harbor_Harness" rev-parse HEAD.
   d. intake.py, loss.py, repackage_one.py and auto.py default to ROOT/Terminal_2.0_Harbor_Harness from mc2-v2.0 on.
   e. 11 self tests fail on it (problem 13).
   Suggested fix: add one explicit step before mc2-v2.3 (best at step 0): how the harness gets into ROOT (clone or move, and which commit), or set paths.kit and paths.harness to the old folder until STAGE B, and make precheck.sh stop with a clear message when the kit folder is missing.

4. BREAKS. Where: delivery/README.md step 4 sends Ayush to STEP0_REPORT.md "for the data copy, backup, preflight and carry over", but that report was written for a different install. Literal reading:
   a. Section A is a commit, branch, tag and push in the worktree (already done; would fail or duplicate).
   b. Section B sets ROOT="/Users/mac/Desktop/mc2" and clones from GitHub https://github.com/Ayush-dvplr/master-task-chat.git, while README says /Users/mac/Desktop/mc2_root from the bundle (RESUME says GitHub refused the branches). If Ayush keeps B's ROOT value and runs section C, every cp fails with "No such file or directory" because $ROOT/master_chat_tasks does not exist.
   c. Section D uses preflight --old "$OLD"; README step 2 of the upgrade path says plain preflight (problem 5).
   Suggested fix: put the data copy commands in delivery/README.md itself with ROOT="/Users/mac/Desktop/mc2_root" and OLD set once, and mark STEP0_REPORT A and B as history.

5. BREAKS (at mc2-v2.0 only, with a workaround in another file). Where: delivery/README.md upgrade path step 2 "python3 master_chat_tasks/tools/upgrade.py preflight". At mc2-v2.0 there is no settings.json, so old_root is unknown and the three copied live rows are a FAIL:
   Command: python3 master_chat_tasks/tools/upgrade.py preflight
   Output: FAIL  no session running / 3 busy: board dabfeb4 running hangar-check-replan ... give --old to tell old system sessions apart / VERDICT: BLOCKED ... No git command is printed. Exit 1.
   With --old E/old: exit 0, READY, the three rows are WARN "old system session, finishes there".
   Suggested fix: README step 2 should read: at mc2-v2.0 run preflight --old "/Users/mac/Desktop/Terminal Bench"; from mc2-v2.1 settings upgrade.old_root does it.

6. BREAKS (for the documented known bundle step). Where: NEXT.md item 1 and STEPS12 D "set upgrade.known_bundle in settings". settings.json is a tracked file, so after the edit every printed "git status --porcelain  # must print nothing" prints " M master_chat_tasks/settings.json" (seen in this run while settings were edited for the simulation). Git carries the edit across checkouts only because settings.json does not change between mc2-v2.1 and mc2-v2.5; the first tag that changes settings.json will refuse the checkout ("Your local changes would be overwritten"). Combined with problem 2 the known bundle can never PASS. Without it every recheck ends WAITING (exit 3), so "UPGRADE GOOD" and the "git branch -f mc2-stable <tag>" line are never printed and mc2-stable stays at mc2-v2.0.
   Suggested fix: move Mac specific values (known_bundle, maybe old_root) into an ignored settings.local.json read on top of settings.json, or give recheck --known-bundle as the documented way, and say in README what to do when recheck ends WAITING.

7. CONFUSING. Where: recheck output, cold recovery test. The prompt Ayush must paste and the PASS criteria are cut at 160 characters (upgrade.py Report.show, line[:160]): "... Read master_chat_tasks/STATE_CARD.md first (regenerate it with python3 " and "PASS when the reply: names the goal, ... says a LONG session is only repor". The full text is in master_chat_tasks/README.md line 25, which the output does not name.
   Suggested fix: do not truncate WAIT details, or print "full prompt: master_chat_tasks/README.md, Compact and restore prompts, part B".

8. CONFUSING. Where: delivery/README.md "After mc2-v2.3, issue one real prompt and read it". No command is given (issue.py needs a draft the master writes from a template, plus SLUG KIND DRAFT OUT). And the issued board row is live, so the next preflight blocks:
   Output (v2.3 to v2.4): FAIL  no session running / 1 busy: board 66f6d42 issued cold-chain-backbone-quote. Exit 1.
   I ended the row with board.py set 66f6d42 status=done to continue. Also issuing changes records, so the next preflight also FAILs "4 record files changed and 4 new since the backup" until backup runs again (correct, and the README order backup then preflight covers it, but only if Ayush issues before the backup).
   Suggested fix: say "use issue.py --dry-run, or issue and let the session finish (or mark the row done) before the next preflight", and give the command.

9. CONFUSING. Where: issued prompts after mc2-v2.3 use [[ROOT]]/QC/reports/<slug>, [[ROOT]]/QC/copies and [[ROOT]]/master_chat_work/... (sample and my real issue). The data copy brings neither QC/ nor master_chat_work/ into ROOT, and the board and registry rows point at the old folder (board.json 292 lines and registry/tasks.json 17 lines name "Terminal Bench"; for example cold-chain-backbone-quote results are in "/Users/mac/Desktop/Terminal Bench/QC/reports/..." and ".../master_chat_work/20261029_cold-chain-backbone-quote/..."). A recheck mode QC (previous report, KEPT.md, previous copy) for a task that started in the old system has its inputs in the old folder, but the prompt's report folder is in ROOT. No doc says where bundles and QC reports live after the switch.
   Suggested fix: one paragraph in delivery/README.md: which folders stay in the old root, and that the master fills [[ORIGINAL]], [[PREV_REPORT]] and [[PREV_COPY]] with old paths for carried tasks (template_check and the "no old root path" rule then need an exception for those fields).

10. CONFUSING. Where: SETUP_STEPS.md step 1 "(If you already have a clone: git fetch ..., then git checkout claude/youthful-feynman-zug0uq, then git pull.)". origin/main holds master_chat_tasks, master_chat_work, QC and "harness queue" at its top, so Ayush's existing clone may be the live old folder (or contain it). A checkout of the planning branch there would switch the live old system's files. Gap: I cannot see whether "Terminal Bench" is a clone of this repo.
   Suggested fix: say "only in a separate clone, never in the Terminal Bench folder", and give the real repo URL instead of <repo url> (STEP0_REPORT B has https://github.com/Ayush-dvplr/master-task-chat.git).

11. CONFUSING. Where: SETUP_STEPS.md step 5. It says "inside the clone" but ../mc2_worktree lands next to the clone (~/Desktop/mc2_worktree), and git worktree add resolves it against the current folder, so it must be run from the clone root. Rerunning step 5 for a newer bundle (delivery/README says later steps replace mc2.bundle) fails:
   git fetch upgrade_plan/delivery/mc2.bundle "refs/heads/mc2-v2:refs/heads/mc2-v2" ... -> "fatal: refusing to fetch into branch 'refs/heads/mc2-v2' checked out at '.../mc2_worktree'", exit 128.
   git worktree add ../mc2_worktree mc2-v2 -> "fatal: '../mc2_worktree' already exists", exit 128.
   Also AGENTS.md lets the session commit in the worktree on mc2-v2 while new bundles from the cloud also move mc2-v2: the two can diverge.
   Suggested fix: "run from the clone root"; for updates use git -C ../mc2_worktree pull from the bundle (or fetch into refs/remotes/bundle/* and merge), and name one side as the only writer of mc2-v2.

12. CONFUSING. Where: printed "git fetch origin --tags  # brings the new tag from GitHub". ROOT's origin is the bundle file inside the planning clone (git remote -v: E/mc2_upgrade/upgrade_plan/delivery/mc2.bundle), not GitHub. It worked here (exit 0) because the tags were already in the bundle. If the planning clone moves, or Ayush follows README step 3 and expects GitHub, the fetch either fails or fetches nothing new. README's own update line (git fetch /path/to/mc2.bundle "refs/heads/*:refs/remotes/bundle/*" --tags) worked, exit 0.
   Suggested fix: comment should say "from origin (the bundle you cloned, or GitHub)", and README should say which remote to use.

13. CONFUSING. Where: self tests at mc2-v2.5. test_e3_e6_tools.py (1 failure, 2 errors) and test_upgrade_tools.py A2Intake and A4Repackage (4 failures, 4 errors) fail on ROOT/Terminal_2.0_Harbor_Harness/{scripts/master_queue.py, scripts/package_rfp_bundles.py, jobs/<slug>, Tasks_INPUT/<slug>, Output_RFP/<slug>}. They need the harness in ROOT and real job folders (problem 3). Preflight does not run them, so nothing blocks, but delivery docs do not say they are expected to fail.
   Suggested fix: skip with a clear reason when the harness or the job folder is missing.

14. CONFUSING. Where: recheck output after a rollback (upgrade.py rollback_commands used inside recheck). After "git checkout mc2-v2.4" the recheck --from mc2-v2.5 --to mc2-v2.4 prints "git checkout mc2-v2.5  # back to the version that worked (leaving mc2-v2.4)". It calls the version just rolled away from "the version that worked".
   Suggested fix: for a recheck whose --to is older than --from, print "rollback done" and no reverse commands.

15. CONFUSING. Where: upgrade_plan/RESUME.md (read by START_PROMPT.md). "Last updated: 3 Nov 2026 15:35 IST" while RUNNING NOW holds 4 Nov text, and it still says "Waiting: Ayush types PROCEED for STAGE A" and RULES item 1 "Edit nothing outside upgrade_plan/ until Ayush types the exact word PROCEED", while AGENTS.md says STAGE A is approved and built. A fresh opencode session gets two different rules.
   Suggested fix: refresh the date and RUNNING NOW, and state STAGE A approved and STAGE B pending in RULES.

16. CONFUSING. Where: knowledge/KIT_CLASSIFY_PROMPT.md line 4: python3 tools/kit_watch.py check --out ../master_chat_work/[[DATE]]_kit/ > ../master_chat_work/[[DATE]]_kit/kit_watch.txt. The shell opens the redirect before kit_watch creates the folder:
   Output: bash: ../master_chat_work/20261104_kit/kit_watch.txt: No such file or directory, exit 1 (zsh gives the same). It also has no --kit, so without the harness in ROOT it exits 2 anyway.
   Suggested fix: mkdir -p the folder first in the same line.

17. MINOR. Where: tools/tests/test_issue_mc2.py test_template_check_clean_then_flags plants the literal "/Users/mac/Desktop/Terminal Bench", but template_check.py reads upgrade.old_root from settings. With old_root set to another path (here E/old for the simulation) the test fails, the preflight "tool self tests" row is a FAIL and the upgrade is BLOCKED. With the committed settings it passes (9 OK). Only bites if Ayush's old folder path ever differs.
   Suggested fix: plant the value read from the test copy's settings.

18. MINOR. Where: issue.py rendering. The P11 issue rendered prompts/rendered/<sha>/P11_full_qc_v3.md (the whole template, header included) with master placeholders [[MODE]], [[PREV_REPORT]], [[PREV_COPY]], [[ORACLE_N]], [[SLUG]], [[SHA]], [[PROMPT_PATH]], [[ORIGINAL]], [[BOARD_SHA]] left in it; the issued prompt never points at that copy (only the "Template:" line names it). Harmless today, but a session that opens it sees unfilled tokens.
   Suggested fix: do not render the template named only by the "Template:" line.

19. MINOR. Where: the issued P11 prompt keeps <YYYYMMDD> (8 lines) and <TS>. <TS> is explained (line 69, date plus openssl rand); <YYYYMMDD> is not explained anywhere in the prompt.
   Suggested fix: one sentence: "<YYYYMMDD> is today's IST date".

20. MINOR. Where: SETUP_STEPS.md step 2 and .opencode/dcp.jsonc. The dcp.jsonc protects "**/upgrade_plan/opencode_handoff/AGENTS.md", but the copy opencode loads is the clone root AGENTS.md, which no pattern matches. Probably fine because AGENTS.md is in the system prompt, but the protected list does not say what it protects. Also cp -R ... .opencode ~/Desktop/mc2_upgrade/.opencode nests .opencode/.opencode if run twice (BSD and GNU alike).
   Suggested fix: add "AGENTS.md" to protectedFilePatterns; use cp -R .../.opencode ~/Desktop/mc2_upgrade/ (copy into the parent).

21. MINOR. Where: NEXT.md item 4 names "harness queue/master_queue.py", which is not in the planning branch (only on origin/main). Every other file named by START_PROMPT, COMPACT_PROMPT, NEXT and AGENTS exists.
   Suggested fix: write it as origin/main:"harness queue/master_queue.py".

22. MINOR. Where: tags in the bundle. mc2-v2.0 is an annotated tag (object 719a09c8, commit 8d1c963e); mc2-v2.1 to mc2-v2.5 are lightweight. W1-043 reports mc2-v2.0 as 8d1c963e, list-heads shows 719a09c8. Not a failure, only confusing when comparing hashes.

23. MINOR. Where: printed "git tag before-<tag>-<YYYYMMDDTHHMM>". Running the printed block twice in the same minute gives "fatal: tag ... already exists"; the local before-* tags (five after this run) are pushed to GitHub if Ayush later runs README step 3's "git push github ... --tags".
   Suggested fix: add seconds to the tag name, and push named tags only.

24. MINOR. Where: one backup folder per day (mc2_backup/20261104) is overwritten by each backup. Doing several steps on one day keeps only the latest backup, so a rollback over two steps cannot restore the records from before the first. Fine for one step at a time.

25. MINOR. Where: tools/stacking_check.py (old tool, present since mc2-v2.0) imports tomllib (Python 3.11+). Fine on Homebrew 3.12; fails if python3 resolves to the Xcode command line tools Python 3.9. No new mc2 tool uses a 3.11+ only feature.

26. MINOR. Where: the planning clone is 2.2 GB checked out (40093 files, .git 840 MB) because master_chat_work is on the branch. SETUP_STEPS does not warn about size or time.

PASSED (37 checks)

1. SETUP 1: git clone -b claude/youthful-feynman-zug0uq of the repo: exit 0.
2. SETUP 2: both cp commands as written: exit 0; AGENTS.md and .opencode/dcp.jsonc in place, untracked.
3. .opencode/dcp.jsonc parses after stripping // comments; all 10 keys ($schema, manualMode.enabled, manualMode.automaticStrategies, compress.protectUserMessages, compress.protectTags, compress.showCompression, turnProtection.enabled, turnProtection.turns, protectedFilePatterns, pruneNotification) exist in dcp.schema.master_20261103.json with matching types; pruneNotification "detailed" is in the enum.
4. START_PROMPT, COMPACT_PROMPT, NEXT and AGENTS name 16 files; 15 exist on the branch (the 16th is problem 21).
5. git bundle verify: complete history, sha1, refs mc2-v2, mc2-stable and tags mc2-v2.0 to mc2-v2.5; mc2-stable = mc2-v2.0 commit 8d1c963e; mc2-v2 = mc2-v2.5 c7b0592a.
6. SETUP 5 first run from the clone root: fetch exit 0, worktree add exit 0, worktree at mc2-v2.5, SYSTEM_VERSION v2.5.
7. README 2: git clone -b mc2-stable <bundle> mc2_root: exit 0, branch mc2-stable, SYSTEM_VERSION v2.0, clean tree, all six tags present.
8. Data copy (STEP0 C mapped to E): all 9 commands exit 0, no nested folders; git status --porcelain prints nothing (every DATA file ignored).
9. upgrade.py status at v2.0 and v2.1: exit 0; 772 record files; 3 live rows listed.
10. upgrade.py backup, 7 runs: exit 0 each (772 to 776 record files).
11. preflight --old at v2.0: exit 0 READY; old system rows WARN.
12. carry_over.py --all-finished dry run: exit 0, 56 slugs, 0 to carry, 0 refused.
13. carry_over.py --slug flood-repair-portfolio: exit 1, refused "has not finished in the OLD system (420bf9a running)", nothing written.
14. carry_over.py --slug cold-chain-backbone-quote: exit 0, nothing to carry.
15. registry_check.py: exit 0, 37 tasks, 0 drift; test_carry_over.py 6 OK.
16. v2.0 to v2.1: printed commands pasted literally in bash, all exit 0; recheck exit 3 WAITING, no FAIL.
17. v2.1 to v2.2: same; card 7.9 KB under 8 KB; opencode and DCP files PASS.
18. v2.2 to v2.3: same; template_check PASS (14 templates, 0 conflicting lines).
19. v2.3 to v2.4: after a new backup and the issued row ended, preflight --old READY, printed commands exit 0, recheck exit 3 WAITING.
20. v2.4 to v2.5: same; recheck exit 3 WAITING; SYSTEM_VERSION v2.5.
21. Preflight guards fire correctly: stale backup is a FAIL (4 changed, 4 new files), a new live ROOT row is a FAIL.
22. Settings old_root (simulated as E/old) makes plain preflight READY from v2.1 without --old.
23. issue.py --lint on the master style P11 draft: lint clean, exit 0.
24. issue.py --dry-run: exit 0, cap warnings only (passed QC, QC rounds), runner oc-opus-5.5.
25. Real issue into ROOT data: exit 0, board 66f6d42, pending item, card rebuilt; the issued prompt has no [[NAME]] and no settings token left (gate, oracle runs, system id, hash8 filled), no "Terminal Bench" and no /tmp path; only the session placeholders <YYYYMMDD> and <TS> remain (problem 19). Copy: logs/s4_issued_prompt.md.
26. kit_watch.py check --kit <old kit>: exit 1, CHANGED 8 files against the 25 Oct snapshot 5574d77e, ids unknown (no text copy), as W1-045 described; knowledge/fingerprints sha256 identical before and after (check never writes).
27. upgrade.py rollback --from mc2-v2.5 --to mc2-v2.4: prints the commands; pasted literally: git checkout mc2-v2.4 exit 0, recheck exit 3 WAITING, SYSTEM_VERSION v2.4. (The rsync dry run line could not run here: rsync is not installed; macOS ships rsync.)
28. Back at v2.5, self tests with python3.12: test_carry_over 6, test_dockfree 5, test_issue_lint 7, test_issue_mc2 9, test_kit_watch 4, test_minor_decisions 2, test_regression_check 5, test_state_card 11, auto/tests/test_auto.py 75: all OK.
29. pytest (/root/.local/bin/pytest, python3 -m pytest is not installed): 143 passed, 11 failed, all 11 on the missing harness (problem 13).
30. Tests left nothing in /tmp, did not change ROOT records (only STATE_CARD.md differs from the backup), and git status stays clean (__pycache__ and the card are ignored).
31. py_compile of all 36 tracked .py files: 0 failures with Python 3.12 and 0 with Python 3.11 (so no 3.12 only f-string syntax either).
32. AST scan: no match statement, no except*, no PEP 695 syntax; no tomllib, StrEnum, Self, ExceptionGroup or datetime.UTC in any new mc2 tool (only problem 25).
33. precheck.sh: no GNU only flags (sed -i, cp --, readlink -f, date -d, grep -P, stat -c, find -printf, xargs -r, timeout) and no bash 4 only syntax (declare -A, mapfile, ${x,,}); runs under bash with PRECHECK_KIT set (logs/s3_precheck_oldkit.txt). The commands in the docs, the current templates, README and the knowledge files also have none.
34. Old root path at mc2-v2.5: 0 lines in the 14 current templates; in tools only as the default value (template_check.py 263, upgrade.py 66); in system files only settings.json old_root.
35. Secret scan (API key, token, private key and password patterns; auth.json, .env, key files): 0 hits in every tag mc2-v2.0 to mc2-v2.5, 0 in the whole bundle history, 0 in ROOT's DATA files.
36. README later step fetch: git fetch <bundle> "refs/heads/*:refs/remotes/bundle/*" --tags in ROOT: exit 0.
37. sqlite3 ".backup" copy of pending.db (stand in) and carry_over reading it read only: worked; git status clean after the copy.

GAPS (only the real Mac can show)

1. zsh at Ayush's prompt: whether interactivecomments is on (problem 1), and zsh globbing of words such as "(mc2-v2.0)," in the pasted lines.
2. BSD cp and sed: no sed is used in the docs; cp -Rp and cp -p were run with GNU cp. BSD cp gives the same result for a missing destination, but the real paths with spaces ("Terminal Bench") were only simulated with a path without spaces.
3. The real sqlite3 CLI ".backup" on a pending.db that the old system may be writing (WAL or locks).
4. Homebrew python3 resolution: that python3 is 3.12 and not the Xcode 3.9 (tools use zoneinfo and datetime.fromisoformat; stacking_check needs 3.11).
5. opencode: DCP manual notice in the upgrade clone (SETUP 2), START_PROMPT 5 line answer, DCP layering G1 in ROOT, the cold recovery test (part B), whether opencode writes untracked files into ROOT/.opencode.
6. Docker Desktop, harbor and the four kit scripts on a real bundle (precheck exit 0 on a QC passed bundle), and all Docker parts of the issued prompts.
7. Whether "/Users/mac/Desktop/Terminal Bench" is itself a git clone of master-task-chat (problem 10), and its real board, pending and live sessions on the day.
8. master_chat_work (2.2 GB) was not copied; any tool path into old work folders, and the work mirror size of the backup, were not exercised.
9. The kit git head: the simulated kit is not a git checkout, so "== kit ?" and kit_watch save --head could not be tested; save itself was not run (it needs Ayush's words).
10. rsync restore of the backup (macOS openrsync or rsync 2.6.9 flags -a --dry-run).
11. Pushing to GitHub (README step 3) and whether GitHub accepts the mc2 branches now.
12. The state card's OLD SYSTEM flags and QC KIT line with the real old folder reachable at the default old_root (in this run they showed "live kit not reachable here").
