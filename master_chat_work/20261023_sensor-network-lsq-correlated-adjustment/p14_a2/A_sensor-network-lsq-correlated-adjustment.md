# Phase A: sensor-network-lsq-correlated-adjustment, attempt 2 (board e30c85c)

**Verdict: GENUINE.** Overall 90.0 = 0.5 x tests 62/62 + 0.5 x judge 12/15. The tests 100 is real: the verifier ran the agent's own `derive_report.py` as `nobody` on three regenerated extracts and compared every document to an independent reference. The 3 judge points lost (R5) come from the agent's real code layout, and the oracle meets R5. R5 is still a JD-15 risk because the instruction promises nothing about code layout.

RUN = `.../traj_a2/job/trajectory/claude-opus-5/Run 1`, B = bundle folder.

## 1. Exceptions, limits, verifier errors
- `RUN/result.json:121` `exception_info: null`. Agent ran from 14:15:45Z to 14:30:13Z (14.5 min), well inside the 7200 s budget. It took 54 trajectory steps against `MAX_ITERATIONS 350`, so no limit was hit. Reward 0.9 (`result.json:117`).
- `RUN/verifier/test-stdout.txt` has 7 lines and only these messages: three per-extract summaries plus `reward: 0.9`. There is no traceback, `Permission denied`, `Errno 13`, `No such file`, timeout, import error, collection error or skip.
  - L1-2 `n=1021 u=4 dof=1017 blunders=19 downweighted=4 verdict=REJECT_HIGH` / `vtpv=1161.2703752995 sigma0_sq=1.1418587761 trace=14726009.649087`
  - L3-4 `n=1022 u=3 dof=1019 blunders=18 downweighted=10 verdict=REJECT_LOW` / `vtpv=1097.9844481686 ...`
  - L5-6 `n=1024 u=3 dof=1021 blunders=16 downweighted=8 verdict=REJECT_HIGH` / `vtpv=1161.8473590016 ...`
  - The three hidden extracts have different `u` (4 vs 3), `n` and verdict. None equals the shipped `REJECT_LOW n=1022 downweighted=3`, so the program was not echoing shipped answers.
- `RUN/trial.log`: only `chown 1000:1000 instruction.txt` and no errors.

## 2. Did the verifier really run the agent's program on hidden inputs?
Yes. Evidence:
- `B/tests/test_output.py:2356-2459`: `_build_corpus(seed)` regenerates a full extract with `emit_corpus` for each of `HIDDEN_SEEDS` (challenge, eval, audit). `_run_agent_program` (L2405-2446) does these steps:
  - chmods the data to 0755/0644;
  - copies the program via `_grant_read` (L2370-2383) into a fresh 0755 directory as 0644;
  - chowns the output directory to `nobody`;
  - runs `setpriv --reuid nobody --regid nogroup --clear-groups python3 prog data out` with a 120 s timeout under an fcntl lock.
- The reference values come from the test file's own Fraction solver `solve(root)`, which is independent of `solution/solve.py`.
- Every positive check (L2494-2720) first asserts `h['code']==0` and then makes whole-document comparisons. The rewardkit wrapper `_passes` (L3228-3245) maps any exception to False.

| criterion (`test_output.py:3341-3364`) | w | ran on | what it compares | result |
|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped `/app/out` | all 31 paths exist and parse | PASS |
| {challenge,eval,audit}_model_test_document | 3 x3 | hidden x3 | vtpv 10 dp, sigma0_sq, n, dof, acceptance lo/hi, verdict, passed | PASS x3 |
| {..}_unknowns_documents | 3 x3 | hidden x3 | every unknown in micrometres and metres, unknowns.csv rows, datum_transformation, XML | PASS x3 |
| {..}_residual_documents | 3 x3 | hidden x3 | every residual row in csv/tsv/jsonl/ndjson; residual_summary exact dict (max-abs tie on lowest obs_id) | PASS x3 |
| {..}_observation_sets | 3 x3 | hidden x3 | removed_blunders ids, downweighted ids, flags, final_weights.psv num/den | PASS x3 |
| {..}_rollup_documents | 3 x3 | hidden x3 | district/epoch/frame-campaign rollups, exact dicts | PASS x3 |
| {..}_summary_reports | 3 x3 | hidden x3 | status.txt exact line, yaml, md tokens, xml, normal_matrix_trace | PASS x3 |
| control_values_on_hidden_extracts | 3 | hidden | u, k, crit, origin, `control_values_source == workbook`, >=3 decoys named | PASS |
| superseded_records_on_hidden_extracts | 3 | hidden | superseded list == reference | PASS |
| canonical_serialization_on_hidden_extracts | 1 | hidden | sorted keys, trailing newline | PASS |

Total 62/62 (`RUN/verifier/reward-details.json`, test_output score 62.0). None of these checks is trivially true. They are exact equality on regenerated data whose `u`, verdict and duplicate sets differ from the shipped extract. Local `wrong/` mutants lose 54-57 of 62 on the same checks (`WORK/LEVERS.md`).

## 3. Why near-100
Tests are at 100 because the program was correct on all levers on the first write. The trajectory shows exactly one full write, at step 26 (14:22:53Z). The first run at step 27 printed `n=1022 u=3 dof=1019 blunders=18 downweighted=3 verdict=REJECT_LOW vtpv=1016.9199434352 sigma0_sq=0.9979587276`, which matches `solution/TRUTH.md:60-62` exactly. `derive_report.py` was never edited after that. Overall is 90 rather than 100 only because judge R5 failed (-3 of 15, which is -10 overall points).

## 4. Judge
- The judge read the response. `reward-details.json` has `atif_trajectory /logs/agent/trajectory.json`, mode batched, model gpt-5.6-sol. R1-R4 passed by quoting the figures from the final message (step 54). The R7 reasoning cites trajectory facts: "determinism was compared, and a modified extract was used for a genericity run" (steps 46-48). So the judge read beyond the final message.
- **R5** `r5_derive_report_py_uses_named_stage_functions` (w3) failed with this reason: "it does not separate the three overall stages into dedicated named functions for reading all inputs, computing the adjustment, and writing all reports. The main function directly performs orchestration, computation setup, and nearly all report construction and writing."
  - **The failure is about the agent's work.** In `RUN/artifacts/app/out/derive_report.py`, `main(argv)` runs from L560 to about L940 and does the orchestration and all report writing. Helpers (`read_shard` L235, `build_observations` L269, `class Stage` L394, `write_json` L533) exist, but there is no single read-stage, adjust-stage or write-stage function.
  - **JD-7 is met.** The oracle `B/solution/solve.py` has `load_observations` (L148), `adjust_extract` (L358), `write_reports` (L391) and `main` (L533).
  - **JD-15 risk.** `B/instruction.md` (9 lines) and `schema.md` contain no code-structure sentence. QC_RULINGS has precedents in both directions: vendor v2:37 FAIL ("outcome criteria grading code layout no file promises"), cohort v1:45 MINOR, emberforge v5:198 PASS. So R5 is a genuine 3-point loss, but it does not separate correct from wrong domain work.
- **The two "failed" negatives are penalties that did not fire.** ctrf shows 24 tests, 22 passed and 2 failed, which is where the "22/24" comes from.
  - Both are inverted-polarity detectors (`test_output.py:2870-2900`): the assertion holds only when the program ran cleanly and either (a) at least 2 shipped answer tokens appear in non-docstring AST constants, or (b) it imports numpy, scipy or pandas.
  - The agent's imports are stdlib only (`derive_report.py:11-19`: csv, io, json, os, re, sys, zipfile, xml.etree, fractions). So `negative_external_dependency` FAILED, meaning no penalty.
  - `negative_hardcoded_sample_answers` FAILED, also meaning no penalty; `reward-details.json` shows weight -5 with score 0.
  - Correction to the prompt: these two are test negatives (ctrf), not judge criteria. The judge's negatives are R6 (w-5), R7 (w-5) and R8 (w-3). `judge_response.txt` scores all three 0: R6 "figures ... agree with the artifacts", R7 "claimed checks were actually run", R8 no outside path.
  - Minor G7 gap: in ctrf the two negatives carry an empty `message`. That is the cause of the misleading "failed" label.

## 5. Permission setup
- `B/tests/test.sh:4-10`: removes old reward files, `mkdir -p /logs/verifier`, `chown root:root /logs/verifier`, `chmod 755 /logs/verifier`, `chmod -R go-rwx /tests`, then `exec rewardkit`. The verifier itself runs as root and writes `/logs/verifier`.
- The agent program runs as `nobody` (`setpriv`, `test_output.py:2405-2446`). It gets read access through a 0644 copy in a 0755 directory (`_grant_read` L2370-2383) and an output directory chowned to `nobody`. This is a deliberate isolation, and it did not cost the agent anything: all three hidden runs exited 0 (test-stdout L1-6).
- No permission artefact.

## Lessons for the master
- The tests 100 is genuine: one correct write, then a whole-document match on three reseeded extracts run as `nobody`. The harden simply did not bite.
- Inverted-polarity negatives show up as "failed" in ctrf with an empty message. Add messages per G7 so readers do not count them as lost points.
- R5 is the only loss. It is real against the agent's code and met by the oracle, but nothing in the instruction promises it (JD-15 risk).
