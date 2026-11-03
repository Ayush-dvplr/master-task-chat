STATE CARD (generated 03 Nov 2026 12:30 IST by tools/state_card.py; do not edit by hand)

<protect> (keeps this block word for word in a compression; it is the rules, follow it)
RULES IN FORCE (RULES_IN_FORCE.md; the only rule text the master follows)
GOAL: many accepted tasks, made the way teammates make them: QC passed, under the gate, solvable from what ships, new (not a copy). Conflicts decided case by case with Ayush.
ROLE (R1): the master is the brain: plans, writes and tunes prompts, sends heavy work to other sessions, verifies every result on disk before recording, flags anything wrong or contradictory, reports updates. A session running long is only reported; never stopped while working (ENTRY 47).
AFTER COMPACTION (R2): read this card first; load only live work; read more only when the next step needs it.
RECORDS (R3 to R5): only the master writes master_chat_tasks, only through the tools. Ayush's corrections word for word to feedback.jsonl; process failures to lessons.jsonl; a lesson that repeats becomes a tool check. Store rules, decisions, state, failures, lessons, scores, levers, ideas; never chat summaries.
HANDOFF (R6, R7): a table with board sha, step, status, clickable file link; never "read and follow". A session stays issued until Ayush says running.
QC FIXES (R8 to R14, R17): never paste QC "Fix:" text as the direction; never move an assert into an existing check or weight onto a conduct criterion; never delete a clause or grader without naming what grades the rest; recheck every touched check; rerun the vacuity probe; regenerate docs and TRUTH.md last, by script; byte diff tests/ before and after; a finding on unchanged lines that passed before is noise, kept with diff evidence.
QC PASS (R16, R18): no fail in 2 QC runs in a row, any CL fail blocks, a minor that does not repeat is accepted, false positive review after every QC result. Stop at the first pass; no hardening after it.
ROUND CAPS (R15): none; Ayush decides each time (issue.py warns, never refuses). TEST AND RUBRIC CRITERIA COUNTS: each at least the QC minimum, soft 70, hard 100 (Ayush's rule).
GATE (R26, R27, setting): tests under 85, rubric under 85, final under 40, on 1 run of frozen QC passed bytes. Never rerun the same bytes after a miss.
LEVERS (R25, R30, CR1, CR6, CR7): primary lever from the PATTERNS.md DESIGN families, at least 40 percent of positive test weight, firing in most hidden inputs. A misread rule lever needs one clear deciding sentence. Timeout lever only as an extra unless Ayush says so. An amended field needs one deciding doc sentence. No "note that", no trap list, no method word; a size bound may be stated for a runtime lever.
RUBRIC (Q106, R29): every criterion traces to an instruction sentence; ask for a worked example in the instruction when one is graded; honesty negative minus 3 in every judge.
DOCKER (R19 to R23): kill tests in Docker only; Docker room from the S1 script (dockfree.py as fallback); worker and harness limits are settings; never harbor delete; prune images only when idle.
COST (R24, R31, R32): paid runs per day and model per step are settings; GPT prompts in opencode say "strictly do not run subagents".
REPOS (R33 to R35): prompts read live QC and generator files; never commit or push in any repo, read only commands only; never edit the generator, QC kit, "QC assigned/" or "my tasks/" without Ayush's "proceed".
OPEN: R28 ("difficulty comes from computation on hidden data, never from withheld rules"), Ayush answers later.
</protect>

SETTINGS (settings.json): gate tests <85, rubric <85, final <40; counts QC minimum, soft 70, hard 100

QC KIT: live kit not reachable here; snapshot 2026-10-25, head 5574d77e

PROGRESS (registry/tasks.json): pushed today 0 of 4, this week 1 of 20
TODAY (GOALS.md): [set 2 Nov 2026, Ayush 13:08; not today: ask Ayush for today's goal] At least 4 push-ready tasks today, counting slipway (pushed 2 Nov 11:42). Sources allowed: flood and depot rebuilt with a new primary lever (R0 1a-c), parked bundles on disk; doc changes allowed; hangar go after the v3.8 upgrade, on Ayush's word. b7c42a8f is Nikhil's task: never counted, never issued without Ayush.

NEWS SINCE LAST CARD (0; board.json, registry/tasks.json)
none

WAITING FOR AYUSH (4; pending.db; always shown, oldest first; over 12 h = raise now)
Q47 | medium | 276 h | Ask PL: Anubis 07-10 verifiers fixed in 5d565653 but trajectories/r...
Q48 | medium | 268 h | Later: store a shasum manifest of every researched peer task (root-...
Q52 | high | 264 h | SECURITY: litellm 1.107.0 payload RAN 21 Oct 17:34 (uv cache env mG...
Q62 | low | 96 h | Apply speed rules to rule files? (verifier worst 15-20 min; wrong-o...

SESSIONS RUNNING OR ISSUED (3; board.json; Ayush decides when issued becomes running)
420bf9a | running | flood-repair-portfolio | flood fix QC v4 TS-16/TS-19/DS-27 (TS-26, AL-27... | master_chat_tasks/prompts/issued/flood-repair-portfolio/20261102T2345_fix.md | LONG 13 h: report to Ayush, never stop it
ffd3a8e | running | sensor-network-lsq-correlated-adjustment | sensor full QC v3 on tree 380f417a8efd | master_chat_tasks/prompts/issued/sensor-network-lsq-correlated-adjustment/20261102T2330_qc.md | LONG 13 h: report to Ayush, never stop it
dabfeb4 | running | hangar-check-replan | hangar fix QC v4 F01-F07 | master_chat_tasks/prompts/issued/hangar-check-replan/20261102T2246_fix.md | LONG 14 h: report to Ayush, never stop it

ACTIVE TASKS (5; registry/tasks.json; detail: python3 tools/status.py <slug>)
sensor-network-lsq-correlated-adjustment | qc | next: full QC v3 ffd3a8e (issued 23:30) on tree 380f417a8efd, t...
flood-repair-portfolio | fix | next: 420bf9a fix TS-16/TS-19/DS-27 (TS-26, AL-27 KEPT by Ayush...
b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 | gate_runs | next: NIKHIL's task (not Ayush's): never count toward Ayush's p...
hangar-check-replan | fix | next: dabfeb4 continue (Ayush 23:28 accepted pred mid 41.4): be...
depot-charge-plan | gate_runs | next: a2 offline no lever (0/2312); off_route1/park HELD: Ayush...

OTHER OPEN ITEMS (top 5 of 12; full list: python3 tools/pending.py list)
S429 | step | high | Today's goal 2 Nov: >=4 push-ready (slipway counts); hangar go afte...
S393 | step | medium | Send district QL round-2 reply
Q46 | reminder | medium | Send PL notes: false positives + kept minors in master_chat_work/20...
Q20-22 | reminder | medium | Trial review ~23-24 Oct: pending lessons (Q22) and temp folder dele...
R08 | reminder | medium | Merge 6 Final_Delivery reads (9bd1ca1 d930be0 f272f70 36f01dd 9fc8d...
WAITING ON PL OR OTHERS: 12 questions; STALE: 6 waiting items older than 48 h, close or confirm with Ayush (pending.py list)

UNIQUENESS (last 3 builds; a new build must not repeat these): emberforge-vault-settlement: none (not a generator scaffold), Data Processing (no design field); vendor-archive-roundtrip-recovery: format-recovery, data-processing (no design field); schema-migration-plan-repair: repo-patch, data-processing (no design field)

HANDOFF FORMAT: a table with board sha, step, status and a clickable file link; never 'read and follow'.
