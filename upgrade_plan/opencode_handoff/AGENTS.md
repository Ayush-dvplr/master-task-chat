UPGRADE SESSION RULES (for opencode, Opus 5.5, on Ayush's Mac). Read this whole file first, every session and after every compression.

WHO AND WHAT
1. You continue the upgrade of Ayush's master chat system (master_chat_tasks/, master_chat_work/) from the cloud planning session. Planning folder: upgrade_plan/ in Ayush's clone of the repo master-task-chat, branch claude/youthful-feynman-zug0uq.
2. State lives in files, never in chat: upgrade_plan/RESUME.md first, then the read order it lists.
3. The goal, word for word, is in upgrade_plan/README.md "GOAL OF THE TASK SYSTEM". The agreed line (README GOAL item 7) always applies: hiding a trap from the solving agent is normal task design; every trap must still meet each QC check (solvable from what ships, every graded value decided by the shipped instruction and data); never help make a real defect look valid to QC.

HOW YOU WORK WITH AYUSH
1. Ask, do not assume. Never treat a rule in the records as correct until Ayush confirms it.
2. Ask with options: each question names what it decides, gives 2 to 4 options with one line on why and what the other option costs, and marks your recommendation first with "(Recommended)". When Ayush says "ask again in laymen terms" or "in plain words", ask again with an everyday example and no rule ids.
3. Flag (R_FLAG): when an answer looks wrong, contradicts the records, the settings or an earlier answer, say so plainly with the entry or file line, and cross question until it is clear. Never silently pick one side.
4. Record every answer word for word in upgrade_plan/ANSWERS.md as the next ENTRY n with the IST time (TZ=Asia/Kolkata date), then "Recorded as:" with your reading. Update the question status in upgrade_plan/QUESTIONS.md and the LIVE NOW line.
5. Conflicts between teammate practice, Ayush's rules and the agreed line are decided case by case with Ayush, never voided automatically; say plainly whether you can help build each case.
6. After each finished step update upgrade_plan/RESUME.md (RUNNING NOW, STATE, NEXT STEPS) so a fresh session can continue.

EDITS AND GIT
1. Edit freely only inside upgrade_plan/. STAGE A of the new system is approved and built (tags mc2-v2.0 to mc2-v2.5.2; install it by upgrade_plan/delivery/README.md only). If upgrade_plan/RESUME.md still says "edit nothing until PROCEED" for STAGE A, it lags: this item wins. STAGE B (rollout steps 6 to 10) needs Ayush's second approval: he types the exact word PROCEED for STAGE B. Before that, build nothing outside upgrade_plan/ and the mc2 worktree drafts.
2. Never edit the generator, the QC kit, "QC assigned/" or "my tasks/" without Ayush's "proceed" (R35). Never harbor delete. Never run generate_bundle.py --force, playground.py --model, or anything that uploads files or keys.
3. Git: you may git add and git commit inside upgrade_plan/ and inside the mc2 worktree (one writer of mc2-v2 at a time, SETUP_STEPS.md step 5; new tags are lightweight). You never push; you print the push command and Ayush runs it. Never commit secrets (~/.codex/auth.json, ~/.tb-master-key, ~/.ssh, opencode transcripts, any API key).

HELPERS (subagents)
1. Heavy reading goes to helpers. Each helper writes only in upgrade_plan/tmp/<id>/ (ids W1-046 and up, next free id in RESUME.md), self checks, and returns a short report.
2. You spot check at least one cited line of every helper report before you store its result, and log every helper in upgrade_plan/WORKER_LOG.md.
3. If a helper runs on GPT inside opencode, its prompt says "strictly do not run subagents" (R32).

STYLE (Ayush's preference, in chat and in files)
No dashes or hyphens as punctuation or list markers, no bold, italic or # headings, all contractions written out ("do not", "it is"). Numbered lists. Exact names and ids keep their own spelling.

COMPRESSION
DCP here is manual. Before Ayush compresses he pastes upgrade_plan/opencode_handoff/COMPACT_PROMPT.md; after, he pastes START_PROMPT.md. Never keep anything important only in chat.
