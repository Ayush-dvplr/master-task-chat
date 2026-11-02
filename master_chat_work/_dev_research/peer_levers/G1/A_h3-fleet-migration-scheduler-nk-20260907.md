# A: h3-fleet-migration-scheduler-nk-20260907 (recorded 67.19 / tests 75.28 / rubric 59.09)

**Verdict: PARTLY.** The verifier ran fine and every failed check is a wrong value. But 19 of the 22 lost test points come from one quantity, `consumed[n, e]`, that the spec never defines. The only file that says what is consumed says MTU units, and the reference uses stream count. The agent followed the written text. The other 3 points (loop shape) are genuine but rest on an ambiguous sentence. On the judge side, 1 of the 6 failed criteria (R14) is an artefact of trajectory capture.

## 1. Harness / exceptions
- `result.json` exception_info null. The agent ran 18:55:33 to 19:07:29Z (about 12 min), 30 steps, and was not timed out.
- `verifier/test-stdout.txt` holds only the `reward:` line. There are no tracebacks, Errno 13, missing files or skips.

## 2. Did the verifier run the agent's work? Yes, and the failures are values
- Permissions are handled correctly. `tests/test_output.py` `_run_agent` (L365-395) uses `setpriv --reuid=65534 --regid=65534 --clear-groups`. `_grant_access` sets data 0755/0644 and out 0777/0666, `_grant_traversal` adds +x on the ancestors, and the scheduler is chmod 0644. Timeout is 180 s.
- The verifier's data comes from a tarball embedded in the test file (`_EMBEDDED_DATA_B64`, L28, extracted L206-228). I extracted it to `_scratch/h3_embedded`. 25 of 26 files are byte-identical to `environment/data`. `case-brigantine.json` differs, but its sealed test passed, so this is not an artefact.
- I reproduced the run locally (`_scratch/h3_cmp.py`: stub rewardkit, test module run against the agent's artifacts and program). It gives exactly the recorded pass/fail set: 8 FAIL (reusable_alternate 1, damping 3, empty_epoch 3, hidden_baseline 3, hidden_tight_slo 3, hidden_burst 3, hidden_migration_dominant 3, hidden_challenge_final_state 3 = 22). All 10 delivered JSONs differ from the reference on the shipped corpus: total_cost is 1216 for the agent against 1431 for the reference, and the agent has extra `no_feasible_node` preemptions in epochs 1-3.

## 3. Root cause, proved by counterfactual
- Agent code (`artifacts/app/out/reusable_scheduler.py:447`): `consumed = tokens_start[node_id] - state.tokens[node_id]`, which is the MTU units deducted during placement.
- Reference: `tests/test_output.py:707` `consumed = {n: sum(1 for s in assign if assign[s] == n) ...}`, a stream count. The oracle does the same (`solution/solve.py:527`).
- Spec: `README-input-schema.md:93` `available[n] = min(bucket_capacity[n], bucket_tokens[n, e] - consumed[n, e])`. `consumed` is not defined anywhere. `README-input-schema.md:16` describes `mtu_matrix.csv` as "mtu_class x node -> units consumed per admitted stream". Feasibility at L71 also deducts MTU units: `bucket_tokens[n, e] >= mtu_units(...)`. `solution/TRUTH.md` does not mention count-based carry-over as an intended trap. Its traps are the four settlements (TRUTH.md:12).
- Counterfactual: I patched only L447 to count streams (`_scratch/h3_fix_out/`) and reran the test module. 7 of the 8 failures flip to PASS. 7 of 10 artifacts then MATCH, and total_cost becomes 1431. Only `test_fresh_fixed_point_damping_converges_within_tolerance` (w3) still fails.
- The remaining 3 points come from loop shape. The agent runs one damped loop over the whole horizon (`reusable_scheduler.py:485-517`, "Phase 9 - damped fixed-point loop over the whole horizon"), which gives 2 iterations. The reference runs a loop per epoch with a global counter, which gives 8 iterations (test L969 compares the iteration count). Spec L31 says "For each epoch e ... Phases 4-6 are wrapped in the fixed-point loop of phase 9" and L102 says "the epoch's admissions from iteration i - 1". Both support a loop per epoch. L106 says "Iterate until ... across all tenants and epochs", which supports the agent's reading. Two defensible readings: RISKY.

## 4. Judge (17 criteria, positives total 44; lost 18 = R6, R9, R11, R12, R14, R15, w3 each)
- All six failures are about conduct or process. None is about output correctness.
- **R14 is an ARTEFACT.** The criterion needs visible output of a listing and header print. Steps 2, 6 and 8 have `observation: null` in `agent/trajectory.json`, although step 6 ran `cat` on fleet_nodes.csv, stream_manifest.csv and the other CSVs. The agent did the work, but the trajectory dropped the output. (Checked with python over all steps: h3 nulls at [2, 6, 8]. psf has one at [2]. gm and lane have none.)
- R6 is about ordering: the sealed harness ran at step 15, before the base run at step 16. That is a preference criterion and counts as a minor w3.
- R9 and R11 ask for an explicit falsification narrative. The agent tested all 24 combinations in one harness, and step 15's output shows the PASS/fail lines, but it never named a discarded combination. This was a real gap in narration.
- R12: totals were printed at step 28, but not derived independently. R15: the step 26 retry was judged non-adaptive.
- Every criterion is meetable by the oracle. None is unmeetable.

## 5. Permission setup
`tests/test.sh` matches the other three tasks: `chown root:root /logs/verifier`, `chmod 755`, `chmod -R go-rwx /tests`, then rewardkit. The agent program runs as nobody, with read access granted explicitly (see 2). This is not our bug.

## Points summary
- Genuine test points lost: 3 (damping loop shape, ambiguous).
- Test points lost to an undefined or contradicted rule: 19 (NOT a usable lever).
- Genuine judge points lost: 15 (R6, R9, R11, R12, R15). Artefact: 3 (R14).
