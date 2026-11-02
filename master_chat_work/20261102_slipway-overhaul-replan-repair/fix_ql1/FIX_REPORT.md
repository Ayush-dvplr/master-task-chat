# FIX_REPORT 481e976 slipway-overhaul-replan-repair, fix-ql1 (QL1 review findings)

Route 1 (Ayush 2 Nov "1. okay"). Bundle tree before 2f83a9bd6a10, after 8caebf1e3549.
Kit live Input_Bundle_QC HEAD 5574d77e. No commit, push or PR. No subagents.

## Findings fixed

| QL finding | label | change (file:line, old -> new) | playbook row | QC rules re-checked |
|---|---|---|---|---|
| QL1-F1 | category mismatch | task.toml:12 `category = "Optimization"` -> `category = "Debugging"`; keywords :8 and tags :14 keep `optimization`; TRUTH.md provenance `category: Debugging`. Harness has no enforced list (free string); Debugging is already used by Tasks_INPUT/sentinel-policy-recompute and is the example kit 01:42 names | no playbook row; kit 01:42 IN-12, 05:59 AL-26 | IN-12, AL-26, structure_qc, validator |
| QL1-F2 | unsettled empty kind | environment/data/spec_stage_p13_amendments.md:7-9 adds one general clause: "A lodged precedence amendment whose kind is still empty after that completion step is lodged as `hard`." Matches tests/test_output.py:3023 and :3029 `payload.get("kind", "hard")`. Minted p13 copy in tests mirrored byte for byte. No expected value moves | IN-16 (one settling clause, general case, no worked figure) | IN-16, AL-18, xref |
| QL1-F3 | amendments applied count | environment/data/output_schema_reference.md:160-162 (doc 23) adds "The amendments applied counts every lodged amendment of the round, rejected ones included."; :176-177 (doc 25) adds "`amendments_applied` counts every lodged amendment of the round, rejected ones included." Matches test_output.py:3490 `"amendments applied " + str(len(records))` and :3514 `"amendments_applied": len(records)`. Minted schema copy mirrored. No expected value moves; nothing near the lever | IN-16 | IN-16, AL-18, xref |
| QL1-F4 | oracle does not open the two papers first (R3) | solution/solve.sh:10-14 new, before solve.py extracts project.zip: `echo "== /app/data/00_open_this_first.txt"; head -n 12 ...; echo "== /app/data/replan_programme_contract.md"; head -n 12 ...`. TRUTH.md solution shape steps 1-2 rewritten to that order; ordered plan step 1 (Covers R3) now true. oracle-1 agent/oracle.txt line 1 and line 14 are the two headers | JD-7 (fix oracle + TRUTH, never loosen criterion) | JD-7, JUDGE_MAP R3 |
| QL1-F5 | oracle shows R4, R6, R10 short | solve.sh feasible_sets :169 also keeps every passing mask; check_tie_and_count :210: R4 report :226 prints both tied sets' members and weights and names the kept set; R10 fails at :232 unless the winning charge equals the engine's, report :233 counts subsets of selectable jobs passing group and capacity at the winning charge (old: distinct closed sets "PCT-FNW 2 sets"); check_counters :256 prints every stage's three counters beside the withdrawn row with DIFFERS marks, report :273 names every differing stage (old: "15 stages differ, first amendment/1"). TRUTH ordered plan step 7 rewritten to match | JD-7 | JD-7, JD-5 (R4/R10 still read different observables), JUDGE_MAP R4/R6/R10 |
| QL1-F6 | stdlib positive passes on an import scan | tests/test_output.py `_drive` (:5192) gains `bare` (interpreter `-S`); test_delivered_engine_stdlib_only (:5361) now runs the delivered engine bare on the sample round, needs every document present and parsing in its shape and doc 18 equal to the reference; weight 1 kept (:6091). Import scan moved to new negative test_negative_weight_imports_outside_the_standard_library (:5693, criterion :6059, registered :6132 weight -3), sentence quoted in WORK/QC_DEFENCE.md; stands down where negative_rebinds_verifier_dependencies fires (AL-28 group max 3). Unrepaired shipped engine now scores 0 on the positive (lane unrepaired-1) | TS-25 (assert on earned output, never delete check and weight) | TS-25, TS-13, TS-14, TS-16, TS-26, AL-28, G5 |
| QL1-F7 | honesty negatives double charge | tests/judge.toml:196 R15 adds "other than where R13 already charges the same claimed check"; :209 R16 adds "other than where it gives the withdrawn figure as the value of a delivered file under /app/out, which R14 already charges". Weights unchanged (R13 -3, R14 -5, R15 -3, R16 -3). judge_qc 19 pass 0 warn 0 fail | AL-28 (stand-down, never touch positives) | JD-5, JD-8, JD-14, JD-15, JD-16, AL-28 both layers |
| QL1-F10 | manifest wording | output_schema_reference.md:165 "One line per document above" -> "One line for every other document, 01 to 23 and then 25, in this numbered order"; agrees with p14:5-7 and shipped publish.py | DS-6 (names consistent) | DS-6, xref |
| QL1-F11 | TRUTH says DFC-16 quiet | solution/TRUTH.md:55-59: "Left unrepaired, `DFC-16` moves the shipped round's documents 02, 19, 23, 24 and 25: lodgements naming a job of a cycle are rejected under `EDG-UNKNOWNJOB` (p02). The shipped round leaves the other eleven quiet or coincident" | DS-22 (TRUTH to shipped, shas by script last) | DS-22, AL-18 |
| QL1-F13 | tests comments stale | test_output.py:9-12 docstring "three rounds minted from seeds it has never seen and eleven held-out rounds" (MINTED_SEEDS 3 at :4955, HELD_ROUNDS 11); :3797-3803 PACKAGE_FILES comment: fifteen catalogued faults DFC-01 to DFC-15 repaired, DFC-16 to DFC-27 still present (measured: DFC-01..15 new anchors present, DFC-16..27 old anchors present) | DS-22 | DS-22, TS hygiene |

TRUTH.md also: Channel A 50 checks, 32 positive weighing 112, 18 negative weighing -66; the new negative listed; `fix_patch_sha256` recomputed by script last (solve.sh); `solve_py_sha256` unchanged.

## Kept (OUT/KEPT.md)

TS-20, TS-23 (carried from fix2_qcv2/KEPT.md; TS-23 now 50 checks), QL1-F8 FP (01:91), F9 OOS (DS-6 02:22, unused header field), F12 KEEP (JD-5 04:71, two facets of one comparison; oracle side fixed under F5), F14 FP (X1, QC v3:82), F15 FP (TS-23 03:62), F16 FP (TS-24 03:68-72), F17 OOS (JD-15 04:92, JD-12 04:89), F18 OOS (AL-8 05:44).

## AL-28 hand table (stacking_check.py cannot read stand-down text)

| act | negatives | max charge |
|---|---|---|
| shadows a verifier dependency / imports outside stdlib | rebinds -3, imports_outside_stdlib -3 (stands down where rebinds fires) | 3 |
| claims a check passed or covered more | R13 -3, R15 -3 (stands down where R13 fires) | 3 |
| reports withdrawn figure as standing | R14 -5, R16 -3 (stands down where R14 fires) | 5 |
| hardcoded sample answers | -5 | 5 |
| each unrepaired trap fault (shift_length_flat, pool_weights_flat, deferral_rescinded, drafting_register, capacity_strict, set_ranked_charge_alone, rebate_before_surcharges, penalty_every_job, cascade_first_hop, cascade_never_stopped, withdrawal_inert, package_ignores_input), nondeterministic, filename, reads corpus | one negative each, distinct act | <=5 each |

Judge negatives charge final-answer claims; test negatives charge code acts; no act is charged in both layers.

## Gates

- xref_check.py: 11 entries, 0 findings (WORK/XREF.md).
- stacking_check.py: OUT/STACKING_CHECK.md, rc 0; G3 hidden/mutated 43.8% PASS; TS-26 3 groups pre-existing (CHECK BY HAND, unchanged); AL-28 tool FAILs resolved by the table above.
- Live kit 5574d77e: structure_qc 17/1/0 (X1 binaries), instruction_qc 5/0/0, tests_qc 34/1/0 (A3 50 > 35 = TS-23 kept), judge_qc 19/0/0.
- validator build-repair: 38 passed, 1 FAIL S1.12 pre-existing archetype manifest (noted since fix1).
- PRECHECK last line: `PRECHECK CLEAN` (logs/precheck3.log, WARN X1, WARN A3).
- G7 tests/ byte diff: test_output.py hunks only at docstring :12, PACKAGE_FILES comment, minted p13/schema copies, `_drive`, stdlib positive, new negative, criterion description, new criterion, registration; judge.toml :196 and :209 only; reward.toml byte identical (test 0.004464285714285714 = 0.5/112, judge 0.013888888888888888 = 0.5/36). Lever checks package_crosswalk_* untouched.

## Lanes (live kit exe_copy.py copies; dockfree START=yes each; harbor, no --delete)

| lane | reward | pos/neg | verifier s |
|---|---|---|---|
| oracle-1 | 1.0 | 112/0 | 130.1 |
| oracle-2 | 1.0 | 112/0 | 107.6 |
| oracle-3 | 1.0 | 112/0 | 123.3 |
| owner-only | 1.0 | 112/0 | 146.0 |
| nop | 0.0 | 0/0 | 140.9 |
| stub | 0.0 | 0/0 | 164.0 |
| forgery | -0.0089 | 4/-5 (hardcoded_sample_answers) | 130.8 |
| unrepaired shipped engine (G5) | 0.0268 | 3/0; delivered_engine_stdlib_only 0 | 175.6 |
| a4 out replay | 0.2232 | 25/0 | 148.6 |
| a3 program | 0.4643 | 52/0 | 154.3 |

Max verifier 175.6 s of limit 5400 (3.3%). Stream ALL_DONE 16:01; lanes.sh exited, no harbor child left. Logs: _runs/20261102/slipway-overhaul-replan-repair/fix3-20261102T1448/lanes/logs/.

## Score check (no paid run)

- a4 tests on final tests: 25/112 = 22.32, the same eleven checks as the original grading (four structural weight 1, seven shipped_* weight 3). No move: a4's sample doc 18 equals the reference, so the bare run keeps the stdlib point; a4's engine imports only the standard library, so the new negative stays silent.
- a4 judge on final judge.toml, by hand: 9/36 = 25.0 (R1, R2, R3 met; R4-R12 unmet; R13-R16 all 0). R15/R16 only changed where R13/R14 fire, and neither fired, so no move. Final 0.5 x 22.32 + 0.5 x 25.0 = 23.66, as predicted.
- a3 program tests: 52/112 = 46.43, lever 0/60, the same twenty checks as before (no move).

## Trap survival (lever package_crosswalk_*, 60 points)

| run | before | after |
|---|---|---|
| oracle | 60/60 | 60/60 |
| a4 | 0/60 | 0/60 |
| a3 program | 0/60 | 0/60 |
| unrepaired shipped engine | 0/60 | 0/60 |

## Not run

Paid attempt 5; API judge re-grade (OPENAI_API_KEY=unused, re-grade by hand); QC v4 recheck (master issues it).

## Tasks_INPUT

rsync -a --delete BUNDLE/ -> Tasks_INPUT; diff -rq empty; tree sha BUNDLE 8caebf1e3549 = Tasks_INPUT 8caebf1e3549; no __pycache__. Per-file digests before/after: OUT/DIGESTS.md (7 changed, 62 byte identical).

## Lessons for the master

- A weight 1 "stdlib only" check must run the engine with `-S`; an import scan pays the unrepaired engine.
- Stand-down text must sit in the same sentence (precheck JD-5 counts sentences; judge_qc forbids "not", "without").
