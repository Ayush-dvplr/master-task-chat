SYSTEM ID FOR RUNNING THE OLD AND NEW SYSTEMS SIDE BY SIDE (P17, Q144, ENTRY 74 to 76). DRAFT W1-039, 4 Nov 2026. Nothing is applied before PROCEED.

THE RULE
1. The new system has one short system id: mc2 (proposed; Ayush to confirm). It lives in settings.json as "system": {"id": "mc2"} and in ROOT/SYSTEM_VERSION. Every tool and template reads it from there; nothing types it twice (DR2 style).
2. Every per run name also gets a short hash: hash8 = the first 8 hex characters of sha256 of "<system id>|<slug>|<step>|<YYYYMMDDTHHMMSS>|<pid>". The run writes it into its board row, so a folder or container can always be traced back.
3. The old system is never renamed, moved or touched. Its containers, folders and processes are foreign to mc2: dockslot counts their real use as foreign use (dockslot.py measure(): unlabeled use beyond what unlabeled leases reserved), and no mc2 tool stops, deletes or cleans anything that does not carry the mc2 id.
4. The new system lives in its own ROOT (Q84, S6). Anything inside ROOT is already apart from the old "/Users/mac/Desktop/Terminal Bench" folder; the id matters most for what both systems share: Docker, /tmp, ~/.local/state, the opencode session database and the oc bridge registry.
5. Naming patterns (the id first, so one grep finds all of it):
   a. containers started by our own scripts: --name mc2-<kind>-<slug>-<hash8> --label mc2.system=mc2 --label mc2.dockslot.lease=<lease id>
   b. images we build ourselves (warm verifier builds, kill test images): mc2-<slug>-<step>:<hash8>
   c. run folders: <ROOT>/_runs/<YYYYMMDD>/<slug>/mc2-<step>-<YYYYMMDDTHHMM>-<hash8>/ (oracle, nop, qc, fixgate, blind, kill, dose, repack)
   d. scratch, locks and pid files: /tmp/mc2/... and ~/.local/state/mc2/...
   e. background processes: started with the marker argument --system mc2 (visible in ps), pid file ~/.local/state/mc2/<name>.pid; a launchd agent, if ever used, is labelled local.mc2.<name>
   f. opencode session titles and bridge names: mc2-master, mc2-<board sha>

PLACES THAT NEED THE ID (grep of the drafts, master_chat_tasks/tools, auto/auto.py, the current templates, and harness queue/master_queue.py on origin/main)

A. Drafts in upgrade_plan
1. drafts/P1/settings.json: add "system": {"id": "mc2"}; docker.state_dir "~/.local/state/dockslot" becomes "~/.local/state/mc2/dockslot"; add "paths": {"root", "kit", "harness", "runs"} so templates stop typing the Mac folder.
2. tmp/W1-031/dockslot.py: default state_dir (line 42) as above; the container label dockslot.lease (lines 197 to 202, read in docker ps, and the hint acquire prints) becomes mc2.dockslot.lease; add mc2.system=mc2 to the hint; daemon.json, lock, leases/, waiters/ (fifos), events.log, hold.json, measure.json and status.json all live in the state dir, so they move with it; the daemon is started as "dockslot.py --system mc2 daemon".
3. drafts/P1/state_card.py: STATE_CARD.md and STATE_CARD.prev.json stay in ROOT/master_chat_tasks (apart already); add the system id and version to the card header so a pasted card is never mistaken for the old one.
4. tmp/W1-032/template_check.py: new finding class SYSID: a current template that types the old root path, a /tmp path, a lock folder, a container name or a run folder without the mc2 id or the [[ROOT]] fill token.
5. tmp/W1-032/kit_watch.py, tmp/W1-034/research_prompt.py, tmp/W1-035/runner_report.py: write only under ROOT (their --out); no change beyond reading paths from settings.
6. tmp/W1-039/upgrade.py: reads the id from settings and SYSTEM_VERSION; its work and backup folders are inside ROOT or a folder Ayush names with mc2 in it.
7. drafts/P1/master.dcp.jsonc and tasks.dcp.jsonc: inside ROOT; the global ~/.config/opencode files are not touched, so no clash.

B. master_chat_tasks/auto/auto.py
1. AUTO_DIR/runs/<YYYYMMDDTHHMM>_<label>/ (line 796): inside ROOT; default label "auto" (line 2039) becomes "mc2-auto".
2. AUTO_DIR/LATEST, SCHEDULED.json, SCHEDULED.log, SCHEDULED.out, state.lock (lines 178, 200, 894 to 942): inside ROOT, apart already.
3. HOLD_FILE auto_hold.json in HARNESS/.master-queue (line 90) and harness_runs() reading HARNESS/.master-queue/state.json (line 443): shared if both systems use one harness clone. The new ROOT gets its own harness clone, so its .master-queue is its own.
4. REGISTRY ~/.local/state/oc-bridge/tui/<NAME>.json (line 56): shared with the oc shell function. The new master and workers are registered under names starting mc2- (oc mc2-master), so names never collide.
5. MASTER_SESSION typed session id (line 33): moves to settings.json (master_session), set to the new master's session.
6. The watcher, the worker server ("opencode serve --port 0", random port, line 764), caffeinate and the scheduled waiter: started with --system mc2 in their argument list; auto.py stop and resume act only on pids recorded in this ROOT's run state and whose command line holds this ROOT path.
7. DB_PATH ~/.local/share/opencode/opencode.db (line 58): shared, read only; sessions are told apart by the mc2- title.
8. MAX_BUSY_WORKERS, MAX_BUILDS, MAX_HARNESS (lines 36 to 38): into settings.json limits (A11).

C. master_chat_tasks/tools
1. repackage_one.py line 86: /tmp/repack-<slug>-<ts> becomes /tmp/mc2/repack-<slug>-<ts>-<hash8>.
2. lever_dose.md lines 8 and 18: /tmp/dose-<slug>-<TS> becomes /tmp/mc2/dose-<slug>-<TS>-<hash8>.
3. precheck.sh line 9: the fixed old kit path "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC" is read from settings paths.kit; its mktemp folder is already unique.
4. name_session.py: titles become mc2-<SHA>; it matches only a first message that holds both "Board id: `SHA`" and "System: mc2", so it never renames an old system session in the shared opencode database.
5. issue.py: every issued prompt gets the line "System: mc2" next to the board id.
6. dockfree.py: no state files; it counts every container on the Docker VM, which is right for a shared Docker (stays as fallback).
7. intake.py, status.py, registry_check.py, board.py, pending.py, decide.py: find their files from MT_ROOT or their own location, so they stay inside ROOT; no change.
8. README.md lines 59 and 74: scratch "/tmp/<slug>-<step>-<ts>/" and logs "/tmp/opencode-logs/<task>-<ts>/" become /tmp/mc2/<slug>-<step>-<ts>-<hash8>/ and the run folder logs.

D. Current templates (13 active, per tmp/W1-032/CURRENT.json)
1. 119 typed copies of the old root path "/Users/mac/Desktop/Terminal Bench" (P11 v3 24, P9 v4 15, _COMMON_RULES_v5 14, P2 v5 12, P16 v1 12, P12 v5 10, P17 v1 10, P14 v2 8, P10 v2 6, P13 v2 4, P15 v2 4). Each becomes the fill token [[ROOT]] from settings. Without this the new system would write into the old system's folders; this is the largest single P17 item.
2. _COMMON_RULES_v5.md line 17: run folders <step>-<YYYYMMDDTHHMM> become mc2-<step>-<YYYYMMDDTHHMM>-<hash8>; locks /tmp/opencode-logs/locks/ become /tmp/mc2/locks/.
3. _COMMON_RULES_v5.md line 35: nohup background jobs log into the mc2 run folder.
4. _COMMON_RULES_v5.md line 48 and P2_build_v5.md line 66: kill tests "docker run --rm --memory 4g --cpus 2" become "dockslot.py run --kind kill -- docker run --rm --name mc2-kill-<slug>-<hash8> --label mc2.system=mc2 --label mc2.dockslot.lease=$DOCKSLOT_LEASE ..." (memory and cpus from settings).
5. P11_full_qc_v3.md line 76: bundle lock /tmp/opencode-logs/locks/<slug>.lock becomes /tmp/mc2/locks/<slug>.lock; the oracle and nop jobs run as dockslot run --kind oracle or nop (fast lane).
6. P11_full_qc_v3.md lines 79 to 83 and 99: copies, jobs and logs under _runs/<date>/<slug>/qc-<TS> become mc2-qc-<TS>-<hash8>.
7. P12_recheck_fix_v5.md line 69: fixgate-<TS> becomes mc2-fixgate-<TS>-<hash8>.
8. P13_blind_solve_v2.md line 7: blind-$TS (already has a random part) becomes mc2-blind-$TS.
9. P16_ql_report_triage_v1.md line 13 and P17_ql_handback_v1.md lines 19 and 31: /tmp/<slug>-qltriage-<TS>/ and /tmp/ql-<slug>-<TS>/ move under /tmp/mc2/.
10. P15_research_angle_v2.md line 53: /tmp/<sha>-*/ moves under /tmp/mc2/.
11. P6_oracle_nop_stub_v2.md line 12 (dormant): /tmp/oracle-qc-<slug>-<ts>/ becomes /tmp/mc2/oracle-qc-<slug>-<ts>-<hash8> if it is ever used again.
12. The P18 stage 1 and stage 2 templates, still to write, carry [[ROOT]] and the mc2 names from the start.

E. Harness queue (harness queue/master_queue.py on origin/main, read for this list only; the dockslot wrap of Q134 (b) is still to design)
1. .master-queue/state.json, runner.pid, state.lock (lines 104 to 150), jobs/ and the private jobs roots .kiro-run-<task>-<stamp> (line 589), Output_RFP: all inside the harness clone, so apart when the new ROOT has its own clone.
2. LOG_ROOT /tmp/opencode-logs (line 54), with master-queue/runner.log and <task>-<stamp>/run.log: shared /tmp; becomes /tmp/mc2/opencode-logs in the new clone's copy (an environment variable or a settings value; a change to a harness file needs Ayush's "proceed", R35).
3. remove_containers() (lines 272 to 287) deletes every container and network whose name starts with "<task name>__", and harbor_pgids() picks harbor processes by task name. Harbor names its containers from the task name, which is part of the frozen bytes and cannot carry mc2. So if both systems run a harness job on the same task at the same time, a kill in one queue could remove the other system's containers. Two guards: (a) a standing rule: the same task never runs in both systems at once; (b) in the new clone, kill only process groups whose command line holds this clone's path, and remove only containers that started after this run's launch time. UNVERIFIED until checked on the Mac.
4. Harbor images (hb__<hash>, P11 line 76) are shared by content: the same bytes give the same image in both systems. The rule "never harbor --delete, never prune while busy" (R23) protects both systems; mc2 never removes an image it did not build under an mc2 name.

F. Outside the two folders (no change, noted so nothing is missed)
1. ~/.config/opencode/opencode.jsonc, dcp.jsonc and plugins/compaction-rules.js: global, used by the old system; not touched (the new root has its own config, S6).
2. ~/.config/oc-bridge/secret: shared read only secret of the oc bridge; fine.
3. The Docker VM itself: shared; dockslot measures it as a whole.

CHECK AFTER PROCEED (on the Mac, with both systems open)
1. docker ps --filter label=mc2.system=mc2 lists only mc2 jobs; docker ps without the filter shows old jobs as well, and dockslot status shows them as foreign MB.
2. ls /tmp/mc2 ~/.local/state/mc2 shows every mc2 lock, pid and state file; nothing new appears in /tmp/opencode-logs/locks from mc2.
3. grep -rn "Terminal Bench" in the new ROOT's current templates returns nothing (template_check SYSID clean).
4. ps ax | grep "system mc2" lists every mc2 background process.
