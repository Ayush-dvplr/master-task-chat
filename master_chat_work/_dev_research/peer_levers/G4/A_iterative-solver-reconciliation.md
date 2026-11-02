# A: iterative-solver-reconciliation (Shivendra Shukla), Phase A

**Verdict: ARTEFACT.** Recorded 53.60 / tests 23.88 / rubric 83.33. Every one of the 51 lost test points comes from one rule that the test reference and the oracle apply but that nothing the agent can read states. The task's own TRUTH.md, the shipped workbook and the judge all contradict that rule. Genuine test points lost: **0**. Judge points lost: 3 (R5, a conduct the instruction never asks for).

Task dir: `Anubis_Tasks_Samples/Pass@1_New/Poonam_Chourey/Shivendra Shukla/iterative-solver-reconciliation/`. Run: `trajectories/claude-opus-5/run_1/`.

## 1. Harness health
- `result.json`: `exception_info` null. Agent ran 21:07:05Z to 21:16:02Z (about 9 min) against a 14400 s timeout (`task.toml`). The agent finished on its own at step 41 of 42.
- `verifier/test-stdout.txt` is 15 bytes: `reward: 0.5361`. It has no tracebacks, `Errno 13`, `No such file` lines, timeouts or collection errors.
- `report.json`: final 53.6, tests 23.88, rubric 83.33, judge gpt-5.6-sol. `reward.toml` weights are test_output 0.007463 (= 0.5/67) and judge 0.027778 (= 0.5/18), so the split is 50/50.

## 2. Did the verifier run the agent's program? Wrong values or harness failures?
- The program does run, under a dropped uid. `test_output.py` L871-876 (`_untrusted`: setpriv nobody, `_grant_read` on args), L879-897 (`_open_tree` chmods dirs 0777 and files 0666 on the input and output trees) and L900-913 (`_run`, 300 s, nonzero exit -> AssertionError). The passed checks `row_order_independence` (5) and `writes_only_output_dir` (3) can only pass when the program executes. So there is no permission artefact.
- The failures are wrong values. A local repro (scratch, read-only: import `test_output.py` with a no-op rewardkit stub, run the agent's `reconcile.py` on `build_extract` corpora, compare with `_expected`) gave these counts of differing artifacts out of 22: sample 18, challenge 16, eval 17, omega-mutation 18, newton-mutation 18, epoch-mutation 16. On the SHIPPED data, the agent's delivered files vs the reference: 18 differ. `solution/solve.py` vs the reference: 0 differ.
- **Single root cause, proven.** I added the omega override (below) to the agent's `reconcile.py` and changed nothing else. Result: **0 differing artifacts in all six cases** (sample, challenge, eval, omega, newton, epoch). Command output: `sample 0 [] / challenge 0 [] / eval 0 [] / omega 0 [] / newton 0 [] / epoch 0 []`.

## 3. The rule behind every failure
- Reference `test_output.py` L278-284: `omega_milli = xlsx Relaxation!B5`, then `for row in omega_history.csv: if int(row["epoch"]) == epoch and row["status"].strip() == "active": omega_milli = int(row["omega_milli"])`. `solution/solve.py` L270-272 has the comment: "if omega_history.csv carries a row whose epoch equals the evaluation epoch and whose status is "active", that row's omega_milli supersedes the workbook base".
- Shipped data: `omega_history.csv` L242 `20260,1205,active` (the only `active` row; status counts are 163 retired, 77 candidate, 1 active). `pipeline_order.yaml` sets evaluation_epoch 20260. Reference omega is 1205; the agent used 1150 (B5).
- **Where the agent could read about it.** It is never stated as an override. `schema.md` L75-77 says the history tables are "**informational only** unless a row's epoch equals `evaluation_epoch`". L214 calls B5 "the base over-relaxation factor". L216 says "`omega_history.csv` is an epoch-scoped table (§3)". L259-260 says "historical/epoch-scoped, active only when a row's epoch equals `evaluation_epoch`". No sentence says the epoch row replaces B5, and the `status == "active"` condition appears nowhere in `schema.md`, `field_glossary.md` or `instruction.md` (grep for `supersede|effective|history`).
- **What contradicts it.**
  - `schema.md` L208-209: "Two figures gate every scaled result and **must** be read from the binary office documents; plain-text decoys carry superseded values" (omega_history.csv is plain text).
  - `known_pitfalls.md` L3: the xlsx `Relaxation!B5` value is the right one.
  - The xlsx NodeAudit sheet shows `omega_applied_milli = 1150` for every node (the agent quotes this in step 41).
  - `solution/TRUTH.md` L21-24: "lives only in cell `Relaxation!B5` ... (`1150` milli = 1.150)".
  - Judge criterion R2 (critically important) requires naming `Relaxation B5` as the source.
- **Agent's reading (trajectory step 41).** "I deliberately rejected the plain-text decoys: `relaxation_notes.txt` (1000, "SUPERSEDED") and `omega_history.csv`'s epoch-20260 row (1205), since §9a/§11 make the workbook cell authoritative and the history table a decoy." The agent saw the row (step 10 greps 20260 in omega_history.csv) and made the reading that the spec, TRUTH and the judge all endorse.
- This is HIDDEN RULE / test-oracle drift: the author's stated intent (TRUTH = 1150) and the oracle (1205) disagree. It fails IN-15 and TS-19, and it is not a lever.

## 4. Judge
The judge read the response: R2 and R3 cite the final message. 15/18.
- R5 (3, trajectory) FAILED: "builds a controlled variant changing omega, Newton cap or epoch, reruns, observes values move". The justification says it tested reordered inputs and synthetic extracts but did no before/after change of omega, cap or epoch. `instruction.md` never asks for this, so the criterion is unstated conduct (JD-15/IN-15 risk). The failure is about the agent's work only in the sense that it did not run that experiment.
- JD-7 concern (INFERRED): R2 credits naming B5 as the omega source, but the oracle's figures use the omega_history row. An oracle response that reports its true source would fail R2, and one that names B5 would misreport its own value.
- Negatives R7 (-5, opens /tests) and R8 (-3) did not fire.

## 5. Permission setup
`tests/test.sh` matches T1-T3: rm the reward files, mkdir `/logs/verifier`, chown root, chmod 755, `chmod -R go-rwx /tests`, `exec rewardkit /tests --workspace /app`. `test_output.py` `_open_tree` L879-897 makes the agent's trees world-readable/writable before running it as nobody. This is correct; it is the fix for our cohort Errno 13 bug.
