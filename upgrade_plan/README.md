UPGRADE PLAN FOR THE MASTER CHAT SYSTEM

Started 3 Nov 2026, 01:19 IST. Planning only.

STATUS: PLANNING. NOTHING OUTSIDE THIS FOLDER IS EDITED.

GOAL OF THE TASK SYSTEM (Ayush, 3 Nov 2026, ANSWERS.md ENTRY 11 and 12; heading agreed, Q73)
0a. GOAL IN ONE LINE (agreed G1, ENTRY 30): make more and more accepted tasks the way teammates make them: each passes QC, scores under the gate, is solvable from what it ships, and is new (not a copy). Traps and levers are one tool for that, next to volume, speed, design shapes and test structure.
0c. LEARN FROM TEAMMATES (G3): traps and levers, design shapes, test structure, rubric style, task size, and pace.
0b. CONFLICTS (ENTRY 29, G2): conflicts between teammate practice, Ayush's rules (including DR3) and Claude's line are decided case by case with Ayush; nothing is voided automatically; in each case Claude says plainly whether it can help build it.
0. TOP PRIORITY (ENTRY 19): the system exists to fix, rebuild and harden existing tasks, and to create new hard tasks that score under the gate. Problems P1 to P12 matter because they block this.
1. Ayush's job is to produce many tasks. His count is low now, so the system must make tasks fast and reliably.
2. Score target on the harness (Opus 5): today tests under 85, rubric under 85, final under 40 (gate v3.7). The gate is a SETTING, not a fixed rule: the PL may lower it (for example final under 30 or 35) and the system must follow a change in one place (DR2).
3. Every task must pass the current QC kit. Ayush's PL and QL said a task that passes QC is acceptable.
4. HARD REQUIREMENT (DR3): every task is solvable. With enough time, an agent can solve it using only what the task ships (instruction, docs, data, environment). It does not matter whether the agent actually passes every test or criterion; it must be possible.
5. Focus: learn which levers, wordings and designs make Opus lose points while the task still passes QC, including what teammates do, and build them in.
6. Uniqueness: measured against Ayush's own tasks. Every build is new, never a copy of an old task. A task must also never be a close copy of one teammate task (an approach may be reused).
7. The agreed line (ENTRY 23): hiding a trap from the SOLVING AGENT is normal task design (hidden test data, no trap announcement, which the kit itself requires under IN-17). Every trap must still meet what each QC check asks for: solvable from what the task ships, every graded value decided by the shipped instruction and data, no underspecified grading. Claude helps with the first and with meeting the checks; Claude does not help make a real defect look valid to the QC.
8. Every upgrade decision is checked against this goal.
9. Solvability is also a QC check (DS-21, F0e, CL-10 "solvable from visible files"). SOLVABILITY_PROMPT, Ayush's extra check, used only if the QL asks: "Read only the prompt in instruction.md and the artifacts in environment/ except for Dockerfile and check if the all the things requested by prompt are completely solveable or not, if an agent is given more than enough time and resources."
10. Count caps (Ayush, ENTRY 13; Q75: hard cap 100 is his own rule): tests and rubric criteria each at least the QC minimum, personal soft cap 70, hard cap 100. Settings, like the gate.

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
7b. DR2 (Q66): score gates are one setting, changeable in one place. DR3 (Q67): every task must be solvable from what it ships.
8. After compaction or in a new session, Claude follows RESUME.md before anything else.
8a. R_REPOS (Ayush, 3 Nov): Claude pushes only to this repo (Ayush-dvplr/master-task-chat, branch claude/youthful-feynman-zug0uq). Never push to any other repo, including the PL's QC repo.
8b0. Kit change classes (Q86, agreed): LENIENT (QC only gets easier; act freely), MINOR (stricter or reworded, no effect on fix mapping or hiding), MAJOR (affects fix mapping, hiding or traps).
8b. R_QC_UPSTREAM (Ayush, 3 Nov): the PL updates the Input Bundle QC kit often, in his repo "terminal bench 2.0" (Terminal_2.0_Harbor_Harness). Ayush keeps snapshots (knowledge/fingerprints). The upgraded system must detect a kit change and classify it. MINOR = a leniency or a lenient new rule that does not affect how fixes map to QC checks, how hidden information and traps stay hidden. MAJOR = anything that does affect those. Today an agent decides which (Q69).
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
2. PROBLEMS.md: the problems (P1 to P12 so far) in Ayush's words, plus any new problems he adds.
3. FINDINGS.md: what Claude found in the repo for each problem, with file and line evidence.
4. QUESTIONS.md: every question, with id and status.
5. ANSWERS.md: Ayush's answers word for word, with date and time.
6. UNVERIFIED_RULES.md: existing rules from the records that affect the upgrade, each waiting for Ayush to verify, change or drop.
7. CONTRADICTIONS.md: places where the current records disagree with each other.
8. REQUESTS.md: material Claude needs from Ayush (repos, uploads, opencode output, Docker settings).
9. WORKERS.md: how helper sessions of this upgrade are used and verified. WORKER_LOG.md: one row per helper. reports/: full helper reports. prompts/: prompts for Ayush to paste on the Mac.
9c. STAGE2_STUDY_PLAN.md: plan for studying the teammate tasks (anubis-stage-2 on main).
9e. RULE_REVIEW.md: KEEP, CHANGE or DROP per rule, batch by batch; builds RULES_IN_FORCE.md.
9b. CONFLICT_REVIEW.md: decisions on the hardening rule conflicts, one by one.
9f. PL_QUESTIONS.md: 30 questions for the PL and QL in plain words (P15), ready to send.
9a. AYUSH_SUGGESTIONS.md: Ayush's suggestions and their status. QL_QUESTIONS.md: questions queued for the QL.
9d. drafts/: draft files for each fix (P1 first). Nothing in drafts/ is applied before PROCEED.
10. inputs/: material Ayush gave (RQ3 and RQ4 output pasted in chat on 3 Nov, saved by Claude).
11. PLAN.md: the old draft fix per problem. PLAN_FINAL.md: the final plan for Ayush's approval before PROCEED.

What Claude has seen so far
This repo (master_chat_tasks/, master_chat_work/ at 10d3e3ff) plus Ayush's inputs on origin/main: Input_Bundle_QC, QC reports, harness queue, _runs, PL generator, opencode_dcp, anubis-stage-2 (teammate tasks). Not seen: the Mac itself, transcripts.
