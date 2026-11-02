MISSING FROM THE REPO (helper W1-003, job 2)

What this is: every folder or file outside master_chat_tasks/ and master_chat_work/ that the records point to. Ayush can push or paste the MUST items. Nothing here was fetched; this is a list only.

HOW THE COUNTS WERE MADE
1. A script walked every text file in master_chat_tasks/ and master_chat_work/ (plus the rows of pending.db) and matched "/Users/mac/Desktop/Terminal Bench/<folder>/..." (with a space or %20). "refs" = number of matches. "files" = number of repo files that contain at least one. "core" = matches inside the core records (decisions, lessons, feedback, log, state.json, board.json, README, GOALS, BOARD, open_questions, pending.db, knowledge/, prompts/templates/, AUTO_POLICY).
2. Big ref counts often come from a few long logs (codex.log, PATH_REFS.csv). "files" and "core" are the better measure of importance.
3. Relative names were also checked by file count: Tasks_INPUT 474 files, Input Bundle Generator New 202, master_queue.py 115, .master-queue 66, Finalized_Tasks_RFP 38, harness_master_tasks 20, "my tasks" 181, /tmp/opencode-logs 479.
4. Present in the repo already (not missing): master_chat_work/gen_memory/ideas.jsonl, master_chat_work/_ql/, master_chat_work/QL_feeback/, master_chat_work/bundles/ (own bundles and _work notes), master_chat_work/_snapshots/20261102_v3.8_pre.
5. Problem codes: P1 compaction, P2 QC fixes, P3 Docker, P4 hardening, P5 tokens, P6 tools, P7 upgrade makes it worse, P8 teammates pass QC and score well, P9 new task design weak, P10 templates still old after upgrade.

GROUP 1. /Users/mac/Desktop/Terminal Bench/QC/   (refs 3940, files 232, core 144)
What it holds (from P11_full_qc_v3.md and the copy rule in P11): our own QC area.
1. QC/reports/<slug>/v<N>.md, _progress_v<N>.md, result_<sha>.json: every QC report (95 v*.md reports across 17 tasks as of 31 Oct, per MCW/20261031_learning/L1_qc_fixes/FINDINGS.md section 5). refs 3313. The L1 and 3b00450 studies, QC_RULINGS carry-over and every fix prompt read these.
2. QC/copies/<board sha>/<slug>/: the exact bundle copy each QC round reviewed. refs 529. Needed to diff "what QC saw" against what the fix changed.
3. QC/notes/: refs 95.
Needed for: P2 (MUST: cannot study QC fix loops, lost levers or new findings without the reports), P4 (what QC flags after a harden), P8 (compare our reports with teammates), P10 (which template version each round used).
Priority: MUST for QC/reports (text, small). USEFUL for QC/copies (large; push only the copies named in the last 2 rounds per active task, or skip). USEFUL for QC/notes.
Newer than the copy: QC/reports/flood-repair-portfolio/v4.md and result_688700c.json (done 2 Nov 23:39), QC/reports/sensor-network-lsq-correlated-adjustment/v3.md (running at copy time).
Secrets: none expected. Private: task content only.

GROUP 2. Older dated QC folders: QC_2026-10-21, QC_2026-10-22, QC_2026-10-22_r2, _r3, _r4, QC_2026-10-23, _r3 to _r7, QC_2026-10-23_lp1 (and the placeholder QC_[[DATE]] in an old template)
refs about 175 in total, files about 85, core 0 (placeholder only).
What it holds: QC rounds from 21 to 23 Oct, before the QC/reports layout.
Needed for: P2 history only (the 3b00450 study already summarised them).
Priority: SKIP (USEFUL only if the P2 plan wants to recount the 22-23 Oct loops).

GROUP 3. /Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/   (refs 3352, files 776, core 125)
The team harness clone (GitHub ShreeyankDoliya/Terminal_2.0_Harbor_Harness per decisions and KNOWLEDGE). Sub folders by refs:
1. Input_Bundle_QC/ (refs 1338): the LIVE QC kit (state.json paths.qc_live; decision 22 Oct "Live QC = the harness clone's Input_Bundle_QC/"). Kit files cited everywhere, for example 01_ to 05_ QC md files, Final_checklist.md, validate_bundle.py (lessons.jsonl:110 cites validate_bundle.py s7.4 :738-740), tests_qc / judge_qc rules. Needed for: P2 (MUST), P4 (MUST: hardening must pass these exact rules), P8 (MUST: teammates pass the same kit, Q36). Priority: MUST.
2. scripts/ (refs 313): master_queue.py (harness queue, 115 files reference it), package_rfp_bundles.py, codex_oauth/. Needed for: P3 (MUST: the queue is one of the three waiting points, Q16), P6. Priority: MUST for scripts/master_queue.py; USEFUL for the rest. SECRETS RISK: scripts/codex_oauth/credentials.py reads ~/.codex/auth.json (MCW/20261030_upgrade2/S2_folders/PATH_REFS.csv:1013); push the code only, never any token file.
3. .master-queue/state.json (66 files): queue state, runs[] DONE/FAILED, run durations (lessons.jsonl:82 measured capacity from it). Needed for: P3 (MUST, real run times and concurrency). Priority: MUST (small json). Check it holds no keys before pushing.
4. src/ (refs 243): harness source. Needed for: P3, P6. Priority: USEFUL.
5. Input Bundle Generator New/ (refs 86; 202 files by name): the PL generator (state.json paths.generator). Needed for: P9 (MUST to judge "generator only gives structure", Q36), P8. Priority: USEFUL to MUST for P9. Contains a sub folder "ayush sah tasks/".
6. Tasks_INPUT/<slug> (refs 182; 474 files by name): the staged copy each fix syncs to, compared with the bundle by tree sha. Needed for: P2, P3. Priority: USEFUL (the same bytes should equal master_chat_work/bundles/<slug>; push only if a diff is suspected).
7. jobs/ (refs 101) and .kiro-run-<slug>-<ts>/ (12 refs each for about 8 runs) and .kiro-staged-tasks/ (refs 301): paid run outputs and trajectories. Needed for: P4 (reading where Opus beat a lever), P8. Priority: USEFUL (large; the counted runs are already copied as gate_run_aN under master_chat_work). SECRETS RISK: run wrapper logs carry a bridge key on the command line (see SECRETS below).
8. Output_RFP/ (refs 61): packaged bundles for push. Priority: SKIP.

GROUP 4. /Users/mac/Desktop/Terminal Bench/QC assigned/   (refs 1205, files 162, core 4)
1. Input_Bundle_QC/ (refs 976): an older copy of the QC kit; decisions say it is NOT the live kit. Priority: SKIP if GROUP 3 item 1 is pushed.
2. converted tasks/ (53), converted_tasks_report/ (18), qc_report/ (17): earlier conversion work. Priority: SKIP.
3. my tasks/ (14 here; 181 files mention "my tasks"): Ayush's own task folders; README.md:71 says never edit without "proceed". Needed for: P8 (compare). Priority: USEFUL.

GROUP 5. /Users/mac/Desktop/Terminal Bench/_runs/   (refs 878, files 175, core 57)
Sub folders: 20261031 (359), 20261101 (291), 20261102 (36), plus the rule path _runs/<YYYYMMDD>/<slug>/<step>-<ts>/{scratch,logs}.
What it holds: since 31 Oct, all scratch and logs (moved from /tmp after the 30 Oct reboot, _COMMON_RULES_v5.md:17) and all P13 blind copies with the blind programs (P13_blind_solve_v2.md:7).
Needed for: P2 and P4 (MUST: blind programs are the evidence for "lever lost or not", Q10), P3 (USEFUL: lane logs show waits).
Priority: MUST for _runs/*/*/blind-*/app/ and blind-*/work/*.md (small text). SKIP the scratch data and big logs.

GROUP 6. /Users/mac/Desktop/Terminal Bench/_tester/lever_hunt/   (refs 172, files 20, core 27)
What it holds: the 31 Oct to 1 Nov lever hunt learning area (decisions.jsonl:661 "tester folder ... for learning only"; pilots E_pilot/L01 to L03, Codex phases A to D).
Needed for: P4 (USEFUL: which lever kinds were tried and failed), P9.
Priority: USEFUL.

GROUP 7. /Users/mac/Desktop/Terminal Bench/harness_master_tasks/   (refs 5, core 2)
What it holds: records of the separate harness master chat (decisions.jsonl:53, 22 Oct 13:22; state.json harness_master: pending list, runs.jsonl).
Needed for: P3 (harness queue view), P6 (two masters).
Priority: USEFUL (small).

GROUP 8. /Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/   (refs 818, files 48, core 9)
The team delivery repo (ShreeyankDoliya/Anubis_Tasks_Samples). Sub folders: Low_Effort_Tasks_(Client_Fixed...) 209, QC_Fixed_18_10_2026 201, stale_Pass@1 67, Perfect_for_Delivery 61, Pass@1_New 54, Final_Delivery 50, Backup_Tasks_(High_Pass_Rate_Rejected...) 34, More_Efforts 31, QC_Fixed_19_10_2026 27, QC_Fixed_17_10_2026 13.
Needed for: P8 (USEFUL: teammate tasks that passed QC and scored well; Q37), P4.
Priority: USEFUL. The 10 teammate tasks studied on 2 Nov are already summarised in master_chat_work/20261102_test_design_study/ (cards, deep2).
PRIVATE: other people's work in a team repo. Ask the repo owner before copying it to another GitHub repo.

GROUP 9. /Users/mac/Desktop/Terminal Bench/anubis-stage-2/ and anubis-stage-1/   (stage-2 refs 10805 but only 39 files, core 0; stage-1 refs 10)
What it holds: 102 teammate stage-2 tasks with recorded Opus runs (the 31 Oct "stage-2" study, MCW/20261030_upgrade2/S4_task_study, MCW/20261031_stage2_calib), stage-1 used for R4 mining.
Needed for: P8, P4 (evidence for which lever kinds really lose points).
Priority: USEFUL to SKIP (very large; the studies already extracted CSVs). PRIVATE: teammates' work.

GROUP 10. /Users/mac/Desktop/Terminal Bench/beta-task-generator/   (refs 330, files 9, core 2)
Ayush's own generator repo (ayushsah-dev/beta-task-generator): core/, tests/, references/, qc/, prompts/, playbooks/, config/, AGENTS.md.
Needed for: P9 (USEFUL to MUST if the plan touches new task design), P6.
Priority: USEFUL. It is Ayush's own GitHub repo, so the cheapest route is to attach it to the session (add_repo) rather than paste.

GROUP 11. /Users/mac/Desktop/Terminal Bench/Harbor_Harness/Terminal_2.0_Harbor_Harness/   (refs 207, files 116, core 2)
Older harness clone b1ffb283, "job outputs only, read only" (state.json paths.old_clone_jobs). decisions.jsonl:123 notes one probe ran in this old checkout by mistake.
Priority: SKIP (only old trajectories). Note for P10: a second, older harness copy exists and was used by mistake once.

GROUP 12. /Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/   (refs 133, core 4)
Backup from 20 Oct, "do not use" (state.json paths.temp_backup; decisions.jsonl:30).
Priority: SKIP.

GROUP 13. Small or one-off references under Terminal Bench
1. HANDOVER_ayush_sah_tasks_2026-10-20.md (1 ref, core 1): the original handover. Priority: SKIP (USEFUL only for P7 history).
2. AGENTS.md at the Terminal Bench root (1 ref). Priority: USEFUL if it is loaded by opencode or Codex for every session (P5 tokens, P6). UNVERIFIED that it is loaded.
3. "help others/" (6), "research/" (4), "Aakrsh tasks/" (3), and outside Terminal Bench /Users/mac/Desktop/Aakarsh/ (18), /Users/mac/Desktop/tasks/newharness (6). Other people's or side work. Priority: SKIP. PRIVATE.
4. Finalized_Tasks_RFP (38 files): a team GitHub repo, final delivery after QL ("Flow (team)" in knowledge/KNOWLEDGE.md:5). Priority: SKIP.

GROUP 14. Outside Terminal Bench on the Mac
1. /tmp/opencode-logs/ (2227 refs, 479 files, core 3): long job logs and bundle locks (/tmp/opencode-logs/locks/<slug>.lock). Wiped by the 30 Oct reboot except what came after. Priority: SKIP (ephemeral). Note for P3: locks still live here (_COMMON_RULES_v5.md:17).
2. /tmp/blind/ (1432 refs): blind copies before 31 Oct. Gone after the reboot. Priority: SKIP (cannot be pushed).
3. ~/Downloads/hardness.md (5 refs): the QL hardness document checked by research R3 0036eb5 (decisions.jsonl:409). Needed for: P4, P8. Priority: USEFUL to MUST for P4 (it is the outside definition of "hard").
4. ~/.config/opencode/ (opencode.jsonc, dcp.jsonc, tui.json, oh-my-openagent/, .omo/, rules/, plugins/, patches/; about 120 refs): opencode and plugin settings. Needed for: P1 (DCP settings, compaction), P5, P6. Priority: MUST for P1 (dcp.jsonc and opencode.jsonc, the plugin list), USEFUL for the rest. Ayush already pasted part (Q47). SECRETS RISK: provider keys may be inside; remove them before pushing.
5. ~/.local/share/opencode/ (59 refs): opencode database, session storage and logs. Needed for: P1 (real compaction events, DCP "Compression #N" lines). Priority: USEFUL as a small extract only (for example the master session's compaction lines). Do NOT push the folder: PRIVATE, every session transcript is inside, very large.
6. ~/.codex/config.toml (12 refs): Codex settings. Needed for: P6. Priority: USEFUL. ~/.codex/auth.json (7 refs) and ~/.codex/sessions: SECRET and PRIVATE, never push.
7. ~/.config/oc-bridge and ~/.local/state/oc-bridge (about 28 refs): the oc master bridge (port, "secret ok" in decisions). Needed for: P6 (auto.py talks to the master through it). Priority: USEFUL for the non-secret config only. SECRETS RISK: holds a bridge secret.
8. ~/.docker/daemon.json (14 refs): Docker gc policy. Needed for: P3. Priority: USEFUL (safe).
9. ~/.zshrc (28 refs): holds the "oc" launcher. Needed for: P6. Priority: USEFUL, paste only the oc function. May hold exported keys: check first.
10. ~/.tb-master-key/id_ed25519 and ~/.tb-master-trust/allowed_signers (from the upgrade 2 S8 signing study): a private SSH signing key. NEVER push the key. allowed_signers is public and only USEFUL if signing is kept.
11. ~/.claude/stats-cache.json and ~/.claude/projects (13 refs): Claude Code usage cache and transcripts. P5 token numbers could come from stats-cache.json. Priority: USEFUL as numbers only; projects/ is PRIVATE, SKIP.
12. ~/.local/bin (harbor, codex, claude, python3) and ~/.local/share/uv, ~/.cache/uv: tool installs. Priority: SKIP (versions can be pasted as text if P6 needs them).

MUST LIST (short)
1. QC/reports/ (all slugs; text only).
2. Terminal_2.0_Harbor_Harness/Input_Bundle_QC/ (the live QC kit).
3. Terminal_2.0_Harbor_Harness/scripts/master_queue.py and .master-queue/state.json (check for keys first).
4. _runs/<date>/<slug>/blind-*/app/ and blind-*/work/*.md (blind programs and reports, 31 Oct on).
5. ~/.config/opencode/dcp.jsonc and opencode.jsonc (keys removed), for P1.
6. The outputs of the 3 sessions still running at copy time: master_chat_work/20261102_hangar-check-replan/fix_qcv4, master_chat_work/20261102_flood-repair-portfolio/fix_qcv4, and the sensor QC v3 report; plus the current master_chat_tasks/ records (the repo copy stops at 3 Nov 00:45 IST).
Close to MUST, depending on the plan: Input Bundle Generator New (P9), ~/Downloads/hardness.md (P4).

SECRETS AND PRIVATE DATA
1. Never push: ~/.codex/auth.json, ~/.tb-master-key/id_ed25519, ~/.ssh/, any oc-bridge secret file, ~/.local/share/opencode (all transcripts), ~/.claude/projects, any .env in the harness.
2. Check before pushing: ~/.config/opencode/*.jsonc, ~/.zshrc, .master-queue/state.json, harness wrapper logs.
3. ALREADY IN THIS REPO: two run wrapper logs contain a bridge key on the command line ("--ve OPENAI_API_KEY=<32 chars>" next to OPENAI_API_BASE=http://host.docker.internal:<port>):
   1. master_chat_work/20261029_tariff-engine-audit-repair/gate_run_a5/logs/wrapper.log
   2. master_chat_work/20261031_metered-usage-rating-pipeline/gate_run_a5/logs/wrapper.log
   It looks like a per run secret of the local Codex bridge (other runs show $ANUBIS_CODEX_BRIDGE_SECRET). UNVERIFIED whether it is still valid. If the repo is or becomes public, mask it and rotate the bridge secret. Other OPENAI_API_KEY strings in the repo are placeholders ("unused", "$SECRET", "<your_anthropic_key>").
4. ALREADY IN THIS REPO: work email addresses of Ayush and teammates (for example 146 hits of Ayush's work address, plus addresses of Sugam, Dinshi, Shubhi, Nikhil and others), and teammates' names in QL notes and study folders. Keep the repo private.
5. Teammate and team repos (Anubis_Tasks_Samples, anubis-stage-1, anubis-stage-2, Finalized_Tasks_RFP, Aakarsh folders): other people's work; ask before copying them to another repo.
