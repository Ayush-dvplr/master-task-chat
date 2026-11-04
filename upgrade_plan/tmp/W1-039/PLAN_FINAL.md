FINAL PLAN OF THE MASTER CHAT UPGRADE (W1-039, 4 Nov 2026). For Ayush's approval before he types PROCEED. Nothing outside upgrade_plan/ changes before PROCEED, and after it only what both Ayush and Claude are sure of.

Paths: UP = upgrade_plan/, P1D = UP/drafts/P1/, T = UP/tmp/. Statuses: DRAFTED (written, read by the master), TESTED (run here), WAITS AYUSH, WAITS MAC.

A. GOAL

GOAL IN ONE LINE (agreed G1, ENTRY 30): make more and more accepted tasks the way teammates make them: each passes QC, scores under the gate, is solvable from what it ships, and is new (not a copy). Traps and levers are one tool for that, next to volume, speed, design shapes and test structure.
The agreed line (ENTRY 23): hiding a trap from the SOLVING AGENT is normal task design (hidden test data, no trap announcement, which the kit itself requires under IN-17). Every trap must still meet what each QC check asks for: solvable from what the task ships, every graded value decided by the shipped instruction and data, no underspecified grading. Claude helps with the first and with meeting the checks; Claude does not help make a real defect look valid to the QC.

B. WHAT CHANGES, BY PROBLEM AND SUGGESTION

1. P1 compaction. Master DCP manual, task sessions DCP off (Q98, Q99); master started from master_chat_tasks/ (Q108); protected files (Q109); generated state card, 8 KB hard, 6 KB target (ENTRY 44 to 47, long sessions only reported); new read order and recovery prompt (ENTRY 48); fold of layered rules, rules split in two (ENTRY 51 to 60); master is a brain, smart loading (ENTRY 40, 41). Files: P1D/state_card.py, settings.json, RULES_IN_FORCE.md, BUILD_RULES.md, MASTER_RECOVERY.md, FOLD_PLAN.md, FOLD_DECISIONS.md, master.dcp.jsonc, tasks.dcp.jsonc, README_P1.md. TESTED (CARD_TEST.md, cold test W1-028); DCP files WAIT MAC.
2. P2 QC fixes. Fix map, not bypass (ENTRY 49, 50); regression check after every fix, lever keeps 90 percent (ENTRY 69); Ayush judges false positives from a triage table (ENTRY 66); grounding replies under kit 487b4697 (ENTRY 83). Files: T/W1-030/FIX_MAP.md, REGRESSION_CHECK.md, BUILD_RULES QC FIXES. DRAFTED; scripts written after PROCEED.
3. P3 Docker (S1). dockslot: blocking queue, room from real use, orphan hold, paid first, QC fast lane (ENTRY 68, Q134). Files: T/W1-031/dockslot.py, DESIGN.md, MEASURE.md. TESTED with fake capacity (TEST.md T1 to T5); WAITS MAC (Q19).
4. P4 hardening. One rule layer: primary lever from PATTERNS families, 40 percent (R25), CR1 to CR7, R28, R30, T1 to T46 (ENTRY 42, 49 to 63, 67); holes only case by case (ENTRY 52). Files: BUILD_RULES.md, FIX_MAP.md. DRAFTED.
5. P5 tokens. Card instead of 100 KB read order; per step context; usage limits are the pain, no cheaper models, DCP off measured one week (ENTRY 71). File: T/W1-033/TOKENS.md (first reads about 406k to 184k tokens per task). DRAFTED; measured after rollout.
6. P6 tools. One steps block in settings, adapter notes per tool, DONE in any case, Codex only for read only work or steps Ayush names (ENTRY 69, 71). Files: T/W1-033/ADAPTER.md, P1D/settings.json. DRAFTED.
7. P7 upgrades made it worse. Built in upgrade with preflight and rechecks, template_check gate (ENTRY 74 to 76). Files: T/W1-039/upgrade.py, UPGRADE.md. TESTED (UPGRADE_DRY_RUN.txt).
8. P8 teammates pass. Teammate study: 68 of 108 tasks, families and confirm list; misread rule lever allowed as primary (CR7, Q111). Files: UP/knowledge/PATTERNS.md, CONFIRM.md. DRAFTED.
9. P9 new tasks. Family order D2, D1, D8, D5, D6, D9, D3, D4 extra, D7 never; prototype is a signal only; failed card switches family (ENTRY 72). Files: T/W1-034/DESIGN_FLOW.md, DESIGN_CARD_TEMPLATE.md, WHY_NEW_FAILS.md. DRAFTED.
10. P10 old templates. CURRENT.json manifest, fill tokens from settings, issue.py refuses a retired template, retire P3, P5, P6, update P4 (ENTRY 69). Files: T/W1-032/CURRENT.json, template_check.py, P10_TEMPLATES.md. TESTED (87 conflicting lines found).
11. P11 research prompts (S8). Prompts built from the knowledge files; idea queue, Ayush approves (ENTRY 72). Files: T/W1-034/research_prompt.py, RESEARCH_INTAKE.md. TESTED (samples).
12. P12 QC pass. One complete pass; fails left only proven false positives; minors and warnings fine; CL false positive passes (ENTRY 57 to 59, 66). File: RULES_IN_FORCE.md QC PASS. DRAFTED.
13. P13 outside intake. Section H (ENTRY 64, 65, 73). Files: T/W1-035/P13_INTAKE.md, TOOL_CHANGES.md. DRAFTED; Q140 later.
14. P14 versioned upgrade. Section C and D (ENTRY 74 to 76). TESTED dry.
15. P15 PL questions. 30 questions in plain words, sent (ENTRY 77, 79 note, 80, 81). File: UP/PL_QUESTIONS.md. WAITS AYUSH (RQ11).
16. P16 step leak. Partly confirmed; BR-SL1 to BR-SL4 in BUILD_RULES and the stage 1 leak check; coupling sentence demand dropped (ENTRY 78, 79). Files: T/W1-037/STEP_LEAK.md, BUILD_RULES.md. DRAFTED.
17. P17 side by side. Section E (ENTRY 74, 75). File: T/W1-039/SYSTEM_ID.md. DRAFTED.
18. P18 no generator, two stage build. Stage 1 design pack in WORK/, stage 2 fresh session from our skeleton (ENTRY 78, 79). Files: BUILD_RULES BUILD IN TWO SESSIONS, DESIGN_CARD_TEMPLATE.md. DECIDED; skeleton folder and the two templates are written after PROCEED.
19. S1 is P3. S2 helper reports with tmp folders: in use. S3 kit snapshots with a text copy in knowledge/fingerprints/ (ENTRY 69, 83): DRAFTED, snapshot WAITS MAC. S4 QL queue (Q70): in use. S5 subagents: Codex research yes, opencode GPT never (ENTRY 71). S6 root config: section C and J; WAITS MAC (Q78 merge check). S7 kit watch: T/W1-032/kit_watch.py, classes LENIENT, MINOR, MAJOR; kit 487b4697 classified LENIENT with one MINOR (ENTRY 82, 83). S8 is P11. S9 runner record: four runners, blinds Opus 5, rest Opus 5.5 when unnamed (ENTRY 70, 71, 73); T/W1-035/S9_RUNNER.md, runner_report.py: TESTED on 419 old rows.

C. DELIVERY LAYOUT (Q84, Q141, Q142, Q145, P14, S6)

1. A new ROOT folder (name to confirm) next to the old "Terminal Bench" folder, which stays untouched. ROOT holds master_chat_tasks/, master_chat_work/, its own harness clone with Input_Bundle_QC, _runs/, SYSTEM_VERSION, .gitignore and opencode.jsonc.
2. Git versions only SYSTEM files: tools, templates, rules, settings, scripts, knowledge how to files, opencode and DCP config. DATA stays out of git (.gitignore): registry, board, pending.db, logs, decisions and lessons, auto runs, fingerprints, QC reports, master_chat_work outputs. Daily backup: upgrade.py backup (records copied whole with sha256 manifest; master_chat_work mirrored, changed files only). List: UPGRADE.md.
3. Branch stable is what Ayush runs; branch v2 is where versions are prepared; one tag per release (v2.0, v2.1). The system never commits or pushes (R34); Ayush runs every git command.
4. DCP layering (README_P1.md): ROOT/.opencode/dcp.jsonc = tasks.dcp.jsonc (off) for task sessions; ROOT/master_chat_tasks/.opencode/dcp.jsonc = master.dcp.jsonc (manual), nearest file wins, so the master starts from master_chat_tasks/.
5. Open: whether v2 and the tags live only in ROOT's local git or also on GitHub (R_REPOS today lets this session push only upgrade_plan/).

D. BUILT IN UPGRADE PROCEDURE (P14, Q142, Q145)

upgrade.py on the Mac never runs git. backup, then preflight: settings valid, template_check clean, kit_watch status, state card builds, tool self tests, no session running, today's backup matches. Any FAIL blocks; otherwise it prints the git commands (status, fetch, a local tag of the current version, checkout of the new tag, recheck). Recheck: settings, state card, template_check, cold recovery test (Ayush pastes the printed prompt and reports pass or fail), one dry precheck on a known QC passed bundle, dockslot status. On a failed recheck it prints the rollback commands (checkout the old tag, recheck it, records rsync from backup only if data changed). Details: UPGRADE.md. Dry run: UPGRADE_DRY_RUN.txt.

E. SIDE BY SIDE WITH THE OLD SYSTEM (P17, Q144)

System id mc2 (proposed) in settings and SYSTEM_VERSION; a hash8 per run. Names: containers mc2-<kind>-<slug>-<hash8> with labels mc2.system and mc2.dockslot.lease; own images mc2-...; run folders mc2-<step>-<ts>-<hash8>; /tmp/mc2/ for locks and scratch; ~/.local/state/mc2/ for dockslot and pid files; background processes carry --system mc2; session titles and bridge names mc2-. dockslot counts old containers as foreign use; nothing of the old system is renamed or touched. Biggest items: 119 typed old root paths in the 13 active templates become [[ROOT]]; the harness queue removes containers by task name, so the same task never runs in both systems at once (UNVERIFIED guard, Mac check). Full list of places: SYSTEM_ID.md.

F. ROLLOUT AFTER PROCEED (lowest risk first; each step one tag, check, rollback)

0. Ayush creates ROOT, copies DATA once from the old system, runs upgrade.py backup. Rollback: delete ROOT; the old system never changed.
1. Settings and rules: settings.json (plus system id, paths, upgrade keys), RULES_IN_FORCE.md, BUILD_RULES.md, FIX_MAP.md into knowledge/, history move (FOLD_PLAN). Check: preflight settings and rules PASS. Rollback: previous tag (nothing reads them yet).
2. State card, read order, recovery prompt, DCP files, root opencode config. Check: card under 8 KB, cold recovery test passes, DCP notice shows manual in the master and nothing in task sessions. Rollback: previous tag; DCP files removed.
3. Templates: CURRENT.json, [[ROOT]] and settings fill tokens, retired families, mc2 names, issue.py refusal of retired templates. Check: template_check exit 0 including SYSID; one issued prompt read by Ayush. Rollback: previous tag.
4. Fix map and regression check scripts, QL triage template. Check: regression check run on a copy of one past fix that lost a lever must flag it. Rollback: previous tag.
5. Kit snapshot with text (on Ayush's word, Mac) and kit_watch. Check: kit_watch card says unchanged right after the save. Rollback: point qc.json back at the archive.
6. Tool changes: issue.py --runner and warnings, intake.py outside and settings gate, status.py provenance, registry design field, design_cards.jsonl, ideas.jsonl, runner_report.py, research_prompt.py. Check: tools/tests, registry_check, one intake dry run. Rollback: previous tag plus records restore (this step migrates DATA).
7. dockslot installed, manager still dockfree; Ayush runs MEASURE.md (Q19). Check: dockslot status idle, peaks CSV saved. Rollback: dockslot.py stop.
8. Manager switched to dockslot with measured sizes. Check: one kill test, one oracle and one nop together, fast lane passes a waiting job. Rollback: settings docker.manager dockfree.
9. Two stage build: skeleton folder from a QC passed task, stage 1 and stage 2 templates, one pilot task. Check: skeleton passes kit scripts and precheck.sh; pilot reaches DESIGN READY and builds. Rollback: previous tag (P2 v5 route).
10. Auto mode: AUTO_POLICY A1 to A13, limits from settings, T25 auto go, Codex steps, runners, mc2 names, paid runs wrapped in dockslot. Check: auto/smoketest, one short auto run beside the old system. Rollback: previous tag.
Needs the Mac: Q19 measurement, kit snapshot with text, master_queue.py adaptation (seen on origin/main, the dockslot wrap and the task name guard not designed; a harness edit needs Ayush's "proceed", R35), DCP and opencode config checks, cold test, known bundle precheck.

G. OPENCODE SETTINGS (current values: UP/inputs/opencode_settings_20261103.md, UP/inputs/dcp/)

1. Master: DCP manual (master.dcp.jsonc: manualMode on with automatic dedup and error purge, protectUserMessages, protectTags, turnProtection 8, protected files README, GOALS, STATE_CARD, state.json, INDEX). Task sessions: DCP off (tasks.dcp.jsonc). Layering by nearest folder (C4). The global ~/.config/opencode/dcp.jsonc stays empty, for the old system.
2. Native auto compaction stays off ("compaction": {"auto": false}); compaction-rules.js stays.
3. Root config ROOT/opencode.jsonc, used only in ROOT (S6): model anthropic/claude-opus-5-5 for the master; plugins kept: @tarquinen/opencode-dcp@3.2.0, oh-my-openagent@5.1.33 (with Sisyphus), opencode-anthropic-console; opencode-kiro off unless Ayush turns it on. UNVERIFIED: opencode merges global and project configs (Q78), so whether ROOT can switch kiro off is checked on the Mac first.
4. Model and variant per step and the four runners from settings.json (runners, steps): oc-opus-5.5 default, blinds oc-opus-5, Codex Sol 6.1 for research.
5. GPT prompts say "strictly do not run subagents" (R32), added by the adapter.
6. The card wraps RULES IN FORCE in <protect>. DCP 3.2.0 keeps protect tags only in user messages; if a tool read card is not kept, Ayush pastes the rules block once per session (MASTER_RECOVERY part C).
7. By hand on the Mac: place the two dcp.jsonc files and ROOT/opencode.jsonc, start the master from ROOT/master_chat_tasks with oc mc2-master. Check: /dcp shows manual mode in the master; a task session started at ROOT shows no DCP notice; opencode shows the root model; a day's compression count is only Ayush's.

H. HELPING TEAMMATES AND OUTSIDE TASKS (P13, ENTRY 64, 65, 73)

1. Intake takes three kinds: own_outside (Ayush's own bundles), assigned (tasks the PL or QL gave Ayush to fix), teammate_agreed (a teammate's task fixed with the teammate's agreement under the PL's oversight; refused without Ayush's stored agreement words).
2. Provenance is written once: origin, original author as given, source, trajectory, received tree sha, author fingerprint. The system never edits author fields; the regression and push checks stop on any change. Who is named at push is settled by Ayush, the teammate and the PL.
3. An outside task counts for Ayush only on his word for that task; assigned tasks do not count unless he says so.
4. An outside trajectory counts as the gate run only when it ran on Opus 5 on exactly the frozen QC passed bytes; otherwise it is diagnosis only.
5. Then the normal loop: full QC, fix map, regression check, QL triage table with Ayush marking false positives, QC again, one paid run.

I. GOAL CHECK

| part | QC passed | under gate | solvable DR3 | new | volume, speed | learn teammates | token light DR1 | agreed line | why |
|---|---|---|---|---|---|---|---|---|---|
| P1 card, DCP, fold | partly | partly | yes | partly | yes | partly | yes | yes | rules survive compaction, so DR3, the line and uniqueness are kept; scores come from other parts |
| P2 fix map, regression | yes | yes | yes | no | yes | yes | yes | yes | fixes pass as teammates pass, keep levers, decide real defects (Q126); not about novelty |
| P3 dockslot | partly | no | no | no | yes | no | yes | yes | more jobs at once, no polling tokens; no effect on content |
| P4 BUILD_RULES | yes | yes | yes | partly | partly | yes | yes | yes | primary lever from teammate families, hidden branches always stated |
| P9, P11, P18 design | yes | yes | yes | yes | yes | yes | partly | yes | family rotation, idea queue, leak check, fresh build session; research prompts cost tokens by design |
| P10 templates, P7 upgrade | yes | partly | yes | no | yes | no | yes | yes | old rules cannot return; safe upgrades and rollback |
| P13 intake, S9 | yes | yes | yes | partly | yes | partly | yes | yes | outside work through the same QC; author and counts guarded |
| P16 step leak | yes | yes | yes | no | no | yes | yes | yes | docs decide values, never the method; DR3 unchanged |
| P17 system id, P5, P6 | no | no | no | no | yes | no | yes | yes | safe side by side running, one runner layer, fewer reads |

J. OPEN ITEMS THAT DO NOT BLOCK APPROVAL, AND RISKS

1. Q19 Mac measurement (MEASURE.md); until then dockslot sizes are placeholders and the manager stays dockfree.
2. Q138 family labels of 14 builds and three task ids; Q140 the 6 old intake tasks.
3. RQ11 PL and QL answers to PL1 to PL30: read with reports/KIT_CHANGE_487b4697.md; an answer may change a BUILD_RULES line or a fix map row (a new small release, not a block).
4. 40 teammate tasks not studied (queue batches B11 to B24 paused for credits); PATTERNS.md rests on 68.
5. The DEFECT family review is paused (CONFLICT_REVIEW.md PAUSE NOTE); W1-002 conflicts C3 to C44 not yet mapped.
6. Q78 opencode config merge; protect tags on tool output; ROOT name; where branch v2 lives; master_queue.py adaptation.
7. Risks: (a) the card or rules drift from settings: the upgrade gate and template_check catch it; (b) same task run in both systems lets the harness queue remove the other's containers: standing rule plus Mac check; (c) dockslot untested on macOS and real Docker: dockfree stays as fallback; (d) more lenient kit (487b4697) tempts traps the line forbids: client checks CL-1 to CL-10 and DR3 stay absolute; (e) DCP off in task sessions may raise cache cost: measured one week (ENTRY 71); (f) the first data copy into ROOT can miss a file: backup manifest and registry_check before the first session.

Decision coverage: CHECK.md maps ENTRY 40 to 83 to these sections.
