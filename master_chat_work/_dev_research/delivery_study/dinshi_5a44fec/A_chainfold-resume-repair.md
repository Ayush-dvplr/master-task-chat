# A — chainfold-resume-repair

Recorded: overall 62.93 / tests 78.49 / rubric 47.37 (`run_1/verifier/score.json`, `pass_summary.json`).

## Verdict: GENUINE

Evidence of a clean run:
- `run_1/result.json`: `"exception_info": null`. Agent ran 12:06:41 to 12:19:17 UTC (about 12.6 min of a 5400 s budget). Verifier ran 12:19:24 to 12:20:36, no timeout.
- `report.json` pytest: 23 passed, 8 failed, exit 1, reward 0.7849 = (93 − 20)/93. The four negatives show `passed:false`, meaning none fired (the arithmetic only works with zero penalty).
- `verifier/test-stdout.txt` holds only `reward: 0.6293`. `ctrf.json` failure messages are empty, so there is no traceback, no Permission denied and no missing-file text anywhere.
- Odd but harmless: `result.json` `verifier_result.reward` = 0.853 while the stored final is 62.93. The recorded scores come from score.json and pass_summary. This is noted, not used.

## Failed checks (positive weight 20 of 93)

| test | w | type of failure | evidence |
|---|---|---|---|
| h_hidden_beta_degenerate | 5 | wrong VALUE | `_compare("beta", ALL_FIELDS)` (test_output.py:1687-1692). The program ran fine on beta because `h_hidden_seals` and `h_hidden_output_set` (1711, 1771) loop over all four tags, return False on `not ok`, and both PASSED. |
| h_hidden_gamma_empty | 5 | wrong VALUE | same compare on gamma (1695-1700); the program ran, as shown above |
| h_hidden_delta_order | 5 | wrong VALUE | same compare on delta (1703-1708) |
| h_hidden_rollups | 5 | wrong VALUE (knock-on) | needs every roll-up field correct across all four tags (1730-1768). alpha passes everywhere, so a beta/gamma/delta lane value is wrong, or a roll-up derived from one. |

There is no crash, path error or gate failure: the alpha tests (4 × 5) and the output-set and seal tests all pass.

Grain: each hidden test compares 25 fields × 5 lanes at once (`_agrees` with all(), 1353-1354). One wrong field zeroes 5 points, and the same wrong lane value also zeroes rollups. This is the natural knock-on the QC accepts, not a stated gate.

Hidden archive features that tell the readings apart (PLANS, test_output.py:435-593, read statically):
- beta: `warmup_steps 0`, `decay_span_steps 0`, `log_every_steps 0` (zero denominators), restart exception `carry_partial False`.
- gamma: min = max = default = 8 against a phase width of 2 (clamp), partial rule "discard", `average_window 0`, no probes.
- delta: `conflict True`, `twin_markers True`, `style 1` (scattered sequences), plus an unused phase row `d9`.

Exact root fields: see the C file (Step 2 static comparison of the agent's program with `_mirror`).

## QC re-grade note
`Aniket_Datta_chainfold-resume-repair_QC_Report.md` re-graded the stored artifacts against the repaired tests: test_output went from 78.49% to **67/87 = 77.01%**, after "two duplicated checks were removed". The positive total fell from 93 to 87, and the genuine loss stays 20 points across the same four hidden checks. Line numbers above refer to the CURRENT (post-QC) tests/test_output.py; the test names come from the recorded report.json.
