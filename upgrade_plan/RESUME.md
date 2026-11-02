RESUME CARD FOR THE UPGRADE SESSION

Last updated: 3 Nov 2026 04:08 IST. Claude updates this card after every step that changes the plan state.

WHO AND WHAT
Ayush is upgrading his "master chat" system (master_chat_tasks/ records and tools, master_chat_work/ session outputs) that builds Harbor 0.24 evaluation tasks. This session is the planning session for that upgrade. Repo: Ayush-dvplr/master-task-chat. Branch: claude/youthful-feynman-zug0uq. Planning folder: upgrade_plan/.

GOAL (README.md "GOAL OF THE TASK SYSTEM"; read it every time)
Ayush must produce many tasks. Each must pass the current QC kit, be solvable from what it ships (DR3), be new (never a copy of an old task or of one teammate task), and make Opus 5 score under the gate: today tests under 85, rubric under 85, final under 40, but the gate is a changeable setting (DR2). Focus: levers and wordings that make Opus lose points while QC passes. Solvability is a QC check (DS-21, F0e, CL-10). Count caps: QC minimum, soft 70, hard 100 (Q75). Claude's boundary: README GOAL item 7, not objected to.

RULES THAT ALWAYS APPLY
1. Edit nothing outside upgrade_plan/ until Ayush types the exact word PROCEED. Even then, only changes both are 100% sure of.
2. Commit and push only upgrade_plan/, only to the branch above.
3. Never assume a rule in the records is correct (UNVERIFIED_RULES.md). Ask, do not assume.
4. R_FLAG: flag Ayush when an answer looks wrong or contradicts the records, settings or an earlier answer; cross question until clear.
5. Record Ayush's answers word for word in ANSWERS.md; update statuses in QUESTIONS.md.
6. R_RECORDS lifted 3 Nov (Q61): records are read through helpers. DR1: tokens free while building, finished system must be token light (Q62).
7. Writing style for Ayush: no dashes or hyphens, no bold, italic or # headings, all contractions expanded ("do not", "it is").
8. Use the date command (TZ=Asia/Kolkata) for every time written.
9. WORKING MODEL: this session is the upgrade master and stays light. Heavy reading goes to helpers per WORKERS.md (W1 helper via Agent tool, W2 cloud session, W3 prompt for Ayush on the Mac). Workers are read only and self check; the master spot checks cited lines before storing; contradictions go to Ayush. Log every worker in WORKER_LOG.md.
10. R_REPOS: push only to this repo and branch, never to any other repo. R_QC_UPSTREAM: the QC kit changes upstream; the system must handle major and minor changes. R_SUGGEST: AYUSH_SUGGESTIONS.md. R_QL: self added QC rules are verified with Ayush or queued in QL_QUESTIONS.md.

READ ORDER AFTER COMPACTION
1. This card.
2. README.md (process rules, file index).
3. PROBLEMS.md (P1 to P11), AYUSH_SUGGESTIONS.md, CONFLICT_REVIEW.md.
4. QUESTIONS.md: read the status of every question; work from the OPEN and FOLLOW UP ones.
5. The last two entries of ANSWERS.md (each entry starts with "ENTRY n."; use grep -n "^ENTRY" to find them).
6. WORKERS.md and WORKER_LOG.md (any helper with status running must be checked first).
7. When the next step is the conflict review, also open tmp/W1-002/CONFLICTS.md. Open FINDINGS.md, CONTRADICTIONS.md, UNVERIFIED_RULES.md, PLAN.md, REQUESTS.md or inputs/ only when the next step needs them.

WHERE WE ARE
1. Problems: P1 to P11 recorded (P11 static research prompts). Suggestions S1 to S8 in AYUSH_SUGGESTIONS.md. Priority order = the order Ayush wrote them, compaction (P1) first (Q34).
2. P1 cause, strong evidence: the DCP plugin (Dynamic Context Pruning) has run 258 compressions in the master session, keeping only about 4 to 5% as summary (FINDINGS F1.8). Native auto compaction is off. compaction-rules.js does not cover DCP.
3. Mac: 32 GiB, 10 cores. Docker Desktop VM 15.6 GiB, 8 CPUs. Claude's reading (UNVERIFIED, Q16 and Q17 parked): waiting comes from dockfree counting task.toml limits, not real use. Ayush wants a background script (no AI tokens) that manages Docker room dynamically; AI can see it and start or stop it (Q51).
4. Root folder today "Terminal Bench" for all sessions; Ayush plans a new root (Q84). Teammate tasks are the main knowledge source (Q80, Q85). Master: one saved opencode session named "Master Task Chat" on Opus 5.5 (model stays per session). Sisyphus (oh my openagent) is the default agent of every opencode session. Task sessions (build, QC, fix): Ayush pastes prompts by hand into opencode GPT Sol 6.1, opencode Opus 5.5, or Codex. Subagents (Q57): fine in principle; avoided for cost and because they default to Claude and fail in GPT sessions when the Claude limit is used up (F6.7).
5. P9 means (b): fixing works, designing new tasks is weak (Q38).
6. Ayush pastes the recovery prompt in this same session after compaction (Q52).
7. P4 hardening: there is no method yet; it must hide levers, avoid leaks, pass QC, keep oracle 1 and nop 0, and more (Q20). Proposed first step: a verified constraint list (Q61).
8. Helpers: W1 and W2 allowed, no limit (Q58, Q62); report only, full findings in tmp/ with sha8 ids (Q59); W3 prompts go to opencode GPT Sol 6.1 with a no subagents line (Q60).
9. Nothing outside upgrade_plan/ has been edited. PROCEED not given.

KNOWN FROM RECORDS (max about 1 KB; each fact with its source file)
1. Copy is complete to about 3 Nov 00:45 IST; 3 sessions were running then (tmp/W1-003, Q1).
2. After compaction the master loses format and process rules, not task facts (lessons.jsonl lines 89 and 100).
3. 27 Oct hang: 3 orphan Python solvers on the host (about 185 GB, swap full), plus other apps, wrong Docker settings and VMware (feedback.jsonl line 21, Q65b).
4. Gate: tests under 85, rubric under 85, final under 40 (confirmed Q66; a score of exactly 85 fails). Harness model is Opus 5; the master chat runs Opus 5.5. Counts: QC minimum, soft 70, hard 100 (Ayush's own rule). P12 v5 active, push = 1 run on frozen bytes (confirmed Q65d).
5. 182 hardening rules, 44 conflicts (tmp/W1-002).
6. The 2 days of tests 100 after an upgrade = 31 Oct and 1 Nov: misread rule levers lost to careful Opus (Q65e).
7. Ayush's pushed inputs (QC reports, QC kit, harness queue, _runs, dcp.jsonc, PL generator) are on origin/main, not this branch: read with git show origin/main:<path> or a read only worktree (F12.1). Kit drift since 25 Oct: 05_Alignment_Integrity_QC.md and Final_checklist.md changed (F12.2).

NEXT STEPS (in this order)
1. W1-005 done and verified: kit change MAJOR only because of C6 (one finding, one id), 8 MINOR, no bundle rework (FINDINGS F12.4, QL2). Conflict review started: CONFLICT_REVIEW.md (CR1 asked). Live: Q83, Q84, Q85, CR1.
2. Conflict review (CONFLICT_REVIEW.md, decisions recorded there): continue with tmp/W1-002/CONFLICTS.md, going through its 5 most serious conflicts with Ayush one at a time (C3 timeouts, C5 careful program, C25 with C6 how much may be written, C1 parking, C2 with C22 carriers), then the rest.
3. Q4 (how to review UNVERIFIED_RULES), then UNVERIFIED_RULES.md batch 1 with Ayush.
4. Shape PLAN.md, P1 (compaction) first, then the order in PROBLEMS.md.
5. Recovery prompt: prompts/RECOVERY_PROMPT.md, cold tested twice (W1-001, W1-004).
