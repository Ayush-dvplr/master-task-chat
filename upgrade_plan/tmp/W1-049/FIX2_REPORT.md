W1-049 FIXES FOR THE NINE PROBLEMS OF W1-048 (E2E2_REPORT.md)

Date: 4 Nov 2026. Helper W1-049. Worktree W = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2 (branch mc2-v2). Scratch E = /tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/e2e4.

RESULT
Commit fe8e377a "mc2-v2.5.2: fixes after the W1-048 end to end test (kit names, QC cap count, --old kit, skip text)" on mc2-v2, on top of 654a2e81 (mc2-v2.5.1). Lightweight tag mc2-v2.5.2 on fe8e377a. SYSTEM_VERSION says version = v2.5.2. Nothing pushed, no other branch checked out, no existing tag changed. mc2-stable still at 8d1c963e (mc2-v2.0). delivery/mc2.bundle was not touched: the master rebuilds it.

PER ISSUE

1. Tag count and every version list now run to mc2-v2.5.2. FIXED.
   Fix: guide title, "What you get", step 2 ("the eight tags mc2-v2.0 to mc2-v2.5.2"), step 3 (all eight tags named, mc2-v2.5.2 the newest), step 4 (NEWEST prints mc2-v2.5.2), step 10 (seven rounds from mc2-v2.0, the loop ends at mc2-v2.5.2 with "UP TO DATE: ROOT runs mc2-v2.5.2"), step 12 (at mc2-v2.5.2, recheck --from mc2-v2.5.1 --to mc2-v2.5.2, mc2-stable mc2-v2.5.2), step 13 (rollback example mc2-v2.5.2 to mc2-v2.5.1), Notes 1 and 2.
   Files: upgrade_plan/delivery/README.md.
   Proof: in the ROOT cloned from the new bundle, git tag -l "mc2-v*" lists the eight tags mc2-v2.0 to mc2-v2.5.2; NEWEST printed mc2-v2.5.2; the final preflight printed "UP TO DATE: ROOT runs mc2-v2.5.2". The s3_sample files name no version, so they needed no change.

2. The kit_watch WARN "CHANGED ... a MAJOR change blocks" that still ends READY. FIXED (guide).
   Fix: new step 10.5. It says the WARN is expected from mc2-v2.5 on; the snapshot (knowledge/fingerprints/qc.json copied in step 6) is from 25 Oct, kit head 5574d77e, and the PL changed the kit after it (4 Nov); a WARN never stops the loop; "a MAJOR change blocks" is about task work (templates, rules, FIX_MAP), not the upgrade; it clears after the master classifies the change with knowledge/KIT_CLASSIFY_PROMPT.md, Ayush gives his word and the master runs kit_watch.py save. Step 12.2 and 11.5 point to 10.5. NEXT.md item 2 says the same.
   Files: delivery/README.md, opencode_handoff/NEXT.md.
   Proof: the e2e4 preflight at mc2-v2.5.1 showed exactly this WARN and "VERDICT: READY", as the text now says. Snapshot date and head read from the old folder's qc.json (generated_ist 2026-10-25T13:15+05:30, git_head 5574d77e).

3. The 9 test_upgrade_tools skips. FIXED.
   Fix: the skip text now reads "needs real harness job folders (jobs/ and Tasks_INPUT/ from real harness runs on the Mac; the clone of INSTALL guide step 5 does not bring them, so this skip is expected); missing: ...". Guide step 11.3 says the 9 skips happen with or without step 5 and that "OK (skipped=9)" is expected. Also the DATA skip texts in test_upgrade_tools.py and test_issue_lint.py now name INSTALL step 6 (the DATA copy), not step 7.
   Files: master_chat_tasks/tools/tests/test_upgrade_tools.py, tools/tests/test_issue_lint.py, delivery/README.md.
   Proof: in ROOT at mc2-v2.5.2 with the harness clone in place, test_upgrade_tools.py -v shows the new text and ends "OK (skipped=9)".

4. Dry precheck passes from mc2-v2.3 with settings.local.json naming a known bundle. FIXED (guide).
   Fix: step 9 now says the recheck is run by the newest upgrade.py, which reads settings.local.json at every tag, so with step 9 done the dry precheck passes from mc2-v2.3 on; at mc2-v2.1 and mc2-v2.2 it stays WAIT (the fixed kit path in that precheck.sh). Step 11.4 refers to it.
   Files: delivery/README.md.
   Proof: the e2e4 recheck after mc2-v2.5.1 to mc2-v2.5.2 shows "PASS dry precheck on a known bundle ... PRECHECK CLEAN" with only settings.local.json naming the bundle. The mc2-v2.3 claim rests on the W1-048 logs (recheck PASS at mc2-v2.3, 2.4, 2.5); not rerun here.

5. State card label instead of a NOTE. FIXED (guide).
   Fix: step 5 ("If you skip this step") and step 11.2 now say precheck.sh, kit_watch.py and issue.py print a NOTE line, and the state card prints no NOTE about the kit but labels its line "QC KIT (old folder kit)" in STATE_CARD.md.
   Files: delivery/README.md.
   Proof: state_card.py line 110 sets the tag "QC KIT (old folder kit)"; W1-048 log shows line 23 of STATE_CARD.md with that label.

6. kit_watch.py cut names in the middle. FIXED.
   Fix: new name_list() in kit_watch.py: whole names up to about 120 characters, then "and n more"; the first name is always whole. The plain hash fallback in state_card.py (it cut at 200 characters) does the same and now gives the file count.
   Files: master_chat_tasks/tools/kit_watch.py, tools/state_card.py, new test test_name_list_never_cuts_a_name in tools/tests/test_kit_watch.py.
   Proof (e2e4 ROOT at mc2-v2.5.2): kit_watch.py card and STATE_CARD.md line 23 now read "QC KIT: CHANGED 8 files (01_Instruction_QC.md, 02_Data_Solution_QC.md, 03_Tests_QC.md, 04_Judge_QC.md, 05_Alignment_Integrity_QC.md and 3 more); ...". Before (mc2-v2.5.1 in the same ROOT): "... 05_Alignment_Integrity_QC.md, Final_checkl)".

7. issue.py QC rounds warning. FIXED.
   Fix: "{n} QC rounds already in v3, cap 2 (sha, ...)".
   Files: master_chat_tasks/tools/issue.py, new test test_qc_cap_names_the_real_count in tools/tests/test_issue_mc2.py (5 QC rows give "5 QC rounds already in v3, cap 2 (q000000, ...)").
   Proof: test_issue_mc2.py 12 tests OK in W and in ROOT.

8. upgrade.py old folder kit lookup honours --old. FIXED.
   Fix: Layout tries --old first, then settings upgrade.old_root, and takes the first that holds the kit.
   Files: master_chat_tasks/tools/upgrade.py, new test test_kit_fallback_honours_old in tools/tests/test_upgrade_mc2.py (old_root unset, and old_root pointing nowhere).
   Proof (e2e4, harness moved out of ROOT, settings old_root "/Users/mac/Desktop/Terminal Bench" not reachable, no old_root in settings.local.json): the new upgrade.py preflight --old "$OLD" printed "ROOT has no Terminal_2.0_Harbor_Harness/Input_Bundle_QC: the old folder's kit is used (read only) ..." and ended VERDICT: READY with the commands. W1-048 got WAIT and no commands in this case. Without --old it still says kit_watch WAIT (and BLOCKED for the copied live rows), as before. The harness was moved back afterwards.

9. RESUME.md and QUESTIONS.md. Done by the master; not touched here.

OTHER FILES
opencode_handoff/NEXT.md (title, item 1 loop to mc2-v2.5.2, item 2, item 7), opencode_handoff/AGENTS.md (EDITS AND GIT item 1: tags mc2-v2.0 to mc2-v2.5.2), opencode_handoff/SETUP_STEPS.md (step 5: now mc2-v2.5.2; the example fix release is now mc2-v2.5.3). START_PROMPT.md and COMPACT_PROMPT.md name no version. upgrade.py header says Release mc2-v2.5.2.

CHECKS
1. Self tests in W (Python 3.13, no DATA): all 12 files OK (test_e3_e6_tools skipped 3, test_issue_lint skipped 3, test_upgrade_tools skipped 23 for missing DATA and harness).
2. Bundle E/mc2.bundle built from W with mc2-v2, mc2-stable and the eight tags mc2-v2.0 to mc2-v2.5.2; git bundle verify: "The bundle records a complete history".
3. ROOT = E/Desktop/mc2_root cloned from that bundle through zsh -f -i (env -i, PATH /usr/bin:/bin, empty HOME), guide steps 3 to 6 and 9 with paths mapped, checked out at mc2-v2.5.1; old folder copied from W1-048's e2e3. Logs: E/_log/*.in and *.out.
4. Upgrade mc2-v2.5.1 to mc2-v2.5.2: NEWEST extraction, backup, preflight --old "$OLD" ended VERDICT: READY; the printed block (10 lines) pasted as is into zsh -f -i after setopt interactivecomments: git status empty, fetch silent, before-mc2-v2.5.2 tag, checkout, recheck "VERDICT: WAITING" exit 3 with no FAIL (cold test WAIT, dry precheck PASS). recheck --cold-result pass ended "VERDICT: UPGRADE GOOD" with git branch -f mc2-stable mc2-v2.5.2 (not pasted). Next preflight: "UP TO DATE: ROOT runs mc2-v2.5.2". git status --porcelain empty throughout.
5. Self tests in ROOT at mc2-v2.5.2 with DATA and harness: all 12 files OK (test_carry_over 6, test_dockfree 5, test_e3_e6_tools 7 skipped 3, test_issue_lint 7, test_issue_mc2 12, test_kit_watch 6, test_minor_decisions 2, test_regression_check 5, test_state_card 11, test_upgrade_mc2 10, test_upgrade_tools 23 skipped 9, auto test_auto 75).
6. py_compile of all 38 tracked Python files: OK in W and in ROOT.
7. template_check.py: "TOTAL templates 14 conflicting lines 0 ... manifest problems 0", exit 0, in W and ROOT.
8. Secret scan (AWS, GitHub, Anthropic, OpenAI, Slack, Google keys, private key blocks, key or token assignments; the pattern was checked to catch planted samples): 0 hits in the commit diff, in all tracked files, in git log --all -p of ROOT, in delivery/README.md, the two s3_sample files and opencode_handoff/. Nothing secret was copied.
9. The old folder copy in E was not written (diff -rq against the e2e3 source: no difference).

LEFT FOR THE MASTER
Rebuild delivery/mc2.bundle from W (mc2-v2, mc2-stable and the eight tags). The guide and NEXT.md now say mc2-v2.5.2 is the newest, so they only hold once the new bundle is in place.
