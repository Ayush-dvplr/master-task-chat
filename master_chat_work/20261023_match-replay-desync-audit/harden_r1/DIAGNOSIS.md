# DIAGNOSIS: match-replay-desync-audit (P9 v2 r1, board 91cc2af)

Run: claude-opus-5, openhands-sdk, trial `.kiro-run-match-replay-desync-audit-20261020T103223`, 2026-10-20 05:02 to 05:43 UTC. Copy: `baseline_v0/trajectory_job_match-replay-desync-audit_6237b4/`. BUNDLE tree sha `6711dce7a011` (equal to SOURCE). Kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e, fingerprints unchanged.

## 1. Phase A: is the score genuine? GENUINE

- `reward.json` 0.8043 = (test_output 103/163 + judge 42/43) / 2, from `reward-details.json` weights 0.5/163 and 0.5/43. Confirmed.
- No `Permission denied`, `Errno 13`, `NOT_RUN` or `Traceback` anywhere in the job copy. `agent/instruction.txt` equals `instruction.md` byte for byte.
- The 12 failed checks are all `trap_*` (12 x 5 = 60 points). Local replay of the real `tests/test_output.py` (rewardkit stub) on the delivered `/app/out` reproduces ctrf exactly: 28 pass, 12 fail, negatives silent. Every failure message is `the delivered program exited 1: CTRL-A does not single out frame_bias_limit (12 values reproduce its figure)` (padded: CTRL-B, 14 values). This is the agent's own assertion at `optimize.py:891` (`if len(matched) != 1: raise SystemExit`), not a permission artefact: the `general_*` checks run under the same uid drop and all passed.
- The failure is real but accidental. The trap corpora set a single wire flag, so most transforms are off and several candidates reproduce the early controls. calibration.md says "At least one value of that further quantity reproduces the figure"; instruction.md:3 says "In the slice shipped here, exactly one value ... reproduces". The agent coded the instruction's promise. **Changing `!= 1` to `< 1` (one line) makes the same program pass all 12 traps: 163/163 on the current tests.** So no designed trap held.

## 2. Root cause

| cause | verdict | evidence |
|---|---|---|
| 1 run error / wrong copy | NO | instruction, tests and judge of the run equal the bundle; reward formula reproduced; local replay equals ctrf. |
| 2 harness / rescoring change | NO | after the run only `tests/judge.toml` (criteria and weights unchanged; mode line) and `tests/test.sh` (chown/chmod) changed, on Oct 21. test_output.py, reward.toml, instruction.md, notes and TRUTH.md equal the fixplan_v2 "after" hashes. |
| 3 conversion / QC fixes made it easier | PARTLY | QC v1/v2 fixes put every judged figure into instruction.md:11 (first divergence position and tick, deepest word and depth, last promotion, echo count), so R7-R13 (35 of 43 judge points) were free for any program that computes them. The QC v1 sentence at instruction.md:3 ("exactly one value reproduces") is a shipped-slice promise; by accident it cost the agent 60 points. |
| 4 levers weak by design | **YES, PRIMARY** | all 12 wire transforms are stated exactly in replay-format.md and all are switched on together in the shipped captures, with CTRL-A..I fingerprinting each decode stage, so a decoder that passes the shipped controls is right for every transform alone. The engine rules (identity chase, windows, earliest-cancel reversals, coupled stocks, cap, cadence, bench) are plain sentences, and every `general_*` check passed. |

**PRIMARY CAUSE: 4.** Contributing: 3 (figure list in the instruction, shipped-slice promise). Also: every corpus, shipped or hidden, uses the same TRUE_VALUES, and no settlement rule depends on the order in which entries are walked except cancellation.

### Cause 3 file list (conversion + QC v1 + QC v2)
| file | change | put a rule, figure or separating case in front of the solver? |
|---|---|---|
| instruction.md:3 | v1 "In the slice shipped here, exactly one value of that further quantity reproduces the published figure." | YES, a shipped-slice promise (banned form); it caused the agent's crash |
| instruction.md:7 | v1 "recovers the eleven quantities from the calibration notes each run" | no, format |
| instruction.md:11 | v1/v2 final-message figure list (T4 now asks word AND depth) | YES, names every judged figure |
| instruction.md:13 | v2 two-minute limit | no |
| data/calibration.md | v1 "At least one value ... reproduces the figure" | no, correct general rule |
| data/replay-format.md | v1/v2 "entry lines the capture carries", "one per wire transform" | partly, clarity only |
| tests/test_output.py, reward.toml | v1/v2 tiebreak seats, cap corpus, serialization split (40 checks, 163) | no (hidden) |
| tests/judge.toml | v1/v2 R7-R10/R12 "The agent states/names ...", R2/R3 evidence, R17 | YES via instruction:11 (J1 violation) |
| solution/*, task.toml | oracle rewrite, tags, category | no |

## 3. Lever table (ctrf + trajectory)
| check | pts | earned | lever / trap | status |
|---|---|---|---|---|
| format_program_delivered | 1 | 1 | format | n/a |
| record_derivation_matches | 1 | 1 | calibration order and falsifiers | LEAKED |
| instance_scenario_visible / perf_report / recommendations / data_quality | 20 | 20 | whole engine on shipped data | LEAKED (shipped-only) |
| instance_report_serialization | 1 | 1 | format | n/a |
| general_scenario_peak / steady / latency | 15 | 15 | cadence classes, hidden | LEAKED |
| trap_sealed .. trap_warded_inverse (12) | 60 | 0 | one wire transform each | LEAKED (lost only to the uniqueness assertion; adapted copy passes all 12) |
| general_deep_identity_chain | 5 | 5 | identity chase | LEAKED |
| general_charter_cap_surplus | 5 | 5 | per-entry cap | LEAKED |
| general_empty_charter | 5 | 5 | empty charter baseline | LEAKED |
| general_window_boundary_shift / degenerate_window_live / dead_window | 15 | 15 | live windows | LEAKED |
| general_reversal_density / reversal_tiebreak | 10 | 10 | earliest cancel | LEAKED |
| general_population_scale / baseline_scale | 10 | 10 | scale | LEAKED |
| general_cadence_partition | 5 | 5 | cadence modulus | LEAKED |
| general_fixpoint_new_unit | 5 | 5 | settling passes | LEAKED |
| general_donor_table_rotation | 5 | 5 | aliased donor ring | LEAKED |
| 5 negatives (-5,-5,-5,-5,-3) | -23 | 0 | cheating acts | did not fire (correct) |

Total 103/163. Judge 42/43: only R3 (append each rejected candidate at the moment it is discarded) missed; R7-R13 earned from the final message the instruction asked for.

## 4. Solve autopsy (102 steps)
- Read order: 3-4 `ls`/`find /app/data`; 5 `cat` all five notes (replay-format, calibration, engine-rules, charter-scale, report-schema); 6 the three csv files and the example; 7-8 capture headers and the two flag-zero samples.
- Step 9 wrote `bottleneck_analysis.json` with the full candidate sets (R1). Steps 9-93: a `_probe.py` loop peeling one transform and pinning one quantity per round against its control; the record was edited in bulk after probes (R3 miss).
- Step 94 wrote `optimize.py` once (with the uniqueness assertion); 95 emptied `/app/out` and rebuilt in one run; 96-100 checks on `/app/data` only (byte compare with the example, rerun into a second dir, determinism, `/app/data` mtimes).
- Graded logic changed after a self-check: NO. Self-checks covered the decode stages (each control) and serialization. It never built its own capture set (no single-transform corpus, no heavy-amount corpus), so the uniqueness crash went unseen. Nothing in the data could keep a control green while a graded value was wrong: the controls cover every rule that was graded.

## 5. Reflex program
`OUT/agent_program/`: `optimize.py` (final program from the run), `outputs/*.json` (the 9 delivered reports), `adapted/optimize.py` (one-line change `!= 1` to `< 1`; 163/163 on the current tests). The reflex gate scores both.

## 6. LEAK_LIBRARY rows
| lever | how it was written | where it leaked | planned fix |
|---|---|---|---|
| 12 wire transforms | replay-format.md states each transform exactly; shipped captures switch all 12 on; CTRL-A..I fingerprint each decode stage | steps 9-93 probe loop pinned each stage against its control | keep as format only; grading weight moves to settlement rules no control reads (L1) |
| per-entry charter cap | charter-scale.md Caps "entry amount reaching cap held at cap" | step 94 code; general_charter_cap_surplus passed | replace with a running allowance per charter drawn in walk order (L3), renewed per live window (L4) |
| earliest-cancel reversals | engine-rules.md Reversals plain sentence; tiebreak and density corpora | step 5 read, step 94 code | keep; now also decides which entries draw on the allowance (L3 interaction) |
| judged figures | instruction.md:11 lists every figure; judge R7-R13 "states figure X" | final message | delete the list; drop R7-R13 (J1); J2 conduct criteria per lever |
| uniqueness promise | instruction.md:3 "In the slice shipped here, exactly one value ..." (shipped-slice promise) | step 94 assertion | delete; calibration.md "at least one" stays the only rule |
| shared TRUE_VALUES | every corpus uses the same eleven values | R15 judged because literals pass every check | hidden corpora keep the eleven values (the notes publish the candidate sets and controls per capture set) but differ in amounts, roster and schedule so literal reports fail; hardcoding stays a cheating negative |

## 7. Chosen levers: L1 + L3 + L4 (interacting)
Not a repeat: cohort L1+L2+L3+(L4/L5), vendor L2+L3+L5+L6, district-heat L1+L2+L4+L7, emberforge L3+L6+L7, schema L1+L2+L5+L6, sentinel L1+L2+L3+L7; none is contained in L1+L3+L4. Two of L1-L3 present.

- **L3 stateful stream (charter allowance).** charter-scale.md Caps changes from a per-entry cap to a running allowance per charter (size unchanged: baseline times the units the register opens under the charter). Settled entries draw on the allowance of the charter they settle under, one at a time in walk order (tick, capture ordinal, in-capture ordinal). An entry takes its whole amount if the allowance covers it, else what is left; the remainder is surplus and joins the reconciliation residual. An entry that finds the allowance spent still settles with amount zero (its ticks still count). Cancelled entries never draw; promoted reversals draw at their own walk position. Reflex readings: per-entry cap (the old rule and the agent's code), draw then refund on cancel, draw by the opening charter.
- **L4 composition (renewal).** engine-rules.md Windows gains one plain sentence: every charter allowance is restored to full at the first tick of each live window. The value of one settled amount then needs four files: allowance size (charter-scale.md), unit count and seat (roster-register.csv), window bounds (tick-schedule.csv), walk order and cancellation (engine-rules.md Reversals). Reflex: one allowance for the whole walk, or renewal at every window including dead/degenerate ones.
- **L1 green control.** CTRL-A..I (decode layer), CTRL-J (cadence class per unit, tick side), CTRL-K (target), the header seal count and the reconciliation identity (decoded = settled + dropped + residual holds under any draw rule) all stay green under every amount-side misread. calibration.md already says truthfully what each control reads (W7). The graded amount figures (unit amount_total and kind_totals, class amount_total, charter stocks via settled kind-one drawn amounts, settled total, residual) sit above that layer.
- **W5.** On the shipped captures the allowance never binds (max per charter per window 2123 against allowances of 31k-51k), so shipped data cannot separate any reading. Hidden corpora draw heavier amounts so it binds in several charter-windows, with planted seats for a cancel after a binding draw, a promoted reversal that draws, and a merged seat drawing on its new charter.
- **Retire the leaks.** Delete instruction.md:3 promise and :11 figure list; add the G5 sentence ("each output document is graded whole on fresh inputs").
- **Grading plan.** The 12 trap corpora and the general corpora become heavy hidden corpora, each compared as a whole document (cascade, G1). Shipped instance checks drop to weight 1 (shipped-only at most 5%). Whole-doc hidden at least 50%, isolated at most 30%. At least 2 G6 mutation tests (one governed input changed, only the dependent family moves). First-differing-path assertion messages (G7). Negatives only for cheating acts, at most 5 per act (fix the current -5 test plus -5 judge for hardcoding). Judge batched: R1-R5 process, one J2 conduct criterion per lever, one J3 honesty negative, one J4 named-shape code quality; drop R7-R13, R16, R17.
- **Reflex gate.** The agent's final program and the adapted copy both apply a per-entry cap; on heavy hidden corpora every amount-bearing document differs, so both must score at most 0.20 on the tests channel.
