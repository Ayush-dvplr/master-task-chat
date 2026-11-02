# A: lane-dispatch-optimisation (recorded 33.90 / tests 3.09 / rubric 64.71)

Verdict: **PARTLY**. Tests did run the agent's real program and outputs, and every failure is a wrong VALUE. But about 89 of the 94 lost test points also need a disposition-precedence rule that no agent-visible file states (HIDDEN). The other lever, the budget cap reducing net value, is stated in a file the agent read, and it alone is necessary for all 94 points. The near-zero score is not caused by a gate or a schema problem.

## 1. Run health
- `result.json` exception_info null. Trajectory 93 steps, 15:54:29-16:40:12Z (~46 min). The 73 s span in result.json does not match the trajectory and is ignored. Agent timeout 21600 s not reached.
- `verifier/test-stdout.txt` holds only the `reward:` line. No traceback, no `Errno 13`, no `No such file`, no timeout, no collection error.
- Permissions are correct: `tests/test_output.py` `_invoke` (L2417-2456) copies `/app/out/*.py` into a fresh 0755 dir as 0644, chmods data 0755/0644 and out 0777, and runs `setpriv --reuid=nobody --regid=nogroup --clear-groups python program data out` with a 600 s timeout. `tests/test.sh` chowns `/logs/verifier` to root and runs chmod 755, which is the same in all 4 tasks.

## 2. Did the verifier grade real values? Yes (reproduced locally)
- `_materialise("shipped")` regenerated data byte-identical to `environment/data` (19 SAME, 0 DIFF/EXTRA/MISSING; `_scratch/lane_cmp.py`).
- The agent's `derive_report.py`, run locally on the shipped data (rc 0, 0.66 s), reproduces all 9 delivered JSONs exactly.
- Delivered vs reference: region_North MATCH. The other 8 value artifacts DIFF. Agent `summary.json`: net_micros_total 242910, orders_deferred 50, orders_rejected 3. Reference (`solution/TRUTH.md:218`): 218890 net, 49 deferred, 4 rejected. Charge 268040, rebate 25130 and capped 24020 are IDENTICAL, and 242910 - 24020 = 218890.
- Counterfactual across every test variant (`_scratch/lane_variants.out`, 38 variants; columns agent | fix_prec | fix_cap | fix_both):
  - fix_both is OK on all 38: shipped, 7 fmt_*, 12 trap_*, 20 mut_*.
  - The agent alone is OK only on mut_scale.
  - fix_prec alone fixes none.
  - fix_cap alone is OK on 7 variants. That is enough to flip only `test_generalises_population_shapes` (w5).
  - So the agent's 12-constant recovery, its decoding and its format handling were all correct.

## 3. Why near zero
There is no gate. `_compare` checks each artifact as a whole JSON object, and every instance/trap/generalises/format check compares money-bearing artifacts. The cap misreading changes net value in every region, segment, summary and data_quality figure, so it fails every value check across all 38 variants. Only 3 schema/conservation checks (3 pts) survive. The conservation check passes because the agent's own numbers are internally consistent.

## 4. Root causes
1. **Budget cap (STATED, RISKY).**
   - `cost_policy.md:8`: "The net value of a placed order is its charge less its rebate."
   - `cost_policy.md:9-13`: "...the part that would pass the ceiling is recorded as capped value and the order settles the remainder."
   - Reference `settle_costs` (test_output.py L738-775) sets net = remaining room.
   - The agent kept net = charge - rebate. Step 92: "`net_micros` is charge less rebate as `cost_policy.md` defines it, with the budget excess reported separately as capped_micros". The agent saw both readings and chose the literal definition over the later modifier.
   - `probe_region_example.json` shows capped_micros 0, so the shipped data contains no example of a binding cap.
2. **Disposition precedence (HIDDEN, NOT ALLOWED).**
   - Reference `classify` (test_output.py L509-540) runs retired -> no revision (reject) -> pre-effective (defer).
   - The agent runs retired -> pre-effective -> gap.
   - W000407 is both inactive and in a revision gap. Step 60 output: `W000407 ... ['inactive', 'gap']`.
   - `report_schema.md:23-29` defines deferred (client not yet active) and rejected (no revision governs). Both definitions match W000407, and no file states which one wins.
   - instruction.md:68-69 "Resolve each order's client to its governing form before you select any governing programme revision" points toward the agent's order. The judge criterion r5_identity_before_revision rewarded exactly that order, and the agent PASSED it.
   - `solution/TRUTH.md:283-285` (step 4 identity/holding, then step 5 gap) also lists identity first.
   - No calibration control separates the readings (billable_slot_total excludes the order either way; agent step 70 note).

## 5. Judge (rubric 64.71 = 22/34)
- 23 criteria: 20 positive totalling 34 and 3 negative (r7 -3, r14 -5, r15 -3), none fired.
- Failed r18, r19, r20, r22 (w3 each, 12 pts). All four are self-test conduct: run on a rewritten-table corpus, an extra document beside the corpus, a rule-value perturbation, and a merge-cycle corpus. The agent did not do these runs, so the failures are genuine on conduct. They are odds-raising conduct at weight 3 (allowed under JD-15).
- JD-7 caveat (INFERRED): a shipped oracle `solve.sh` leaves no trajectory, so it cannot visibly perform these runs.
- Value criteria r8-r13 passed. The derivation record figures are correct because they come from the constants and placement stages, upstream of both errors.

## 6. Permission setup
Correct (see 1). This is not an artefact like our Errno 13 bug.
