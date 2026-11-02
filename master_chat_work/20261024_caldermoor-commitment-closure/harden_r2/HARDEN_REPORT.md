# HARDEN_REPORT caldermoor-commitment-closure (593ecae, P9 r2, harden round 2 of 3)

Status: **PILOT_WEAK**. Final reflex score is 0.3519 after two strengthen tries (0.6014, then 0.4595, then 0.3519).
Every gate passes: oracle x3 1.0, owner 1.0, nop 0.0, stub 0.0, forgery 0.2346, precheck CLEAN, stacking PASS, xref 0.

## Diagnosis (detail in DIAGNOSIS.md)
- Phase A: **GENUINE**. The probe ran from a copy identical to BUNDLE, apart from harness staging. There was no exception, no verifier error, and the judge read the response.
- Primary cause: **4, the levers were weak by design**. Cause 3 is PARTLY: the P12 r1 cut did not reveal A or B, but the instruction hint "several rules are written in the document that owns the idea" (instruction.md:9-10) pointed the agent at A. Causes 1 and 2 are NO.
- In the probe the agent got lever A right in its first program, at 11 minutes. It fixed lever B in one edit after an audit row showed it. Both leaked because the rule docs explained the trap (W1): the cycle carve-out sentence and the "both discharged and waived is discharged" restatement.

## Levers: before / after
| lever | rule written at | before (probe 1) | after: one fact wrong, alone |
|---|---|---|---|
| A: blocked = any non-cycle commitment with a live outgoing blocking edge | dependency-semantics.md:50-51 | LEAKED (the 21.1% cost was not reached by the agent) | 54/162 = 33.3%, 12 tests |
| B: periods_waived = periods the walk takes on its second line | cadence-register.md:58-69 | LEAKED (15.8%) | 57/162 = 35.2%, 13 tests |
| C (new, H6/L3): one allowance of four waivers per principal across all its cadences, drawn by period start | cadence-register.md:49-54, 74-76 | n/a | 67/162 = 41.4%, 15 tests |
| coupling: envelope reserve = 30 x blocked lines + 15 x waived periods | commitment-protocol.md:189-195 | n/a | amplifier, counts 0 |

- Carriers: `allocated_minutes` in the ledger, queues, blocked_commitments, project_lineage and project_rollup; `waivers_granted`/`waivers_lapsed` in actor_roster; `dependent_blocked` in live_edges; `reserve_minutes` in month_load_index; `waivers_lapsed` in run_manifest.
- W1 cuts: the instruction hint, the cadence restatement, and the cycle explanation, which is now folded into the predicate.
- W5: the shipped seed drops 252 edges and 74 waivers, so the shipped data has no separating case for A or B. The hidden seeds keep them.
- If one lever is wrong and everything else is right, overall at the measured rubric of 47.37 would be A 57.0, B 56.1, C 53.0. All are below 70.

## Counts and weight shares
- Tests: 49 in total. 44 are positive, worth 162 points: 16 at w5, 27 at w3, 1 at w1. 5 are negatives, worth -21, and no single act costs more than 5.
- Judge: 12 criteria, +22/-12, batched. R12 (allowance, w3) is new and is shown by `check 4 ok`.
- reward.toml: test_output 0.5/162 = 0.0030864197530864196; judge 0.5/22 = 0.022727272727272728.
- Weight shares:
  - Hidden or mutated reruns: 119/162 = 73.5%. This is 14 `_hard` family tests, 10 probes, escalation, class partition, identity, determinism and failed_run.
  - Whole-document: 0. The old unseen_* full-exact tests were removed.
  - Shipped-only: 43/162 = 26.5%.
  - Mutation tests: determinism and failed_run, 6 points = 3.7%.
- RULE_COVERAGE has 39 rows and none has 0 tests. Rule r28 (reserve clamp) needed a small-envelope fixture on PROBE_SEEDS[10].

## Reflex gate
The agent program in OUT/agent_program was scored against the new tests with the local rewardkit stub. The stub scores oracle 1.0 and nop 0.0. The agent program gets 57/162 = **0.3519 > 0.20, so `PILOT WEAK: 0.3519`**.

The agent already had A and B right. It fails every family downstream of the reserve and the allowance (27 tests). It passes the upstream parsing, identity and alias families.

## Gates
| gate | result |
|---|---|
| precheck.sh (structure, instruction, tests, judge QC + exe_copy) | PRECHECK CLEAN. Warning A3: 49 checks against a cap of 35. |
| QC scripts | 0 FAIL |
| validate_bundle.py | 38 pass / 11 fail. All 11 fails are already present on the pre-round bundle (this is a converted non-generator bundle, so they are advisory). |
| xref_check | 8 entries, 0 findings |
| stacking_check + OUT/STACKING_CHECK.md | STACKING PASS. The tool's static hints were corrected by hand (G3, AL-28 lumping). |
| Docker (TS 20261024T192304-e086, warm verifier) | oracle 1.0/1.0/1.0, all of checks 1-4 ok; owner-only 1.0; nop 0.0; stub 0.0; forgery 0.2346 |
| kit HEAD | 976c166611e555e2ba20eb8d81bed279cee1ea30, fingerprints match |
| tree_sha | 2cede4bfa44d (65 files) |

Forgery is a program that replays the 28 shipped outputs. It scores 0.2346, earning only the shipped `_exact` w3 tests plus declared, and pays the -5 hardcoded penalty. That is below the genuine partial range of 0.35-0.67.

## Not run
- No live agent probe and no real-model judge run. The master issues the probe next.
- playground.py is not run; it no longer exists, per the round notes.
- My hash method does not reproduce the prompt's tree sha 751fb8be624d. The probe-1 bundle was confirmed identical to Tasks_INPUT and to the staged copy by diff instead.
- The session rename ran at the start (LOG.md line 1).

## Lessons for the master
- A rule-doc sentence that explains why a carve-out exists gives the lever away just as a figure does. Cut such sentences in P12, not only figures | template_change: knowledge/LEVER_RULES_v1.md W1 (add "explanatory consequences of a definition")
- If the agent gets the levers right, stacking downstream carriers reaches about 0.35 but not 0.20. You need one lever the reflex program misses upstream | no change: already in LEVER_RULES section 6 pilot lesson
- tests_qc rejects w2, so visible family tests must be w3. Plan shares with weights in {1,3,5} only | template_change: knowledge/LEVER_RULES_v1.md G1 (state allowed weights)
- A clamp rule (reserve larger than envelope) never fires on generated budgets and needs an explicit fixture. Mutants that lose 0 points are found only by the G11 batch | no change: AL-27 already requires it
- stacking_check counts `_hard` per-family tests as isolated and AL-28 lumps distinct acts into one group. Both had to be corrected by hand | template_change: tools/stacking_check.py (classify _probe-seeded tests as hidden; group negatives by act)
