UPGRADE PLAN FOR THE MASTER CHAT SYSTEM

Started 3 Nov 2026, 01:19 IST. Planning only.

STATUS: PLANNING. NOTHING OUTSIDE THIS FOLDER IS EDITED.

AYUSH'S GOAL (3 Nov 2026, ANSWERS.md ENTRY 11; flags Q66 to Q68 still open)
1. Target: tasks that score on the harness (Opus 5) under 40% overall, with neither tests nor rubric above 80%. (FLAG Q66: the records say tests under 85, rubric under 85.)
2. Every task must pass the QC kit.
3. Make many tasks, the way teammates do. An approach may be reused; a whole task may not be the same as a teammate's task, or it gets flagged. (FLAG Q68: GOALS G9 only checks uniqueness against Ayush's own registry.)
4. Ayush says it is not possible to make Opus 5 fail by the "legit process" alone, and that his goal is not a 100% genuine task, but the score. (FLAG Q67: what this allows is not yet agreed.)
5. Claude's boundary, stated 3 Nov: Claude helps make tasks hard and QC passing in the way the QC kit intends (hidden test data, scale, carrier variation, exact bars, honest judges). Claude does not help design a task to hide a defect from the QC kit, the PL or the QL, for example an unsolvable or underspecified grading made to look valid. Where a request crosses that line, Claude says so.
6. Every upgrade decision is checked against this goal.

The edit rule (Ayush, 3 Nov 2026)
1. No file outside upgrade_plan/ is created, edited, moved or deleted until Ayush types the exact word PROCEED.
2. Even after PROCEED, a change is made only when both Ayush and Claude are 100% sure of it.
3. Only this folder is committed and pushed, to branch claude/youthful-feynman-zug0uq.
4. No existing rule in master_chat_tasks or master_chat_work (the "avoid this, avoid that" rules, QC rules, caps, limits) is treated as correct until Ayush verifies it. See UNVERIFIED_RULES.md.
5. Style (Ayush preference): no dashes or hyphens, no bold, italic or # headings, contractions written out, in chat and in these files. Exact names and ids keep their own spelling (oh-my-openagent, W1-001).
5a. Claude asks; Claude does not assume. Anything not verified is marked UNVERIFIED.
6. R_FLAG (Ayush, 3 Nov): Claude must flag Ayush when an answer looks wrong, or contradicts the records, the settings, or an earlier answer, and cross question until it is clear.
7. R_RECORDS (Ayush, 3 Nov): most answers already exist in the master_chat_tasks records (decisions, lessons, status, logs). Lifted 3 Nov (Q61): Claude reads them through helpers and checks them before asking Ayush.
7a. DR1 design requirement (Q62): tokens are not limited while building this upgrade, but the finished system must be light on tokens in daily use.
8. After compaction or in a new session, Claude follows RESUME.md before anything else.
8a. R_REPOS (Ayush, 3 Nov): Claude pushes only to this repo (Ayush-dvplr/master-task-chat, branch claude/youthful-feynman-zug0uq). Never push to any other repo, including the PL's QC repo.
8b. R_QC_UPSTREAM (Ayush, 3 Nov): the PL updates the Input Bundle QC kit often, in another repo. Ayush keeps snapshots (knowledge/fingerprints). The upgraded system must detect a kit change, tell major from minor, and adjust levers and fixes for it.
8c. R_SUGGEST (Ayush, 3 Nov): Ayush's suggestions go to AYUSH_SUGGESTIONS.md. Each is discussed; none is assumed; a suggestion may be dropped if it is not possible.
8d. R_QL (Ayush, 3 Nov): QC rules Ayush added himself (for example "the test count may exceed the QC cap and still pass") are not trusted. Each is verified with Ayush or queued in QL_QUESTIONS.md for the QL; the QL's answer is verified before it is used.
9. WORKING MODEL (Ayush, 3 Nov): this session is the upgrade master. Heavy reading goes to worker sessions (WORKERS.md): helpers Claude starts itself, separate cloud sessions, or prompts Ayush pastes on the Mac. Every worker self checks; the master verifies before storing; contradictions go to Ayush.

How we work
1. Claude writes questions in QUESTIONS.md, each with an id (Q1, Q2 ...) and a status.
2. Ayush answers in chat. Claude copies each answer word for word into ANSWERS.md and updates the question status.
3. When Claude needs a file, folder, setting or upload, it goes into REQUESTS.md. Ayush adds the material to the repo, pushes, and tells Claude.
4. For opencode settings, Claude writes a prompt in REQUESTS.md; Ayush pastes it into opencode and brings back the output.
5. PLAN.md only holds approaches that are drafts until every question they depend on is answered and Ayush approves that section.

Question and rule statuses
OPEN: asked, no answer yet.
ANSWERED: Ayush answered; Claude has recorded it.
VERIFIED: Ayush confirmed the recorded answer or rule is right.
FOLLOW UP: the answer raised a new question (the new id is noted).
DROPPED: Ayush said it does not matter.
LATER: Ayush will answer later.
PARKED: waits for the records to be read or for its problem to be planned (see the top of QUESTIONS.md).
Running, done, verified, rejected: statuses for helpers in WORKER_LOG.md.
All times are IST.

Files
0. RESUME.md: the recovery card. Read first after any compaction or in a new session. Kept current after every step.
1. README.md: this file. Rules of the planning process and the index.
2. PROBLEMS.md: the problems (P1 to P10 so far) in Ayush's words, plus any new problems he adds.
3. FINDINGS.md: what Claude found in the repo for each problem, with file and line evidence.
4. QUESTIONS.md: every question, with id and status.
5. ANSWERS.md: Ayush's answers word for word, with date and time.
6. UNVERIFIED_RULES.md: existing rules from the records that affect the upgrade, each waiting for Ayush to verify, change or drop.
7. CONTRADICTIONS.md: places where the current records disagree with each other.
8. REQUESTS.md: material Claude needs from Ayush (repos, uploads, opencode output, Docker settings).
9. WORKERS.md: how helper sessions of this upgrade are used and verified. WORKER_LOG.md: one row per helper. reports/: full helper reports. prompts/: prompts for Ayush to paste on the Mac.
9a. AYUSH_SUGGESTIONS.md: Ayush's suggestions and their status. QL_QUESTIONS.md: questions queued for the QL.
10. inputs/: material Ayush gave (RQ3 and RQ4 output pasted in chat on 3 Nov, saved by Claude).
11. PLAN.md: the draft fix for each problem. Not approved.

What Claude has seen so far
This repo only: master_chat_tasks/ and master_chat_work/ at commit 10d3e3ff ("Work till now").
Not seen: the harness repo (Terminal_2.0_Harbor_Harness, including scripts/master_queue.py), the QC kit (Input_Bundle_QC), the generator, opencode config, Docker settings, chat transcripts.
