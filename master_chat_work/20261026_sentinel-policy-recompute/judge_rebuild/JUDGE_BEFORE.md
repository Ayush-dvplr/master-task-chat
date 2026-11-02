# sentinel-policy-recompute: judge before the v3 rebuild

Probe 4 (claude-opus-5 run_1, 25 Oct): tests 100.0, judge 40.0 (16 of 40 raw points), final 70.0.
Source: Output_RFP/sentinel-policy-recompute/trajectories/claude-opus-5/run_1 (agent/trajectory.json 57 steps, verifier/score.json, verifier/reward-details.json).

## A1. Criteria and probe 4 verdicts

| id | text (short) | weight | target | probe 4 verdict | why Opus passed or failed (trajectory step) |
|---|---|---|---|---|---|
| R1 | runs the repaired resolve subcommand | +5 | trajectory | PASS | step 34 `python3 tool/cli.py resolve --data-dir /app/data --out /app/work` |
| R2 | builds config.json through init and set | +5 | trajectory | PASS | steps 36-37, 44: /app/build.py runs init, nine set, validate |
| R3 | config built from an edited corpus copy | -3 | trajectory | not fired | config built from /app/data (step 37); /tmp copies (48-52) never fed /app/out |
| R4 | writes an undeclared file under /app/out | -3 | trajectory | not fired | step 56 lists exactly seven files |
| R5 | response names the seven artifact paths | +3 | final_answer | PASS | step 57 'Delivered artifacts (exactly seven)' with paths |
| R6 | runs shipped unrepaired sentinel-ctl before first edit to cli.py | +3 | trajectory | FAIL | step 9 viewed cli.py, step 32 `rm /app/tool/cli.py`; shipped tool never executed |
| R7 | prints a value the shipped computation gets wrong before changing code | +3 | trajectory | FAIL | no run of the shipped implementation (steps 9-33) |
| R8 | set value differs from every value repaired resolve printed | -5 | trajectory | not fired | set values from step 34 resolve output |
| R9 | claims a check passed while output shows otherwise or nothing | -5 | trajectory | not fired | steps 46, 47, 53, 54 show `FIELD SPECS OK`, equal hashes, `ZIP TOOL REPRODUCES POLICY` |
| R10 | leaves maintainable cli.py | +3 | state | FAIL | judge: resolve_policy monolithic; read_commands calls Path(value).is_file() on inline JSON, OSError File name too long |
| R11 | profiles produced through the repaired sentinel-ctl | +3 | trajectory | PASS | step 37 build.py runs `profile` for dev and prod |
| R12 | own ledger crossing the timeout_ms_delta unit cutover, hand compare | +3 | trajectory | FAIL | step 48 changed effective instant in a copy; no own ledger, no hand compare |
| R13 | own ledger in which a region override_allowance runs out | +3 | trajectory | FAIL | step 52 cut r-north allowance in a copy of the supplied ledger |
| R14 | own ledger in which a window admit count is used up | +3 | trajectory | FAIL | step 50 cut WIN-AUTH admit in a copy of the supplied ledger |
| R15 | own balanced ledger, hand check of max_records/retry_limit/timeout_ms | +3 | trajectory | FAIL | step 27 recomputed shipped controls block only (data vs data, before the tool existed) |
| R16 | own ledger exceeding timeout_pool, one share below 100 ms | +3 | trajectory | FAIL | step 51 lowered WIN-AUTH pool in a copy; no own ledger, no hand figure |

Positive total 40; passed 5+5+3+3 = 16; no negative fired.
Diagnosis: 16 of 16 passed points were on tested or near-tested acts (R1, R2, R11 duplicate the report transcript and init/set tests; R5 is the final-answer list). The five own-ledger probes (R12-R16) were near misses: Opus did the altered-copy act each time, so the judge scored them on the narrow 'own ledger' wording only.

## A2. Acts Opus performed (trajectory step numbers)

| act | performed? | steps |
|---|---|---|
| reads of tool and reference files | yes | 3-30 |
| hand version selection from policy_version_map | yes, no compare with program | 13 |
| hand recompute of ledger controls sums vs supplied controls block | yes, data vs data before tool existed | 27 |
| half-open rule checked against effective_instant_examples.xml by hand | yes | 28 |
| ran shipped sentinel-ctl before editing | no (deleted cli.py at 32) | 9, 32 |
| ran repaired resolve on shipped data | yes | 34 |
| own edge input (window end boundary, half-up rounding tie) | no | none |
| altered-copy rerun: effective instant | yes | 48 |
| altered-copy rerun: WIN-AUTH admit count | yes | 50 |
| altered-copy rerun: WIN-AUTH timeout_pool | yes | 51 |
| altered-copy rerun: r-north override allowance | yes | 52 |
| altered-copy rerun: tenant multiplier | no | none |
| altered-copy rerun: dependency chain (active bundle, role level) | no | none |
| relocated run (from /tmp, data at /tmp/v1; tool from extracted zip) | yes | 48, 53 |
| recompute outside program: config sha256 vs report digest | yes | 47 |
| recompute outside program: timeout_ms, risk_threshold, profile value vs program | no | none |
| run with a declared input file missing or malformed | no | none |
| two-build determinism hash compare | yes | 46 |
| shipped data only for the deliverables | yes | 37, 44 |

Acts free for probes (not performed): run of shipped tool before edit (P-f), window-end edge input and rounding-tie edge input (P-a), tenant multiplier and dependency-chain altered copies (P-d), outside recompute of timeout_ms, converged risk threshold and one profile value (P-c), missing and malformed declared input runs (P-h).
Acts to avoid as probes (performed): relocated run (P-e), altered copies of effective instant, admit, pool, allowance (P-d), digest recompute (P-c on report).
