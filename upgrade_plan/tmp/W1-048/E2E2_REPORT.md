W1-048 SECOND END TO END CHECK OF THE STAGE A INSTALL (report only, nothing delivered was changed)

Date: 4 Nov 2026. Helper W1-048. Simulation folder E = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/e2e3 (fresh, not e2e or e2e2).

HOW THE MAC WAS SIMULATED
1. zsh 5.9 was installed in the container and every pasted block ran in an interactive "zsh -f -i" (default options, so interactivecomments is off until the guide's setopt line), with only python3 = Python 3.12.3 on PATH, an empty HOME and LANG C.UTF-8. The options verbose and printexitvalue were added only to log each line and its exit code. Logs: E/_log/*.in (exactly what was pasted) and E/_log/*.out.
2. Path mapping: /Users/mac/Desktop became E/Desktop by text replacement of each pasted block. The GitHub URL in SETUP step 1 became /home/user/master-task-chat. Everything else was pasted literally, in order.
3. Old folder "E/Desktop/Terminal Bench" (with the space): master_chat_tasks copied from the planning branch working tree; master_chat_work subset (20261024_process, 20261020_analysis/reports/qc, _dev_research/delivery_study2 and peer_levers, gen_memory/ideas.jsonl, bundles/cold-chain-backbone-quote); Terminal_2.0_Harbor_Harness as a git repo holding Input_Bundle_QC from git show origin/main (commit 05c6fc9c, remote origin set to a placeholder URL), plus Tasks_INPUT/cold-chain-backbone-quote (untracked) as the known bundle, and QC/reports/sample.
4. A sha256 list plus a tree list with mtimes of the old folder was taken before step 1 and again at the end.

PROBLEMS (no BREAKS found)

1. CONFUSING. Where: delivery/README.md step 3, "Expected: the six tags and version = v2.0". What happens: the bundle has seven mc2 tags, so a careful reader counts seven and wonders whether something is extra.
   Command and output:
    git -C "$ROOT" tag -l "mc2-v*"
    mc2-v2.0
    mc2-v2.1
    mc2-v2.2
    mc2-v2.3
    mc2-v2.4
    mc2-v2.5
    mc2-v2.5.1
   Suggested fix (not applied): write "the seven tags mc2-v2.0 to mc2-v2.5.1".

2. CONFUSING. Where: preflight from mc2-v2.5 on (step 10.1), and the guide is silent about it. What happens: kit_watch status is WARN with "kit changed since the snapshot: classify it (S7, Q86); a MAJOR change blocks", yet the verdict is READY. The live kit on origin/main (commit 487b4697 "updated QC bundle", 4 Nov) differs from the snapshot in ROOT (head 5574d77e, taken 2026-10-25, no text copy), so Ayush will see this on the Mac too. The guide's step 11.5 only explains the WAIT case (no kit found); step 12.2 mentions saving the snapshot but not this WARN or the word "blocks".
   Command and output (preflight at mc2-v2.5):
    python3 "$UP" preflight --old "$OLD"
      WARN  kit_watch status
            QC KIT: CHANGED 8 files (01_Instruction_QC.md, 02_Data_Solution_QC.md, 03_Tests_QC.md, 04_Judge_QC.md, 05_Alignment_Integrity_QC.md, Final_checkl); 0 check ids, 0 in the fix map, 0 in BUILD_RULES; ids unknown for 8 files (snapshot has no text copy). An agent classifies LENIENT, MINOR or MAJOR (S7); Ayush decides.
            kit changed since the snapshot: classify it (S7, Q86); a MAJOR change blocks
    VERDICT: READY. Paste these commands yourself (upgrade.py never runs git).
   Suggested fix: add a line to step 11 or 12.2: "From mc2-v2.5 preflight shows kit_watch WARN CHANGED 8 files because the PL updated the kit after the snapshot; it does not block the loop; the master classifies it and saves the snapshot on your word (12.2)."

3. CONFUSING. Where: tools/tests/test_upgrade_tools.py (intake and repackage parts) and guide step 11.3. What happens: 9 tests skip with "needs the harness clone in ROOT with real job folders (INSTALL guide step 5)", but step 5 itself says the clone does not bring jobs/ and Tasks_INPUT/. So the tests skip for good even after step 5 is done, and the message sends Ayush to a step that cannot fix it. Step 11.3 reads as if they run once the harness is in ROOT.
   Command and output (harness clone in ROOT, step 5 done):
    python3 master_chat_tasks/tools/tests/test_upgrade_tools.py -v
    test_ayush_ok_only_for_regrade ... skipped 'needs the harness clone in ROOT with real job folders (INSTALL guide step 5); missing: .../mc2_root/Terminal_2.0_Harbor_Harness/jobs/sentinel-policy-recompute, .../jobs/district-heat-flex-procurement'
    (8 more alike)
    OK (skipped=9)
   Suggested fix: let these tests fall back to the old folder's jobs/ and Tasks_INPUT/ read only (as precheck.sh does for the kit), or change the skip text and 11.3 to "needs real job folders, which stay in the old folder; skipped by design".

4. MINOR. Where: guide step 9 ("until mc2-v2.5.1 the recheck shows the dry precheck as WAIT") and 11.4. What happens: the recheck is always run by the newest upgrade.py copied in step 4, which reads settings.local.json at every tag, so with step 9 done the dry precheck is PASS from mc2-v2.3 on. At mc2-v2.1 and mc2-v2.2 it was WAIT for a different reason (the fixed KIT= path in the old precheck.sh; see GAPS 3).
   Command and output (recheck after mc2-v2.3, mc2-v2.4 and mc2-v2.5 alike):
      PASS  dry precheck on a known bundle
            .../Terminal Bench/Terminal_2.0_Harbor_Harness/Tasks_INPUT/cold-chain-backbone-quote: exit 0 (kit .../mc2_root/Terminal_2.0_Harbor_Harness/Input_Bundle_QC, from settings paths.kit (ROOT, else the old folder))
            PRECHECK CLEAN
   Suggested fix: step 9 text: "the recheck reads it from mc2-v2.3 on (the newest upgrade.py does the reading); at mc2-v2.1 and mc2-v2.2 it stays WAIT".

5. MINOR. Where: guide step 11.2 says that at mc2-v2.5.1 "the state card ... print a NOTE". What happens: state_card.py prints no NOTE about the kit on stdout; it marks the card line instead.
   Command and output (harness moved out of ROOT, old_root set):
    python3 "$ROOT/master_chat_tasks/tools/state_card.py" | grep -i 'note\|kit'
    NOTE: over the 6 KB target
    grep -n 'QC KIT' "$ROOT/master_chat_tasks/STATE_CARD.md"
    23:QC KIT (old folder kit): CHANGED 8 files (...)
   Suggested fix: guide text "the state card marks its QC KIT line (old folder kit)".

6. MINOR. Where: master_chat_tasks/tools/kit_watch.py line 342, names = ", ".join(...)[:120]. What happens: the summary line on the state card, preflight and kit_watch check cuts the file list in the middle of a name ("Final_checkl") with no sign that names were left out (8 files changed, 6 shown).
   Output: see problem 2.
   Suggested fix: cut at a whole name and add "and N more".

7. MINOR. Where: master_chat_tasks/tools/issue.py line 164. What happens: the cap warning always says "2 QC rounds" while it lists every QC round, here five.
   Command and output (step 10.4 dry run):
    WARNING (cap, issued anyway; Q120): 2 QC rounds already in v3 (4e298da, 4fef871, 7304a6f, 78b8d5b, c75ddad)
   Suggested fix: f"{len(qcs)} QC rounds already in v3 (cap 2) (...)".

8. MINOR. Where: upgrade.py Layout init (lines about 304 to 313 of the mc2-v2.5.1 copy). What happens: the fallback to the old folder's kit uses only settings upgrade.old_root and ignores --old. With --old given but old_root unset or different, preflight at mc2-v2.5 and later without a ROOT harness says kit_watch WAIT and prints no commands, although the guide says giving --old "$OLD" is "always fine". No effect on Ayush's Mac as long as settings.json old_root is the real old folder (it is "/Users/mac/Desktop/Terminal Bench" from mc2-v2.1).
   Command and output (harness moved out of ROOT, settings old_root not reachable):
    python3 "$UP" preflight --old "$OLD"
      WAIT  kit_watch status
            live kit not found (.../mc2_root/Terminal_2.0_Harbor_Harness/Input_Bundle_QC); place the harness clone in ROOT (INSTALL guide step 5), or give --kit
    VERDICT: WAITING for the items marked WAIT above. No git command is printed yet.
   With upgrade.old_root pointed at the old folder in settings.local.json, the same preflight used the old kit, printed "ROOT has no Terminal_2.0_Harbor_Harness/Input_Bundle_QC: the old folder's kit is used (read only)" and ended READY.
   Suggested fix: use L.old_root(a) (which honours --old) for the kit fallback.

9. MINOR. Where: planning files the session reads. What happens: (a) upgrade_plan/RESUME.md STATE OF THE WORK item 4 still says "Nothing outside upgrade_plan/ has been edited. PROCEED has not been given.", against its own RULES item 1 and RUNNING NOW (NEXT.md item 7 and AGENTS.md EDITS AND GIT item 1 already say they win, so a session is not misled for long). (b) QUESTIONS.md LIVE NOW says "kit snapshot save at mc2-v2.5", NEXT.md item 2 says "At mc2-v2.5.1".
   Suggested fix: update RESUME.md STATE item 4 and the LIVE NOW line to mc2-v2.5.1.

PASSED CHECKS (30)

1. SETUP step 1: setopt, PLAN=, git clone -b claude/youthful-feynman-zug0uq into "$PLAN": exit 0; branch --show-current prints claude/youthful-feynman-zug0uq; rev-parse --show-toplevel prints PLAN. Clone 3.0 GB in all, in line with the 2.2 GB plus 840 MB stated.
2. SETUP step 2: both cp lines exit 0; PLAN/AGENTS.md and PLAN/.opencode/dcp.jsonc in place, no nested folder. git status shows only these two as untracked, as Notes item 1 expects.
3. SETUP step 5: fetch from the bundle into bundle/mc2-v2 and bundle/mc2-stable, worktree add at 654a2e81 "mc2-v2.5.1: shorter state card tag for the old folder kit"; the repeat fetch is silent and merge --ff-only says "Already up to date." All exit 0. "now mc2-v2.5.1" in step 5 matches.
4. INSTALL step 2: pull "Already up to date."; bundle verify: "is okay", 9 refs (mc2-v2, mc2-stable, tags mc2-v2.0 to mc2-v2.5.1), "The bundle records a complete history."
5. INSTALL step 3: clone exit 0; SYSTEM_VERSION "version = v2.0".
6. INSTALL step 4: exclude line, mkdir, NEWEST is mc2-v2.5.1, upgrade.py extracted.
7. INSTALL step 5: harness clone, remote set-url; ROOT and old folder both print 05c6fc9c; origin is the old clone's URL.
8. INSTALL step 6: every copy line exit 0 (BSD style cp -Rp into the parent), sqlite3 .backup exit 0, git status --porcelain prints nothing.
9. INSTALL step 7: bundle copy, the four reference copies and ln -sfn; QC/old_reports lists the old reports; git status empty.
10. INSTALL step 8: status, registry_check ("37 tasks, 0 field(s) with type drift"), backup to mc2_backup/<stamp>/ (772 record files), preflight: three copied live rows shown as WARN "old system session, finishes there", VERDICT: READY with the block for mc2-v2.1.
11. INSTALL step 9: settings.local.json written, git status empty at every later tag (exclude line works).
12. INSTALL step 10 loop: six rounds mc2-v2.0 to mc2-v2.1, 2.2, 2.3, 2.4, 2.5, 2.5.1. Every preflight READY, every printed block pasted as is into zsh -f with interactivecomments: git status empty, fetch, before-* tag, checkout, recheck ending "VERDICT: WAITING" with exit 3 and no FAIL, as 10.3.1 says. Template_check turned PASS at mc2-v2.3, state card PASS from mc2-v2.2, self tests in preflight all OK.
13. INSTALL step 10.4 at mc2-v2.3 and again at mc2-v2.5.1: --render wrote P11_rendered.md (117 lines, ROOT paths only, no old root, only the master filled [[NAME]] fields left); the dry run printed "DRY RUN ok" with cap warnings only. A record diff of ROOT against the first backup (rsync -rcn) shows no changed record: no board row, pending item or record written.
14. INSTALL step 12.1: recheck --cold-result pass ended "VERDICT: UPGRADE GOOD" and printed git branch -f mc2-stable mc2-v2.5.1; pasted, mc2-stable at 654a2e81.
15. Preflight at mc2-v2.5.1 with and without --old: "UP TO DATE: ROOT runs mc2-v2.5.1 ...".
16. INSTALL step 13 rollback mc2-v2.5.1 to mc2-v2.5: block pasted, "ROLLBACK DONE", the mc2-stable hint shown because mc2-stable pointed at the version left, rsync --dry-run line exit 0; SYSTEM_VERSION v2.5. Forward again: backup, preflight READY, block pasted, WAITING, then cold pass gives UPGRADE GOOD and mc2-stable back at mc2-v2.5.1.
17. INSTALL step 11 at mc2-v2.5 with the harness moved out of ROOT: precheck.sh ran the four kit scripts with exit 2 each, kit_watch "kit folder not found", test_e3_e6_tools.py and test_upgrade_tools.py fail when run by hand, preflight kit_watch WAIT with no command printed. All as 11.1, 11.3 and 11.5 say.
18. INSTALL step 11 at mc2-v2.5.1 with the harness out of ROOT: precheck.sh, kit_watch.py and issue.py print the NOTE and use the old folder's kit read only; test_e3_e6_tools.py OK (skipped=3), test_upgrade_tools.py OK (skipped=9); recheck WARN in settings row naming the old kit, still WAITING (no FAIL).
19. INSTALL step 12.3 (later bundle): pull, fetch origin --tags, NEWEST, upgrade.py refresh all exit 0.
20. INSTALL step 14 against a local bare repo standing in for GitHub: pushed mc2-v2, mc2-stable and the seven mc2 tags only; no before-* marker tag was pushed.
21. INSTALL Notes item 1: mc2-v2.0 is annotated (719a09c8, commit 8d1c963e); mc2-v2.1 to mc2-v2.5.1 are lightweight.
22. Every self test in ROOT at mc2-v2.5.1 under Python 3.12: 12 files, all OK (test_carry_over 6, test_dockfree 5, test_e3_e6_tools 7 with 3 skipped, test_issue_lint 7, test_issue_mc2 11, test_kit_watch 5, test_minor_decisions 2, test_regression_check 5, test_state_card 11, test_upgrade_mc2 9, test_upgrade_tools 23 with 9 skipped, auto/tests/test_auto 75).
23. py_compile of all 38 tracked Python files: OK.
24. template_check.py: "TOTAL templates 14 conflicting lines 0 ... manifest problems 0", exit 0.
25. Shell portability: bash -n precheck.sh OK; no sed -i, readlink -f, stat -c, sha256sum, timeout, mapfile, declare -A or other GNU or bash 4 only constructs in tracked .sh and .py files.
26. Secret scan (AWS, GitHub, Anthropic, OpenAI, Slack, Google keys, private key blocks, key or token assignments): 0 hits in all seven tags, 0 in the full bundle history (11 commits, git log --all -p), 0 in delivery/, opencode_handoff/, the root AGENTS.md and .opencode/, 0 in the copied DATA. Nothing was copied out.
27. START_PROMPT.md, COMPACT_PROMPT.md, NEXT.md and AGENTS.md name only files that exist in the planning clone (RESUME.md, ANSWERS.md, QUESTIONS.md, WORKER_LOG.md, README.md with "GOAL OF THE TASK SYSTEM", PLAN_FINAL.md, CONFLICT_REVIEW.md, tmp/W1-031/MEASURE.md, tmp/W1-041/MAP.md, delivery/README.md, .opencode/dcp.jsonc), plus master_chat_tasks/README.md part B in ROOT, which exists and is the prompt the recheck prints. origin/main:"harness queue/master_queue.py" exists on GitHub main (checked in the source repo).
28. Names agree across SETUP_STEPS.md, the INSTALL guide, NEXT.md and AGENTS.md: root "/Users/mac/Desktop/mc2_root", planning clone mc2_upgrade, worktree mc2_worktree, branch claude/youthful-feynman-zug0uq, branches mc2-v2 and mc2-stable, newest tag mc2-v2.5.1, mc2-stable at mc2-v2.0 until marked, lightweight tags, next tags mc2-v2.6 and mc2-v2.5.2.
29. The old folder was never written: 1567 files with the same sha256 before and after, and the tree list with mtimes (1781 entries) is identical.
30. Paste safety: no indented command in the INSTALL guide or SETUP_STEPS.md has a trailing comment or an unquoted path with a space; every block upgrade.py printed has its # lines on their own line and pasted cleanly. Without setopt interactivecomments, zsh -f would print a # line as text, which the guide's step 1 and the tool's own reminder line prevent.

GAPS (only a real Mac can close these)

1. Real Terminal zsh with Ayush's own ~/.zshrc and macOS BSD userland (cp, ln, grep, mktemp) and /bin/bash 3.2 for precheck.sh; here zsh -f on Linux with GNU tools and a code scan stood in.
2. macOS rsync (openrsync or 2.6.9) for the rollback restore line; here rsync 3.2.7, only -a and --dry-run used.
3. settings.json upgrade.old_root is the literal "/Users/mac/Desktop/Terminal Bench", which the mapped simulation cannot reach. Because of that the dry precheck at mc2-v2.1 and mc2-v2.2 was WAIT (old precheck.sh fixed KIT= path), and the old kit fallback was tested only with a temporary old_root override in settings.local.json (restored afterwards).
4. The real harness repo: its scripts/ (master_queue.py, package_rfp_bundles.py, so the 3 skipped e3_e6 tests), its real commit and whether its HEAD is the 487b4697 named in NEXT.md item 2 and the sample P11; real kit scripts against real bundles.
5. Cold recovery test in a real fresh master session (here only --cold-result pass was typed), DCP layering G1, opencode start in the planning clone and in ROOT, Q78 global config and plugins.
6. Clone from GitHub (here from the local repo, whose local main is stale, so origin/main paths could not be read inside the simulated clone), push of the mc2 branches to GitHub, disk space and time.
7. Homebrew python3 3.12 versus an Xcode 3.9 on PATH; sqlite3 .backup while the live old system holds pending.db open; IST times on the Mac clock.
