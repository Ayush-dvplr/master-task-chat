# BUILD_REPORT: batch-lease-scheduler-replay (board 98c5c50)

Status: DONE (BUILD READY). Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/batch-lease-scheduler-replay/`. Session rename: `name_session.py 98c5c50` printed `codex: no match` and listed opencode `ses_e8c03c08bffeeJY1kiqaIMpcF3`; codex rename not shown, carried on.

## Tree (21 files)
- environment/: Dockerfile; data/ checkpoints.txt, dependencies.csv, durations.csv, events.jsonl, jobs.tsv, policy.ini, pools.json, project.zip (10 members), replay_contract.md, workers.csv (10 files)
- instruction.md (1416 chars), task.toml
- solution/: solve.sh, solve.py (embeds the repaired package), TRUTH.md
- tests/: Dockerfile, test.sh, test_output.py (37 checks, embedded generator and unit-step reference, shipped data embedded), reward.toml, judge.toml (9 criteria)
- tree_sha (sorted paths + contents) `90cf995ed64d`

## Data (8 formats, one book of 420 sets, seed 413927)
| file | format | lines |
|---|---|---|
| events.jsonl | jsonl | 19303 |
| jobs.tsv | tsv | 5505 |
| durations.csv | csv | 5505 |
| dependencies.csv | csv | 3571 |
| checkpoints.txt | txt | 2520 |
| workers.csv | csv | 2485 |
| replay_contract.md | md | 114 |
| pools.json | json | 28 |
| policy.ini | ini | 5 |
| project.zip | zip | binary, 10 members |
A5: 39073 lines total (>= 20000), every csv/tsv/jsonl/txt >= 2000. Chains: C1 checkpoints.txt -> set ids -> every table; C2 jobs.tsv + pools.json + workers.csv -> dispatch -> module_core; C3 durations.csv + policy.ini -> remaining/lease/backoff -> module_metrics; C4 dependencies.csv + events.jsonl (cancel/fail) -> release/cascade -> dependency_resolution; C5 all documents -> summary.json digest; plus 3 dependency chains of length 4 per set. No answer for any graded document in environment/ (W11).

## Levers (where each rule is written)
| lever | rule lines (environment/data/replay_contract.md) | checks | weight | share |
|---|---|---|---|---|
| LV-BS-1 exact replay across timestamps | 36, 46, 48-51, 53 (instant phases, dispatch at end of every instant) | 23 | 105 | 75.5% |
| LV-BS-2 attempt accounting | 38, 40, 57-68 (65 stale_attempt, 66 not_running) | 22 | 102 | 73.4% |
| LV-BS-3 dependency outcomes | 42, 48 (release), 59 (redelivery), 90 (edge outcome) | 22 | 102 | 73.4% |
No secondary stated-rule lever. Shares overlap through the coupling quantity (one replayed timeline feeds all four documents; contract l5 "Every reported figure of a set is computed from the replayed timeline that produced it."). Contract deviation from IDEA wording: expiry and retry-ready are one phase (their relative order provably never changes a result; mutant READYFIRST lost 0); the sentence "a job preempted during a dispatch waits for a later instant" was dropped for the same reason.

## Weights and shares
37 checks (WARN A3 recorded, no merges), positive 139; negatives negative_package_reads_grader_paths -5, negative_hardcoded_sample_answers -3. Hidden or mutated reruns 117/139 = 84.2%; whole-document exact 102/139 = 73.4%; shipped-only 12/139 = 8.6%; isolated (invariants, refusals, package) 34/139 = 24.5%. Judge: 9 criteria, positive 24 (R1-R5 conduct recomputations, R6 J9 altered copy, R7 code quality, R8 changed-files list), R9 honesty -3.

## Interaction cases per hidden corpus (sets carrying / times fired; 3 sets per corpus) and shipped book
| case | hidden 1 | hidden 2 | hidden 3 | hidden 4 | shipped (420 sets) |
|---|---|---|---|---|---|
| coinc3 | 3/13 | 3/12 | 3/18 | 3/11 | 104/122 |
| coinc_comp_exp | 3/20 | 3/23 | 3/35 | 3/20 | 242/344 |
| coinc_x_ready | 3/41 | 3/45 | 3/49 | 3/41 | 185/344 |
| token_at_deadline | 3/50 | 3/76 | 3/71 | 3/46 | 258/473 |
| event_at_internal | 3/122 | 3/147 | 3/155 | 3/142 | 368/928 |
| resume_before_old_finish | 3/132 | 3/195 | 3/166 | 3/165 | 201/346 |
| preempt2_expire | 3/13 | 3/16 | 3/16 | 3/7 | 34/38 |
| token_on_preempted | 3/134 | 3/248 | 3/217 | 3/219 | 55/71 |
| stale_while_retry_runs | 3/93 | 3/92 | 3/88 | 3/84 | 237/395 |
| cancel_running_resumed | 3/19 | 3/24 | 3/34 | 3/24 | 12/13 |
| cancel_preempted_with_children | 3/8 | 3/21 | 3/20 | 3/17 | 21/22 |
| cascade_waiting | 3/29 | 3/40 | 3/41 | 3/45 | 326/1185 |
| cascade_unsubmitted | 3/41 | 3/48 | 3/43 | 3/47 | 140/283 |
| cascade_depth4 | 3/17 | 3/18 | 3/15 | 3/16 | 207/441 |
| redeliver_boost | 3/82 | 3/105 | 3/66 | 3/110 | 96/107 |
| redeliver_cancel | 3/22 | 3/14 | 3/15 | 3/23 | 21/21 |
| victim_tie_start | 3/6 | 3/8 | 2/7 | 3/9 | 92/94 |
| victim_tie_prio | 3/29 | 3/35 | 3/52 | 3/48 | 24/28 |
| preemption | 3/162 | 3/255 | 3/230 | 3/217 | 229/502 |
| eviction | 3/8 | 3/12 | 3/6 | 3/9 | 58/60 |
| expiry | 3/81 | 3/119 | 3/130 | 3/76 | 398/2322 |
| dead | 3/33 | 3/54 | 3/55 | 3/40 | 343/857 |
| audit_redelivery | 3/189 | 3/233 | 3/165 | 3/235 | 286/453 |
| audit_finished | 3/134 | 3/153 | 3/150 | 3/173 | 357/882 |
| audit_stale_attempt | 3/152 | 3/172 | 3/169 | 3/143 | 299/739 |
| audit_not_running | 3/134 | 3/248 | 3/217 | 3/219 | 55/71 |
| event_submit | 3/271 | 3/333 | 3/352 | 3/347 | 420/5315 |
| event_heartbeat | 3/850 | 3/1105 | 3/960 | 3/972 | 420/10989 |
| event_fail | 3/192 | 3/241 | 3/231 | 3/246 | 324/691 |
| event_cancel | 3/91 | 3/78 | 3/95 | 3/97 | 212/281 |
| event_boost | 3/285 | 3/309 | 3/248 | 3/308 | 392/1160 |
| event_worker_down | 3/14 | 3/15 | 3/12 | 3/17 | 198/247 |
| event_worker_up | 3/19 | 3/12 | 3/15 | 3/13 | 128/148 |
| redeliver_submit | 3/10 | 3/20 | 3/18 | 3/23 | 83/93 |
| redeliver_heartbeat | 3/52 | 3/73 | 3/48 | 3/56 | 156/192 |
| redeliver_fail | 3/17 | 3/12 | 3/12 | 3/19 | 13/13 |
| redeliver_worker_down | 1/2 | 2/3 | 1/2 | 2/2 | 17/17 |
| redeliver_worker_up | 2/4 | 3/6 | 3/4 | 2/2 | 10/10 |
| boost_unsubmitted | 3/73 | 3/43 | 3/38 | 3/73 | 256/430 |

Edge outcomes: hidden 1 broken 94 / open 6 / satisfied 26; hidden 2 102/17/34; hidden 3 108/8/45; hidden 4 113/10/38; shipped 1781/481/1308. Events per hidden set 509-998; shipped 18-67.

## Cost table (real tests, patched fixed package; overall = 0.5 tests + 45)
| row | lost % | overall |
|---|---|---|
| LV-BS-1 alone (LAZY+FW2) | 75.5 | 57.2 |
| LV-BS-2 alone (PREFAIL+STALE) | 73.4 | 58.3 |
| LV-BS-3 alone (ANYTERM+REDUP) | 73.4 | 58.3 |
| FIRSTWRITE (FW3b+FW4+FW5) | 73.4 | 58.3 |
| FW1 / FW2 / FW4 / FW5 / PREFAIL / STALE / ANYTERM / SUBORDER / PEREVENT | 73.4 each | 58.3 |
| LAZY 71.9, REDUP 69.8, FW3b 56.8, EXPFIRST 51.8 | | 59.0 / 60.1 / 66.6 / 69.1 |
| slips FW3 36.7, PRECSWAP 36.7, FW2R 20.1 (not levers) | | 76.7 / 76.7 / 84.9 |
Full table WORK/COST_TABLE.md; rule coverage WORK/RULE_COVERAGE.md 55 rows, 0 uncovered.

## Expected loss per lever (careful solver)
- LV-BS-1: hidden_book_1..4 core/metrics/deps/summary, rows_reshuffled, policy_changed (completion+expiry+ready at one instant, heartbeat at the deadline, resume before old finish).
- LV-BS-2: same documents, driven by token_on_preempted, stale_while_retry_runs, preempt2_expire, cancel_running_resumed.
- LV-BS-3: same documents, driven by cascade through waiting/unsubmitted chains of 4, redelivered cancels/boosts, cancel of preempted parents.

## Gates
- QC scripts: instruction_qc 5/0/0 PASS; structure_qc 17 pass, WARN X1 (project.zip binary), 0 fail; tests_qc 35 pass, WARN A3 (37 checks), 0 fail, O1 overlap 3%; judge_qc 19/0/0 PASS.
- validate_bundle.py --archetype build-repair: 40 passed, 0 failed, 0 warnings, GATE PASS.
- check_exact.py (unit-step, own parser): shipped 420 sets 0 diffs; 300 generated sets 0 disagreements; override-removal probe (drop redelivered copies) moves audit in 279 sets.
- Timing (Docker python:3.12-slim, 4-set book at bounds): reference package 0.36 s, unit-step simulator 1.47 s; limit 60 s.
- Harbor oracle x3: 1.0, 1.0, 1.0; nop 0.0 (judge removed in copy per QL procedure).
- Stacking: STACKING PASS (OUT/STACKING_CHECK.md).
- PRECHECK last line: `PRECHECK CLEAN` (IN17 phrase warns on counts cleared by rewording instruction.md).
- Fingerprints GEN 160 and QC 12 files re-checked after the build: 0 differences.

## Open conflicts
None. TRUTH provenance keeps the scaffold keys; validator 15.5 passes, no forbidden keys (no Q18).

## Not run
Probe run and blind reads (master's next step). Oracle x5 (Ayush: x3).

## Lessons for the master
- Every slip is a stated sentence; hardness rests on whether solvers make interaction slips, so blind reads decide it | no change: probe gate already covers it
- Rule-coverage mutants exposed two contract sentences with no effect (READYFIRST, victim waits); drop such sentences early | template_change: LEVER_RULES_v2.md G11 add "write the mutant before the sentence"
- precheck IN17 lint flags deliverable counts ("seven files"); reword without numbers | no change: warn-only
