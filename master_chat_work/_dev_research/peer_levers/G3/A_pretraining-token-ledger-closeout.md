# A: pretraining-token-ledger-closeout — is the low score genuine?

Recorded: overall 33.34 / tests 0.00 / rubric 66.67. Run dir `trajectories/claude-opus-5/run_1/`.

## Verdict: GENUINE (with a heavy amplifier: every check is an exact hash)

The tests channel ran the agent's real outputs and its re-run package. Nothing points to a harness fault. The 0.00 comes from wrong values, graded by all-or-nothing SHA-256 digests (whole file, or per slice of ~35-268 trap records). There is no single format gate: the one shape check passed.

## Evidence

1. **Harness health**
   - `result.json`: `exception_info` null. The agent ran from 16:12:05Z to 17:36:51Z (~85 min, 197 steps, MAX_ITERATIONS 350, so not cut off). The verifier ran from 17:37:01Z to 17:48:00Z.
   - `verifier/test-stdout.txt` is 15 bytes, only the reward line. No traceback, `Errno 13`, `No such file`, timeout or collection error.
   - `verifier/ctrf.json`: 39 tests, none skipped, every message empty. The tests leave no diagnostics, so we cannot see per-check deltas.
2. **Did the verifier use the agent's outputs?** Yes.
   - `outputs_have_documented_shape` (w1) PASSED. Per `tests/test_output.py:438-444` it checks the exact top-level key order of every file, `stage == S3` and a well-formed package.
   - My own check at trajectory step 180 confirms the agent's files are exact `json.dumps(indent=2, ensure_ascii=False)+"\n"` with the contract's key orders and sort orders.
   - The posting rows I sampled from `artifacts/app/out/scenario_alpha.json` carry the contract's 12 keys in order. `idempotency_key` = `<stage>/<account>/<ref>/<kind>`, which matches contract line 11.
   - So the failures are value mismatches, not shape or location problems.
3. **Hidden tier actually ran the package.** `negative_nondeterministic_output` (w -3) is reported "passed", which means it fired.
   - Per `test_output.py:621-659` that negative returns True only when runs A and B both produced output within the 1800 s limit (`_comparable`) and the bytes differed.
   - So the package ran under `setpriv` as uid 65534 in the separate verifier and wrote output. Its outputs were not byte-identical across two fresh-service runs.
   - That is a real agent defect. Its final message (step 196) says "two runs produce byte-identical files", but that self-test used `/app/data`, not the regenerated S4 corpus. The cause is not identified (INFERRED: some ordering path that only the S4 corpus exercises).
4. **Why every value check is 0**
   - Visible checks compare whole-file digests (`test_output.py:150-152`).
   - Slice checks (`:172-186`) hash `[postings, exceptions]` for the slice's refs, dropping only `ledger_seq` and `remaining_after_tokens`. One wrong row zeroes the slice.
   - TRUTH lists 1,881 traps (1,431 in scope) over 650,621 records, with 24 trap or drift families.
   - The hidden S4 checks use the agent's own `final_state.json` as the opening balance (`:314-365`). TRUTH "Root cause" says "an error in S3 repeats in the hidden tier even when the package itself is right", so the hidden tier fails as a consequence of the visible errors (dependent chain).
   - INFERRED: budget-state errors (opening, carry cap, exhaustion order) change BUDGET_EXHAUSTED / OVER_EPOCH reasons across many slices, so a few defects can zero most slices. The digests do not let us count how many records were actually wrong.
5. **Is the rule text readable?**
   - instruction.md:13 states the gate plainly: "An output is accepted only as a whole: one wrong value, row, key, type or position rejects the file".
   - TRUTH:5 states "Nothing is redacted: every rule is written in the shipped register, contract and procedures".
   - I spot-checked the five drift rules in the agent's `runner.py`. It implemented half-even rounding (L69, 1726), COMPLETE-cutover tokenizer switching (L989-996), crawl_date / 0000-00-00 handling (L1074-1075), GPS/UNIX epochs (L29, 1434) and footnote overrides (L94-145).
   - So the agent read most of the rules. It lost on residual per-record errors spread across 24 families, which are not visible from digests.
6. **Judge**: it read the response; 40/60.
   - Failed criteria, all genuine:
     - R8 (NEG -3): ran `pip install pyflakes` at step 161.
     - R12 (1): listed only one of the 7 output paths.
     - R13 (3): did not say whether any discrepancy remains open.
     - R15 (3): `except Exception: d = None` swallowed errors.
   - All four are meetable by the oracle (JD-7 holds).
7. **Permissions** (`tests/test.sh`):
   - It runs `chown root:root` and `chmod 700 /logs/verifier`, then `chmod -R go-rwx /tests`, then `rewardkit /tests --workspace /app`.
   - There is no chmod on `/app/out`. The verifier is root (INFERRED from `chown` and `setpriv` use), so it can read the agent's files.
   - For package runs, `test_output.py` chowns each private out/cwd to the run uid with mode 0700 (`:314-365`).
   - None of this resembles our Errno 13 bug.

## What this means for us
- The low tests score is real, but its size comes from exact-hash all-or-nothing grading over a very wide corpus (24 families, 100 files).
- That generalises poorly: one subtle defect costs a whole slice, and the agent gets no signal.
- The genuine lever is breadth × exactness × a dependent hidden stage, not any single clever rule. See B.
