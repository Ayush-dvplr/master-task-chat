# A: sentinel-fraud-training-release — is the low score genuine?

Recorded: overall 19.76 / tests 2.68 / rubric 36.84. Run dir `trajectories/claude-opus-5/run_1/`.

## Verdict: GENUINE (amplified by exact-digest grading where every concept hashes the full example set)

## Evidence

1. **Harness health**
   - `result.json`: `exception_info` null. The agent ran from 16:12:24Z to 17:31:22Z (~79 min, under the 14400 s budget). The verifier took ~2 min.
   - `test-stdout.txt` holds only the reward line.
   - `ctrf.json`: 35 tests, none skipped, every message empty. No tracebacks or permission errors.
2. **Did the verifier run the agent's program?** Yes.
   - `held_release_when_catalog_file_missing` (w3) PASSED.
     - Per `tests/test_output.py` (criterion just after `eval_delta_state_and_exclusions_exact`) it regenerates the hidden TR-2027.01 exports, drops `chargebacks_vantage_2027-01.xml`, and runs the agent's `transform.py` as uid 65534 (`RUN_UID`, `_run_locked`).
     - The pass needs a digest match on all 13 outputs, so the agent's builder executed in the verifier and wrote readable output.
   - `outputs_have_documented_shape` (w1) PASSED: all 14 outputs exist, status is consistent, and every example has exactly the 12 `EXAMPLE_KEYS`.
   - So there is no location, permission or schema gate.
3. **Wrong VALUES, shown by numbers**
   - TRUTH "Measured release" (`solution/TRUTH.md:72-75`) expects train 23,746 / val 5,760 / test 7,139 / oot 11,034 (47,679 released).
   - The agent's `artifacts/app/out/summary.json` has train 23,240 / val 5,720 / test 7,837 / oot 11,072 (47,869 released). That is +190 examples overall and +698 in test, so example membership and cluster splits are both wrong.
   - AUC (expected val 0.544254, agent 0.540259) and the counts are all off.
4. **Why tests sit near 0**
   - Each concept check (`_project`, `test_output.py:121-149`) hashes a projection over every released example: pit, labels, splits, preprocessing, class_weights, vocab and scores. A wrong example set therefore fails all of them at once.
   - Slice checks (`_slice_ok`, `:200-212`) need every per-record digest of the trap family to match.
   - The hidden delta release (`eval_delta_*`) starts from the agent's own prior outputs (`--prior` = copy of `/app/out`). Visible errors carry into it as a dependent chain.
   - INFERRED: one upstream membership error (the +190 examples) is enough to zero 7 of the 10 concept checks. It is a genuine error, but the grader multiplies its cost.
   - No negatives fired (all four are "failed", meaning not triggered).
5. **Is the rule text stated?** TRUTH:5 says "every hazard is documented somewhere in /app/data, usually in a different file from the data it governs". instruction.md says "every value is compared exactly". The gate is stated.
6. **Judge**: it read the trajectory and response; 14/38.
   - Failed criteria, all genuine and meetable by the oracle (JD-7 holds):
     - R3: no per-export candidate check.
     - R4: no explicit cluster-in-one-split check.
     - R9 (NEG -3): claimed the HELD path was exercised but never ran it.
     - R11: opaque names; an unknown file family silently returns `[]`.
7. **Permissions**: `tests/test.sh` runs `chown root:root` and `chmod 755 /logs/verifier`, then `chmod -R go-rwx /tests`, then rewardkit over `/tests` with workspace `/app`. There is no chmod on `/app/out`. The verifier reads as root (INFERRED), and builder runs use uid 65534 dirs prepared by the test (`_runner_dir`, `_readonly_tree`). No permission issue is visible, and the HELD pass shows the builder could run.
