# QL oracle/nop procedure (temporary, from Ayush 20 Oct 23:12 IST)
Status: interim workaround from the QL while the normal Step 10 oracle/nop/stub run has problems. Pasted verbatim below.

Run the oracle and nop checks for this task bundle, using Harbor 0.24.0 and harbor-rewardkit 0.2.1. Grade the tests only and skip the LLM judge, because oracle and nop runs have no OpenAI key.

1. Copy the bundle to a temporary folder, keeping the same folder name, for example /tmp/oracle-qc/<bundle-name>. Never edit or commit the original bundle.
2. In the copy only:
   a. Delete tests/judge.toml.
   b. Read tests/test_output.py. Add up the positive weights in the criteria.<name>(weight=W) registrations; call that total P.
   c. Replace tests/reward.toml with exactly this, writing 1/P at full Python float precision (for example 1/6 = 0.16666666666666666):
      [[reward]]
      name = "reward"
      aggregation = "weighted-sum"
      weights = { test_output = <1/P> }

      [scoring.test_output]
      aggregation = "weighted-sum"
   d. Only if local Docker rejects network_mode = "no-network" under [environment] in task.toml, change it to "public" in the copy and do not modify the original or suggest doing so.
3. On the copy, run Harbor with the oracle agent max of 3 times and with the nop agent once. Use `harbor run --help` to confirm the flags for the task path and the agent.
4. For each run, read the reward from the run's verifier/reward.json.
5. Expected result: oracle = 1.0 on every run and nop = 0.0 on every run.
   - Oracle below 1.0: solve.sh fails a check, or a check has a bug. Name the failing checks from reward-details.json.
   - Nop not 0.0: a positive check passes on an empty run, or a negative check fires on one. Name the check.
   - No reward.json: rewardkit crashed, usually because a check raised an exception. Quote the error from the verifier log.
   - Different scores across runs of the same agent: the checks are non-deterministic. Report it.
6. Report a table of agent, run number and reward, then list any failing checks with their names, and every change made to the copy. Delete the temporary copy at the end.

## Notes for use (master chat)
- Tests channel is renormalised to 1.0 (judge removed), so oracle must be exactly 1.0, nop exactly 0.0.
- Covers oracle + nop only; stub is not in this procedure (see Q15).
- Harbor runs can exceed 4 min: builder prompts must run them via nohup + log + polling.
