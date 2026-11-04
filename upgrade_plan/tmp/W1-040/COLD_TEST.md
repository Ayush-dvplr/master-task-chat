COLD TEST OF PLAN_FINAL.md (W1-040, 4 Nov 2026)

Read only PLAN_FINAL.md and the GOAL OF THE TASK SYSTEM section of README.md. Linked paths checked with ls only. Reading as Ayush, the owner, before PROCEED.

1. WHAT CHANGES FOR AYUSH DAY TO DAY

Master chat: I start the master with "oc mc2-master" from ROOT/master_chat_tasks, not from the old folder. It reads a small generated state card (under 8 KB) instead of the 100 KB read order. DCP is manual in the master and off in task sessions. After a compaction there is a recovery prompt; if the rules block is not kept by DCP, I paste it once per session myself.
Building a new task: two sessions. Stage 1 writes a design pack (design card) in WORK/ and has to reach DESIGN READY; stage 2 is a fresh session that builds from a fixed skeleton. Families are picked in a fixed order (D2, D1, D8, D5, D6, D9, D3, D4 extra, D7 never); a failed card moves to the next family. Research prompts fill an idea queue I approve.
QC and fixes: every QC fail goes through a fix map, then a regression check that makes sure the lever survives (90 percent). I mark false positives myself in a QL triage table. A pass means one complete QC pass where only proven false positives remain; minors and warnings are fine.
Paid runs: they run through dockslot (a blocking Docker queue, paid jobs first, QC fast lane) once it is measured and switched on; until then dockfree stays. Outside trajectories count as the gate run only on Opus 5 with the exact QC passed bytes.
Auto mode: same AUTO_POLICY A1 to A13 but limits come from settings, mc2 names, Codex steps, paid runs wrapped in dockslot. Switched last.
Tools and models: one steps block in settings.json chooses model and runner per step. Default oc-opus-5.5, blinds oc-opus-5, Codex Sol 6.1 for research and read only work. issue.py refuses retired templates and takes --runner; intake.py takes three kinds of outside work. Upgrades are done with upgrade.py (backup, preflight, printed git commands, recheck, printed rollback). The old "Terminal Bench" system keeps running beside it untouched.

2. THE ROLLOUT

Order (section F): 0 create ROOT and copy DATA, 1 settings and rules, 2 state card, recovery and DCP config, 3 templates, 4 fix map and regression scripts, 5 kit snapshot and kit_watch, 6 tool changes (this one migrates DATA), 7 dockslot installed but not used, measurement, 8 manager switched to dockslot, 9 two stage build with one pilot task, 10 auto mode.
How I check: each step names a check (preflight PASS, card size and cold recovery test, template_check exit 0 and reading one issued prompt, regression check flags a known lost lever, kit_watch unchanged, tools/tests and an intake dry run, dockslot idle and peaks CSV, kill test and two runs together, pilot reaches DESIGN READY, auto smoketest and one short auto run). upgrade.py runs preflight before and recheck after.
How I go back: mostly "previous tag" by git checkout of the old tag, which I type from the printed commands. Exceptions: step 0 delete ROOT; step 2 also remove DCP files; step 5 point qc.json back at the archive; step 6 previous tag plus records restore from backup; step 7 dockslot.py stop; step 8 set docker.manager back to dockfree.

3. WHAT AYUSH DOES BY HAND ON THE MAC, IN ORDER

a. Pick the ROOT name and confirm system id mc2; create ROOT next to "Terminal Bench"; set up its git (not described how); copy DATA once; run upgrade.py backup.
b. For every step: run upgrade.py, then type the printed git commands (status, fetch, tag current, checkout new tag), then the recheck; on fail type the printed rollback.
c. Step 2: place the two dcp.jsonc files and ROOT/opencode.jsonc, check the opencode config merge (Q78, kiro off), start the master with oc mc2-master, check /dcp shows manual, check a task session shows no DCP notice, paste the cold recovery prompt and report pass or fail, run one dry precheck on a known QC passed bundle.
d. Step 3: read one issued prompt.
e. Step 5: say the word and save the kit snapshot with text.
f. Step 7: run MEASURE.md (Q19) and save the peaks CSV.
g. Step 8: kill test, one oracle and one nop together, fast lane test.
h. Give "proceed" for the master_queue.py harness edit (R35) once it is designed.
i. Step 10: one short auto run beside the old system.
j. Ongoing: daily backup, paste the rules block if DCP drops it, send PL_QUESTIONS and bring back the answers (RQ11), watch DCP off cost for one week, never run the same task in both systems.

4. HOW THE PLAN SERVES EACH GOAL ITEM

QC pass: P2 fix map and regression check, P12 one complete pass definition, P10 retired templates cannot come back, kit_watch catches kit changes. Served, but the P12 definition leans on my own false positive marking (see 6).
Under the gate: P4 primary lever from teammate families, P9 family order, regression check keeps the lever. The gate as one setting (DR2) is not named in the plan; only "limits from settings". Weakly shown.
Solvable from what ships (DR3): stated as absolute in J7(d); P16 step leak rules; table says yes almost everywhere. No step in the rollout checks solvability itself.
New: P9 design flow, WHY_NEW_FAILS, idea queue. How uniqueness is measured against my tasks and against teammate tasks (README item 6) is not said.
Volume and speed: dockslot (more jobs at once), smaller reads, upgrade safety. The two stage build adds a session per task; its speed cost is not discussed.
Learn from teammates: P8 PATTERNS.md from 68 of 108 tasks; 40 not studied (J4).
Token light (DR1): state card, per step context, TOKENS.md estimate 406k to 184k first reads; measured only after rollout.
The agreed line: quoted in A and kept absolute in J7(d). The table marks every part "yes", even Docker and system ids, which says nothing.

5. UNCLEAR, VAGUE, CONTRADICTORY, OR BROKEN LINKS

Links checked with ls. Everything under P1D, T/W1-030 to W1-039, UP/knowledge, inputs/ and reports/ exists. Problems:
a. "Decision coverage: CHECK.md maps ENTRY 40 to 83 to these sections." No upgrade_plan/CHECK.md. Files exist at tmp/W1-039/CHECK.md and tmp/W1-028/CHECK.md; the plan does not say which.
b. "S3 kit snapshots with a text copy in knowledge/fingerprints/" Not in UP/knowledge (which the plan uses for PATTERNS.md); it exists only as master_chat_tasks/knowledge/fingerprints. Path base not stated.
c. "TESTED (CARD_TEST.md, cold test W1-028)" and "TESTED with fake capacity (TEST.md T1 to T5)" give no folder; they exist at P1D/CARD_TEST.md and T/W1-031/TEST.md.
d. "Files: BUILD_RULES.md, FIX_MAP.md" (P4) and "FIX_MAP.md into knowledge/" (F1): which knowledge folder, UP or ROOT/master_chat_tasks.
e. "Statuses: DRAFTED ..., TESTED ..., WAITS AYUSH, WAITS MAC." but the plan also uses "DECIDED", "in use", "TESTED dry", "Q140 later". Undefined statuses.
f. "each step one tag, check, rollback" but step 0 has no tag, and the plan never says how ROOT's git repo is created or what the first tag is.
g. "Rollback: point qc.json back at the archive." Which archive.
h. "Rollback: previous tag plus records restore (this step migrates DATA)." Restore from which backup, by which command.
i. "Rollback: previous tag; DCP files removed." versus G7 "By hand on the Mac: place the two dcp.jsonc files" and C2 "Git versions ... opencode and DCP config". Are DCP files placed by git checkout or by hand.
j. "10. Auto mode: ... paid runs wrapped in dockslot." versus F "master_queue.py adaptation (... the dockslot wrap and the task name guard not designed ...)" and J6 lists it as not blocking. Step 8 and 10 depend on something not designed.
k. "ROOT/.opencode/dcp.jsonc ... nearest file wins" stated as fact, while G3 marks the opencode merge UNVERIFIED (Q78). The DCP layering is not marked UNVERIFIED.
l. "S5 subagents: Codex research yes, opencode GPT never" versus G5 "GPT prompts say strictly do not run subagents (R32), added by the adapter". If GPT is never used, which GPT prompts.
m. "lever keeps 90 percent" (P2): 90 percent of what.
n. "primary lever from PATTERNS families, 40 percent (R25)" (P4): 40 percent of what.
o. "first reads about 406k to 184k tokens per task" reads as a range; probably a reduction.
p. "8 KB hard, 6 KB target (..., long sessions only reported)" unclear what is only reported.
q. "DONE in any case" (P6) unclear.
r. "Check: template_check exit 0 including SYSID" SYSID undefined. "Rollback: previous tag (P2 v5 route)" undefined.
s. "a day's compression count is only Ayush's" (G7) unclear.
t. "S9 runner record: four runners" the four are not named.
u. Rule ids are not explained anywhere in the plan: CR1 to CR7, R25, R28, R30, T1 to T46, T25, BR-SL1 to BR-SL4, CL-1 to CL-10, A1 to A13, IN-17, D1 to D9. A cold reader cannot judge them.
v. Goal check table has no row for P8, P12, P14, P15; P8 and P12 are central to the goal.
w. "System id mc2 (proposed)" and "ROOT (name to confirm)" are open, but steps 0 and 3 need them.

6. RISKY DECISIONS OR RULES AYUSH MAY NOT HAVE MEANT

a. "One complete pass; fails left only proven false positives; ... CL false positive passes" with "Ayush judges false positives from a triage table". README item 3 says a task must pass the current QC kit. A task with remaining fails counted as passed on my own judgment may be rejected by the QL.
b. "misread rule lever allowed as primary (CR7, Q111)". A lever built on the solver misreading a rule sits close to the agreed line and DR3; it needs a clear test that the rule is still decided by the shipped instruction.
c. "0. Ayush creates ROOT, copies DATA once from the old system" while the old system keeps running. From then on there are two registries, boards and pending.db. Which one is the source of truth for my task count is not said.
d. "the same task never runs in both systems at once (UNVERIFIED guard, Mac check)". The only protection is a standing rule and my memory; a slip lets the harness queue remove the other system's containers.
e. "teammate_agreed ... An outside task counts for Ayush only on his word". Counting fixed teammate tasks is sensitive; even with the PL's oversight, it should need the PL's agreement too, not only mine.
f. "J5 The DEFECT family review is paused; W1-002 conflicts C3 to C44 not yet mapped" while BUILD_RULES is listed as DRAFTED for step 1. README 0b says conflicts are decided case by case with me; 42 are undecided.
g. "J. OPEN ITEMS THAT DO NOT BLOCK APPROVAL" includes master_queue.py adaptation and Q78, which steps 2, 8 and 10 depend on. Approving the plan approves steps whose key part is not designed.
h. "DCP off measured one week" and "usage limits are the pain, no cheaper models" accept a possible cost rise in task sessions with no stated threshold to revert.
i. "Every trap must still meet what each QC check asks for" with a "more lenient kit (487b4697)" classified LENIENT; the plan relies on CL-1 to CL-10 staying absolute but PL answers (RQ11) may still change BUILD_RULES after approval as "a new small release, not a block".

7. VERDICT

I could approve the direction and steps 0 to 5 as written: they are low risk, each has a check and a rollback, and the old system is untouched. I would not approve steps 6 to 10 yet.
Before approving, change: fix the CHECK.md and fingerprints paths and give full paths for CARD_TEST.md and TEST.md; define every status and the rule ids used; say how ROOT's git is created and what the first tag is; settle ROOT name and mc2; name the archive and backup used in steps 5 and 6; say whether DCP files come from git or by hand; mark the DCP layering UNVERIFIED; move master_queue.py adaptation and Q78 into blockers for steps 8 and 10; state which system's DATA is the truth after the copy; restate the P12 QC pass rule so a task is not counted as passed while real fails remain; decide CR7 and the C3 to C44 conflicts with me before BUILD_RULES goes live; add rows for P8 and P12 to the goal check; explain "90 percent" and "40 percent".
