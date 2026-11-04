THE MASTER CHAT UPGRADE, A SHORT BOOK

Written 4 Nov 2026 for you, the owner of the master chat system. It tells the whole idea in plain words. The full technical detail is in upgrade_plan/TECHNICAL.md. Every decision named here is recorded word for word in upgrade_plan/ANSWERS.md.


CHAPTER 1. WHY THE UPGRADE

Your job is to make many accepted tasks. The old master chat helped, but it kept getting in the way. The everyday problems, as you listed them (upgrade_plan/PROBLEMS.md, P1 to P19):

1. The master forgot. After opencode compressed a long chat, it kept the task facts but lost the way of working, and you had to teach it again.
2. QC fixes broke things. A fix session would pass a QC check but quietly soften the trap that made the task hard, or the fix itself created two new findings.
3. Docker waited for nothing. Sessions kept polling for room on a Mac that had room, and each retry cost tokens. Once the Mac hung because three forgotten solver programs held about 185 GB with swap.
4. Hardening was guesswork. There were 182 hardening rules in the records and 44 of them clashed.
5. Tokens ran out fast. Every new master session read about 100 KB of rules before doing anything.
6. Many tools, no record of which one (Codex, opencode Claude, opencode GPT) ran which session.
7. Upgrades made things worse, and old prompt templates stayed in use after an upgrade.
8. Teammates made tasks that passed QC and scored low. Your new tasks did not, although your fixes of old tasks were fine.
9. Research prompts for deep research tools were static and went stale.
10. "QC passed" had no fixed meaning, because the AI reviewer finds different things each run.
11. Later: outside and teammate tasks (P13), versions you can go back to (P14), questions for the PL (P15), docs that leaked the exact steps (P16), old and new systems side by side (P17), a two session build instead of the PL generator (P18), and triage of old tasks (P19).

An imagined example of problem 2. Picture a task with a trap where hidden files use a rare but legal form of a date. QC asks for "every graded value decided by the shipped files". A fix session simply lists all the date forms in the docs. QC passes, but now the model reads the list and the trap is gone, and the task scores 100 on tests. The upgrade adds a fix map and a regression check so that cannot happen silently again.


CHAPTER 2. THE BIG PICTURE

Think of five places and three people.

1. The old system. The folder "/Users/mac/Desktop/Terminal Bench" on the company side of your Mac. It keeps running exactly as before. Nothing in the upgrade writes into it. Tasks already running there finish there.
2. The planning copy. /Volumes/ayush_prsnl/mc2_upgrade on your personal volume. It holds upgrade_plan/: problems, questions and answers, the final plan, drafts, and the delivery folder with the install guide and mc2.bundle.
3. The worktree. /Volumes/ayush_prsnl/mc2_worktree, next to the planning copy. It is a working copy of the new system's git branch mc2-v2. New versions of the new system are made here, and only here. Nothing runs from it.
4. The new system, called mc2. Its root folder ROOT is /Users/mac/Desktop/mc2_root, on the company side next to the old folder. It is a git clone, so every version is a tag you can move between. It has its own records, its own harness clone with the QC kit, and its own work folders.
5. The backup. A folder mc2_backup next to ROOT. Every backup run makes a new dated folder there with a copy of all records.

Git picks your personal or company account by folder, by itself, so the personal volume pushes as you and the company side stays company.

The three people and one session:

1. You decide. Every rule, every waiver, every PROCEED comes from your words.
2. The PL (project lead) owns the QC kit and the harness. The PL changes the kit often. The PL answered 30 questions on 4 Nov, and those answers are now rules.
3. The QL (quality lead) runs the final full QC on your task and sends back findings.
4. The opencode session on your Mac (Opus 5.5) continues the upgrade. From 4 Nov it is the only writer of the branch mc2-v2; the cloud planning session never changes it again, and the bundle stays frozen at mc2-v2.5.2.

Inside ROOT lives the master chat, the brain: it plans, writes prompts, sends heavy work to other sessions, checks results on disk and keeps the records. It never commits or pushes; you run every git command.


CHAPTER 3. A DAY IN THE LIFE AFTER THE UPGRADE

MORNING: THE MASTER WAKES UP LIGHT
You start the master from ROOT/master_chat_tasks. It reads one file, STATE_CARD.md, under 8 KB, which a script rewrites after every records change: rules in force, settings, the QC kit line, progress, questions for you, sessions, open items. It answers in five short lines and waits.

MAKING A NEW TASK, FROM IDEA TO PUSH
1. Idea. A domain and a data shape, for example "an event log with clocks" in security, taken from an idea queue that research prompts fill.
2. Family. It picks the main trap family by rotation, skipping the families and domains of the last 3 designs. The order comes from what worked for teammates: D2 first (a rare legal form inside a named standard), then D1 (a documented branch only hidden data fires), then D8 (carried state that never heals), D5, D6, D9, D3. D4 (a time limit on a big input) is only an extra, never the main lever.
3. Design card. One page: deliverable, shipped and hidden data, the main lever with its deciding sentence, the predicted loss, and where a careful program goes wrong. It must predict a final under 35 (gate 40 minus margin 5). If a careful program keeps 60 percent or more of the lever's points, the card is "no core" and switches family.
4. Stage 1 session writes the full design pack in WORK/ and runs a leak check: the docs must say what decides each value, never how to find it step by step. It stops at DESIGN READY and waits for your go.
5. Stage 2 is a fresh session that reads only the pack and builds the task from a clean skeleton. (This two session build is a STAGE B item; until then the one session build template P2_build_v5 is used.)
6. Precheck, oracle and nop. The oracle must score 1.0 on 2 runs and the nop exactly 0.
7. Full QC until it passes (chapter 4 has the rule).
8. Freeze. The exact bytes get a tree sha. By day, after QC pass and freeze, the master starts the one paid run itself, inside the daily budget.
9. Under the gate: Step 10 on the same frozen bytes, then you push exactly those bytes. Gate missed: harden from what the run got wrong, QC again, one new run. The same bytes are never rerun after a miss.

FIXING QC
Say QC returns DS-22 (TRUTH.md counts out of date) and TS-13 (one test checks two things). The fix session looks each up in the fix map: DS-22 is fixed by regenerating TRUTH.md by script as the last edit, TS-13 by splitting the test in two with the same total weight. Then the regression check: every changed line of tests/ is named by a fix direction, each lever's wrong reading still loses at least 90 percent of what it lost before, oracle and nop still pass, and every changed graded value still has its deciding line. Only then does QC run again.

For a QL report the master builds a triage table: each finding with the diff and the kit line. You mark the false positives; real ones are fixed.

WHICH RUN COUNTS AFTER A FIX
1. Only the solution changed: nothing to redo.
2. Tests or the judge changed: regrade the last valid run.
3. Data or the instruction changed: a new paid run.
4. task.toml changed: the master asks you.

PAID RUNS
A paid run is the harness run of the paid model (Opus 5). It counts for the gate only on exactly the frozen QC passed bytes, never runs in parallel with QC unless you say so, and the daily limits come from settings (6 a day, 2 at once).

AUTO MODE OVERNIGHT
Before bed you write a short PLAN.md and start auto mode until a set time. The master answers for you by auto/AUTO_POLICY.md: it starts sessions, sends "go", hands bundles to the harness and keeps REPORT.md current for the morning. Auto mode exists today; its upgraded form (limits from settings, paid runs through the Docker room manager) is STAGE B step 10.

HELPING A TEAMMATE'S TASK
A teammate's task, a task assigned to you, or your own outside bundle comes in through intake. Intake works on a copy, records where it came from, who wrote it and a fingerprint of the author lines, and stops any step that would change them. A teammate task needs the teammate's agreement under the PL, stored in your words. It counts for you only if you say so for that task. Then it goes through the same loop: full QC, fix map, regression check, QC again, one paid run.

For a pile of old tasks, a triage tool is being added in upgrade_plan/triage/. It reads the folder without Docker and without AI tokens and ranks which tasks are worth fixing and pushing under the gate. It also separates real scores from scores broken by verifier errors such as "permission denied", a grader crash or timeout, or a judge or API error. Example: a task shows tests 12, but every run says permission denied on the output folder. That score is broken, not real, so the task may be an easy win after a fix.


CHAPTER 4. THE RULES THAT MATTER MOST, AND WHY

THE GOAL
Make more and more accepted tasks the way teammates make them: each passes QC, scores under the gate, is solvable from what it ships, and is new. Traps and levers are one tool for that, next to volume, speed, design shapes and test structure. Every upgrade decision is checked against this line.

THE AGREED LINE
Hiding a trap from the solving agent is normal task design: hidden test data, no announcement (the kit itself asks for that, IN-17). Every trap must still meet each QC check: solvable from what ships, every graded value decided by the shipped instruction and data. Claude never helps make a real defect look valid to the QC. Example: hiding which input has the rare date form is fine. Grading a date form that no shipped file allows is a defect, and it gets fixed, not disguised.

SOLVABLE (DR3)
With enough time, an agent can solve the task from what it ships alone: instruction, docs, data, environment. It must be possible, not necessarily done. Nothing loosens this without coming to you first.

THE GATE
Today: tests under 85, rubric under 85, final under 40, on one run of the frozen QC passed bytes. It is one setting in settings.json, so if the PL lowers it to 35, one edit changes every prompt and tool.

THE ONE SLIP CAP
No single wrong reading may cost more than 50 percent of the positive test points. The client flagged a task where changing one word, emit to omit, took away 96 percent of the tests. So tests check per row or per field, and the main lever carries at least 40 percent of the weight but never more than the cap.

QC PASS, MINORS AND WARNS
One complete QC pass. Every real fail is fixed. A fail is closed only when it is truly false against the check text, with a note. An IN-17 fail you may waive. Warns are fixed, except the test count and rubric count warns. Minors: the master proposes keep or fix for each one, you decide, and your decisions are stored and reused as proposals. Then the QL runs a full QC.

OTHER NUMBERS YOU WILL MEET
Oracle runs 2. Time limit at least 2 times the reference time on a busy machine. At most 3 "what if" figure criteria per judge. Tests and rubric criteria each at least the QC minimum, soft cap 70, hard cap 100. No caps on rounds; the tools warn but never refuse.


CHAPTER 5. HOW SAFETY WORKS

VERSIONS
Every change to the new system is a git tag. mc2-v2.0 is the old system's files plus the upgrade tools. Rollout step N is mc2-v2.N. A fix release gets three numbers, like mc2-v2.5.1 and mc2-v2.5.2. Today there are eight tags, mc2-v2.0 to mc2-v2.5.2. The branch mc2-stable marks the version you trust; it stays at mc2-v2.0 until you mark a newer one good.

BACKUP
Before every step, "upgrade.py backup" copies every record into a new dated folder in mc2_backup with a sha256 manifest, and keeps a mirror of master_chat_work. A second backup on the same day never overwrites the first.

UPGRADE AND ROLLBACK
The upgrade tool never runs git itself. It checks, then prints the commands, and you paste them.
1. Preflight: settings valid, rules present, template check clean, kit watch status, the state card builds, tool self tests pass, no session running, today's backup matches. Any FAIL blocks. It also warns when a task is open in both systems.
2. You paste the printed block: git clean check, fetch, a local marker tag, checkout of the next tag, recheck.
3. Recheck: settings, card, template check, the cold recovery test (you paste a prompt into a fresh master and report pass or fail) and a dry precheck on a known QC passed bundle. It ends UPGRADE GOOD, WAITING or RECHECK FAILED.
4. On failure it prints the rollback: checkout of the older tag, its recheck and, only if records changed, a restore from the backup (dry run first).

OLD AND NEW SIDE BY SIDE
1. Everything new carries the system id mc2 plus a short hash per run: containers, run folders, locks under /tmp/mc2/, session titles.
2. The same task never runs in both systems at once, because the harness queue removes containers by task name. The upgrade tool and the state card warn about it; a real guard in the harness is a STAGE B item.
3. Tasks already running in the old system finish there; carry_over.py then copies their results into the new records once. From day one only the new records count.

NOTHING TOUCHES THE OLD FOLDER
The install copies data out of it once and then only reads it. In the second end to end check, 1567 files had the same checksums before and after.


CHAPTER 6. WHAT IS DONE AND WHAT IS LEFT

STAGE A IS DONE
You typed PROCEED on 4 Nov. In order: mc2-v2.0 (old files plus the upgrade tools), mc2-v2.1 (one settings file, the rules, the fix map), mc2-v2.2 (state card, compact and restore prompts, DCP files), mc2-v2.3 (template manifest, fill tokens, refusal of retired templates, mc2 names), mc2-v2.4 (regression check, minor decisions), mc2-v2.5 (kit watch), then fix releases mc2-v2.5.1 and mc2-v2.5.2 after two end to end checks (26 problems, then 9 small ones and no breaks). All of it is in upgrade_plan/delivery/mc2.bundle with the install guide upgrade_plan/delivery/README.md.

STAGE B WAITS
It needs its blockers closed and a second PROCEED:
1. The paid run wrap: a change to the harness queue script so paid runs go through the Docker room manager and a task open in the other system is refused (harness code, so it needs your "proceed").
2. Whether a project opencode config can switch off a plugin your global config turns on (Q78).
3. The Mac measurement of real Docker sizes (Q19).
4. A short design of steps 6 to 10 that you read and approve.
STAGE B then brings the tool changes (runner record, outside intake, research prompts), the Docker room manager dockslot, the two session build and the upgraded auto mode.

OPEN ITEMS THAT DO NOT BLOCK
1. Install STAGE A on the Mac and run the checks only the Mac can do: the cold recovery test, the DCP layering, real harness and Docker runs.
2. Classify the 4 Nov kit change and save the new kit snapshot on your word.
3. Two small decisions: a glossary or rename for old lever labels in templates, and whether a prompt without a "Template:" line should warn or be refused.
4. Six old intake tasks to classify (Q140), 40 teammate tasks not yet studied (paused), and one week of measuring DCP off in task sessions.
5. The triage tool for old teammate or assigned tasks, being added now in upgrade_plan/triage/.


CHAPTER 7. GLOSSARY (ONE PAGE)

1. Lever: the thing in a task that makes the paid model lose points while the task stays fair. Example: hidden files use a rare but legal form of a named standard.
2. Trap: one concrete place where a lever bites, such as one hidden input that fires a documented branch. Traps are hidden from the solving agent, never from QC.
3. Gate: the score bar a task must stay under on its paid run. Today tests under 85, rubric under 85, final under 40. A setting.
4. QC: the PL's quality check kit (Input_Bundle_QC), run by an AI reviewer. It returns fails, warns and minors by check id, such as DS-22 or IN-17.
5. QL: the quality lead, who runs the last full QC and answers QC questions.
6. PL: the project lead, who owns the QC kit, the harness and the rules for what is accepted.
7. Bundle: one task folder: instruction.md, environment/, solution/, tests/, task.toml.
8. Trajectory: the record of a harness run: what the model did and the score of each check, in folders like Run N/verifier/reward-details.json.
9. Oracle: the reference solution shipped in solution/. It must score 1.0 on every run.
10. Nop: a run that does nothing. It must score exactly 0, which proves no test pays for free.
11. DCP: the opencode plugin that compresses chat context. Manual in the master (you paste the compact prompt, compress, then paste the restore prompt); off in task sessions.
12. State card: STATE_CARD.md, the one small file a script writes so the master can recover after a compression without reading 100 KB of rules.
13. Fix map: FIX_MAP.md, one row per QC check that fires in practice: what it asks, a fix that keeps the hardness, the wording that passes, and what tends to fire next.
14. Also: freeze (record the tree sha of the exact bytes), regrade (score the last valid run again with new tests or judge), tag (one saved version).
