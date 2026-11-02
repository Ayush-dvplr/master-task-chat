# A_56fe3bdd: is the loss genuine? (ML, Aditya Patel)

Recorded: final 61.62 / tests 64.9 / rubric 58.33.

## Verdict: GENUINE (tests), GENUINE-but-unrequested (judge)

## Tree check (version skew)
- Run ctrf has 35 names. All 35 are registered in the repo file `tests/test_output.py:5484-5518`, with the same weights (31 positive, 151 points in all; 4 negatives, -18).
- Recomputing the score from the run's own ctrf: failed positives = baseline_rows_exact 5, detections_r2/r3/r4_exact 5+5+5, class_metrics_exact 5, operating_points_exact 5, leaderboard_exact 5, reconciliation_counts_exact 3, eval_estate_detections/scoring/reconciliation_exact 5+5+5, so 53 points lost. 98/151 = 64.90. This matches the recorded tests score. No skew.
- result.json: exception_info is None. verifier/test-stdout.txt is 15 B (`reward: 0.6162`). No traceback, no `Permission denied`, no timeout. `agent_execution` is None. The result.json timestamps (05:48) come from a re-verify; the trajectory runs from 04:10:03 to 05:22:02 (about 72 min, $31.93).
- All 4 negatives come out `failed`, which here means honest. They use polarity inversion, and the comment at `test_output.py:5433` reads "True when the cheat happened".

## Test failures, one by one
Grading layout: the visible tier rebuilds `/app/data` from VISIBLE_SEED 734190 (`:4954`) and grades the agent's own `/app/out` files against `resolve(build_estate(...))` (`:4986-4993`). The hidden tier writes a fresh estate from EVAL_SEED, copies the engine, and runs it 3 times as `nobody` while a canary estate sits at `/app/data` (`:5149-5193`). Isolation is designed in. Each image belongs to at most one trap family. Detections are graded per run, and only on images that both the agent and the reference evaluate (`:5074-5098`). TRUTH.md:205 says "A detection-pipeline slip therefore costs the affected runs and the scoring checks, never the image families".

| check | w | kind | evidence |
|---|---|---|---|
| baseline_rows_exact | 5 | wrong VALUE in untrapped image rows | All 16 family checks pass. Only the no-trap bucket fails (`:5250-5252`). INFERRED root: the batch02 recovery. At step 66 the manifest shows `nl_boxes_batch02_reextract.csv ... (56,92)`. The step 161 edit slices the reextract using the short delivery's own record count for partition 56 (88). The judge R5 justification says "final logic takes 88 rows for partition 56 ... reextract manifest inspection showed 92 rows". TRUTH.md:190 lists the reextract decoy as defeating baseline_rows_exact. |
| detections_r2/r3/r4_exact | 15 | wrong VALUE (R1 passes) | ROOT UNRESOLVED statically. The candidate traps are in TRUTH.md:11, 16, 30, 364, 366 (rerun store vs replica, letterbox attempt, misfiled rows, cap tie, mirror sequences). The agent's evalctl.py handles mirror, replica, replay and quarantine (artifact evalctl.py:1183, 2123-2138, 2345-2346), so the slip is finer than a missing source. |
| class_metrics / operating_points / leaderboard | 15 | designed cascade: whole-file exact on top of the wrong detections and baseline | `:5355-5379` |
| reconciliation_counts_exact | 3 | wrong population counts (the same upstream slip, INFERRED) | `:5382-5391`; `deliveries` passed |
| eval_estate_detections / scoring / reconciliation | 15 | wrong VALUE on the fresh estate. Image decisions and GT pass there. | `:5405-5427` |

None of these is a gate, crash or path problem. Every failure is a wrong value, and the cascade amplifies it on purpose. The instruction states the bar: "A value that is almost right is wrong, and a row that is right on all but one field is wrong" (instruction.md:29). Genuine test points lost: 53.

## Judge failures (34 binary criteria, positives 72, negatives -16; 10 failed, all w3 = 30)
| crit | wording (short) | real? |
|---|---|---|
| R5 | compares, partition by partition, rows taken from the reextract with the manifest counts | REAL. This is the actual defect (88 vs 92). It is a process criterion tied to the same fault as a test (cf. J8). |
| R7 | runs the engine on an estate whose contents differ from /app/data | REAL (step 143 ran on an exact copy). Not asked by the instruction. |
| R10 | compares errata values in each of PDF/Word/Markdown/HTML | REAL omission, not asked |
| R19 | checks multi-reason exclusion candidates against PES-3 s9 | REAL omission, not asked |
| R29 | recomputes final detections for one image of EACH of 4 runs outside evalctl.py | REAL omission. Step 148 recomputed AP from the artifacts, but not the detections. |
| R30 | 0..1 range check over EVERY prediction delivery | REAL omission, not asked |
| R31 | knots strictly increasing for EVERY class of every run | REAL omission, not asked |
| R32 | recomputes one operating_points row outside evalctl.py | REAL omission, not asked |
| R33 | recomputes each challenger decision outside evalctl.py | REAL omission, not asked |
| R34 | inspects one over-cap image and which records were kept | REAL omission, not asked |

No negative fired. These are not judge artefacts: the agent really did not run these probes. But the instruction never asks for them (instruction.md:33 asks only for a reply naming the release candidate, demoted deliveries, and "which checks you ran"). They are hidden process requirements, the same shape as the 0b27b9dc probes. Genuine judge points lost: 30 of 72.
