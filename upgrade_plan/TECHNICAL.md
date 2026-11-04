MC2 TECHNICAL REFERENCE

Written 4 Nov 2026 (helper W1-051) for the owner of the master chat system. The plain words version is upgrade_plan/BOOK.md. This file links to the source files instead of copying them; when a source and this file disagree, the source wins. Facts were checked against the mc2 worktree at tag mc2-v2.5.2 (commit fe8e377a) and the planning files on branch claude/youthful-feynman-zug0uq. Items not checked are marked TO BE CONFIRMED.

Paths. A path that starts with upgrade_plan/ is in the planning clone. A path that starts with master_chat_tasks/ or master_chat_work/ is inside ROOT (and inside the worktree, which holds the same tracked files). Status words follow upgrade_plan/PLAN_FINAL.md: DRAFTED, TESTED, DECIDED, TO BE DRAFTED, IN USE, WAITS MAC, and one that waits for the owner's word.


1. THE PLACES AND THEIR FOLDERS

1. Old system: "/Users/mac/Desktop/Terminal Bench" (company side). Holds master_chat_tasks/, master_chat_work/ (about 2.2 GB), QC/reports, QC/copies and the harness clone Terminal_2.0_Harbor_Harness with jobs/, Tasks_INPUT/ and Output_RFP/. Read only from the upgrade's side: the install copies DATA out once; tools read its board and kit (settings upgrade.old_root). Tasks running there finish there.
2. Planning clone: /Volumes/ayush_prsnl/mc2_upgrade (personal volume), branch claude/youthful-feynman-zug0uq of the repo master-task-chat. The work lives in upgrade_plan/. Setup: upgrade_plan/opencode_handoff/SETUP_STEPS.md steps 0 to 4. The clone is about 2.2 GB checked out plus about 840 MB in .git.
3. Worktree: /Volumes/ayush_prsnl/mc2_worktree, a git worktree of the planning clone on branch mc2-v2, made from the bundle (SETUP_STEPS.md step 5). The only place where new system versions are committed and tagged. Nothing runs from it. Its commits and tags live in the planning clone's .git.
4. ROOT: /Users/mac/Desktop/mc2_root (company side, next to the old folder). Cloned from upgrade_plan/delivery/mc2.bundle on branch mc2-stable, then moved from tag to tag (upgrade_plan/delivery/README.md). Its git remote origin is first the bundle file; before the first version made in the worktree it is pointed at the planning clone once: git -C "/Users/mac/Desktop/mc2_root" remote set-url origin "/Volumes/ayush_prsnl/mc2_upgrade".
5. Backup: settings upgrade.backup_dir "../mc2_backup", relative to ROOT, so /Users/mac/Desktop/mc2_backup. One new folder per backup run, named YYYYMMDDTHHMMSS (a suffix _2 and up if the name exists), each with records/ and MANIFEST.json (sha256 and size per record file), plus one shared work_mirror/ that copies only new or changed files of master_chat_work (the tool's own master_chat_work/_upgrade is skipped). Code: master_chat_tasks/tools/upgrade.py, backup subcommand. Note: PLAN_FINAL.md C4 still says BACKUP/YYYYMMDD/records/; the code at mc2-v2.5.2 is as written here.
6. Git accounts (ENTRY 96): one Mac, two places. Git picks the personal or the company account by folder by itself. How that is configured on the Mac (for example an includeIf rule in the global git config) is TO BE CONFIRMED; the plan only records that it switches by itself.

ROOT LAYOUT (tracked SYSTEM files)
1. SYSTEM_VERSION: two lines, system_id = mc2 and version = v2.5.2 at the newest tag.
2. .gitignore (see DATA below), opencode.jsonc, .opencode/dcp.jsonc (task sessions).
3. master_chat_tasks/: README.md (read order, tool table, layout), settings.json, RULES_IN_FORCE.md, .opencode/dcp.jsonc (master), tools/ (all tools and tools/tests/), prompts/templates/ (all template versions, CURRENT.json, CHANGELOG.md), knowledge/ (BUILD_RULES.md, FIX_MAP.md, REGRESSION_CHECK.md, PATTERNS.md, CONFIRM.md, KIT_CLASSIFY_PROMPT.md, INDEX.md, history/, intake/ and other how to files), auto/ (auto.py, AUTO_POLICY.md, PLAN_TEMPLATE.md, tests/, smoketest/).
4. master_chat_work/README.md (the only tracked file in master_chat_work).

ROOT LAYOUT (DATA, never in git)
The .gitignore at mc2-v2.5.2 ignores: __pycache__/, *.pyc, .DS_Store; in master_chat_tasks/: registry/, board.json, BOARD.md, pending.db, state.json, settings.local.json, GOALS.md, STATE_CARD.md, STATE_CARD.prev.json, *.jsonl, open_questions.json, prompts/issued/, prompts/drafts/, prompts/rendered/, auto/runs/, auto/plans/, auto/LATEST, auto/SCHEDULED.*, knowledge/fingerprints/, knowledge/archive_md/; at ROOT: master_chat_work/* (except README.md), QC/, _runs/, Terminal_2.0_Harbor_Harness/. upgrade.py lists the same record set in DATA_RECORDS and DATA_WORK. knowledge/history and knowledge/intake stay in git on purpose (decided in mc2-v2.1). The install guide also adds master_chat_tasks/settings.local.json to ROOT/.git/info/exclude so every older tag ignores it too.

WORK FOLDERS UNDER ROOT (made on first use)
1. Session outputs: master_chat_work/<YYYYMMDD>_<topic>/; bundles master_chat_work/bundles/<slug>/; the upgrade tool copy master_chat_work/_upgrade/upgrade.py.
2. QC: QC/reports/<slug>/, QC/copies/, and the read only link QC/old_reports to the old folder's reports.
3. Runs: _runs/<YYYYMMDD>/<slug>/mc2-<step>-<ts>-<hash8>/{scratch,logs}/; locks /tmp/mc2/locks/.
4. Harness: ROOT/Terminal_2.0_Harbor_Harness, a read only clone of the PL repo made from the old folder's clone (INSTALL step 5). Until it is placed, tools fall back to the old folder's kit and harness, read only, with a NOTE line (mc2-v2.5.1 on).


2. SETTINGS

FILES
1. master_chat_tasks/settings.json (tracked): the one place for numbers (DR2). Draft history: upgrade_plan/drafts/P1/settings.json.
2. master_chat_tasks/settings.local.json (git ignored): values for one Mac only, merged on top of settings.json by every tool from mc2-v2.5.1. Today its only intended key is upgrade.known_bundle (INSTALL step 9). Never put known_bundle into settings.json.
3. Loader: master_chat_tasks/tools/mc2_settings.py (show, kit, harness). upgrade.py has its own copy of the loader so a newer upgrade.py can drive an older tag.

KEYS IN settings.json AT mc2-v2.5.2
1. gate: tests 85, rubric 85, final 40 (a task must score under each). design_margin 5 (DESIGN READY needs a predicted final under gate.final minus 5).
2. no_core_keep_pct 60: a careful program keeping this share of the primary lever's points makes the design NO CORE.
3. counts: soft_cap 70, hard_cap 100 (tests and criteria, each also at least the QC minimum).
4. target: push_ready_per_day 4, push_ready_per_week 20.
5. card: target_kb 6, hard_kb 8, sessions_shown 6, open_items_shown 5, next_chars 60, step_chars 50, title_chars 70, long_running_hours 3, question_age_hours 12, news_hours 48, unique_last 3.
6. limits: workers 5, builds 2, harness 2, paid_per_day 6, busy_at_launch 2, busy_with_run 3, last_spawn_min 20.
7. docker: manager "dockfree" (dockslot after STAGE B step 8), state_dir, headroom_mb 3072, cpu_cap 12, fallback_vm_mb 15970, fallback_vm_cpus 8, refresh_s, measure_max_age_s, dead_grace_s, kinds (kill 4096 MB 2 CPUs; oracle and nop 2048 MB 1 CPU with fast true; paid 8192 MB 4 CPUs priority 0), host (min_free_pct 15, max_swap_mb 8192, orphan_rss_mb 2048, orphan_hold_mb 8192, orphan_names, big_rss_mb 4096), fast_max_running 4, fast_starve_s 300. Kind sizes are placeholders until the Mac measurement (Q19).
8. oracle_runs: day 2, auto 2, final 2 (ENTRY 88). time_limit_factor 2. runs_per_task: build 1, final_approval 8.
9. lever_keep_pct 90 (regression check). slip_cap_pct 50. what_if_max 3.
10. models: worker claude-opus-5-5, paid_run claude-opus-5.
11. runners: default oc-opus-5.5; options oc-opus-5.5, oc-opus-5, codex-sol-6.1, oc-gpt-sol-6.1; default_by_step blind oc-opus-5, other oc-opus-5.5; ask_when_unnamed false.
12. steps: blind, master, build, qc, fix, mechanical, research (research runner codex-sol-6.1, subagents true, auto_may_start true) and the _codex_rule note (Q136).
13. paid_run_auto_start_by_day true (C28).
14. system: id mc2, root_name mc2_root, backup_dir, branches stable mc2-stable and next mc2-v2, first_tag mc2-v2.0.
15. paths: root null (never stored; ROOT is the folder that holds SYSTEM_VERSION), records master_chat_tasks, work master_chat_work, runs _runs, harness Terminal_2.0_Harbor_Harness, kit Terminal_2.0_Harbor_Harness/Input_Bundle_QC.
16. upgrade: backup_dir "../mc2_backup", old_root "/Users/mac/Desktop/Terminal Bench", known_bundle "" (set in settings.local.json instead).


3. RULES FILES AND HOW THEY ARE LOADED

1. master_chat_tasks/RULES_IN_FORCE.md: the master's standing rules (from the rule review R1 to R35 and the fold T1 to T46). It is not read on its own: state_card.py copies it into STATE_CARD.md as the first section, so it reaches the master through the card. Draft: upgrade_plan/drafts/P1/RULES_IN_FORCE.md.
2. master_chat_tasks/knowledge/BUILD_RULES.md: design, grading, test and QC fix rules, read only when a design, harden or fix step needs them; every build, harden and fix prompt cites it. Draft: upgrade_plan/drafts/P1/BUILD_RULES.md. Its last line (PL ANSWERS) replaces older lines above it: 2x time limit instead of 4x, at most 3 what if criteria instead of 6, the one slip cap instead of whole document grading.
3. master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md: read first by every task session (named current in CURRENT.json).
4. Knowledge read on demand: FIX_MAP.md and QC_FIX_PLAYBOOK_v3.md for a QC fix, REGRESSION_CHECK.md after a fix round, PATTERNS.md for a design, INDEX.md first for research. Never read: knowledge/history/, the whole feedback.jsonl or lessons.jsonl, old template versions (master_chat_tasks/README.md read order).
5. The planning session's own rules: upgrade_plan/opencode_handoff/AGENTS.md, copied to the planning clone root so opencode loads it into the system prompt by itself (SETUP_STEPS.md step 2).
6. CURRENT.json names RULES_IN_FORCE.md and BUILD_RULES.md as the rules, and template_check.py scans templates for terms these rules retired.


4. TEMPLATES, CURRENT.json AND FILL TOKENS

1. master_chat_tasks/prompts/templates/CURRENT.json: the manifest. Per family: current file, status (active or retired), history list, reason. Active at mc2-v2.5.2: _COMMON_RULES (v5), P1 chatgpt ideas v3, P2 build v5, P4 rebuild v2, P9 harden from results v4, P10 upstream diff v2, P11 full QC v3, P12 recheck fix v5, P13 blind solve v2, P14 task analysis v2, P15 research angle v2, P16 QL report triage v1, P17 QL handback v1, QL_REPLY_TEMPLATE. Retired: P3, P5, P6, P7, P8. A version bump edits CURRENT.json and CHANGELOG.md in the same change.
2. Fill tokens (master_chat_tasks/tools/fill_tokens.py): [[ROOT]], <SYSTEM_ID>, <HASH8>, <GATE>, <GATE_TESTS>, <GATE_RUBRIC>, <GATE_FINAL>, <DESIGN_BAR>, <NO_CORE_KEEP_PCT>, <SOFT_CAP>, <HARD_CAP>, <SLIP_CAP>, <WHAT_IF_MAX>, <LEVER_KEEP_PCT>, <TIME_FACTOR>, <ORACLE_RUNS>, <ORACLE_RUNS_AUTO>, <ORACLE_RUNS_FINAL>, <RUNS>, <PAID_MODEL>, <DOCKER>, <DOCKER_CHECK>. HASH8 is the first 8 hex of sha256 of "system id|slug|kind|timestamp|pid". Other <WORD> fields such as <SHA> or <OUT> are not fill tokens.
3. The 119 typed old root paths in the then 13 current templates became [[ROOT]] (Q156, PLAN_FINAL.md B10). template_check reported 14 current templates and 0 conflicting lines in the W1-048 check.
4. Rendered copies of the templates an issued prompt names go to prompts/rendered/<sha>/ (DATA). Issued prompts go to prompts/issued/<slug>/.


5. TOOLS

All tools are in master_chat_tasks/tools/ unless named otherwise. Standard library Python. The master writes the records only through them.

upgrade.py (P14; mc2-v2.0, newest copy mc2-v2.5.2)
1. Commands: status; backup [--backup-dir DIR] [--records-only]; preflight [--to TAG] [--backup-dir DIR] [--old DIR] [--kit DIR] [--snapshot FILE]; recheck --from TAG [--to TAG] [--known-bundle DIR] [--kit DIR] [--backup-dir DIR] [--cold-result pass|fail]; rollback --from TAG --to TAG [--backup-dir DIR]. Global --root and --work.
2. Never runs git, never commits, pushes, checks out or tags; prints the commands, each comment on its own line above its command. Never stops a session, container or script; never writes into the old system.
3. Reads: SYSTEM_VERSION, settings.json plus settings.local.json, the board, pending.db, the auto run, dockslot leases, the old board (upgrade.old_root or --old), the kit and snapshot, the last backup MANIFEST.json, .git files for tag names. Writes: only the backup folder.
4. Self contained (imports nothing from tools/), Python 3.9 or newer, so the newest copy in master_chat_work/_upgrade/ can drive any older tag.
5. Exit codes: 0 all PASS or WARN, 1 a FAIL (BLOCKED), 2 usage, 3 only WAIT items left.
6. ARRIVES table: settings and rules from step 1, state card and opencode files from 2, template_check from 3, kit_watch from 5, dockslot from 7. A part is WARN while the running version is older than the step that delivers it, FAIL once delivered.

carry_over.py (mc2-v2.0; PLAN_FINAL.md C5, ENTRY 85)
1. carry_over.py --old OLD_ROOT --new NEW_ROOT (--slug SLUG ... | --all-finished) [--apply]. Dry run without --apply.
2. Reads the old registry/tasks.json, board.json, registry/scores.jsonl and pending.db read only; merges into the new records without deleting, replacing a value only when the old one is newer; a clashing pending id becomes <id>-old; marks items carried_from "old system"; appends master_chat_tasks/carry_over.jsonl; rebuilds BOARD.md through board.py.
3. Refuses a slug still live in the old board, or live in the new board but not the old (Q154). Exit 0, 1 refused, 2 usage.

state_card.py (mc2-v2.2)
1. state_card.py [--root DIR] [--out FILE] [--now "YYYY-MM-DD HH:MM"]. Writes STATE_CARD.md and its own STATE_CARD.prev.json (both DATA).
2. Fill order: rules, settings, QC kit, progress, news since the last card, questions waiting for the owner, sessions, active tasks, other open items, uniqueness reminder, handoff format. Target 6 KB, hard 8 KB; over the hard limit sections drop from the bottom and a LEFT OUT line names them. 7.6 KB on the test day (PLAN_FINAL.md K6).
3. Reads RULES_IN_FORCE.md, settings, GOALS.md, board.json, registry/tasks.json, pending.db, knowledge/fingerprints/qc.json and the live kit (through kit_watch.py card_line), SYSTEM_VERSION and the old board (marks copied old sessions).

card_hook.py (mc2-v2.2)
refresh(records_dir) is called at the end of the write paths of issue.py, intake.py, status.py, pending.py and board.py (from mc2-v2.3) and minor_decisions.py record. It runs state_card.py in a child process; any failure prints one WARNING on stderr and never breaks the caller. defer() lets a parent tool rebuild once. MC2_CARD_OFF=1 switches it off.

issue.py (mc2-v2.3)
1. issue.py SLUG KIND DRAFT OUT [--title T] [--runner R] [--override "exact words"] [--by WHO] [--dry-run] [--force-lint "reason"]; issue.py --lint FILE [--slug SLUG]; issue.py --render FILE.
2. KIND: build probe qc fix harden rebuild blind loss ql research run adhoc. The draft must contain <SHA>.
3. Fills tokens, renders named templates to prompts/rendered/<sha>/, refuses a retired family and warns on an older or unknown file (CURRENT.json), lints (a leftover [[NAME]] or unfillable token, two oracle counts: refused; a gate number that differs from settings or a predicted bar without a "Reachable:" line: refused unless --force-lint).
4. Caps only warn (2 fix rounds per QC, 2 QC rounds, QC or harden after a pass, 3 harden rounds, 8 session time box) and are logged to decisions.jsonl. Refuses a dropped, killed or parked task unless --override with the exact words.
5. Runner (S9): --runner from settings runners.options, default by step; the board row gets runner and hash8. A GPT runner needs "strictly do not run subagents" in the draft (R32).
6. Writes the prompt file, the board row, a pending item; prints the handoff: board sha, step, one clickable link.

intake.py
1. intake.py SHA [--apply] [--status done|partial|failed] [--note TEXT]: checks a finished session's OUT folder and result.json.
2. intake.py --job SLUG [--bundle PATH] [--event probe|gate_run|run|ql_rerun|regrade] [--ayush-ok TEXT] [--apply]: reads a harness job (scores, staged path, staged copy against the bundle, author note grep, gate and kill rule, tree_sha). gate_run and ql_rerun are refused unless the tree sha equals the registry's; a regrade row needs the owner's exact words. --apply writes registry/scores.jsonl and registry/tasks.json.
3. At mc2-v2.5.2 its gate check still uses fixed numbers in code (docstring "tests<85, rubric<85, final<40"). Reading the gate from settings, the outside intake (--outside, --origin, provenance block, author fingerprint) and the runner check are STAGE B step 6 (upgrade_plan/tmp/W1-035/P13_INTAKE.md, S9_RUNNER.md, TOOL_CHANGES.md).

template_check.py (mc2-v2.3)
template_check.py [--root DIR] [--manifest FILE] [--settings FILE] [--all] [--max-rows N] [--json]. Read only. Checks the manifest, version pointers in README.md, INDEX.md, AUTO_POLICY.md, auto.py and issue.py, and scans current templates for SETTING (a typed settings number), RETIRED (retired terms), POINTER (superseded file), SYSID (old root, /tmp path, lock folder, container or run folder without mc2 or [[ROOT]]) and TOKEN (unfillable). Exit 0 clean, 1 findings. Preflight runs it.

regression_check.py (mc2-v2.4; ENTRY 69)
1. regression_check.py --before DIR --after DIR [--plan FILE] [--scope tests|all] [--run-dir DIR] [--oracle-runs N] [--loss-dir DIR] [--lever L=BEFORE.txt,AFTER.txt ...] [--levers LEVERS.md] [--deciding-map FILE] [--settings FILE] [--out DIR] [--json].
2. Step 1 byte diff: every tests/ hunk must be named by a fix direction line. Step 2 lever survival: after over before at least lever_keep_pct (90). Step 3 execution gate from result.json files: enough oracle runs, oracle and owner 1.0, nop 0.0. Step 7 changed graded values, checked against a DECIDING_MAP when given. Steps 4, 5, 6, 8 stay with the fix session (knowledge/REGRESSION_CHECK.md).
3. Exit 0, 1 a step FAIL, 2 usage. --out writes REGRESSION.md and regression.json.

minor_decisions.py (mc2-v2.4; ENTRY 88)
propose --check ID [--text T] or propose --file FINDINGS.md (reuses an earlier decision on the same check when its finding text is at least 60 percent alike); record --slug --check --finding --decision keep|fix --verbatim "exact words" (refused without them); list. Only writer of master_chat_tasks/minor_decisions.jsonl.

kit_watch.py (mc2-v2.5; S7; design upgrade_plan/tmp/W1-032/S7_KIT_WATCH.md)
1. check [--kit DIR] [--snapshot qc.json] [--text DIR] [--fixmap FILE] [--rules FILE ...] [--out DIR] [--json] [--diff-lines N]: hashes the kit against the snapshot, diffs against the snapshot's text copy when it has one, lists changed check ids and the FIX_MAP rows and BUILD_RULES lines that name them. Exit 0 unchanged, 1 changed, 2 error.
2. card: the one QC KIT line for the state card.
3. save --by "exact words" [--kit] [--head SHA] [--dest DIR] [--no-install]: only on the owner's word; writes knowledge/fingerprints/qc_<head8>/qc.json and qc_text/, moves the old qc.json to archive_<old head8>/, logs the words to decisions.jsonl. Never edits the kit.
4. A change is classified with knowledge/KIT_CLASSIFY_PROMPT.md: LENIENT (act freely), MINOR (report, wording may follow), MAJOR (affects fix mapping, hiding or traps; waits for the owner). The 4 Nov change 57c22748 to 487b4697 was read by the master as 9 LENIENT and 1 MINOR (upgrade_plan/reports/KIT_CHANGE_487b4697.md). The snapshot in ROOT is still the 25 Oct one (head 5574d77e), so preflight shows a kit_watch WARN until the save.

mc2_settings.py (mc2-v2.5.1): see section 2.

OTHER TOOLS CARRIED FROM THE OLD SYSTEM (IN USE)
status.py (task stages and scores), board.py (session board, BOARD.md), pending.py (SQLite open items with history), name_session.py, registry_check.py (type drift in registry/tasks.json), precheck.sh (kit scripts, exe_copy, gaps, author note grep, counts; exit 0 CLEAN, 1 findings, 2 no kit; --print-kit; PRECHECK_KIT override), trajectory_readout.py, loss.py, stacking_check.py (needs Python 3.11), dockfree.py (today's Docker room check), decide.py, xref_check.py, peer_manifest.py, repackage_one.py, auto/auto.py (start, resume, adopt, spawn, send, harness, status, stop).

dockslot.py (STAGE B, steps 7 and 8; draft upgrade_plan/tmp/W1-031/dockslot.py, design DESIGN.md, test TEST.md, measurement MEASURE.md)
1. Commands: status [--json]; acquire --kind K [--mb] [--cpus] [--owner-pid] [--ticket] [--wait-max S]; release LEASE; run --kind K -- command; daemon [--once]; stop; hold REASON and unhold; peaks --minutes M [--csv FILE]. Global --settings, --state-dir, --fake-capacity.
2. A blocking acquire on a named pipe instead of a poll loop, so a waiting session spends no tokens. Room = Docker VM memory minus headroom minus the larger of reservation and measured use per lease minus foreign use. Grants stop while the Mac is short of memory or swap, or orphan solver processes hold orphan_hold_mb. Paid first, then oldest; the QC fast lane for oracle and nop.
3. State in ~/.local/state/dockslot (the side by side plan says mc2 state goes under ~/.local/state/mc2/; which one the installed version uses is TO BE CONFIRMED at STAGE B). Never removes, kills or stops a container; never harbor delete.
4. TESTED with fake capacity only; untested on macOS; sizes wait for Q19.

triage_tasks.py (P19, new; ENTRY 95 and 97; being written by helper W1-050 into upgrade_plan/triage/, empty when this file was written)
What is decided: a read only script, no Docker and no AI tokens, over a folder of teammate or assigned tasks named by a TASKS_DIR setting (full bundles, trajectories, or mixed). Output: a ranked table with worth working on (fix and push under the gate through the P13 intake, owner design and author kept), real score versus broken score (signs: permission denied, grader crash or timeout, judge or API error, anything unusual flagged), levers and traps found (D1 to D9, points lost), and what to do next (fix QC, harden with owner agreement, rerun, regrade, drop). A precise opencode prompt then runs it, reads only the top picks deeply and asks before any Docker run. Exact commands, files and output names: TO BE CONFIRMED from upgrade_plan/triage/ when W1-050 finishes.


6. THE QC LOOP

1. Order (RULES_IN_FORCE ORDER): design, build, full QC until it passes, QL QC, one paid run on the frozen bytes. No hardening between QC pass and paid run.
2. QC pass (ENTRY 87, 88; PLAN_FINAL.md K1): one complete QC pass; every real fail fixed; a fail closed as a false positive only when truly false against the check text, with a note (CL checks too); an IN-17 fail may be waived by the owner; warns fixed except the test and rubric count warns; minors proposed keep or fix by the master and decided by the owner (minor_decisions.py); every finding judged on its merits (the old "unchanged lines are noise" rule U13 is dropped by PL5, although master_chat_tasks/README.md and BUILD_RULES QC FIX STEPS still carry it: TO BE CONFIRMED which text the templates follow). Then the QL runs a full QC.
3. Fix map: master_chat_tasks/knowledge/FIX_MAP.md (draft upgrade_plan/tmp/W1-030/FIX_MAP.md): one row per check that fires (counted over 116 reports, 21 tasks, 501 findings): what the kit asks with file and line, fires, the fix that keeps the hardness, the wording that passes, side effects, the real defect fix (Q126: one deciding sentence and the hardness rebuilt in a valid form). For grounding findings under kit 487b4697 the first reply is the route plus a request for the two equally permitted answers.
4. Regression check after every fix round, before QC again: regression_check.py plus the session steps of knowledge/REGRESSION_CHECK.md. Note: REGRESSION_CHECK.md step 3 still says 3 oracle runs and 5 in the final QC; settings oracle_runs is 2 everywhere since ENTRY 88.
5. QL triage: on a QL report the master issues P16_ql_report_triage_v1 and builds a triage table (finding, diff, kit line); the owner marks false positives and vague ones; only real ones are fixed; then QC again and P17_ql_handback_v1 (ENTRY 66).
6. After a harden that changes tests, judge or docs, the next QC is a full QC (C16).

WHICH RUN COUNTS AFTER A FIX (PL29, PL30, ENTRY 88)
1. solution/ change: nothing.
2. tests or judge change: regrade the last valid run (tests and rubric); the record names the regraded run and tree.
3. data or instruction.md change: a new paid run.
4. task.toml change: ask the owner.
A gate run counts only on the frozen QC passed tree sha; the same bytes are never rerun after a miss; only valid runs are baselines.


7. THE TWO STAGE BUILD (P18; DECIDED, STAGE B step 9)

1. No PL generator. Stage 1 (design session) writes the WORK/ design pack, never shipped: design card (upgrade_plan/tmp/W1-034/DESIGN_CARD_TEMPLATE.md), every deciding sentence as it will appear, file and folder plan, shipped and hidden data plan with its generator spec, levers and traps, the leak check (BR-SL1 to BR-SL4, upgrade_plan/tmp/W1-037/STEP_LEAK.md). It stops at DESIGN READY.
2. Stage 2 (a fresh session) reads only the pack and builds end to end from the skeleton folder (task.toml in the kit's key order, tests/Dockerfile, test.sh, reward.toml); kit scripts and precheck.sh check the structure.
3. Family rotation and design checks: upgrade_plan/tmp/W1-034/DESIGN_FLOW.md (order D2, D1, D8, D5, D6, D9, D3; D4 only an extra; D7 never; skip the families and domains of the last card.unique_last cards; after 2 family switches report to the owner).
4. TO BE DRAFTED: the skeleton and the stage 1 and stage 2 templates. Until then P2_build_v5 (one session) is used.


8. OPENCODE SETUP

1. Planning session: opencode started from the planning clone root with Opus 5.5; AGENTS.md and .opencode/dcp.jsonc (manual) copied there from upgrade_plan/opencode_handoff/. Prompts: START_PROMPT.md (5 line answer, then wait), COMPACT_PROMPT.md (before a compression). Steps: SETUP_STEPS.md. What is left: NEXT.md.
2. ROOT/.opencode/dcp.jsonc: task sessions, "enabled": false (Q99).
3. ROOT/master_chat_tasks/.opencode/dcp.jsonc: the master, manualMode enabled with automatic strategies, protectUserMessages, protectTags, showCompression, turnProtection 8 turns, protected files README.md, GOALS.md, STATE_CARD.md, state.json, knowledge/INDEX.md (Q98, Q109). The master is started from ROOT/master_chat_tasks so the nearest file wins (Q108). Layering UNVERIFIED until the Mac check (G1).
4. ROOT/opencode.jsonc: sets nothing but the schema on purpose, because whether a project file can turn off a globally enabled plugin is open (Q78). Planned values are in its comments (master anthropic/claude-opus-5-5; plugins opencode-dcp 3.2.0, oh-my-openagent 5.1.33, opencode-anthropic-console; opencode-kiro off).
5. Compaction of the master (Q155, ENTRY 84): paste the compact prompt (master_chat_tasks/README.md part E), run the DCP compress, paste the restore prompt (part B). The master then reads STATE_CARD.md first.
6. Runners and models per step come from settings.json, never from opencode config.


9. VERSIONS AND TAGS

1. Branches: mc2-v2 (where versions are made) and mc2-stable (what the owner trusts). Both started without history from main and never hold data. In the bundle and ROOT, mc2-stable points at 8d1c963e, the mc2-v2.0 commit, until a recheck ends UPGRADE GOOD and the owner pastes git branch -f mc2-stable <tag>.
2. Tags: mc2-v2.N for rollout step N, a third number for a fix release (mc2-v2.5.1, mc2-v2.5.2). mc2-v2.0 alone is annotated (tag object 719a09c8, commit 8d1c963e); every tag from mc2-v2.1 on, and every later one, is lightweight. Newest: mc2-v2.5.2 = fe8e377a. Next: mc2-v2.5.3 for a fix, mc2-v2.6 for STAGE B step 6.
3. Local marker tags before-<tag>-<YYYYMMDDTHHMMSS> come from the printed preflight block and are never pushed except by name.
4. Writer (ENTRY 94): only the opencode session on the Mac commits and tags in the worktree; never force a branch or move a tag; the owner pushes named refs. upgrade_plan/delivery/mc2.bundle is frozen at mc2-v2.5.2.
5. GitHub refused new branches from the cloud session (HTTP 403), so the versions travel as the bundle; pushing them from ROOT is optional (INSTALL step 14).


10. THE UPGRADE PROCEDURE

Full steps: upgrade_plan/delivery/README.md (INSTALL guide). In short:
1. Clone ROOT from the bundle on mc2-stable; take the newest upgrade.py out of the newest tag into master_chat_work/_upgrade/; add settings.local.json to .git/info/exclude; place the harness clone; copy DATA once (sqlite3 .backup for pending.db); copy a few reference work folders; run registry_check.py.
2. Loop per tag: backup, then preflight (with --old at mc2-v2.0). Preflight rows: settings.json valid, rules files present, template_check clean, kit_watch status, state card builds, tool self tests, no session running (board, auto run and dockslot leases idle), data backup done today, plus a warning for a slug open in both systems. Verdicts READY (prints the block), BLOCKED, UP TO DATE.
3. The printed block: git status --porcelain must print nothing, git fetch origin --tags, the local marker tag, git checkout of the next tag, then the recheck.
4. Recheck rows: SYSTEM_VERSION is the target, settings, state card, template_check, cold recovery test (WAIT until --cold-result pass|fail), dry precheck on a known bundle (WAIT without upgrade.known_bundle), kit_watch, dockslot status. Verdicts UPGRADE GOOD, WAITING (exit 3), RECHECK FAILED (prints the rollback).
5. Rollback: upgrade.py rollback --from A --to B prints the checkout of the older tag, its recheck (ROLLBACK DONE), the mc2-stable line only when needed, and an rsync restore of records from the backup taken while the older version ran, only if DATA changed (dry run first).
6. At mc2-v2.5 and later the kit_watch WARN "kit changed since the snapshot" is expected and does not stop the loop (INSTALL step 10.5).


11. SIDE BY SIDE WITH THE OLD SYSTEM (P17)

1. System id mc2 (Q153) in settings and SYSTEM_VERSION, plus hash8 per issue: containers mc2-<kind>-<slug>-<hash8> with labels mc2.system and mc2.dockslot.lease, run folders mc2-<step>-<ts>-<hash8>, /tmp/mc2/, ~/.local/state/mc2/, session titles starting mc2. Nothing old is renamed or touched; dockslot counts old containers as foreign use. (Container labels and the dockslot parts arrive with STAGE B.)
2. Standing rule (Q154): the same task never runs in both systems at once, because the harness queue master_queue.py (lines 272 to 287 on origin/main) removes containers by task name. upgrade.py preflight and the state card warn; carry_over.py refuses a live slug; a guard in the harness is a STAGE B blocker.
3. Records truth (ENTRY 85): the new records count from day 1; old running tasks finish in the old folder and are carried once.
4. template_check SYSID finds any current template that types the old root or an unnamed /tmp path, lock, container or run folder.


12. TESTING DONE

1. W1-046 (upgrade_plan/tmp/W1-046/E2E_REPORT.md): first end to end run of the install in a simulated Mac (bash, Python 3.12, path mapping). 26 problems (for example comments after printed git commands broke under plain zsh, the dry precheck regex, no install step for the harness). All fixed as mc2-v2.5.1 by W1-047 (upgrade_plan/tmp/W1-047/FIX_REPORT.md; 25 of 26 proven by a literal install run).
2. W1-048 (upgrade_plan/tmp/W1-048/E2E2_REPORT.md): second run in real zsh 5.9 with default options. 0 breaks, 3 confusing, 6 minor; every self test passed (12 files), template_check exit 0, secret scan clean, the old folder unchanged (1567 files, same sha256).
3. W1-049 (upgrade_plan/tmp/W1-049/FIX2_REPORT.md): the 9 issues fixed as mc2-v2.5.2; 65 tests passed and 29 skipped (skips need the harness or real job folders); zsh upgrade from mc2-v2.5.1 to mc2-v2.5.2 ended UP TO DATE.
4. Earlier tests: state card (upgrade_plan/drafts/P1/CARD_TEST.md), template check (upgrade_plan/tmp/W1-032/TEMPLATE_CHECK_OUTPUT.txt), upgrade dry run (upgrade_plan/tmp/W1-039/UPGRADE_DRY_RUN.txt), dockslot with fake capacity (upgrade_plan/tmp/W1-031/TEST.md), runner report on 419 old rows (upgrade_plan/tmp/W1-035/RUNNER_REPORT_SAMPLE.txt).

MAC ONLY GAPS (from the W1-046 and W1-048 GAPS lists and NEXT.md)
1. Real Terminal zsh with the owner's own ~/.zshrc, BSD cp, ln and grep, /bin/bash 3.2 for precheck.sh, paths with the space in "Terminal Bench".
2. Homebrew python3 (3.11 or newer) versus an Xcode 3.9 on PATH; the real sqlite3 .backup while the old system holds pending.db open; macOS rsync for the restore line.
3. The real harness repo and its head, kit scripts on real bundles, Docker Desktop and harbor, the 3 skipped tool tests and the 9 skipped intake tests.
4. The cold recovery test in a fresh master, the DCP layering (G1), opencode starting in the planning clone and ROOT, Q78.
5. The state card's old system flags and kit line against the real old folder, kit_watch save with a real kit head, and pushing the mc2 branches to GitHub.


13. STAGE B: DESIGN AND BLOCKERS

STEPS (PLAN_FINAL.md F)
1. mc2-v2.6 tool changes: issue.py runner choice and warnings, intake.py outside work (upgrade_plan/tmp/W1-035/P13_INTAKE.md), status.py provenance, registry design field, design_cards.jsonl, ideas.jsonl, runner_report.py (upgrade_plan/tmp/W1-035/runner_report.py), research_prompt.py (upgrade_plan/tmp/W1-034/research_prompt.py).
2. mc2-v2.7 dockslot installed, dockfree still in charge; the Mac measurement upgrade_plan/tmp/W1-031/MEASURE.md.
3. mc2-v2.8 manager switched to dockslot with measured sizes and the harness wrap.
4. mc2-v2.9 the two stage build with a pilot task.
5. mc2-v2.10 auto mode with A1 to A13, limits from settings, runners, paid runs through dockslot. (Tag name for step 10 inferred from the rule "step N is mc2-v2.N": TO BE CONFIRMED.)
Blockers (all open): the paid run wrap in master_queue.py (needs "proceed", R35); Q78; Q19 measurement; a short design of steps 6 to 10 read by the owner; then PROCEED for STAGE B.


14. OPEN ITEMS

1. Install STAGE A on the Mac; classify the kit change and save the snapshot on the owner's word.
2. Glossary or rename of old lever labels (W2, G8a, J2b) in templates; warn or refuse a prompt without a "Template:" line.
3. Q140 six old intake tasks; 40 teammate tasks unstudied (batches B11 to B24 paused); the paused DEFECT family review; 4 cleanup notes in upgrade_plan/tmp/W1-041/MAP.md; DCP off measured for one week.
4. Triage tool (P19) in upgrade_plan/triage/.


15. WHERE EVERY DECISION IS RECORDED (upgrade_plan/ANSWERS.md)

1. ENTRY 11, 12: goal of the task system. ENTRY 13: count caps. ENTRY 16: P11 and suggestions S6 to S8. ENTRY 19: top priority. ENTRY 20: P12. ENTRY 23: the agreed line. ENTRY 29, 30: conflicts case by case and the goal in one line (G1, G2).
2. ENTRY 40 to 43: rule review R1 to R35. ENTRY 44 to 46: card budget. ENTRY 48: Q8, Q120, Q121. ENTRY 49, 50: fix map, not bypass; Q126 real defect fix. ENTRY 51 to 59: rule fold T1 to T46 and A1 to A13. ENTRY 57, 58: one complete QC pass. ENTRY 61 to 63: CR2 to CR5. ENTRY 64, 65: P13 intake scope. ENTRY 66: triage table. ENTRY 67: R28 kept. ENTRY 68: dockslot. ENTRY 69: regression 90 percent. ENTRY 70: runner record S9. ENTRY 71: Codex subagents, DCP off measured a week. ENTRY 72: family order. ENTRY 74 to 76: P14 to P17 and the upgrade procedure. ENTRY 78: P18.
3. ENTRY 82, 83: kit change 487b4697. ENTRY 84: GitHub branch, mc2 id, never both at once, compact then restore. ENTRY 85: new records from day 1, teammate count on the owner's word, conflict mapping, two stage approval. ENTRY 86: old clashes (Q157) and branch, backup and root names (Q158). ENTRY 87, 88: PL and QL answers (slip cap 50, minors, which run counts, oracle 2, 2x time, 3 what if). ENTRY 89: PROCEED for STAGE A. ENTRY 90: continue in opencode. ENTRY 91 to 93: end to end checks and fix releases. ENTRY 94: opencode is the only writer of mc2-v2. ENTRY 95: two volumes, P19, setup guide, the two READMEs. ENTRY 96: folder places. ENTRY 97: triage decisions.
4. Older ENTRY numbers above are as cited in README.md, RESUME.md and PLAN_FINAL.md; this helper read ENTRY 80 to 97 in full.
5. Cross checks: upgrade_plan/tmp/W1-039/CHECK.md maps ENTRY 40 to 83 to plan sections; upgrade_plan/tmp/W1-042/CHANGES.md lists the cold test fixes.
