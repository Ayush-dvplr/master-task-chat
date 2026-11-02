RESUME CARD FOR THE UPGRADE SESSION

Last updated: 3 Nov 2026 01:59 IST. Claude updates this card after every step that changes the plan state.

WHO AND WHAT
Ayush is upgrading his "master chat" system (master_chat_tasks/ records and tools, master_chat_work/ session outputs) that builds Harbor 0.24 evaluation tasks. This session is the planning session for that upgrade. Repo: Ayush-dvplr/master-task-chat. Branch: claude/youthful-feynman-zug0uq. Planning folder: upgrade_plan/.

RULES THAT ALWAYS APPLY
1. Edit nothing outside upgrade_plan/ until Ayush types the exact word PROCEED. Even then, only changes both are 100% sure of.
2. Commit and push only upgrade_plan/, only to the branch above.
3. Never assume a rule in the records is correct (UNVERIFIED_RULES.md). Ask, do not assume.
4. R_FLAG: flag Ayush when an answer looks wrong or contradicts the records, settings or an earlier answer; cross question until clear.
5. Record Ayush's answers word for word in ANSWERS.md; update statuses in QUESTIONS.md.
6. Do not read the master_chat_tasks records in depth until Ayush says so (R_RECORDS).
7. Writing style for Ayush: no dashes or hyphens, no bold, italic or # headings, all contractions expanded ("do not", "it is").
8. Use the date command (TZ=Asia/Kolkata) for every time written.

READ ORDER AFTER COMPACTION
1. This card.
2. README.md (process rules, file index).
3. PROBLEMS.md (P1 to P10).
4. QUESTIONS.md: read the status of every question; work from the OPEN and FOLLOW UP ones.
5. The last two entries of ANSWERS.md.
6. Open FINDINGS.md, CONTRADICTIONS.md, UNVERIFIED_RULES.md, PLAN.md, REQUESTS.md or inputs/ only when the next step needs them.

WHERE WE ARE
1. Problems: P1 to P10 recorded. Priority order = the order Ayush wrote them, compaction (P1) first (Q34).
2. P1 cause, strong evidence: the DCP plugin (Dynamic Context Pruning) has run 258 compressions in the master session, keeping only about 4 to 5% as summary (FINDINGS F1.8). Native auto compaction is off. compaction-rules.js does not cover DCP.
3. Mac: 32 GiB, 10 cores. Docker Desktop VM 15.6 GiB, 8 CPUs. Waiting most likely comes from dockfree counting task.toml limits, not real use (Q51 open).
4. Master: one saved opencode session on Opus 5.5 (model stays per session). Workers: Ayush pastes prompts by hand into opencode GPT Sol 6.1, opencode Opus 5.5, or Codex. Whether workers run the Sisyphus agent: Q56.
5. P9 means (b): fixing works, designing new tasks is weak (Q38).
6. Ayush pastes the recovery prompt in this same session after compaction (Q52).
7. Nothing outside upgrade_plan/ has been edited. PROCEED not given.

NEXT STEPS
1. Get answers to Q47 (print command), Q51 (re-explained), Q53 and Q55 (recommendations given), Q54 (cold test, re-explained), Q56.
2. Finish and verify this recovery card and prompt.
3. When Ayush allows, read the master_chat_tasks records to answer Q35 and Q39 and the questions marked IN RECORDS.
4. Go through UNVERIFIED_RULES.md batch 1 with Ayush.
5. Then shape PLAN.md, starting with P1.
