TASK: fb91cc7f-793e-5852-a976-bd859255194d, Data Processing (restoration lab settlement: lineage identity, conform, impairment union, decaying repair ceiling, cadence conversion, grade fixpoint, admission fixpoint, exact-fit vault seating, lane cascade; 14 JSON reports plus program), Opus tests 25.0, rubric 64.91, final 44.95.

1. VERDICT: MIXED, leaning DEFECT. About 100 percent of lost test weight (93 of 124 positive weight) traces to one cause: the agent settled under a different convention set (quantise toward the source count, impairment and credit before cadence) than the reference (round half to even, impairment then cadence then credit). Whether that is DESIGN or DEFECT turns on one fact I could not check without rerunning: does the agent's set also reproduce the published calibration figures? Its program docstring says it was recovered from them, and the judge (R12) says it tested candidates against the control cycle. If it does, the uniqueness promise is false and this is a DEFECT. Confidence low to medium.

2. LOSSES:
1. Cadence and settlement checks, 6 checks, weight 28 (cadence_converted 5, settled_frames_fixed 5, admission_settled 5, vaults_seated 5, lane cascade 5, ledger reconciles 3). Cause: WRONG output, every settled count drifts by the quantisation and order.
2. Focal mutation checks, 2 checks, weight 10 (print never governs, admission prefix). Cause: WRONG output, same upstream drift.
3. Generalisation reruns, 11 checks, weight 55 (tie, cap, precedence, group emptied, loop, window, new holder, all print, direction flip, partition count, every void reason). Cause: WRONG output, the whole-report comparison inherits the drift. No crash, no timeout.
4. Passed: identity, spans, conform, defects, impairment, repairs, condition grades, serialisation (31 of 124).

3. DIFFICULTY KIND: if DESIGN, (e) recover hidden conventions by search over a control cycle. The agent's quantisation (floor on up conversion, ceiling on down) is outside the four modes the reference sweeps.

4. EVIDENCE:
1. Promise: instruction.md:20 and calibration_slice.md:59 say exactly one combination reproduces every published figure, but no shipped file lists the candidate quantisations, orders or fractions.
2. Reference space: tests/test_output.py:27 ROUNDINGS = floor, ceil, half_up, half_even; TRUTH.md item 1 says uniqueness was proven only over 4 x 6 x 8 = 192 combinations.
3. Agent: cadence_settle.py:9-13 and 373-378 quantise toward the source count and convert after impairment and credit; the ceiling fraction 3/5 matches (R3 passed).

5. TEST DESIGN: fixed catalogue embedded as an archive, recomputed by an embedded reference settle(); 11 hand-written mutators of that corpus (one per edge case) rerun the agent's program. Comparison per field on keyed tuples for the focal checks, whole report for the reruns. Amplification: a 15-stage chain, so one convention error fails every downstream check. Negatives: hardcoded figures, name-dependent behaviour, nondeterminism, catalogue modified.

6. INSTRUCTION: "exactly one combination of the three reproduces every figure published for it, and no other combination reproduces even its per-programme figures"; "There is exactly one correct settlement"; deliverable python3 /app/out/cadence_settle.py CATALOGUE OUT; stdlib only; byte-identical reruns; 7200 seconds; final message names the three conventions "and that you recovered rather than assumed". Not said: the candidate set for each convention, or that the program is rerun on mutated catalogues with the conventions held fixed.

7. RUBRIC: lost R1 and R2 (stated conventions differ from the reference), R12 and R13 (process criteria that grade the recovered values, not the method), so one root cause costs 20 rubric points. R19 and R21 are penalties that did not fire.

8. REUSABLE IDEA: hide a small number of conventions and ship a control cycle with published figures that pin them, then rerun the program on mutated corpora. Lesson: if uniqueness is promised, either list the candidate space in the shipped docs or prove uniqueness over every reasonable rule, including direction-dependent rounding.
