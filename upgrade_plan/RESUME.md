RESUME CARD FOR THE UPGRADE SESSION

Last updated: 5 Nov 2026 11:55 IST (opencode session on the Mac, after ENTRY 110; the opencode session is the only writer of this branch and of mc2-v2; the cloud session writes neither)

WHO AND WHAT
Ayush is upgrading his "master chat" system (master_chat_tasks/ records and tools, master_chat_work/ session outputs) that builds Harbor 0.24 evaluation tasks. This session plans that upgrade. Repo Ayush-dvplr/master-task-chat, branch claude/youthful-feynman-zug0uq, planning folder upgrade_plan/. Ayush's inputs (QC kit, QC reports, harness queue, _runs, PL generator, teammate tasks anubis-stage-2/) are on origin/main: read them with git show origin/main:<path>, never merge.

GOAL (README.md "GOAL OF THE TASK SYSTEM"; read it)
GOAL IN ONE LINE (agreed G1): make more and more accepted tasks the way teammates make them (QC passed, under the gate, solvable, new); traps are one tool. Learn all of it from teammates: levers, design shapes, test structure, rubric style, size, pace (G3). Conflicts: case by case, never voided automatically (G2). TOP PRIORITY: fix, rebuild and harden tasks, and create new hard tasks under the gate. Problems P1 to P12 matter because they block this. Each task must pass the current QC kit, be solvable from what it ships (DR3), be new (never a copy of an old task or of one teammate task), and make Opus 5 score under the gate: today tests under 85, rubric under 85, final under 40, a changeable setting (DR2). Count caps: QC minimum, soft 70, hard 100 (Ayush's own rule). Agreed line (README GOAL item 7): hide traps from the solving agent; never make a real defect look valid to QC.

RULES THAT ALWAYS APPLY
1. STAGE A is approved (PROCEED, ENTRY 89), built as mc2-v2.0 to mc2-v2.5.3 and installed in ROOT (mc2-stable at mc2-v2.5.3, 5 Nov 00:32). STAGE B needs a second PROCEED. Outside upgrade_plan/ only the mc2 worktree (/Volumes/ayush_prsnl/mc2_worktree) and the repo root .gitignore (ENTRY 99) are changed by the session; ROOT is changed only by Ayush running the printed commands; main and the old Mac folder never.
2. Commit only upgrade_plan/ (and .gitignore), only on this branch (R_REPOS: never any other repo). The session never pushes; it prints the push command and Ayush runs it.
3. Never assume a rule in the records is correct. Ask, do not assume. R_FLAG: flag answers that conflict.
4. Record Ayush's answers word for word in ANSWERS.md; update QUESTIONS.md.
5. Style: no dashes or hyphens, no bold, italic or # headings, contractions written out. Times from TZ=Asia/Kolkata date.
6. This session stays light: heavy reading goes to helpers (WORKERS.md), each logged in WORKER_LOG.md; the master spot checks before storing.
7. Other rules: R_QC_UPSTREAM (kit classes LENIENT, MINOR, MAJOR), R_SUGGEST (AYUSH_SUGGESTIONS.md), R_QL (QL_QUESTIONS.md), DR1 (tokens free while building, finished system token light).

READ ORDER AFTER COMPACTION
0. In opencode on the Mac: upgrade_plan/opencode_handoff/AGENTS.md (session rules) and NEXT.md (what is left). Open item files: reports/DATA_PRODUCT_TRIAGE.md (waiting question). INSTALL_LOG.md only when a step needs install history.
1. This card, then LESSONS.md (mistakes of this session and what each changed).
2. README.md.
3. PROBLEMS.md, AYUSH_SUGGESTIONS.md, CONFLICT_REVIEW.md, RULE_REVIEW.md.
4. QUESTIONS.md first 30 lines (LIVE NOW and the parked lists).
5. The last two entries of ANSWERS.md (grep -n "^ENTRY" ANSWERS.md).
6. WORKER_LOG.md, and if a card run is in progress, tmp/S2-CARDS/CARD_RUN.md (it says how to continue).
7. Only when the next step needs them: STAGE2_STUDY_PLAN.md, PLAN.md, FINDINGS.md, tmp/W1-002/CONFLICTS.md, CONTRADICTIONS.md, UNVERIFIED_RULES.md, REQUESTS.md, inputs/.

RUNNING NOW
5 Nov 2026 01:35 IST, opencode session on the Mac (only writer of this branch and of mc2-v2). Full install history: INSTALL_LOG.md (read only when needed).
1. STAGE A is INSTALLED: ROOT /Users/mac/Desktop/mc2_root at mc2-v2.5.3 (8ad18ec5), recheck UPGRADE GOOD 5 Nov 00:32, mc2-stable at mc2-v2.5.3. ROOT origin = this planning clone (one time set-url done). The new master runs in ROOT/master_chat_tasks; the old master issues nothing new (ENTRY 107). Planning branch pushed to 57071b53.
2. mc2 worktree: /Volumes/ayush_prsnl/mc2_worktree, branch mc2-v2. Commit 9718df83 on top of mc2-v2.5.3 (README parts E and B in text code blocks, .omo/ in .gitignore; ENTRY 107, 110) is NOT tagged; next tag mc2-v2.5.4 when Ayush says, then a normal round in ROOT (it should not block: the two Mac test bugs are fixed in v2.5.3). Tag mc2-v2.5.3 was moved once (ENTRY 106); never again without a new exception.
3. Every system change: made here (worktree, tests, lightweight tag), then Ayush runs the round in ROOT (backup, preflight, printed commands, recheck). The new master only does task work.
4. DATA-PRODUCT (data-product-config-compiler, stage qc_pass, frozen tree 2ad86997ab52): HANDED OVER to the new master (ENTRY 113): TS-26 and JD-14 triage, harden or not, paid run S460 are decided there; the QL QC before the paid run is gone by the new ORDER. JD-16 KEEP (ENTRY 109). Reference: reports/DATA_PRODUCT_TRIAGE.md.
5. QC kit: classified in the new master (board d11f933, KIT_CLASSES: MAJOR, accepted ENTRY 113); follow ups applied and snapshot qc_48726eb7 saved 5 Nov 08:13 (with a text copy).
6. Open after these: six questions of ENTRY 99 (lever label glossary; Template line warn or refuse; kit snapshot save; STAGE B blockers and PROCEED; Q140; the 5 TO BE CONFIRMED facts in TECHNICAL.md), the old harness clone's local edit to scripts/package_rfp_bundles.py and the untracked "Input Bundle Generator New/ayush sah tasks/" (not in ROOT), state card size (7.6 KB, above the 6 KB target, under 8 KB hard), G1 task half (no DCP notice in a task session at ROOT), PL1 reading ("minors must be fixed") against the JD-16 keep.
6a. Ayush is starting the new master (steps and prompts given 5 Nov about 01:45: part B, today's goal, kit classify prompt, task sessions in ROOT, part E then /dcp-compress then part B, JD-16 record command). Checked what the master raises by itself: reports/MASTER_GAPS.md. WAITING: (a) add the gaps (task session folder, compression reminder, TS-26 and JD-14, kit evidence workaround) to the master's rules or card in mc2-v2.5.4; (b) whether the data-product decisions move to the new master. LESSONS.md has 8 entries (ENTRY 111).
6b. 5 Nov 08:16: ROOT is not clean. The ROOT master edited RULES_IN_FORCE.md (02:28, ORDER without QL QC before the paid run) and 7 knowledge and template files (08:13, kit 48726eb7 follow ups; kit snapshot saved) on Ayush's word in the master. The next round stops at git status until this is settled. QUESTION A and B answered option 1 (ENTRY 112, 08:21); ROOT diff saved as reports/root_edits_20261105T0821.patch (sha256 f468065e), applies cleanly to the worktree. ENTRY 113: ORDER without QL QC stands (data-product item 3 gone), kit change MAJOR accepted, data-product decisions handed to the new master (items 2 and 4 and S460 are the master's now), new change: handoff sha cell "<sha> . new" or ". old". ENTRY 114, 115: new or old cell decided (old shows "<sha> . old (<window>)", no rename line in old prompts, master decides with issue.py --same-session, shown everywhere). mc2-v2.5.4 TAGGED dd7e147b (on 98c33185; ENTRY 116: settings card.hard_kb 9, the two live rows keep the plain sha, nothing more). WAITING: reports/OLD_SYNC.md (ENTRY 117; Ayush stops using the old system after a complete resync: carry data-product (paid run done 09:50, final 84.69 = tests 100, rubric 69.39, gate missed) and Nikhil multi-tenant rows, 6 jsonl lines, data-product bundle copy; the old folder is never deleted; paid runs stay in the old harness until STAGE B). Then the ROOT round when 31c1a08 and 0e4f7f9 are done: backup, check ROOT diff still sha256 f468065e, git checkout the 8 files, preflight, printed commands, recheck. Until the round is done the master must not edit system files. LESSONS.md entry 9.
7. Helpers: none running. W1-050 and W1-051 done and verified. Next free helper id: W1-052.
History, cloud session: STAGE A BUILT and fixed: tags mc2-v2.0 to mc2-v2.5 plus fix releases mc2-v2.5.1 and mc2-v2.5.2 (W1-047, W1-049; mc2-v2.5.1 W1-047, 26 problems from the W1-046 end to end check) on branch mc2-v2; mc2-stable at mc2-v2.0; delivered as upgrade_plan/delivery/mc2.bundle (GitHub refused new branches from this session). INSTALL guide: upgrade_plan/delivery/README.md. W1-048 second end to end check: 0 breaks, 9 small issues; fixed as mc2-v2.5.2 (W1-049, ENTRY 93); bundle rebuilt. OPENCODE IS THE ONLY WRITER of mc2-v2 from 4 Nov (ENTRY 94): this cloud session never changes the mc2 worktree or the bundle again. Also ready: upgrade_plan/triage/ (P19), BOOK.md and TECHNICAL.md. READY for Ayush to install on the Mac (delivery/README.md) and continue in opencode (opencode_handoff/). STAGE B needs its blockers and a second PROCEED.

STATE OF THE WORK (3 Nov)
1. Teammate study (anubis-stage-2 on main): 68 of 108 tasks studied (55 light cards, 3 pilot, 10 from 2 Nov). Families: tmp/S2-CARDS/SUMMARY.md. Design guide: knowledge/PATTERNS.md; check against R0: knowledge/CONFIRM.md (durable copies of tmp/W1-025). Queue of all teammate tasks: tmp/S2-CARDS/QUEUE.txt. QUEUE batches B11 to B24 stay PAUSED (Ayush, credits); do not start them. The case by case review of the DEFECT families is paused (reason in CONFLICT_REVIEW.md PAUSE NOTE); do not restart it without Ayush.
2. Rule review batch one (R1 to R35) DONE: decisions in RULE_REVIEW.md (ENTRY 40 to 43). R28 KEEP (ENTRY 67).
3. P1 compaction drafts in drafts/P1/: master.dcp.jsonc (manual), tasks.dcp.jsonc (off), README_P1.md (how files reach each session, path check), state_card.py v2 (tested, CARD_TEST.md), RULES_IN_FORCE.md (one layer from the rule review), sample_STATE_CARD.md (5.9 KB).
4. PROCEED for STAGE A given (ENTRY 89). Outside upgrade_plan/ only the mc2 worktree (scratchpad) was changed; main and the Mac folders never.

DECISIONS SO FAR (short; details in the named files)
1. Compaction (P1): master DCP manual (Q98), task sessions DCP off (Q99); master starts from master_chat_tasks/ (Q108); protected files list accepted (Q109).
2. Order: task making first, system fixes in parallel (Q87).
3. QC pass = 1 complete QC pass (ENTRY 57, 58 replace the 2 runs rule of Q95, R18): fails left must be false positives proven by review; minors and warnings are fine; real fails block. CL false positive: Q129.
4. Levers: CR1 timeout extra by default; CR6 amended field needs one deciding doc sentence; CR7 misread rule lever allowed as primary with one clear deciding sentence; R25 primary lever from PATTERNS.md families, 40 percent, fires in most hidden inputs; R30 a size bound may be stated for a runtime lever.
5. Rubric: every criterion traces to an instruction sentence (Q106).
6. No caps on rounds (Q114). Gate 85, 85, 40 as a setting (R26). Never commit or push in any repo from the task system (R34).
7. Root later: one git folder with master_chat_tasks, master_chat_work, QC and anything needed (Q84).

KNOWN FROM RECORDS (short)
1. After compaction the master loses format and process rules, not task facts (lessons.jsonl lines 89 and 100).
2. 27 Oct Mac hang: 3 orphan Python solvers on the host (about 185 GB) plus other apps and VMware.
3. 2 days of tests 100 (31 Oct and 1 Nov): misread rule levers lost to careful Opus.
4. 182 hardening rules and 44 rule conflicts in the records (tmp/W1-002/CONFLICTS.md C1 to C44; not the CONTRADICTIONS.md C1 to C6).

NEXT STEPS (in order)
1. Card budget settled (Q117 to Q119, ENTRY 44 to 46): 8 KB hard, 6 KB target, 6.3 KB accepted; settings in drafts/P1/settings.json.
2. Card points are in state_card.py v2 (done 12:20); registry design field planned (after PROCEED).
3. P1 steps 3 to 5 drafted (drafts/P1/MASTER_RECOVERY.md, FOLD_PLAN.md); Q8, Q120, Q121 answered (ENTRY 48); W1-027 fold table and W1-028 cold test verified; waiting for Q122 to Q125. Then the next system fixes: P2 QC fix regression gate, P3 Docker slot script (S1), P10 old templates, S7 QC kit watch, P6 tools.
3a. Fold review done (T1 to T46 and A1 to A13, ENTRY 51 to 59; drafts/P1/FOLD_DECISIONS.md); rules split into RULES_IN_FORCE.md and BUILD_RULES.md (Q131).
4. Conflict review CR2 to CR5 DONE (ENTRY 61 to 63). Other W1-002 conflicts: many settled by the fold; map the rest later.
5. Then shape PLAN.md into the final plan for Ayush to approve before PROCEED.
6. Before a compaction: prompts/COMPACT_PROMPT.md. Recovery: prompts/RECOVERY_PROMPT.md.
