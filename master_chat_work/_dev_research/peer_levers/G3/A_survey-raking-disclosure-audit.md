# A: survey-raking-disclosure-audit — is the low score genuine?

Recorded: overall 36.88 / tests 41.41 / rubric 32.35. **Verdict: GENUINE.** On the shipped extract the whole loss comes from one misread rule, and I reproduced the fix locally.

## 1. Harness errors
- `result.json`: `exception_info` is None. The agent finished on its own (62 steps, ~23 min, final message at step 61). It hit no step limit and no timeout.
- `verifier/test-stdout.txt` is 15 bytes, only the reward line. No traceback, no `Errno 13`, no `No such file`, no collection error.
- `ctrf.json` has 35 tests and no failure messages. 13 passed and 22 failed. None of the negatives fired (hardcoded, reuses_shipped_margin_order, nondeterministic, filename, row_order, writes_outside, third_party_library).

## 2. Did the verifier run the agent's program?
Yes. `unseen_run_writes_complete_report_set` (w1) passed. So did `challenge_/second_/third_` frame, benchmarks and dispositions (9 × w5). Those checks only exist on extracts the verifier builds itself (TRUTH.md:87-153), so the agent's `derive_survey.py` ran under the verifier as `nobody` and wrote correct upstream reports. The failures are wrong VALUES, not missing files.

The pass/fail pattern is a dependent chain. Every group upstream of nonresponse adjustment/raking passes on all 4 extracts. Every group from `adjustment` onward fails on all 4: weighting, estimates, disclosure, trimming. The `adjustment` group includes `raking_trace.json` (test_output.py:3198), and `_group_on` needs every file in the group to match (:3284).

## 3. Root cause, proven locally (read-only; outputs went to a temp dir)
- I ran the oracle `python3 solution/solve.py environment/data <tmp>` (rc 0) and compared it with the agent's `artifacts/app/out`. 8 files are byte-identical: design_weights, adjusted_weights, adjustment_cells, control_totals, control_margins, frame_audit, response_status, replicate_design. The other 14 differ, starting at `raking_trace.json`:
  - Oracle: 13 iterations, not converged, final deviation 5,393,296.
  - Agent: 4 iterations, converged, final deviation 867,448.
- The two `rake()` routines are equivalent: solve.py:481-521 vs derive_survey.py:807+, same factor product and rounding. The difference is in what feeds raking, namely the **band at the reference wave**:
  - Oracle `band_at` (solve.py:463-476) uses the wave-3 interview's own hours first. Only when those hours are absent does it fall back to wave-2 interview hours, then the wave-2 prior file, then the wave-1 prior file, then zero.
  - Agent (derive_survey.py:1242-1251, first written at trajectory step 28) never looks at wave-3 hours. It starts the chain at wave-2 interview hours.
- **Proof:** I copied the agent's script to temp and inserted the single missing branch (`if iv3["hours"] is not None: band_ref = band_of_hours(..., iv3["hours"])`). The copy then reproduces **all 22 shipped reports byte-for-byte** against the oracle.
- The rule as written, HAS-7-standard.md:237-243: "The band of a unit at a wave follows from its hours through the band register ... Where hours are absent the band carries forward. For the reference wave it is the band of the unit's wave two interview hours; where that interview is absent or carries no hours, the `prior_band` of ... the wave two prior band file; ...". The agent read "For the reference wave it is ..." as unconditional. The oracle reads it as the carry-forward chain that applies only when hours are absent. **PARTLY ambiguous**: the pronoun "it" can bind to "the band" in general or to "the band [that] carries forward". This is a likely IN-16 finding, see B §8. TRUTH.md:133 lists a nearby mutation ("carrying a wave two interview forward to the reference wave 0.258").

## 4. Judge
`score.json` shows the judge read the closing summary: each failed criterion quotes the agent's number next to the oracle's.
- R1, R4, R5, R6, R7, R8 failed: agent values 867,452, 4, 331,500,000,002, 6, 4, 44. Oracle values 5,393,301, 5, 331,499,999,995, 3, 15, 43. All six are what-if reruns built on the same wrong raking base, so they are genuine but come from the **same root cause** as the tests. This is double exposure of one error, not independent levers.
- R10 (code quality, dead `eligible_set`) is genuine and minor.
- JD-7: the oracle numbers come from solve.py, so the criteria can be met. I did not re-derive R1-R8 myself; INFERRED that they are consistent because the oracle's raking trace final deviation of 5,393,296 sits next to R1's 5,393,301 for the other rounding point.

## 5. Permissions
`tests/test.sh` removes the old reward files, does `mkdir /logs/verifier`, `chown root:root`, `chmod 755`, `chmod -R go-rwx /tests`, then runs rewardkit. The program runs as `nobody` (TRUTH.md verification section). The grader reads `/app/out` as root, so there is no permission trap like ours.

## Verdict
GENUINE. All test loss from adjustment onward (75 of 128 test points) and 22 of the 23 lost judge points trace to one misread sentence about the reference-wave band fallback. Judge arithmetic: 34 positive points; R1 3 + R4 5 + R5 5 + R6 3 + R7 3 + R8 3 come from that sentence, and R10 adds 1. That gives 11/34 = 32.35%. The test stack magnifies the error because every downstream report is byte-compared.
