# A_3def42a3: is the loss genuine?

Task 3def42a3-f168-5e85-a2b6-5c7570423bcc (Harshank Kanungo, Data Processing). Run `trajectories/claude-opus-5/run_1`. Recorded 60.63 / 37.93 / 83.33.

**Verdict: GENUINE** (tests: the agent produced wrong values under exact per-family row checks; judge: one process step it really did not do). There was no artefact, version skew or gate that zeroed many tests.

## 1. ctrf vs tests/ in folder
- The ctrf has 35 tests. Their names match the weight table in `tests/test_output.py:6799-6833` one to one, so there is no version skew.
- Positive weights: t01-t16 are 5 each (80); dc01-dc15 total 65. That makes 145 positive points. The four negatives (hardcoded -5, filename -5, io_outside -5, nondeterministic -3) did not fire.
- Passed: t03, t04, t09, t10, t14, t16 (30) plus dc01 3, dc02 5, dc06 3, dc07 3, dc08 3, dc10 5, dc11 3 (25). 55/145 = 37.93, which matches the recorded tests score.
- Failed (90): t01, t02, t05, t06, t07, t08, t11, t12, t13, t15 (50) and dc03, dc04, dc05, dc09, dc12, dc13, dc14, dc15 (40).

## 2. Crash / gate / path checks
- `result.json`: exception_info None. The agent ran 75.5 min of the 240 allowed, and the verifier took about 3 min.
- test-stdout: only a LiteLLM warning and `reward: 0.6063`. No traceback, no `Permission denied`, no timeout line.
- All 9 deliverables plus transform.py are present in `artifacts/app/out/`, and transform.py is mode 0644. In any case `_stage_program` (test_output.py:6331) copies the program to a root-owned 0644 directory, so the 0600 artefact cannot occur.
- Gate `_hard` (test_output.py:6555-6563): a test passes only if the visible outputs pass AND hidden run r1 passes, and any exception returns False. This gate did NOT zero the tier:
  - 13 tests passed, and every one of them needs the hidden run r1 output. So the transform ran on the hidden corpus inside RUN_TIMEOUT 1500 and produced parseable outputs.
  - The nondeterministic and io_outside negatives (r2 identical-rerun, r3 relocated-run probes) did not fire.
- Each failure is therefore a VALUE failure: at least one focused expected line, or one owned residual row, of that family is not byte-exact in the visible output and/or the hidden output (`_tier_ok` :6515-6552 checks subset + owned residual equality).

## 3. Per failed test: value or gate?
None of the failed tests can be traced to a specific row without running the generator, which the rules forbid. Evidence that these are value failures:
- the transform completed on both tiers (above);
- `_disjoint` (:6263) gives each output row to exactly one test, so no single wrong row can fail several tests through shared rows;
- UFE columns are masked everywhere except t12 (:6097-6105), so the system-wide UFE coupling does not cascade into the other tests.

Each failed test is therefore an independent family in which at least one trap row or residual row is wrong (INFERRED from the grading code; the exact rows are untraced).

The agent did implement most named mechanics. Evidence from the artifact transform.py:
- holds cutoff at :37 and :1305
- CAB-approved errata only, at :450-486
- UPHELD disputes at :1255
- UNQUARANTINE at :1314
- 900 s snap at :1345
- FAIL inspection at :1506
- WEEKEND day type at :1843
- COMM_FAIL at :2139
- half-even at :46/:50

So the misses are second-order details (tie-breaks, per-register precedence, firmware windows, crosswalk validity) inside families graded all-or-nothing. INFERRED.

TRUTH.md maps every graded rule to a contract or manual section (TRUTH.md:3-37 and the trace at :423-461). I found no rule that exists only in the generator. Hidden-rule check: none found (not exhaustive; 31 rules × 63 loops).

## 4. Judge
- 11 criteria (6 positive × 3 = 18; 5 negatives).
- Only R5 failed: "compares the deliverables its transform produces from a copy of the data placed in a different directory, or from a deliberately altered copy, against the ones it produced from /app/data". The judge wrote: "ran the transform repeatedly with different output directories, but every recorded transform run used /app/data as DATA_DIR".
- The trajectory confirms this:
  - Every transform invocation uses `/app/data` (steps 132, 140, 149, 151, 154, 163, 180, 187, 195, 205, 216, 220, 237, 247, 248) with out dirs out1-out9/outA/outB and PYTHONHASHSEED variations at step 216.
  - No step copies /app/data elsewhere.
- So this is a real process miss, not a judge artefact. Genuine judge loss: 3/18.

## 5. Genuine points lost
- Tests: 90/145 positive points (all value failures; per-row cause INFERRED).
- Judge: 3/18 (R5, process step).
