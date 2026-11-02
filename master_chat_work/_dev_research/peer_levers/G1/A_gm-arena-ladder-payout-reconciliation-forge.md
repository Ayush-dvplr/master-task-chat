# A: gm-arena-ladder-payout-reconciliation-forge — is the low score genuine?

Recorded: overall 45.25 / tests 22.58 / rubric 67.92. Run dir `trajectories/claude-opus-5/run_1`.

**Verdict: GENUINE** (tests: wrong values, proved by local reproduction; judge: mostly genuine, with 4 criteria of doubtful fairness, listed below).

## 1. Harness / exceptions
- `result.json` `exception_info`: null. Agent ran 12:55:41 to 13:09:29Z (about 14 min of a 14400 s budget; instruction.md last line "You have 14400 seconds"). No timeout, no step limit.
- `verifier/test-stdout.txt`: only the `reward:` line. No traceback, no `Errno 13`, no `No such file`, no collection or import error, no skips.

## 2. Did the verifier grade the agent's outputs and are failures wrong values?
- `tests/test_output.py` L1-15 docstring: it regenerates the corpus from seeds, recomputes the ground truth, and "grades /app/out byte-for-byte". `_expected()` L1838-1844 calls `generate(seed)` into a temp dir and runs the in-test reference pipeline. Every positive check (L1992-2123) is a byte compare of one `/app/out` file against the expected one. No agent program is executed, so no uid or permission path is involved.
- Local reproduction (read-only, stub rewardkit, all writes to `OUT/_scratch`): corpus regenerated from `SAMPLE_SEED=4471903288` (L1813) is byte-identical to shipped `environment/data` (59 files same, 0 diff, 0 extra). So the graded inputs are the shipped data.
- Agent outputs vs expected: 5 files MATCH (population, confidence_intervals, label_distribution, decision_distribution, frame_counts) = exactly the 5 value tests that passed (plus `test_all_artifacts_exist`). All 16 failing files DIFF on values.
- Root cause proved by counterfactual: I rebuilt the agent's final script from trajectory step 22 (create), step 23 (str_replace) and step 25 (sed fix). It reproduces all 29 recorded agent outputs byte for byte. Patching one line (count only `drawn=1` rows in the per-server resolved count) makes 8 more tests' files match. A second, separate error (per-match vs per-stratum half-even rounding in S8) explains the remaining 8. Details in B.

## 3. Near-zero gate?
Not applicable. Tests 22.58 is not near zero, and no gate check zeroes the rest. But the byte-exact whole-file design makes the scoring brittle: one upstream scope error spread to 16 files (family B, dependent chain).

## 4. Judge
- Batched mode, reads the atif trajectory (`tests/judge.toml` L1-6). The verdicts quote trajectory steps, so it read the response.
- Failed: R1 (w1), R6 (w3), R13 (w5), R14 (w5), R15 (w3), R18 (w5), R24 (w3), R25 (w3), R26 (w3), R33 (w3).
  - Agent's work, genuine: R24 (real code difference: agent breaks share ties by fixed stratum order, not by name), R33 (code quality), R6 and R1 (reporting), R25, R26 (the agent did not explain these).
  - Doubtful (fairness): **R13 and R14 (w5 each)** ask the agent to *show* or *demonstrate* a counterfactual (reorder to change p_eff, show a thousandfold unit error). Nothing in instruction.md or the data files asks for those demos. That is a conduct preference at weight 5, which JD-15 fails ("a preference weighted 5 is a fail"). **R18 (w5)**: the maximum expected weight is 5.245614 (my reproduction, `gm_expected/weights.csv`) against a cap of 240, so trimming never happens on the shipped data and nothing can be "shown". **R24's tie-break** ("smaller stratum name") appears in no agent-visible file (grep of instruction.md and environment/data for remainder, tie and stratum name finds only the S5 residue rule, `spec_stage_s5_two_level_weights.md:11`). That makes it a HIDDEN RULE under IN-15/JD-15.
  - So about 18 of 34 lost judge points are on criteria our QC would fail or call risky. INFERRED: the judge score is partly inflated in difficulty by unfair criteria.

## 5. Permissions
`tests/test.sh` (same in all 4 tasks): `chown root:root /logs/verifier`, `chmod 755 /logs/verifier`, `chmod -R go-rwx /tests`, then `exec rewardkit /tests --workspace /app ...`. It does not chmod `/app/out` and runs no other user. That does not matter here because the tests only read files as root and never run agent code.
