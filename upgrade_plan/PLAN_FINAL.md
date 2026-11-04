FINAL PLAN OF THE MASTER CHAT UPGRADE (W1-042, 4 Nov 2026; revises W1-039 after the W1-040 cold test and ENTRY 84 and 85). Approval in two stages: STAGE A (rollout steps 0 to 5) with PROCEED now, STAGE B (steps 6 to 10) with a second approval later (section F). Nothing outside upgrade_plan/ changes before PROCEED.

PATHS. Every path starts at the repo root (the folder holding upgrade_plan/ and master_chat_tasks/). ROOT is the new root folder on the Mac (section C).

STATUSES (the only ones used):
1. DRAFTED: written and read by the master, not run.
2. TESTED: run in this planning repo; the result file is named.
3. DECIDED: agreed with Ayush, nothing written yet.
4. TO BE DRAFTED: agreed; written after PROCEED.
5. IN USE: already working today.
6. WAITS AYUSH: needs his answer or word.
7. WAITS MAC: needs a run or check on the Mac.

RULE IDS (one line each):
1. P1 to P18: Ayush's problems (upgrade_plan/PROBLEMS.md). S1 to S9: his suggestions (upgrade_plan/AYUSH_SUGGESTIONS.md).
2. Q, RQ: questions to Ayush and requests to him (upgrade_plan/QUESTIONS.md, upgrade_plan/REQUESTS.md); ENTRY n: his answer word for word (upgrade_plan/ANSWERS.md).
3. DR1 to DR3: design requirements (upgrade_plan/README.md): token light; score gate is one setting; every task solvable from what it ships.
4. R1 to R35: the master's standing rules (upgrade_plan/drafts/P1/RULES_IN_FORCE.md); R34 the system never commits or pushes; R35 a harness edit needs Ayush's "proceed".
5. T1 to T46: rule fold review items (upgrade_plan/drafts/P1/FOLD_DECISIONS.md).
6. CR1 to CR7: old conflicts decided with Ayush (upgrade_plan/CONFLICT_REVIEW.md); C1 to C44 are the raw conflicts (upgrade_plan/tmp/W1-002/CONFLICTS.md).
7. A1 to A13: auto mode rules (master_chat_tasks/auto/AUTO_POLICY.md).
8. BR-SL1 to BR-SL4: build rules against step leaks (upgrade_plan/drafts/P1/BUILD_RULES.md).
9. CL, IN, DS: check ids of the PL's QC kit; CL-1 to CL-10 client checks outrank lenient rules; IN-17 a fail the tasker may waive; DS and others are further kit checks.
10. D1 to D9: design families of teammate tasks (upgrade_plan/knowledge/PATTERNS.md).
11. PL, QL: Ayush's project lead and quality lead.

A. GOAL

GOAL IN ONE LINE (G1, ENTRY 30): make more and more accepted tasks the way teammates make them: each passes QC, scores under the gate, is solvable from what it ships, and is new (not a copy). Traps and levers are one tool for that, next to volume, speed and design.
The agreed line (ENTRY 23): hiding a trap from the SOLVING AGENT is normal task design (hidden test data, no trap announcement, as IN-17 itself requires). Every trap must still meet what each QC check asks: solvable from what ships, every graded value decided by the shipped instruction and data, no underspecified grading. Claude never helps a real defect look valid to the QC. A PL answer (RQ11) that would loosen CL-1 to CL-10, DR3 or this line comes to Ayush as a decision first.

B. WHAT CHANGES, BY PROBLEM AND SUGGESTION

1. P1 compaction. Master DCP manual, task sessions DCP off (Q98, Q99); master started from master_chat_tasks/ (Q108); generated state card, 8 KB hard, 6 KB target; a long running session shows as LONG and is only reported, never stopped; compact prompt then restore prompt (G6); rules folded and split in two (ENTRY 44 to 60). Files: upgrade_plan/drafts/P1/ (state_card.py, settings.json, RULES_IN_FORCE.md, BUILD_RULES.md, MASTER_RECOVERY.md, FOLD_PLAN.md, master.dcp.jsonc, tasks.dcp.jsonc, README_P1.md). TESTED (upgrade_plan/drafts/P1/CARD_TEST.md, upgrade_plan/tmp/W1-028/CHECK.md); DCP behaviour WAITS MAC.
2. P2 QC fixes. Fix map, not bypass (ENTRY 49, 50); regression check after every fix: each lever's wrong reading must still lose at least 90 percent of the positive test points it lost before the fix (ENTRY 69); triage table for false positives (ENTRY 66). Files: upgrade_plan/tmp/W1-030/FIX_MAP.md, upgrade_plan/tmp/W1-030/REGRESSION_CHECK.md. DRAFTED; scripts TO BE DRAFTED.
3. P3 Docker (S1). dockslot: blocking queue, room from real use, orphan hold, paid first, QC fast lane (ENTRY 68). Files: upgrade_plan/tmp/W1-031/dockslot.py, upgrade_plan/tmp/W1-031/DESIGN.md. TESTED with fake capacity (upgrade_plan/tmp/W1-031/TEST.md); sizes WAITS MAC (Q19).
4. P4 hardening. One rule layer: the primary lever comes from a PATTERNS.md family and carries at least 40 percent of the task's positive test weight (R25); CR1 to CR7, R28, R30, T1 to T46; holes only case by case. File: upgrade_plan/drafts/P1/BUILD_RULES.md. DRAFTED.
5. P5 tokens. Card instead of the 100 KB read order; per step context; no cheaper models; DCP off measured one week (ENTRY 71). First reads per task fall from about 406k to about 184k tokens (upgrade_plan/tmp/W1-033/TOKENS.md). DRAFTED.
6. P6 tools. One steps block in settings picks model and runner per step; intake reads a result status in any letter case, so "DONE" counts as done; Codex only for read only work or steps Ayush names. File: upgrade_plan/tmp/W1-033/ADAPTER.md. DRAFTED.
7. P7 safe upgrades. upgrade.py with preflight, recheck, template_check gate (ENTRY 74 to 76). Files: upgrade_plan/tmp/W1-039/upgrade.py, upgrade_plan/tmp/W1-039/UPGRADE.md. TESTED (upgrade_plan/tmp/W1-039/UPGRADE_DRY_RUN.txt).
8. P8 teammates pass. Study of 68 of 108 teammate tasks. A misread rule lever may be primary (CR7) only when one clear sentence in the shipped docs decides the rule; the stage 1 leak check and DESIGN READY check that sentence; DR3 stays absolute. Files: upgrade_plan/knowledge/PATTERNS.md, upgrade_plan/knowledge/CONFIRM.md. DRAFTED.
9. P9 new tasks. Family order D2, D1, D8, D5, D6, D9, D3; D4 only an extra; D7 never; a failed design card moves to the next family (ENTRY 72). File: upgrade_plan/tmp/W1-034/DESIGN_FLOW.md. DRAFTED.
10. P10 old templates. CURRENT.json manifest, fill tokens, issue.py refuses retired templates; the 119 typed old root paths in the 13 current templates become the [[ROOT]] fill token (Q156, part of P17). Files: upgrade_plan/tmp/W1-032/template_check.py, upgrade_plan/tmp/W1-032/P10_TEMPLATES.md. TESTED (upgrade_plan/tmp/W1-032/TEMPLATE_CHECK_OUTPUT.txt).
11. P11 research prompts (S8). Built from the knowledge files; idea queue Ayush approves. File: upgrade_plan/tmp/W1-034/research_prompt.py. TESTED (upgrade_plan/tmp/W1-034/RESEARCH_PROMPT_SAMPLES.md).
12. P12 QC pass, exact rule: one complete QC pass. A fail counts as not blocking only when Ayush marks it a false positive from the triage table (which shows the diff and the kit line), or it is an IN-17 fail he waives (kit 487b4697). Real fails are fixed. Minors and warns go to the PL as notes. The QL then reviews. The PL answers (RQ11) may adjust this rule. File: RULES_IN_FORCE.md QC PASS. DRAFTED.
13. P13 outside intake. Section H. File: upgrade_plan/tmp/W1-035/P13_INTAKE.md. DRAFTED; 6 old intake tasks WAITS AYUSH (Q140).
14. P14 versioned upgrade. Sections C and D. TESTED (dry run, B7).
15. P15 PL questions. 30 sent (upgrade_plan/PL_QUESTIONS.md). Answers WAITS AYUSH (RQ11).
16. P16 step leak. BR-SL1 to BR-SL4 and the stage 1 leak check. File: upgrade_plan/tmp/W1-037/STEP_LEAK.md. DRAFTED.
17. P17 side by side. Section E. File: upgrade_plan/tmp/W1-039/SYSTEM_ID.md. DRAFTED.
18. P18 two stage build. Stage 1 design pack in WORK/, stage 2 a fresh session from our skeleton. File: upgrade_plan/tmp/W1-034/DESIGN_CARD_TEMPLATE.md. DECIDED; skeleton and two templates TO BE DRAFTED.
19. Suggestions. S2 helper tmp folders: IN USE. S3 kit snapshot with a text copy in ROOT/master_chat_tasks/knowledge/fingerprints/ (today master_chat_tasks/knowledge/fingerprints/): DRAFTED, WAITS MAC. S4 QL queue: IN USE. S5 subagents: Codex research may use them; the GPT runner never does, so its prompts carry "strictly do not run subagents" (R32). S6 root config: sections C and G. S7 upgrade_plan/tmp/W1-032/kit_watch.py: kit 487b4697 LENIENT with one MINOR (upgrade_plan/reports/KIT_CHANGE_487b4697.md), TESTED. S9 runner record, four runners: oc-opus-5.5 (default), oc-opus-5 (blinds), codex-sol-6.1 (research, read only work), oc-gpt-sol-6.1 (only when Ayush names it); upgrade_plan/tmp/W1-035/runner_report.py TESTED on 419 old rows (upgrade_plan/tmp/W1-035/RUNNER_REPORT_SAMPLE.txt).

C. DELIVERY LAYOUT (Q141, Q142, Q145, Q152)

1. ROOT is a new folder next to the old "Terminal Bench" folder, which stays untouched. Ayush names it at step 0; nothing depends on the name, since everything reads it from settings (paths.root, [[ROOT]]). ROOT holds master_chat_tasks/, master_chat_work/, its own harness clone with Input_Bundle_QC, _runs/, SYSTEM_VERSION, .gitignore, opencode.jsonc and two .opencode/dcp.jsonc files.
2. Git (Q152). System files live on GitHub in this repo on two new branches, stable (what Ayush runs) and v2 (where versions are prepared), plus tags. Both start without history from main and never hold data. ROOT is created by cloning branch stable of this repo into ROOT. First tag mc2-v2.0 (step 0); rollout step N is tag mc2-v2.N. Claude prepares the files and prints the commands; Ayush runs every git command (R34).
3. In git: tools, templates, rules, settings, scripts, knowledge how to files, opencode config, both DCP files. Out of git (.gitignore): registry, board, pending.db, logs, decisions, lessons, auto runs, fingerprints, QC reports, master_chat_work outputs.
4. Daily backup: upgrade.py backup copies every record into BACKUP/YYYYMMDD/records/ with a sha256 MANIFEST.json and mirrors master_chat_work (changed files only). BACKUP is outside ROOT (settings upgrade.backup_dir; proposed: a folder mc2_backup next to ROOT).
5. Records truth (ENTRY 85). The new records are the truth from day 1 (step 0); no new task is issued in the old system. Tasks already running there finish there; their results are copied once into the new records by ROOT/master_chat_tasks/tools/carry_over.py (TO BE DRAFTED), which reads the old records read only and writes through the new tools. Ayush's task count comes from the new records only.

D. BUILT IN UPGRADE PROCEDURE (P14)

upgrade.py never runs git. It runs backup, then preflight: settings valid, template_check clean, kit_watch status, state card builds, tool self tests, no session running, today's backup matches; it warns when a task id is open in both systems (Q154). Any FAIL blocks; otherwise it prints the git commands (status, fetch, local tag of the current version, checkout of the new tag). Recheck: settings, state card, template_check, cold recovery test (Ayush pastes the printed prompt, reports pass or fail), dry precheck on a known QC passed bundle, dockslot status. On a failed recheck it prints the rollback: checkout of the old tag, its recheck and, only if DATA changed, an rsync of the records from today's backup (dry run first).

E. SIDE BY SIDE WITH THE OLD SYSTEM (P17, Q144, Q153, Q154)

1. System id mc2 (DECIDED, Q153) in settings and SYSTEM_VERSION, plus a hash8 per run: containers mc2-<kind>-<slug>-<hash8> with labels mc2.system and mc2.dockslot.lease; own images; run folders mc2-<step>-<ts>-<hash8>; /tmp/mc2/; ~/.local/state/mc2/; session titles start mc2. dockslot counts old containers as foreign use; nothing old is renamed or touched.
2. Standing rule (Q154): the same task never runs in both systems at once, because the harness queue removes containers by task name. upgrade.py and the state card warn. A guard in the harness is a STAGE B blocker.
3. template_check finding class SYSID: a current template that types the old root, a /tmp path, a lock folder, a container name or a run folder without mc2 or [[ROOT]].

F. ROLLOUT (lowest risk first; each step one tag, a check, a rollback)

Before STAGE A starts: a helper is mapping the old conflicts C3 to C44 now (upgrade_plan/tmp/W1-041/MAP.md); the ones Ayush's recorded decisions do not settle come to him in one batch, and his answers go into BUILD_RULES.md before step 1.

STAGE A, approved now with PROCEED.
0. mc2-v2.0: old system files unchanged plus SYSTEM_VERSION, .gitignore, upgrade.py, carry_over.py. Ayush creates stable, v2 and the tag, clones stable into ROOT, copies DATA once, runs upgrade.py backup, then carry_over.py. Check: preflight PASS, registry_check clean. Rollback: delete ROOT; the old system never changed.
1. mc2-v2.1: settings.json (system id, paths, upgrade keys), RULES_IN_FORCE.md, BUILD_RULES.md, FIX_MAP.md into ROOT/master_chat_tasks/knowledge/, history move (FOLD_PLAN.md). Check: preflight PASS. Rollback: previous tag.
2. mc2-v2.2: state card, read order, compact and restore prompts, both DCP files and ROOT/opencode.jsonc, all placed by the git checkout. Check: card under 8 KB, cold recovery test, G1 and G3 checks. Rollback: previous tag (the checkout removes those files).
3. mc2-v2.3: CURRENT.json, [[ROOT]] and fill tokens, retired families, mc2 names, issue.py refusal. Check: template_check exit 0 with no SYSID finding; Ayush reads one issued prompt. Rollback: previous tag.
4. mc2-v2.4: fix map and regression check scripts, triage template. Check: the regression check flags a copy of one past fix that lost a lever. Rollback: previous tag.
5. mc2-v2.5: kit snapshot with text (on Ayush's word) and kit_watch. The save moves the old ROOT/master_chat_tasks/knowledge/fingerprints/qc.json into archive_<old head8>/ beside it. Check: kit_watch says unchanged. Rollback: copy archive_<old head8>/qc.json back over qc.json.

STAGE B, after its blockers close and a second approval.
6. Tool changes: issue.py runner choice and warnings, intake.py outside work, status.py provenance, registry design field, design_cards.jsonl, ideas.jsonl, runner_report.py, research_prompt.py. Check: tools/tests, registry_check, one intake dry run. Rollback: previous tag, then the rsync upgrade.py prints from BACKUP/<day of step 6>/records/ (the backup taken just before the step), dry run first.
7. dockslot installed, manager still dockfree; Ayush runs upgrade_plan/tmp/W1-031/MEASURE.md (Q19). Check: dockslot idle, peaks CSV saved. Rollback: dockslot.py stop.
8. Manager switched to dockslot with measured sizes, harness wrap in place. Check: one kill test, one oracle and one nop together, fast lane passes a waiting job. Rollback: settings docker.manager dockfree.
9. Two stage build: skeleton from a QC passed task, stage 1 and stage 2 templates, one pilot task. Check: skeleton passes kit scripts and precheck.sh; pilot reaches DESIGN READY and builds. Rollback: previous tag, back to the one session build template P2_build_v5.
10. Auto mode: A1 to A13, limits from settings, T25 auto go, runners, paid runs through dockslot. Check: auto/smoketest, one short auto run beside the old system. Rollback: previous tag.

STAGE B BLOCKERS (all open):
1. Paid run wrap: the design of the change to the harness queue file master_queue.py (lines 272 to 287 remove containers by task name), so paid runs go through dockslot and a task open in the other system is refused. Editing it needs Ayush's "proceed" (R35). Blocks steps 8 and 10.
2. Q78: whether a project opencode config can switch off a plugin set globally (opencode merges both). Blocks the runner config of steps 6 and 10.
3. Q19 measurement. Blocks step 8.
4. A short design of steps 6 to 10, read by Ayush, then the second approval.

G. OPENCODE SETTINGS (current: upgrade_plan/inputs/opencode_settings_20261103.md, upgrade_plan/inputs/dcp/)

1. DCP layering, UNVERIFIED until checked on the Mac in step 2: ROOT/.opencode/dcp.jsonc is tasks.dcp.jsonc (off); ROOT/master_chat_tasks/.opencode/dcp.jsonc is master.dcp.jsonc (manual); the nearest file should win, so the master starts from ROOT/master_chat_tasks (upgrade_plan/drafts/P1/README_P1.md). The global dcp.jsonc stays as it is. Check: /dcp shows manual in the master; a task session at ROOT shows no DCP notice; every compression in a day was started by Ayush. If the nearest file does not win, roll back step 2.
2. master.dcp.jsonc: manualMode with automatic dedup and error purge, protectUserMessages, turnProtection 8, protected files README, GOALS, STATE_CARD, state.json, INDEX.
3. ROOT/opencode.jsonc, UNVERIFIED (Q78): model anthropic/claude-opus-5-5 for the master; plugins opencode-dcp 3.2.0, oh-my-openagent 5.1.33, opencode-anthropic-console; opencode-kiro off. If the global config keeps kiro on, ROOT runs with it, as today.
4. Runner per step from settings.json (B19).
5. By hand on the Mac: only starting the master from ROOT/master_chat_tasks (title mc2-master) and the G1 and G3 checks; the files come from git.
6. Compaction (Q155, ENTRY 84). The master's DCP is manual, so a compression happens only when Ayush starts it. He pastes the compact prompt (upgrade_plan/drafts/P1/MASTER_RECOVERY.md part E: checkpoint into the records, regenerate the card), runs the compress, then pastes the restore prompt (part B: reread the card, report). The protect tag around RULES IN FORCE (part C) is an extra only; the plan does not rely on it.

H. HELPING TEAMMATES AND OUTSIDE TASKS (P13)

1. Intake kinds: own_outside (Ayush's own bundles), assigned (given to Ayush by the PL or QL to fix), teammate_agreed (fixed with the teammate's agreement under the PL's oversight; refused without Ayush's stored agreement words).
2. Provenance written once (origin, author as given, source, trajectory, received tree sha, author fingerprint); author fields are never edited; regression and push checks stop on any change. Who is named at push is settled by Ayush, the teammate and the PL.
3. An outside or teammate task counts for Ayush only on his word for that task (ENTRY 65, kept in ENTRY 85); assigned tasks only if he says so.
4. An outside trajectory counts as the gate run only on Opus 5 on exactly the frozen QC passed bytes.
5. Then the normal loop: full QC, fix map, regression check, triage table, QC again (B12), one paid run.

I. GOAL CHECK

Order in each line: QC passed, under gate, solvable (DR3), new, volume and speed, learn teammates, token light, agreed line; then why.
1. P1 card, DCP, fold: partly, partly, yes, partly, yes, partly, yes, yes. Rules survive compaction.
2. P2 fix map, regression: yes, yes, yes, no, yes, yes, yes, yes. Fixes pass and keep levers.
3. P3 dockslot: partly, no, no, no, yes, no, yes, yes. More jobs at once.
4. P4 BUILD_RULES: yes, yes, yes, partly, partly, yes, yes, yes. Teammate families, hidden branches stated.
5. P8 teammate study: yes, yes, partly, yes, partly, yes, partly, yes. Shows what passes; CR7 kept inside DR3; 40 tasks unstudied.
6. P9, P11, P18 design: yes, yes, yes, yes, yes, yes, partly, yes. Rotation, idea queue, leak check; research costs tokens.
7. P10, P7: yes, partly, yes, no, yes, no, yes, yes. Old rules cannot return.
8. P12 QC pass rule: yes, no, yes, no, yes, yes, yes, yes. Real fails are never counted away.
9. P13, S9: yes, yes, yes, partly, yes, partly, yes, yes. Same QC for outside work.
10. P14 versioned upgrade: partly, no, no, no, yes, no, yes, yes. Every change can be undone.
11. P15 PL questions: yes, partly, yes, partly, no, yes, yes, yes. Answers settle what the QL accepts.
12. P16 step leak: yes, yes, yes, no, no, yes, yes, yes. Docs decide values, never the method.
13. P17, P5, P6: no, no, no, no, yes, no, yes, yes. Safe side by side, fewer reads.

J. OPEN ITEMS AND RISKS

1. Not blocking STAGE A: Q19 measurement; Q138 family labels; Q140 old intake tasks; RQ11 PL answers (read with upgrade_plan/reports/KIT_CHANGE_487b4697.md; may change BUILD_RULES, a fix map row or B12 as a new release); 40 teammate tasks unstudied; the DEFECT review paused (upgrade_plan/CONFLICT_REVIEW.md); DCP off cost measured one week, then Ayush decides, no number set in advance.
2. Blocking: STAGE A waits for the C3 to C44 leftovers; STAGE B for its four blockers.
3. Risks: rules drift from settings (template_check, upgrade gate); same task in both systems (rule, warnings, STAGE B guard); dockslot untested on macOS (dockfree fallback); lenient kit tempts forbidden traps (CL-1 to CL-10, DR3 absolute); first data copy misses a file (manifest, registry_check); an old running task forgotten (carry_over.py lists them; the card shows them until copied).

Decision coverage: upgrade_plan/tmp/W1-039/CHECK.md maps ENTRY 40 to 83 (same section letters); ENTRY 84 is in C2, C4, E, G6, B10; ENTRY 85 in C5, F, H3. Cold test fixes: upgrade_plan/tmp/W1-042/CHANGES.md.

K. ADDENDUM 4 NOV: PL AND QL ANSWERS (ENTRY 87, 88). These replace the matching lines above where they differ.
1. QC pass: one complete QC pass; every real fail fixed; a false positive is closed only when it is truly false against the check text, with a note; an IN-17 fail Ayush may waive; warns fixed except the test and rubric count warns; minors decided per QC by Ayush on the master's proposal, stored in minor_decisions.jsonl and reused as proposals; every finding judged on its merits; then the QL runs a full QC.
2. Which run counts after a fix: solution change nothing; tests or judge change regrade the last valid run; data or instruction change new paid run; task.toml change ask Ayush.
3. Grading: no single wrong reading may cost more than 50 percent of positive test points (slip_cap_pct); tests check per row or per field.
4. Settings: oracle runs 2 everywhere; time limit at least 2x the reference time on a busy machine; at most 3 what if figure criteria per judge.
5. Q19 (Mac measurement) is a STAGE B blocker only. Q138 settled: helper labels used, 3 ids unsure.
6. Files: upgrade_plan/drafts/P1/RULES_IN_FORCE.md, upgrade_plan/drafts/P1/BUILD_RULES.md, upgrade_plan/drafts/P1/settings.json. State card on the test day: 7.6 KB, under the 8 KB limit.
