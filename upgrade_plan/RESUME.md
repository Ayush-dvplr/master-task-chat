RESUME CARD FOR THE UPGRADE SESSION

Last updated: 3 Nov 2026 02:45 IST. Claude updates this card after every step that changes the plan state.

WHO AND WHAT
Ayush is upgrading his "master chat" system (master_chat_tasks/ records and tools, master_chat_work/ session outputs) that builds Harbor 0.24 evaluation tasks. This session is the planning session for that upgrade. Repo: Ayush-dvplr/master-task-chat. Branch: claude/youthful-feynman-zug0uq. Planning folder: upgrade_plan/.

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

READ ORDER AFTER COMPACTION
1. This card.
2. README.md (process rules, file index).
3. PROBLEMS.md (P1 to P10).
4. QUESTIONS.md: read the status of every question; work from the OPEN and FOLLOW UP ones.
5. The last two entries of ANSWERS.md (each entry starts with "ENTRY n."; use grep -n "^ENTRY" to find them).
6. WORKERS.md and WORKER_LOG.md (any helper with status running must be checked first).
7. Open FINDINGS.md, CONTRADICTIONS.md, UNVERIFIED_RULES.md, PLAN.md, REQUESTS.md or inputs/ only when the next step needs them.

WHERE WE ARE
1. Problems: P1 to P10 recorded. Priority order = the order Ayush wrote them, compaction (P1) first (Q34).
2. P1 cause, strong evidence: the DCP plugin (Dynamic Context Pruning) has run 258 compressions in the master session, keeping only about 4 to 5% as summary (FINDINGS F1.8). Native auto compaction is off. compaction-rules.js does not cover DCP.
3. Mac: 32 GiB, 10 cores. Docker Desktop VM 15.6 GiB, 8 CPUs. Claude's reading (UNVERIFIED, Q16 and Q17 parked): waiting comes from dockfree counting task.toml limits, not real use. Ayush wants a background script (no AI tokens) that manages Docker room dynamically; AI can see it and start or stop it (Q51).
4. Master: one saved opencode session named "Master Task Chat" on Opus 5.5 (model stays per session). Sisyphus (oh my openagent) is the default agent of every opencode session. Task sessions (build, QC, fix): Ayush pastes prompts by hand into opencode GPT Sol 6.1, opencode Opus 5.5, or Codex. Subagents (Q57): fine in principle; avoided for cost and because they default to Claude and fail in GPT sessions when the Claude limit is used up (F6.7).
5. P9 means (b): fixing works, designing new tasks is weak (Q38).
6. Ayush pastes the recovery prompt in this same session after compaction (Q52).
7. P4 hardening: there is no method yet; it must hide levers, avoid leaks, pass QC, keep oracle 1 and nop 0, and more (Q20). Proposed first step: a verified constraint list (Q61).
8. Helpers: W1 and W2 allowed, no limit (Q58, flag Q62); report only, full findings in tmp/ with sha8 ids (Q59); W3 prompts go to opencode GPT Sol 6.1 with a no subagents line (Q60).
9. Nothing outside upgrade_plan/ has been edited. PROCEED not given.

KNOWN FROM RECORDS (max about 1 KB; each fact with its source file)
1. Copy is complete to about 3 Nov 00:45 IST; 3 sessions were running then (tmp/W1-003, Q1).
2. After compaction the master loses format and process rules, not task facts (lessons.jsonl lines 89 and 100).
3. 27 Oct hang: 3 orphan Python solvers on the host, about 185 GB, swap full (feedback.jsonl line 21).
4. Gate live: tests under 85, rubric under 85, final under 40; no count cap; P12 v5 active; push = 1 run on frozen bytes (tmp/W1-003, Q30 to Q33, unconfirmed by Ayush).
5. 182 hardening rules, 44 conflicts (tmp/W1-002).

NEXT STEPS
1. W1-002 done and verified: tmp/W1-002/CONSTRAINTS.md (182 hardening constraints), CONFLICTS.md (44). Next with it: Ayush reviews the conflicts first, then the constraints. W1-003 done and verified (one correction: 24 wrapper.log files hold an OPENAI_API_KEY, not 2). Waiting for Ayush on Q63 (secrets), Q64 (push list), Q65 (confirm answers from records). Then: go through the W1-002 conflicts with Ayush.
2. Recovery prompt: cold test W1-001 done and its gaps fixed. Use the prompt saved in prompts/RECOVERY_PROMPT.md.
3. When Ayush allows, read the master_chat_tasks records to answer Q35 and Q39 and the questions marked IN RECORDS.
4. Go through UNVERIFIED_RULES.md batch 1 with Ayush.
5. Then shape PLAN.md, starting with P1.
