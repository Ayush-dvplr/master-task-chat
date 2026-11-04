STATE CARD (mc2 v2.2; generated 04 Nov 2026 14:37 IST by tools/state_card.py; do not edit by hand)

<protect> (keeps this block word for word in a compression; it is the rules, follow it)
RULES IN FORCE (RULES_IN_FORCE.md; the only rule text the master follows)
GOAL: many accepted tasks, made the way teammates make them: QC passed, under the gate, solvable from what ships, new (not a copy). Conflicts decided case by case with Ayush.
ROLE (R1): the master is the brain: plans, writes and tunes prompts, sends heavy work to other sessions, verifies every result on disk before recording, flags anything wrong or contradictory, reports updates. A long running session is only reported, never stopped while working.
AFTER COMPACTION (R2): read this card first; load only live work; read more only when the next step needs it.
RECORDS (R3 to R5, T35): only the master writes master_chat_tasks, only through the tools. Ayush's corrections word for word to feedback.jsonl; process failures to lessons.jsonl; a repeated lesson becomes a tool check. Store rules, decisions, state, failures, lessons, scores, levers, ideas; never chat summaries. Never claim an unmeasured number; mark guesses UNVERIFIED; no secrets.
HANDOFF (R6, R7): a table with board sha, step, status, clickable file link; never "read and follow". A session stays issued until Ayush says running (auto mode: auto.py starts it).
ORDER (T24, T25): design, build, full QC until it passes, QL QC (on a QL report: triage table, Ayush marks false positives and vague ones, only real ones fixed, QC again), 1 paid run on the frozen bytes; no hardening between QC pass and paid run; after a gate miss, harden from what the run got wrong with the fix map, QC again, 1 new run. By day stop at DESIGN READY for Ayush's go; after QC pass and freeze the master starts the paid run itself within the settings budget (C28); in auto mode the master checks it and sends the go or a correction (go file, REPORT.md).
QC PASS (R16, R18, ENTRY 88, PL answers): 1 complete QC pass; every real fail fixed; a fail is closed as a false positive only when it is truly false against the check text, with a note (CL too); an IN-17 fail Ayush may waive; warns fixed except the test and rubric count warns; minors: the master proposes keep or fix per minor, Ayush decides, decisions stored in minor_decisions.jsonl and reused as proposals. Every finding judged on its merits. Then the QL runs a full QC.
QC FIXES: follow the fix map and the QC FIXES rules in BUILD_RULES.md; a real defect is always fixed.
GATE (R26, R27): from settings (today tests under 85, rubric under 85, final under 40), on 1 run of frozen QC passed bytes. Never rerun the same bytes after a miss.
RUNS AND PUSH (T26 to T34, PL29): after a fix: solution change nothing; tests or judge change regrade the last valid run; data or instruction change new paid run; task.toml change ask. diff the staged copy against the bundle before diagnosing a run; only valid runs are baselines; freeze records the tree sha, a gate run counts only on it; Step 10 done on the frozen bytes before push; push packages exactly those bytes and scores; no task is parked except on Ayush's word.
CAPS (R15): no round caps (issue.py warns, never refuses); tests and rubric criteria each at least the QC minimum, soft 70, hard 100.
LEVERS AND BUILD: BUILD_RULES.md, read before any design, harden or fix. Primary lever from the PATTERNS.md families, at least 40 percent of positive test weight, lost by the paid run program (CR2). Holes only case by case with Ayush.
DOCKER AND COST (R19 to R24, R31, R32): kill tests in Docker only; Docker room from the S1 script (dockfree.py fallback); workers, harness, paid runs per day, runs per task and model per step are settings; never harbor delete; prune only when idle; GPT prompts say "strictly do not run subagents".
REPOS AND SAFETY (R33 to R35, T39, T40): prompts read live QC and generator files; never commit or push in any repo, read only commands only; never edit the generator, QC kit, "QC assigned/" or "my tasks/" without Ayush's "proceed"; never run generate_bundle.py --force, playground.py --model or any upload; teammate tasks only from anubis-stage-2.
</protect>

SETTINGS (settings.json): gate tests <85, rubric <85, final <40; counts QC minimum, soft 70, hard 100

QC KIT: live kit not reachable here; snapshot 2026-10-25, head 5574d77e

PROGRESS (registry/tasks.json): pushed today 0 of 4, this week 1 of 20
TODAY (GOALS.md): [set 2 Nov 2026, Ayush 13:08; not today: ask Ayush for today's goal] At least 4 push-ready tasks today, counting slipway (pushed 2 Nov 11:42). Sources allowed: flood and depot rebuilt with a new primary lever (R0 1a-c), parked bundles on disk; doc changes allowed; hangar go after the v3.8 upgrade, on Ayush's word. b7c42a8f is Nikhil's task: never counted, never issued without Ayush.

NEWS SINCE LAST CARD (12; board.json, registry/tasks.json)
a79e23e done | hangar-check-replan | DONE 17:26: G12 30 seeds/form 270/270 ok (300 stopped, Ayush); tree 0163b9762...
8d006fd done | _screen | top2 sensor (a quoted CSV carrier, 8/10), flood (b shared crew >=11 hits a4 2...
75de8e7 done | slipway-overhaul-replan-repair | QL1 triage: 9 real, 4 FP, 2 partly, 3 OOS; tests+judge change -> a4 void, QC ...
481e976 done | slipway-overhaul-replan-repair | DONE: 10 QL1 fixes, 10 kept; tree 8caebf1e3549 synced; oracle 1x3 owner 1 nop...
c0f4820 done | flood-repair-portfolio | NO_CORE: paid a4 exact on H1-H3 at n=11 (cutoff -> exact branch_and_bound, no...
2939ad0 done | flood-repair-portfolio | DESIGN READY A+B 19:46: 6 crowd rounds/book (10-member shared crew, C(10,6)=2...
89cb168 done | slipway-overhaul-replan-repair | QC v4 PASS 0/0/0, 2 ack (TS-20,TS-23); oracle 1.0x3 owner 1 nop 0 stub 0; QL ...
8dfccc8 done | hangar-check-replan | QC v4 full FAIL 6/0/1 (F01 source-token negatives, F02 h4 settlement/group to...

WAITING FOR AYUSH (4; pending.db; always shown, oldest first; over 12 h = raise now)
Q47 | medium | 302 h | Ask PL: Anubis 07-10 verifiers fixed in 5d565653 but trajectories/r...
Q48 | medium | 294 h | Later: store a shasum manifest of every researched peer task (root-...
Q52 | high | 290 h | SECURITY: litellm 1.107.0 payload RAN 21 Oct 17:34 (uv cache env mG...
Q62 | low | 123 h | Apply speed rules to rule files? (verifier worst 15-20 min; wrong-o...

SESSIONS RUNNING OR ISSUED (2; board.json; Ayush decides when issued becomes running)
ffd3a8e | running | sensor-network-lsq-correlated-adjustment | sensor full QC v3 on tree 380f417a8efd | master_chat_tasks/prompts/issued/sensor-network-lsq-correlated-adjustment/20261102T2330_qc.md | LONG 39 h: report to Ayush, never stop it
dabfeb4 | running | hangar-check-replan | hangar fix QC v4 F01-F07 | master_chat_tasks/prompts/issued/hangar-check-replan/20261102T2246_fix.md | LONG 40 h: report to Ayush, never stop it

ACTIVE TASKS (5; registry/tasks.json; detail: python3 tools/status.py <slug>)
sensor-network-lsq-correlated-adjustment | qc | next: full QC v3 ffd3a8e (issued 23:30) on tree 380f417a8efd, t...
flood-repair-portfolio | fix | next: 420bf9a fix TS-16/TS-19/DS-27 (TS-26, AL-27 KEPT by Ayush...
b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 | gate_runs | next: NIKHIL's task (not Ayush's): never count toward Ayush's p...
hangar-check-replan | fix | next: dabfeb4 continue (Ayush 23:28 accepted pred mid 41.4): be...
depot-charge-plan | gate_runs | next: a2 offline no lever (0/2312); off_route1/park HELD: Ayush...

HANDOFF FORMAT: a table with board sha, step, status and a clickable file link; never 'read and follow'.

LEFT OUT (over the hard limit; read the named source): open items, uniqueness
