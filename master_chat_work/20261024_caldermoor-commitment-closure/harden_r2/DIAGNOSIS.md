# DIAGNOSIS 593ecae caldermoor-commitment-closure, P9 harden r2

Probe 1 (job `H/jobs/caldermoor-commitment-closure`, trial `__riweGRq`, claude-opus-5, 24 Oct 11:45:48Z to 12:06:39Z):
tests 133/133 = 100.00, judge 9/19 = 47.37, overall 73.69. Last hard baseline: v0 run (archived job
`H/jobs/_archive/caldermoor-commitment-closure-20261024T173751`, 19 Oct): tests 74.44, rubric 100, overall 87.22,
failing exactly the eight tests that read lever A and lever B.

## Phase A: GENUINE

| check | evidence | verdict |
|---|---|---|
| copy vs BUNDLE | `diff -rq H/Tasks_INPUT/caldermoor-commitment-closure BUNDLE` identical; staged copy differs only in `.kiro-staged-from` and task.toml `allowed_hosts` + `host.docker.internal` (harness staging) | ok |
| result.json | `exception_info: null`, verifier reward 0.7368 | ok |
| timeouts / crashes | trial 20 min 51 s of 8 h budget; no Traceback, Errno 13 or Permission denied in trial.log or reward-details.json | ok |
| verifier | test-stdout `reward: 0.7368`; 38 tests ran, all positives True, all negatives False; ctrf complete | ok |
| judge read the response | gpt-5.6-sol batched, 11 per-criterion reasonings citing steps 59, 65, 66 and the final message | ok |
| harness integrity | wrapper.log "all 1 trial(s) completed cleanly"; finalize rescale 0.7368 to 73.69 | ok |
| kit | HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30 as expected; qc.json 12 and pl_generator.json 160 fingerprints match | ok |

Tree hash note: the round-notes method (sha256 over sorted paths and contents) gives 6ed520ad1af9 with no
separator; nine separator variants were tried and none gives the prompt's 751fb8be624d. The bundle is byte
identical to Tasks_INPUT, so the difference is the hashing convention, not the content.

## Root cause

| # | cause | verdict | evidence |
|---|---|---|---|
| 1 | run error or wrong copy | NO | Phase A above |
| 2 | harness or rescoring change | NO | kit HEAD and fingerprints unchanged; tests channel is rewardkit programmatic, unaffected by the judge rebuild |
| 3 | our QC/fix rounds made it easier | PARTLY | see below |
| 4 | levers weak by design | YES (PRIMARY) | see below |

### Cause 3: files changed since the last hard baseline (v0 archive `.master-queue/task-archive/caldermoor-commitment-closure-20261024T155943`)

`diff -rq archive BUNDLE`: instruction.md, solution/TRUTH.md, solution/solve.py, solution/solve.sh,
tests/Dockerfile, tests/judge.toml, tests/reward.toml, tests/test.sh. No data file and no rule document changed.

| file | agent sees it | put a rule, figure or separating example in front of the agent |
|---|---|---|
| instruction.md (lines 86-140 cut, 141-142 reworded) | yes | no for A and B: none of the twelve figure lines or units A-G named a closed dependent on a live edge or the `periods_waived` count. Line 8 (a waiver returning the streak to zero) and line 10 (a cycle of holding commitments blocked the ordinary way) sat next to B and A but were deleted, not added |
| solution/*, tests/* | no (verifier side) | no |

Master's question: did the P12 r1 cut of instruction.md:86-138 or anything else in 8826f3a put A or B in front
of the agent? No. Nothing new reached the agent. The cut did remove the twelve-figure counterfactual workload:
v0 ran 33 steps in 44 min and spent them on the figures, while probe 1 ran 69 steps in 18.5 min and spent
steps 33-66 on self-audit of its own outputs. That audit is where B was caught (step 41). This contributes, it is
not the cause, and both runs are n=1.

### Cause 4: the levers were weak by design (PRIMARY)

Lever A, blocked set = any non-circular commitment with a live outgoing blocking edge.
- Rule: dependency-semantics.md:50 "A commitment is blocked when at least one live edge leaving it carries a
  block." A bare property in the governing file (good form).
- What gave it away: (a) the agent's first program (step 32, 11:57:13, before any output was seen) already
  used the predicate, so the plain sentence was read correctly first time; (b) dependency-semantics.md:72-74 "no
  cycle member appears among the blocked commitments" is a carve-out that only matters if non-BLOCKED classes can
  be blocked, and the agent said exactly that in its reasoning; (c) instruction.md:9-10 "several rules are written
  in the document that owns the idea, not in the document that first uses it" told it to prefer
  dependency-semantics over the protocol's class table, and it quoted this hint; (d) shipped data separates the
  readings: its own audit printed 347 blocked lines against class_blocked 156 (step 35), so the shipped extract
  showed the case (W5 broken).
- Cost by design: 28/133 = 21.1% alone (P12 COST_TABLE), under G10.

Lever B, `periods_waived` excludes waivers in a discharged period.
- Rule: cadence-register.md:51-59 walk table "take the first of these that applies"; `periods_waived` defined
  nowhere except the column name at output-contract.md:137-139.
- What gave it away: cadence-register.md:61-64 spells the trap out ("A period that is both discharged and waived
  is discharged, the waiver in it is inert, and the streak returns to zero", a W1 restatement with "therefore");
  shipped data separates the readings (74 INERT waivers; CAD-001 printed 38 elapsed = 5 + 11 + 22), so a
  partition self-check (periods_elapsed == discharged + waived + debt, step 42) exposed it.
- Trajectory step where it was right: step 41 (11:59:07) edit moved `waived += 1` under `elif is_waived`; the
  first program (step 32) had it wrong.
- Cost by design: 21/133 = 15.8% alone.

Both levers are owned only by their own files plus the whole-document unseen tests; no stated quantity carries the
blocked set or `periods_waived` into other deliverables, so even both wrong (v0) cost only 34/133.

PRIMARY CAUSE: 4. Contributing: 3 (figure workload removed, agent time moved to self-audit), single-run variance.

## Lever table (probe 1, reward-details.json + trajectory)

| lever | checks reading it | points | earned | levers in it | status |
|---|---|---|---|---|---|
| A blocked predicate | closure_and_blocked_exact, audit_and_reconciliation_exact, unseen_alpha/beta/gamma_full_exact, validation_report_residuals_zero | 28 | 28 | A | LEAKED (step 32, read right first time; shipped data showed 347 vs 156) |
| B periods_waived | cadence_and_waiver_exact, cadence_streak_and_waiver_semantics_exact, unseen_* | 21 | 21 | B | LEAKED (step 41 after partition self-check on shipped CAD-001) |
| judge R4 own extract, closed dependent | R4 | 3 | 0 | A conduct | HELD (inspected shipped extract only) |
| judge R5 own extract, waiver in discharged period | R5 | 3 | 0 | B conduct | HELD |
| judge R3 code quality | R3 | 3 | 0 | none | HELD (publish ~330 lines) |
| judge R7 file listing | R7 | 1 | 0 | none | HELD |

## Trajectory autopsy (B1)

| phase | steps | time | what |
|---|---|---|---|
| read rules | 3-7 | 11:46:19-11:46:30 (15 s) | all eight documents with `cat`, protocol first, contract last |
| explore data | 8-31 | 11:46:34-11:53:38 (7 min) | heads of every feed, encodings, explore.py and load.py in /app/work, cadences and waivers at step 27 |
| write program | 32 | 11:57:13 | /app/work/reconcile.py in one write, 1727 lines; A already right, B wrong |
| self-tests | 33-50 | to ~12:01 | run, input-untouched diff, identities I1-I5 zero, determinism, class Counter (347 vs 156), contests, aliases; step 41 B fixed, step 42 asserts the per-cadence partition |
| graded-logic edits | 41, 51 | | 41 waiver count (B); 51 allocation survivor rule |
| refactors | 52, 56, 63, 64 | | retired_feeds, lambda to def, unused field, out_dir guard |
| publish + reruns | 57-66 | to 12:04 | publish to /app/out, byte-identical rerun, copy without the .md documents (ex1), ex2, malformed rows appended (ex3) |
| final message | 69 | 12:04:48 | lists the A and B readings explicitly |

Self-tests covered A (indirectly, via counts on shipped data) and B (partition assertion on shipped data). It
never built an input of its own for either lever, which is why R4 and R5 held.

Agent program and its outputs saved at `agent_program/reconcile.py` (1732 lines) and `agent_program/outputs/` (28 files).

## LEAK_LIBRARY rows

| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| CC-A blocked predicate vs class BLOCKED | dependency-semantics.md:50 bare property; :72-74 cycle carve-out names "blocked commitments"; instruction.md:9-10 "rules written in the document that owns the idea"; shipped data 347 vs 156 | step 32 (first program); confirmed step 35 | W5 (strip separating cases from shipped data), W1 (cut the instruction hint), G1 coupling (envelope reserve reads blocked_commitments.csv) |
| CC-B periods_waived on a discharged period | cadence-register.md:51-59 walk table plus :61-64 restatement of the trap; column undefined in output-contract.md:137-139; shipped 74 INERT waivers | step 41 after partition self-check on CAD-001 | W1 (cut :61-64), W3 (define the column by the walk line), W5 (no waiver in a discharged period in shipped data), G1 coupling (reserve reads periods_waived) |

Planned fix (Phase 2): keep A and B; add lever C (H6, a waiver allowance per principal drawn across all its
cadences in period order); one stated COUPLING quantity, the envelope reserve in protocol section 9, reads
`blocked_commitments.csv` and `periods_waived` so a slip on A, B or C moves allocation, load, escalation, rollups,
audit and manifest rows; whole-document unseen tests replaced by one hidden `_hard` test per deliverable family;
shipped data carries no case that separates any lever.

## Lessons for the master
- Shipped data that separates a lever lets a self-auditing agent fix it from its own outputs | template_change: LEVER_RULES_v1.md W5 already says so; no change: rule existed, bundle broke it
- Removing a large what-if workload frees the agent's budget for self-audit | no change: expected side effect, note for future figure cuts
