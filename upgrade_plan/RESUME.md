RESUME CARD FOR THE UPGRADE SESSION

Last updated: 3 Nov 2026 09:40 IST. Claude updates this card after every step that changes the plan state. Times are IST.

WHO AND WHAT
Ayush is upgrading his "master chat" system (master_chat_tasks/ records and tools, master_chat_work/ session outputs) that builds Harbor 0.24 evaluation tasks. This session plans that upgrade. Repo Ayush-dvplr/master-task-chat, branch claude/youthful-feynman-zug0uq, planning folder upgrade_plan/. Ayush's inputs (QC kit, QC reports, harness queue, _runs, PL generator, teammate tasks anubis-stage-2/) are on origin/main: read them with git show origin/main:<path>, never merge.

GOAL (README.md "GOAL OF THE TASK SYSTEM"; read it)
TOP PRIORITY: fix, rebuild and harden tasks, and create new hard tasks under the gate. Problems P1 to P12 matter because they block this. Each task must pass the current QC kit, be solvable from what it ships (DR3), be new (never a copy of an old task or of one teammate task), and make Opus 5 score under the gate: today tests under 85, rubric under 85, final under 40, a changeable setting (DR2). Count caps: QC minimum, soft 70, hard 100 (Ayush's own rule). Agreed line (README GOAL item 7): hide traps from the solving agent; never make a real defect look valid to QC.

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
3. PROBLEMS.md, AYUSH_SUGGESTIONS.md, CONFLICT_REVIEW.md.
4. QUESTIONS.md first 30 lines (LIVE NOW and the parked lists).
5. The last two entries of ANSWERS.md (grep -n "^ENTRY" ANSWERS.md).
6. WORKER_LOG.md, and if a card run is in progress, tmp/S2-CARDS/CARD_RUN.md (it says how to continue).
7. Only when the next step needs them: STAGE2_STUDY_PLAN.md, PLAN.md, FINDINGS.md, tmp/W1-002/CONFLICTS.md, CONTRADICTIONS.md, UNVERIFIED_RULES.md, REQUESTS.md, inputs/.

RUNNING NOW
1. Layer D light cards: 95 tasks in tmp/S2-CARDS/QUEUE.txt; batches B01 to B03 started 09:34 (helpers W1-009 to W1-011). Continue with tmp/S2-CARDS/CARD_RUN.md. B01 to B03 done and verified; B04 to B06 running (W1-014 to W1-016). Next free helper id: W1-017.

DECISIONS SO FAR (short)
1. P1 compaction cause: the DCP plugin on defaults (pushes compression from 100k tokens, about 10 percent of the 1 million window; nothing protected, not even Ayush's messages). Decided: master DCP B (manual), task sessions DCP C (off). DCP 3.2.0 reads a per folder .opencode/dcp.jsonc and OPENCODE_CONFIG_DIR (FINDINGS F1.8 to F1.10, PLAN.md P1).
2. Order: task making first, system fixes in parallel (Q87).
3. CR1 timeouts: extra lever by default, main lever only with Ayush's word (CONFLICT_REVIEW.md).
4. QC working definition: no fail in 2 runs in a row, any CL fail blocks, minor accepted if it does not repeat; plus a false positive review after each QC result (Q95).
5. Pilot cards: in 2 of the 3 pilot cards the main loss was a DEFECT (oracle bug, unreadable program file), not levers; light cards mark DEFECT or DESIGN first (Q100).
6. New root later: one git folder with master_chat_tasks, master_chat_work, QC and anything needed (Q84).
7. Gate per category: none (Q94). Work mostly on tests (rubric already low).

KNOWN FROM RECORDS (short)
1. After compaction the master loses format and process rules, not task facts (lessons.jsonl lines 89 and 100).
2. 27 Oct Mac hang: 3 orphan Python solvers on the host (about 185 GB) plus other apps and VMware.
3. 2 days of tests 100 (31 Oct and 1 Nov): misread rule levers lost to careful Opus.
4. Fix template in use: P12_recheck_fix v5. Push needs 1 harness run on frozen bytes.
5. 182 hardening rules, 44 conflicts (tmp/W1-002).

NEXT STEPS (in order)
1. Keep the card run going (CARD_RUN.md) and update Ayush after every 3 batches.
2. In parallel: conflict review CR2 (tmp/W1-002/CONFLICTS.md C5, the careful program), then CR3 to CR5.
3. Then the UNVERIFIED_RULES review (Q4 first), then Layer F patterns, then shape PLAN.md.
4. Recovery prompt: prompts/RECOVERY_PROMPT.md (version 3), cold tested four times (W1-001, W1-004, W1-012, W1-013).
