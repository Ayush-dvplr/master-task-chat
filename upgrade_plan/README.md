UPGRADE PLAN FOR THE MASTER CHAT SYSTEM

Started 3 Nov 2026, 01:19 IST. Planning only.

STATUS: PLANNING. NOTHING OUTSIDE THIS FOLDER IS EDITED.

The edit rule (Ayush, 3 Nov 2026)
1. No file outside upgrade_plan/ is created, edited, moved or deleted until Ayush types the exact word PROCEED.
2. Even after PROCEED, a change is made only when both Ayush and Claude are 100% sure of it.
3. Only this folder is committed and pushed, to branch claude/youthful-feynman-zug0uq.
4. No existing rule in master_chat_tasks or master_chat_work (the "avoid this, avoid that" rules, QC rules, caps, limits) is treated as correct until Ayush verifies it. See UNVERIFIED_RULES.md.
5. Claude asks; Claude does not assume. Anything not verified is marked UNVERIFIED.
6. R_FLAG (Ayush, 3 Nov): Claude must flag Ayush when an answer looks wrong, or contradicts the records, the settings, or an earlier answer, and cross question until it is clear.
7. R_RECORDS (Ayush, 3 Nov): most answers already exist in the master_chat_tasks records (decisions, lessons, status, logs). Claude reads them later, when Ayush says so (not yet), and checks them before asking.
8. After compaction or in a new session, Claude follows RESUME.md before anything else.

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

Files
0. RESUME.md: the recovery card. Read first after any compaction or in a new session. Kept current after every step.
1. README.md: this file. Rules of the planning process and the index.
2. PROBLEMS.md: the six problems in Ayush's words, plus any new problems he adds.
3. FINDINGS.md: what Claude found in the repo for each problem, with file and line evidence.
4. QUESTIONS.md: every question, with id and status.
5. ANSWERS.md: Ayush's answers word for word, with date and time.
6. UNVERIFIED_RULES.md: existing rules from the records that affect the upgrade, each waiting for Ayush to verify, change or drop.
7. CONTRADICTIONS.md: places where the current records disagree with each other.
8. REQUESTS.md: material Claude needs from Ayush (repos, uploads, opencode output, Docker settings).
9. PLAN.md: the draft fix for each problem. Not approved.

What Claude has seen so far
This repo only: master_chat_tasks/ and master_chat_work/ at commit 10d3e3ff ("Work till now").
Not seen: the harness repo (Terminal_2.0_Harbor_Harness, including scripts/master_queue.py), the QC kit (Input_Bundle_QC), the generator, opencode config, Docker settings, chat transcripts.
