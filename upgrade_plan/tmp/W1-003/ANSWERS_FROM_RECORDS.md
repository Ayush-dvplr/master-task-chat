ANSWERS FROM RECORDS (helper W1-003, job 1)

Written 2 Nov 2026 (UTC) by helper W1-003 from the repo copy on branch claude/youthful-feynman-zug0uq. Read only. Nothing outside upgrade_plan/tmp/W1-003/ was edited.

HOW TO READ
1. MCT means master_chat_tasks/ and MCW means master_chat_work/.
2. A citation "decisions.jsonl:737 (2 Nov 09:17)" means line 737 of MCT/decisions.jsonl and the "ist" time on that line. Same form for lessons, feedback, log, scores.
3. Confidence: HIGH = the record says it in words; MEDIUM = the record supports it but needs one step of reading; LOW = thin evidence. UNVERIFIED marks my own inference.
4. "Ayush still to confirm" lists what only Ayush can settle after reading this.

Q1. IS THIS REPO A FULL COPY OR AN OLDER SNAPSHOT?
What the records say:
1. The copy commit is 10d3e3ff "Work till now", dated Tue 3 Nov 2026 00:45:28 +0530 (git log). That is the only commit that touches master_chat_tasks and master_chat_work.
2. Newest timestamps in the records:
   1. pending.db history: 2026-11-03 00:10 (item S440 "status=running"); items max updated_ist 2026-11-03 00:10.
   2. board.json: 2026-11-03 00:10 (row dabfeb4 hangar, status running), board.json:5555.
   3. decisions.jsonl:763 (2 Nov 23:45), lessons.jsonl:110 (2 Nov 23:25), feedback.jsonl:36 (2 Nov 20:01), scores.jsonl:116 (2 Nov 17:51).
   4. log.jsonl:169 (24 Oct 11:28) is the last line on purpose: log.jsonl was RETIRED that day (plan v1 U6).
   5. state.json "updated_ist" says 2026-10-24 11:28 (state.json:2), but the file holds later text (gate v3.7 of 28 Oct at state.json:126), so updated_ist itself is stale.
   6. Newest line in any work file: MCW/bundles/_work/flood-repair-portfolio/LOG.md:2 at "2026-11-03 00:36 IST" (flood fix 420bf9a, "Oracle2 now running").
3. So the copy was taken about 9 minutes after the last work log line and 35 minutes after the last record update. It is complete up to the moment of the copy, but three sessions were still running and their outputs are partial or missing:
   1. S440 / board dabfeb4: hangar fix QC v4 F01-F07, running (pending.db history 3 Nov 00:10). OUT = MCW/20261102_hangar-check-replan/fix_qcv4 (present, has result_dabfeb4.json, but decision 762 sent the same session on to further lanes, QC v5 recheck, freeze, paid a2).
   2. S443 / board 420bf9a: flood fix QC v4, running (updated 2 Nov 23:56). OUT = MCW/20261102_flood-repair-portfolio/fix_qcv4 holds only KEPT.md and STACKING_CHECK.md; no FIX_REPORT or result json yet.
   3. S442 / board ffd3a8e: sensor full QC v3, running (updated 2 Nov 23:38). Its report goes to /Users/mac/Desktop/Terminal Bench/QC/reports/sensor-network-lsq-correlated-adjustment/ which is not in the repo at all.
4. Files the records reference that are newer than this copy or never copied (sample, see MISSING.md for the full list):
   1. QC/reports/flood-repair-portfolio/v4.md and result_688700c.json (flood full QC v4 done 2 Nov 23:39; named in MCT/prompts/issued/flood-repair-portfolio/20261102T2345_fix.md).
   2. QC/reports/sensor-network-lsq-correlated-adjustment/v3.md (running at copy time).
   3. Whatever S440, S442, S443 wrote after 00:36 on 3 Nov.
   4. Terminal_2.0_Harbor_Harness/Tasks_INPUT/<slug> copies that fix sessions sync in their last step.
5. Side finding: registry/scores.jsonl is behind the decisions. The depot a1 paid run (tests 100, decisions.jsonl:716, 1 Nov 17:18) and the hangar a1 paid run (reward 0.75, decisions.jsonl:735, 2 Nov 01:47) have no line in scores.jsonl. That is a recording gap on the Mac, not a copy gap (UNVERIFIED that the Mac file is not newer, but the copy is 35 min after the last record).
Confidence: HIGH that the copy matches the Mac as of about 3 Nov 00:45 IST. Anything after that is not here.
Ayush still to confirm: whether work continued on the Mac after 3 Nov 00:45 (very likely, since 3 sessions were running).

Q7. WHAT DID THE MASTER GET WRONG AFTER A COMPACTION?
What the records say (concrete cases):
1. lessons.jsonl:89 (1 Nov 11:27, kind master_process): "After compaction the master wrote 3 prompts by hand (invented board ids, no board rows, no pending items), handed them off as 'Read and follow' lines, and stamped feedback times without running date." Same hour Ayush complained twice: feedback.jsonl:33 (prompts not in the table he asked for) and feedback.jsonl:34 ("pormtps should be link and you gave me again read this").
2. lessons.jsonl:100 (2 Nov 16:31, kind master_process): "After compaction the master set 868afdf and 2939ad0 to running when Ayush only said he had 2 free terminals, handed off without the table/links, issued 2939ad0 via board.py (no pending row, no decision line), and did not flag the 14:45 '2 at a time' cap". The cap is decisions.jsonl:751 (2 Nov 14:45, "run at most 2 sessions at a time"). The broken rules were already written down (feedback.jsonl:35, 2 Nov 00:24: sessions stay issued until Ayush says running).
3. feedback.jsonl:36 (2 Nov 20:01): Ayush: "your session was compacted read again the readme and store all your important context". The master then ran the README read order.
4. Pattern: what is lost is the FORMAT and PROCESS rules from feedback (link only, hand-off table, issued vs running, issue only via issue.py, session cap, take time from date), not the task facts. Both lessons say "no change: rules already in README/feedback", meaning the rule existed but was not reloaded.
5. Older repeats that look like the same loss, but the records do not say "after compaction" (UNVERIFIED as compaction cases):
   1. feedback.jsonl:10 (24 Oct 12:52): "master kept re-introducing a 35 test/criteria cap" ("i again and again mentioned there is not cap").
   2. feedback.jsonl:7, :8, :9 (23 Oct 17:10, 18:35; 24 Oct 10:10): "Read and follow" instead of the link, three reminders.
   3. feedback.jsonl:23 (29 Oct 10:08): path given as code text, not a link, "this happened again".
6. The read order the master is told to run is README.md:5 "Read order after any compaction"; GOALS.md:9 goal G1 "After any compaction, a fixed read order restores the exact state".
Confidence: HIGH for cases 1 to 3; MEDIUM for case 5 being compaction related.

Q10. WHERE ARE CAREFUL, BLIND AND PAID RUN PROGRAMS SAVED PER TASK?
What the records say: there is no single fixed place. Each kind has a rule, and the rule changed on 31 Oct.
1. Paid run (harness) programs:
   1. The harness writes the run under Terminal_2.0_Harbor_Harness/.kiro-run-<slug>-<ts>/ (example: MCW/20261102_hangar-check-replan/harden_r1/gate_run_a1/result.json trial_uri) and jobs/. Both are outside this repo.
   2. The master copies each counted run into MCW/<date>_<slug>/gate_run_aN/ (with TRIP.md). Examples: MCW/20261031_flood-repair-portfolio/gate_run_a1 (TRIP.md, logs, trajectory), MCW/20261102_hangar-check-replan/harden_r1/gate_run_a1 (agent, artifacts, verifier, result.json), MCW/20261101_depot-charge-plan/harden_r3/gate_run_a1.
   3. A harden session extracts the agent's final program into OUT/agent_program/ (MCT/prompts/templates/P9_harden_from_results_v4.md:52 "save the agent's final program and outputs ... as OUT/agent_program/"). 28 folders named agent_program* exist, for example MCW/20261025_tariff-engine-audit-repair/harden_r2/agent_program.
2. Blind programs (P13):
   1. Until 30 Oct: /tmp/blind/<slug>-<ts>/ (log.jsonl:162, 23 Oct 14:58; auto/runs/20261027T2031_evening/REPORT.md:8). The 30 Oct reboot wiped /tmp (MCT/prompts/templates/_COMMON_RULES_v5.md:17), so those programs are gone unless copied.
   2. From 31 Oct: /Users/mac/Desktop/Terminal Bench/_runs/<YYYYMMDD>/<slug>/blind-<TS>/app/ with work/BLIND_REPORT.md and result json (MCT/prompts/templates/P13_blind_solve_v2.md:7, :36-38). _runs/ is not in the repo.
   3. Copies the master or a harden session made: MCW/<date>_<slug>/score_blinds/, MCW/2026102[78]_blind_scores/, MCW/bundles/_work/<slug>/proto/blind_r1/ (bundles/_work/hangar-check-replan/LOG.md:68), and MCW/bundles/_work/<slug>/design_blind/.
3. Careful programs (route 1 R0, 2 Nov):
   1. The rule only says the lever needs "a saved input under WORK/" and names the careful program's branch file:line in DESIGN.md (MCT/prompts/issued/_adhoc/20261101_route1_notes.md:11). It does not fix a folder for the program itself.
   2. In practice they sit in the task WORK folder: MCW/bundles/_work/depot-charge-plan/h3_a1/proto/progs/careful.py and careful_r13.py, MCW/bundles/_work/hangar-check-replan/h1_a1/proto/progs/careful_reader.py, older ones as S4_careful in MCW/bundles/_work/district-heat-flex-procurement/wrong/ and MCW/bundles/_work/schema-migration-plan-repair/wrong/auditor_r1/solvers/.
   3. Kill programs (all-but-one, first-write, every blind) are gathered per harden round in the same proto/progs/ folder (hangar LOG.md:129).
Confidence: HIGH that there is no single place; HIGH for the paths above.
UNVERIFIED: whether every paid run since 31 Oct was copied into a gate_run_aN folder (depot a1 and hangar a1 were; the scores.jsonl gap in Q1 point 5 suggests the registry step was skipped, not the copy).

Q11. WHEN A FIX LOST A LEVER, HOW WAS IT FOUND?
What the records say:
1. Mostly by the next paid run, then a P9 diagnosis. Every P9 DIAGNOSIS has a fixed row "cause 3: our QC/fix rounds made it easier" (from lessons.jsonl:57, 23 Oct 08:48). Cases:
   1. sentinel: MCW/20261023_sentinel-policy-recompute/harden_r1/DIAGNOSIS.md:21 "PARTLY ... QC v1 rewrote the tier rule into a direct instruction sentence, QC v2 defined iterations in output_field_spec". Found after the probe scored tests 100.
   2. cohort: MCW/20261023_cohort-retention-reconciliation/harden_r2/DIAGNOSIS.md:22 and :28: the P12 fix corrected R4 from 13 to 14, which "made 100 reachable on the rubric". Found after a2 scored 100/100/100.
   3. emberforge: the reverse. Harden lp1 deleted the I3 tiebreak sentence, and fixes v7 to v9 restored it: +65 pp tests, of which about 33 pp from the restored sentence (MCW/_dev_research/qc_loop_analysis/3b00450/ANALYSIS.md section 5, emberforge row; lessons.jsonl:72, 24 Oct 00:40).
   4. match-replay: fix directions wrote the fragment grammar into calibration.md and loosened CL-4: "+22.3 pp tests, +11.2 pp final" (same ANALYSIS.md section 5, match row).
2. By measuring an old program on the fixed bundle (reflex or kill table) before or after the fix:
   1. decisions.jsonl:90 (23 Oct 19:45, sentinel G03-1/G03-3): split rejected because "split makes task easier: reflex 0.25-0.29".
   2. sentinel 7e07424 split "raised the share a partial program can earn (reflex v0 0.161 to 0.364)" (MCW/20261023_sentinel-policy-recompute/harden_r2/DIAGNOSIS.md:21).
   3. Since 27 Oct (P12 v4) and 31 Oct (P12 v5) the fix session itself must show a before/after lever table and a fix receipt; examples MCW/20261029_schema-migration-plan-repair/p12_fix_v12_08741c4/RECHECK_FIX.md:95 and p12_fix_v13_6ebf33a/RECHECK_FIX.md:83 ("lever | before | after | ratio | verdict").
3. By the next QC round, when a fix or harden cut a core check: lessons.jsonl:108 (2 Nov 22:38): hangar harden r1 dropped core h4_settlement_per_check from weight 5 to 1, caught as QC v4 F02 TS-20; decisions.jsonl:762 (2 Nov 23:28) restores it ("a1 tests 52.03 after F02 core restore").
4. Reading the diff alone is not recorded as the way it was found in any case I saw (UNVERIFIED that it never happened).
5. Rule that came out of it: decisions.jsonl:86 (23 Oct 11:12): "QC fixes must keep levers and traps ... passes the trap-survival check or pauses". QC_FIX_PLAYBOOK v1 then v3 G1-G7.
Confidence: HIGH that the paid run plus P9 cause-3 row is the usual way; HIGH for the cases.

Q12. NEW ERRORS AFTER FIXES: QC FINDINGS, BROKEN ORACLE/NOP, OR BOTH?
What the records say: almost all are new QC findings at recheck. Broken oracle or nop after a fix is not recorded.
1. QC loop study 3b00450 (27 Oct), MCW/_dev_research/qc_loop_analysis/3b00450/ANALYSIS.md:12-22: of 255 findings after round 1, FIX_CAUSED 67 (26.3%, 33 fails), HARDEN_CAUSED 37 (14.5%, 20 fails), REFLAG_FIXED 25, MISSED_EARLIER 67, REFLAG_KEPT 50, NEW_RULE 6, RULE_CONFLICT 3. "Our own edits total 107/255 = 42.0%", reviewer side 55.7%, kit 2.4%. Verdict H1: "at least 22 were directed by the prompt" (ANALYSIS.md:180).
2. Master upgrade plan v1 (24 Oct): "60% of new QC findings came from our own edits (harden 32%, fix 28%); 38% are reviewer noise on unchanged text" (MCW/20261024_process/MASTER_UPGRADE_PLAN_v1.md table, first row).
3. feedback.jsonl:20 (27 Oct 13:28, class master-error): "My fix v6 prompt caused 2 of QC v7 findings: F1 moved the rebuild assert into one check (TS-13 bundling) and F6 moved R6 weight onto route criteria R7-R9 at w5 (JD-15)."
4. Learning run L1 (31 Oct): MCW/20261031_learning/L1_qc_fixes/FINDINGS.md section 3: 27 links from a new finding to a file the fix edited (labelled INFERRED by the study), 40 findings "CAME BACK", 22 "MOVED". P12 v5 says "learning run L1: fixes often break something new" (MCT/prompts/templates/P12_recheck_fix_v5.md:3).
5. Another kind: a fix that regenerated tests lost an earlier fix: "dispatch P12 r2 lost r1 fixes this way" (MCW/20261031_learning/L3_auto_problems/FINDINGS.md, rule 11, quoted in L7 codex.log:1620).
6. Recheck mode itself hides findings: lessons.jsonl:107 (2 Nov 22:38): full QC v4 found 3 fails "already present in the v3 copy b63471d that passed 0/0/0".
7. Oracle and nop: every fix session gates on "oracle 1.0x3, owner 1, nop 0" before it reports DONE (for example decisions.jsonl:609, 31 Oct 11:55). I found no record of a fix that broke the oracle or nop and reached QC. UNVERIFIED: it may have happened inside a session and been repaired there.
Confidence: HIGH that new QC findings dominate; MEDIUM that oracle/nop breakage is rare.

Q16. WHEN SESSIONS WAIT, WHAT DO THEY PRINT?
What the records say: all three kinds occur; since 31 Oct the most common is dockfree START=no.
1. dockfree START=no (since 31 Oct, min plan v2):
   1. MCW/bundles/_work/hangar-check-replan/LOG.md:100 "nop rerun skipped (Docker busy, START=no 15 min ...)"; :20 "first preflight returned START=no, so no container started"; :106 "Docker START=no".
   2. MCW/bundles/_work/flood-repair-portfolio/LOG_harden_c3aca8d.md:5 and :13 "waiting dockfree START=no (2 foreign containers)".
   3. MCW/bundles/_work/metered-usage-rating-pipeline/LOG.md:168 "waiting on dockfree (START=no, flood-repair-portfolio harbor run holds 8 GB)".
   4. MCW/bundles/_work/flood-repair-portfolio/LOG.md:4 (3 Nov 00:08) "Extra probe admission START=no (610MB free)".
   5. MCW/bundles/_work/sensor-network-lsq-correlated-adjustment/LOG.md:7 (2 Nov 23:03): "set -e treated dockfree START=no as fatal", so the chain died instead of waiting.
2. Harness queue (master_queue.py): MCT/auto/runs/20261027T2239_overnight/REPORT.md:20 (28 Oct 03:40) "district run is QUEUED, not started: master_queue counts the workers' own harbor run --agent oracle gate runs ... against its 2-run" limit. Also MCT/decisions.jsonl:418 (29 Oct 01:47) "Live MQ still PAUSED (old cold-chain usage-limit reason, limit long over)".
3. auto.py worker slots and stalls: MCT/auto/runs/20261027T0200_night/REPORT.md:47 and :48 ("Freed slot"), :38 ("3022cae busy, so send refused"); 20261027T2239_overnight/REPORT.md:30 "STALL 05:00-07:50: every busy worker ... made no visible progress for ~2 h 50 min".
4. Also: "New Harbor chain is waiting for capacity, not yet running a lane" (hangar LOG.md:6).
Confidence: HIGH that all three exist in the records; MEDIUM that START=no is the main one now (13 files in master_chat_work contain START=no: 12 session logs or reports plus MIN_PLAN_v2.md; dockfree exists only since 31 Oct).
Ayush still to confirm: which message he sees most in daily use.

Q17. WHICH DOCKER RULE IS IN FORCE? (C1, C6)
What the records say, newest first:
1. 2 Nov 14:45, decisions.jsonl:751: "run at most 2 sessions at a time" (Ayush "4. 2 at a time"). This caps sessions, not containers.
2. 31 Oct 10:30, decisions.jsonl:603 (min plan v2 applied) and MCT/auto/AUTO_POLICY.md:47: "Docker room (31 Oct, replaces the 27 Oct 'at most 2 Docker-heavy' advice): workers check tools/dockfree.py ... and wait while it says START=no". MCT/knowledge/INDEX.md:15 lists dockfree.py ACTIVE 31 Oct.
3. 29 Oct: Docker VM set to 16 GiB (decisions.jsonl:413); AUTO_POLICY.md:57 "Metered may run beside one other Docker-heavy job: Docker has 16 GiB now".
4. 27 Oct: after the Mac hang, every kill test and solver run "ONLY in Docker with --memory 4g --cpus 2" (feedback.jsonl:21).
5. Harness: MCT/auto/auto.py:67 MAX_HARNESS = 2. The "one Docker task at a time" in lessons.jsonl:81-82 (24 Oct) described the harness at that time (serial master_queue), not a rule set later.
6. Older text still present: README.md:31 "Harness: one Docker task at a time, max 2 Docker-heavy jobs on the Mac"; state.json:79 "Docker-heavy jobs still max 2" (22 Oct, decisions.jsonl:57 and :59).
Reading: the newest dated rule is dockfree only (31 Oct), plus Ayush's 2-session cap (2 Nov), plus 2 harness runs in auto.py. README.md:31 and state.json were not updated. That README line is itself a P10 case (stale text after an upgrade).
Confidence: MEDIUM. The records favour dockfree (it says "replaces"), but Ayush never wrote "the max 2 rule is dead" himself.
Ayush still to confirm: dockfree only, yes or no; and whether the 2-session cap of 2 Nov is still wanted.

Q18. THE 27 OCT MAC HANG: CAUSE?
What the records say: feedback.jsonl:21 (27 Oct 14:40, class gap): "Mac froze: 3 orphan python processes held ~185 GB (swap 76.8/77.8 GB on 32 GB RAM). 2 = cold-chain 678c839 kill-test solver frontier_bfs run on the HOST (not Docker, no memory cap; 71 GB + 59 GB, orphaned after the session's own timeout); 1 = old sentinel tool resolve on hidden rbig corpus from 04:44 (55 GB, 9h50m). Master killed all 3 at 14:38." Fix ideas (a) to (d): solver runs only in Docker with --memory 4g --cpus 2 and a wall clock timeout, ulimit on host runs, sessions kill their own child processes, master runs a periodic orphan check.
So the cause was memory (swap full) from orphaned host Python solvers, not Docker containers and not disk.
Confidence: HIGH.
Note: Q45 says about 3 times the file limit was running; the record does not count sessions or containers for that moment.

Q22. WHAT GOES WRONG WHEN HARDENING?
What the records say: all three happen; the most frequent is "the lever does not bite" (a fresh model reads it).
1. Lever does not bite:
   1. lessons.jsonl:87 (24 Oct 21:36): habit levers stated in an explicit contract "do not trip Opus"; lessons.jsonl:88 (24 Oct 22:48): hardened levers also held at tests 199/199 and 44/44.
   2. Leak audit ed0bc62 (25 Oct): MCW/20261025_process/leak_audit_ed0bc62/LEAK_AUDIT.md:22 "the contract sentence that states the whole graded procedure" in 7 of 8 bundles; first program write is a line-by-line copy.
   3. decisions.jsonl:211 (25 Oct 16:25): tariff L11 lever, 3 blinds 157/157, "0 of 3 missed".
   4. decisions.jsonl:650 (31 Oct 15:58): flood harden c3aca8d NO CORE, careful exact solver keeps 67-100% of the lever.
   5. lessons.jsonl:95 (2 Nov 13:15): "Misread-rule levers lose to careful Opus 5 (paid runs tests 100 since 31 Oct)".
2. Too many rounds: decisions.jsonl:363 (27 Oct 22:29) sentinel "7 harden/rebuild rounds already"; :364 metered 4 rounds; :753 (2 Nov 14:45) flood "4 harden/rebuild rounds already"; decisions.jsonl:201-202 (25 Oct 07:28, 07:31) metered and config "ROUND LIMIT, no credible lever".
3. QC flags it: HARDEN_CAUSED 37 of 255 later QC findings, 20 of them fails (3b00450 ANALYSIS.md:17); hangar harden r1 dropped a core weight, QC v4 F02 (lessons.jsonl:108); sensor harden r0 lever good (69/86 lost) but stopped on validator fails (pending.db S433 note; lessons.jsonl:109).
4. Harden after QC pass needs an override every time ("no harden after PASS", decisions.jsonl:717, :720, :736, :753).
Confidence: HIGH.

Q30. COUNT CAP ON TESTS AND JUDGE CRITERIA? (C2)
What the records say:
1. decisions.jsonl:88 (23 Oct 18:20): check-count cap (A3 / TS-23, over 35) "is NOT an issue for any task: treat as approved".
2. decisions.jsonl:112 (24 Oct 12:52): "No upper cap on tests or judge criteria (35 rule removed everywhere; kit floors 10/8 stay; A3 warn above 35 recorded, never fixed by merging)".
3. feedback.jsonl:10 (24 Oct 12:52): "There is NO cap. Never reintroduce it".
4. decisions.jsonl:336 (27 Oct 17:55, pipeline v4): "(3) check cap: option A only (over 35 = recorded warn, never m[erged])". QC_FIX_PLAYBOOK_v3.md:3: "row NEW-CHECK no longer asks for count <= 35 (TS-23 option A, matches row TS-23)".
5. Stale: state.json:29 "caps": "tests<=35, judge criteria<=35 ..." (written 24 Oct 11:28 or earlier, before the 12:52 removal).
Reading: no cap of ours. "Option A, over 35 = warn" only describes what the QC kit does (it prints a warn) and says that warn is accepted as a KEEP. The two are the same rule. state.json:29 is stale.
Confidence: HIGH.

Q31. WHICH P12 FIX TEMPLATE IS ACTIVE, V4 OR V5? (C3)
What the records say:
1. MCT/knowledge/INDEX.md:16: "P12_recheck_fix_v5.md ... ACTIVE 31 Oct; v4 SUPERSEDED".
2. MCT/prompts/templates/CHANGELOG.md:55 (31 Oct 10:40, min plan v2, Ayush "proceed"): P11 v3 lanes and P12 changes. P12_recheck_fix_v5.md:1-3: "template v5 (31 Oct 2026) ... fix receipt ... learning run L1".
3. decisions.jsonl:603 (31 Oct 10:30): min plan v2 applied.
4. Stale: state.json:49 "P12_recheck_fix": "v4"; README.md:31 "Templates: _COMMON_RULES_v5, P2 v5, P9 v4, P11 v3, P12 v4".
5. Practice: fix prompts issued 31 Oct (Nikhil 1105, 1205, 1310; flood 1200; metered 1230; depot 1 Nov 0415) carry the v5 "Fix receipt". Fix prompts issued from 1 Nov 11:27 on (depot 1127 and 1402, hangar 1633, 2234, 2 Nov 2246, slipway 1739, 2234, 2 Nov 1443, flood 2 Nov 2345, sensor 2 Nov 2246) are written in a new short form ("You are fixing the QC vN findings ...") that reads route1_notes, _COMMON_RULES_v5 and QC_FIX_PLAYBOOK_v3, and has no "Fix receipt" section (grep count 0). UNVERIFIED whether that was a deliberate route 1 choice or the template being dropped.
Reading: v5 is active by INDEX and CHANGELOG; state.json and README were not updated.
Confidence: HIGH for v5 being the declared active one; MEDIUM on what the fix sessions actually followed after 1 Nov.

Q32. GATE: TESTS<85, RUBRIC<85, FINAL<40, AND IS 100/100/70 DEAD? (C4)
What the records say:
1. CHANGELOG.md:49 (29 Oct 01:15): "gate v3.7 (Ayush 28 Oct 'Target <40 now' ...): final gate tests<85 AND rubric<85 AND final<40". decisions.jsonl:415 (29 Oct 01:04): "gate v3.7 final<40 text in 11 files".
2. state.json:126 (top level test_phase_gate): "tests<85, rubric<85, final<40 (v3.7 ...; was 50 under v3.6 27 Oct; was tests<100, rubric<100, 70 before)". The record itself marks 100/100/70 as before.
3. state.json:31 (targets.test_phase_gate) "tests<100, rubric<100, overall<70% (22 Oct 22:31)" is the old value left in place. README.md:31 also still says "gate met (tests<100, rubric<100, overall<70) = push".
4. Exceptions after v3.7, decided per task by Ayush: decisions.jsonl:504 and :506 (30 Oct 00:40, 01:00) warrant "<50 = pass"; decisions.jsonl:514 (30 Oct 02:29) metered a4 44.05 accepted above <40; decisions.jsonl:455 (29 Oct 09:15) tariff crash/timeout cap 60%.
5. External rule: decisions.jsonl:265 (26 Oct 18:55, QL Sugam): "tests 100 + final <70 via rubric is NOT deliverable. Gate = tests <100 AND final <70 on 2 runs". That is the QL's floor; our v3.7 gate is stricter.
6. decisions.jsonl:503 (30 Oct 00:12): "harness 'yes' uses old <50" (the harness chat still judged with v3.6).
Reading: v3.7 (85/85/40) is the live house gate; 100/100/70 is dead as a house gate but is roughly the QL acceptance floor. Per task exceptions exist.
Confidence: HIGH.

Q33. PUSH NEEDS 1 HARNESS RUN, OR 8 ON FINAL APPROVAL? (C5)
What the records say:
1. GOALS.md:34: "score under the gate on 1 real run of the frozen QC-passed bytes (Ayush 27 Oct 17:17: 'push needs only 1 run that is QC passed and under our gate score')". state.json:34 same.
2. decisions.jsonl:336 (27 Oct 17:55, pipeline v4 (1)): "order harden->blind->QC->freeze->1 run".
3. decisions.jsonl:706 (1 Nov 11:27, route 1): "build -> full QC -> 1 paid run -> harden ...".
4. 8 runs: state.json:60 "Trajectory runs: 1 run per task while building/hardening (cost); 8 runs only on final approval (Ayush 22:54)" (22 Oct). decisions.jsonl:159 (24 Oct 21:56, kind pl_rule): "for now its 1 run but later its average of 8". KNOWLEDGE.md:5 "Flow (team): ... Finalized_Tasks_RFP -> 8 runs at final approval".
5. In between: feedback.jsonl:19 (27 Oct 11:20) and decisions.jsonl:265 (26 Oct) asked for 2 runs; replaced by the 27 Oct 17:17 one-run rule.
Reading: they do not conflict. Ayush pushes after 1 valid run on frozen bytes. The 8-run average happens later on the team side at final approval (Finalized_Tasks_RFP), not in his pipeline.
Confidence: HIGH for 1 run to push; MEDIUM that the 8 runs are done by the team, not by Ayush (UNVERIFIED who starts them).

Q35. P7: WHICH UPGRADE WAS FOLLOWED BY 2 DAYS OF TESTS 100, AND WHAT WAS WRONG?
Two episodes in the records fit "after an upgrade, about 2 days of tasks built and fixed, tests 100, then found something wrong". The second is the closest match in time to "2 whole days" being noticed by Ayush himself; the first is the one tied to a document named "Master upgrade plan".
1. Episode A: 24 Oct to 25 Oct (master upgrade plan v1).
   1. Upgrade: MCW/20261024_process/MASTER_UPGRADE_PLAN_v1.md, "APPROVED 24 Oct 11:26" (decisions.jsonl:103, 24 Oct 11:20). Templates bumped 24 Oct 11:39 (_COMMON_RULES v3, P12 v3, P2 build v3, QC_FIX_PLAYBOOK v2; CHANGELOG.md:23-27). Then decisions.jsonl:115 (24 Oct 13:40): Ayush "yes" to 5 improvements, incl. an "Opus-habit bank" of levers H1-H6 (LEVER_RULES_v1 1b), cost table gate, rubric shape.
   2. Then every probe scored tests 100: registry/scores.jsonl:78 to :93 (24 Oct 18:13 to 25 Oct 07:15): caldermoor 100 twice, metered 100 three times, sentinel 100 three times, tariff 100 twice, data-product-config 100 twice (one 100/100/100), sensor 100, district 100. Only exceptions: dispatch 35.64 (an older task, :79) and caldermoor 98.45 (:91). Then cold-chain 100 (decisions.jsonl:228, 25 Oct 22:30). New builds on the upgrade (metered, tariff, config) all scored 100 on the first probe (decisions.jsonl:146, :156).
   3. Noticed: lessons.jsonl:87 (24 Oct 21:36) "Stated habit levers in an explicit contract do not trip Opus"; decisions.jsonl:156 (24 Oct 21:36) Ayush "wait wait we will have a small discuss on now record all data"; decisions.jsonl:203 (25 Oct 08:13) "every shape leaked tonight".
   4. What was wrong: leak audit ed0bc62 (25 Oct 10:50-11:10), LEAK_AUDIT.md:22: "The one leak that best explains tests at 100: the contract sentence that states the whole graded procedure ... 7 of 8 bundles ... In every probed trajectory the first program write is a line-by-line copy of that sentence". CHANGELOG.md:41 (25 Oct 16:45): "measured: every stated-rule lever leaked (98-100), only computational cores held".
   5. Response: LEVER_RULES v2 (decisions.jsonl:206, 25 Oct 13:35), v3 (26 Oct 17:55, decisions.jsonl:259), stated-rule levers PAUSED (decisions.jsonl:319, 27 Oct 11:05).
2. Episode B: 31 Oct to 2 Nov (upgrade 2 / min plan v2, then route 1).
   1. Upgrade: upgrade 2 research 30 Oct (decisions.jsonl:589), min plan v2 applied 31 Oct 10:30 (decisions.jsonl:603; CHANGELOG.md:55, P11 v3 lanes, P12 v5, dockfree, _runs). Gate v3.7 from the 29 Oct upgrade (CHANGELOG.md:49). Then route 1 on 1 Nov 11:27 (decisions.jsonl:706).
   2. Paid runs with tests 100: flood a1 56.66 = tests 100 / rubric 13.33 (decisions.jsonl:627, 31 Oct 14:15; scores.jsonl:113); depot a1 72.37, tests 100 (197/197), judge 44.74 (decisions.jsonl:716, 1 Nov 17:18). Hangar a1 reward 0.75 (decisions.jsonl:735, 2 Nov 01:47; gate_run_a1/result.json). Meanwhile tasks were fixed and hardened on the same lever style (decisions.jsonl:704-736).
   3. Noticed: decisions.jsonl:737 (2 Nov 09:17): Ayush "hold all go/paid runs; diagnose why paid runs hit tests 100 ... we have to find the culprit first".
   4. What was wrong: lessons.jsonl:95 (2 Nov 13:15): "Misread-rule levers lose to careful Opus 5 (paid runs tests 100 since 31 Oct)". The levers relied on the model misreading a rule; a careful program reads every doc and gets it right. Evidence studies 191d357 and 1deab9c (MCW/20261102_test_design_study/, deep2/WHY.md).
   5. Response: v3.8 lever order (decisions.jsonl:738, 2 Nov 09:19, reverted at :739 until "proceed", applied 13:15 per CHANGELOG.md:56): primary lever must be lost by the careful exact program (route1 notes R0).
3. Earlier, smaller case: 22 to 23 Oct. After the 22 Oct P11 v2 / P12 v1 template change (CHANGELOG.md:7), cohort a2 and vendor a2 scored 100/100/100 (scores.jsonl:40, :43). feedback.jsonl:1 (23 Oct 01:01): "second oen also got 100, 100, 100 so I am stopping ... instead of getting better its getting worsen". Part of that was a verifier permission bug (scores.jsonl:49-50 mark those runs invalid). Root cause written in master_process lessons 53 to 58 (23 Oct 08:48), for example lessons.jsonl:56 "Levers written as one plain sentence next to their use ... the agent coded every rule right on first write".
Common thread in A, B and the 23 Oct case: the levers were stated rules (written so QC passes), and a frontier model implements stated rules exactly. Each time this was found only after several paid runs.
Confidence: HIGH that both A and B happened as described; MEDIUM on which one Ayush means. UNVERIFIED: the mapping to his words "2 whole days" (A is about 1.5 days of probes, 24 Oct 18:13 to 25 Oct 22:30; B is 31 Oct 14:15 to 2 Nov 09:17, almost exactly 2 days).
Ayush still to confirm: A (24-25 Oct, habit levers) or B (31 Oct-2 Nov, misread-rule levers).

Q39. P10: TEMPLATES OR FILES STILL OLD AFTER AN UPGRADE
What the records say (cases):
1. log.jsonl:166 (24 Oct 01:20): "S25 season-ladder prompt is P9 v1 (22 Oct) and must be reissued on P9 v2 before use". P9 v2 had been active since 23 Oct 09:40 (CHANGELOG.md:11). A prompt was waiting on the old version.
2. decisions.jsonl:103 (24 Oct 11:20): with the plan v1 upgrade, prompts 9fe2a50 and f99c855 (issued 24 Oct 01:05 on P12 v2, log.jsonl:164) had to be cancelled and reissued as v3, and 69e1128 cancelled.
3. decisions.jsonl:503 (30 Oct 00:12): after the 29 Oct v3.7 gate upgrade, "Tariff a6 ... gate v3.7 NOT met (harness 'yes' uses old <50)": the harness chat still judged with the v3.6 gate. decisions.jsonl:416 (29 Oct 01:26) had claimed "old gate text grep empty".
4. README.md:31, in the read order every compaction uses, still says "gate met (tests<100, rubric<100, overall<70) = push", "Count cap option A", "Templates: _COMMON_RULES_v5, P2 v5, P9 v4, P11 v3, P12 v4", and "Harness: one Docker task at a time, max 2 Docker-heavy jobs". The 2 Nov v3.8 change was added as a bracket in front ("the WRONG-only wording below is superseded") instead of rewriting the line.
5. state.json:49 P12 "v4" while INDEX.md:16 says v5 ACTIVE 31 Oct (C3). Also state.json:38 P1_chatgpt_ideas "v1" while P1 v3 was installed 26 Oct (CHANGELOG.md:43; decisions.jsonl:259); P3, P4, P5, P6, P10 listed as v1 while v2 files exist; P13 to P17 missing. state.json:29 still has the 35 caps removed on 24 Oct; state.json:31 the 22 Oct gate. state.json was "retired" for live status on 24 Oct (state.json:125 _scope), but still read in the README read order.
6. Fix prompts after 1 Nov 11:27 do not carry the P12 v5 fix receipt (see Q31 point 5). UNVERIFIED whether this was meant.
7. Snapshots kept next to live files: KNOWLEDGE_v3.6_snapshot.md, LEVER_RULES_v3.6_snapshot.md, _COMMON_RULES_v5_v3.6_snapshot.md in the live folders; LEVER_RULES_v1, v2 still in knowledge/ (INDEX marks them SUPERSEDED). A reader without INDEX can pick the wrong one (UNVERIFIED that this happened).
Confidence: HIGH for 1 to 5.
