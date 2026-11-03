RESUME CARD FOR THE UPGRADE SESSION

Last updated: 3 Nov 2026 15:35 IST. Claude updates this card after every step that changes the plan state. Times are IST.

WHO AND WHAT
Ayush is upgrading his "master chat" system (master_chat_tasks/ records and tools, master_chat_work/ session outputs) that builds Harbor 0.24 evaluation tasks. This session plans that upgrade. Repo Ayush-dvplr/master-task-chat, branch claude/youthful-feynman-zug0uq, planning folder upgrade_plan/. Ayush's inputs (QC kit, QC reports, harness queue, _runs, PL generator, teammate tasks anubis-stage-2/) are on origin/main: read them with git show origin/main:<path>, never merge.

GOAL (README.md "GOAL OF THE TASK SYSTEM"; read it)
GOAL IN ONE LINE (agreed G1): make more and more accepted tasks the way teammates make them (QC passed, under the gate, solvable, new); traps are one tool. Learn all of it from teammates: levers, design shapes, test structure, rubric style, size, pace (G3). Conflicts: case by case, never voided automatically (G2). TOP PRIORITY: fix, rebuild and harden tasks, and create new hard tasks under the gate. Problems P1 to P12 matter because they block this. Each task must pass the current QC kit, be solvable from what it ships (DR3), be new (never a copy of an old task or of one teammate task), and make Opus 5 score under the gate: today tests under 85, rubric under 85, final under 40, a changeable setting (DR2). Count caps: QC minimum, soft 70, hard 100 (Ayush's own rule). Agreed line (README GOAL item 7): hide traps from the solving agent; never make a real defect look valid to QC.

RULES THAT ALWAYS APPLY
1. Edit nothing outside upgrade_plan/ until Ayush types the exact word PROCEED; even then only changes both are 100% sure of.
2. Commit and push only upgrade_plan/, only to this branch (R_REPOS: never any other repo).
3. Never assume a rule in the records is correct. Ask, do not assume. R_FLAG: flag answers that conflict.
4. Record Ayush's answers word for word in ANSWERS.md; update QUESTIONS.md.
5. Style: no dashes or hyphens, no bold, italic or # headings, contractions written out. Times from TZ=Asia/Kolkata date.
6. This session stays light: heavy reading goes to helpers (WORKERS.md), each logged in WORKER_LOG.md; the master spot checks before storing.
7. Other rules: R_QC_UPSTREAM (kit classes LENIENT, MINOR, MAJOR), R_SUGGEST (AYUSH_SUGGESTIONS.md), R_QL (QL_QUESTIONS.md), DR1 (tokens free while building, finished system token light).

READ ORDER AFTER COMPACTION
1. This card.
2. README.md.
3. PROBLEMS.md, AYUSH_SUGGESTIONS.md, CONFLICT_REVIEW.md, RULE_REVIEW.md.
4. QUESTIONS.md first 30 lines (LIVE NOW and the parked lists).
5. The last two entries of ANSWERS.md (grep -n "^ENTRY" ANSWERS.md).
6. WORKER_LOG.md, and if a card run is in progress, tmp/S2-CARDS/CARD_RUN.md (it says how to continue).
7. Only when the next step needs them: STAGE2_STUDY_PLAN.md, PLAN.md, FINDINGS.md, tmp/W1-002/CONFLICTS.md, CONTRADICTIONS.md, UNVERIFIED_RULES.md, REQUESTS.md, inputs/.

RUNNING NOW
W1-032 running (P10, S7). Next free helper id: W1-033. P3 dockslot verified with fast lane (tmp/W1-031/). P2 fix map draft verified (tmp/W1-030/). Fold review done (drafts/P1/FOLD_DECISIONS.md).

STATE OF THE WORK (3 Nov)
1. Teammate study (anubis-stage-2 on main): 68 of 108 tasks studied (55 light cards, 3 pilot, 10 from 2 Nov). Families: tmp/S2-CARDS/SUMMARY.md. Design guide: knowledge/PATTERNS.md; check against R0: knowledge/CONFIRM.md (durable copies of tmp/W1-025). Queue of all teammate tasks: tmp/S2-CARDS/QUEUE.txt. QUEUE batches B11 to B24 stay PAUSED (Ayush, credits); do not start them. The case by case review of the DEFECT families is paused (reason in CONFLICT_REVIEW.md PAUSE NOTE); do not restart it without Ayush.
2. Rule review batch one (R1 to R35) DONE: decisions in RULE_REVIEW.md (ENTRY 40 to 43). R28 KEEP (ENTRY 67).
3. P1 compaction drafts in drafts/P1/: master.dcp.jsonc (manual), tasks.dcp.jsonc (off), README_P1.md (how files reach each session, path check), state_card.py v2 (tested, CARD_TEST.md), RULES_IN_FORCE.md (one layer from the rule review), sample_STATE_CARD.md (5.9 KB).
4. Nothing outside upgrade_plan/ has been edited. PROCEED has not been given.

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
