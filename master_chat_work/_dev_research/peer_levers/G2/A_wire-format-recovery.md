# A: wire-format-recovery: is the low score genuine?

**Verdict: PARTLY, close to ARTEFACT.** The whole 32-point test loss comes from one exact-key-set gate. The agent's decoded **values** were right on all 32 hidden eval captures. Its only mistake was an extra key, `wide_value: false`, on delta and dictionary records, and no spec file states the key set for those two modes. The 3 judge points lost come from a preference criterion.

Run: overall 73.37 / tests 55.56 (40/72) / rubric 91.18 (31/34).

## 1. Harness health
- `result.json`: exception_info None. Agent ran 18:55:53-19:01:43Z (about 6 min, 24 steps). Verifier ran 19:01:50-19:02:54Z. No timeout, and no step limit was hit.
- `verifier/test-stdout.txt` holds only the reward line (15 bytes). There are no tracebacks. `ctrf.json` holds no failure messages.
- Permissions: `tests/test.sh` does `chown root:root /logs/verifier`, `chmod 755`, `chmod -R go-rwx /tests`, then `exec rewardkit`. `_run_agent` (test_output.py L785-798) runs the program under `setpriv --reuid=nobody`, with `python -I` and a 60 s timeout. `_readable_program_copy` (L753-770) first copies the program to mode 0644, and its docstring says "An agent editor can leave the delivered file at mode 0600...". So the permission bug we had is handled explicitly.
- Every check that uses the agent's program ran it. The tests that passed show this: round-trips on the eval corpus (3) and on the samples (3), the three rejection tests, `record_count_matches_and_file_order`, and `pre_resolution_payload_fields_present`. These tests run the same decoder binary on the same eval corpus as the failed tests.

## 2. Failed checks: wrong value or gate?
Failed tests (32 of 72 points): decodes_raw_i32_from_eval 3, decodes_raw_i16_from_eval 3, decodes_delta_from_eval 5, decodes_dict_from_eval 5, decodes_mixed_modes_from_eval 5, decodes_large_magnitude_signed 5, decodes_long_keys 3, decodes_short_keys_from_eval 3.
- Each one compares the WHOLE decoded document with `_docs_equal` (L821-835), which requires identical key sets: `if set(a.keys()) != set(b.keys()): return False`.
- The reference `_generate_doc` (L483-551) gives raw records the keys {key, mode, long_key, wide_value, raw_value, value}. Delta records get {key, mode, long_key, delta_raw, value} and dict records get {key, mode, long_key, dict_index, value}, so neither has `wide_value`.
- The agent's `decode.py` (artifacts/app/decode.py L110-115) builds every record with `"wide_value": wide`, whatever the mode. The trajectory shows this at step 13, where the agent's own output prints `{"delta_raw": -3, "key": 42, "long_key": false, "mode": "delta", "value": 7, "wide_value": false}`.
- The raw-only tests (raw_i32, raw_i16) fail as well, because they compare the whole capture and eval captures mix modes (EVAL_SPECS L408-441).
- **Confirmation run** (read-only; temp dir; test_output.py imported with `rewardkit` stubbed; agent decode.py run on the 32 reference eval captures): `total 32 exact_equal 1 equal_after_dropping_nonraw_wide_value 32`. Every resolved value, sign extension, delta chain, dictionary lookup and long key is correct. Only the extra key differs.
- Is the gate stated? Spec mentions found by grep:
  - container-format.md L41: "bit `0` carries the `WIDE_VALUE` flag (raw mode only)". This describes the selector bit.
  - L53-57: a JSON object is shown for the raw record only.
  - §4 L71 and §5 L77 name only the payload key: "reported as `delta_raw`", "reported as `dict_index`".
  - encoder-notes.md L10: "Raw records set `wide_value`".
  - instruction.md L18: "key order and whitespace inside the JSON are up to you". This implies the key set is fixed but never states it for delta or dict.
  - For error objects only, the instruction says "carrying exactly the keys the specification defines for that error".

  So the delta/dict key set can only be **implied by omission**: no file states it, and no shipped example shows a delta or dict object (the capture log is raw-only by design, test comment L661-665). That puts it on the IN-15/TS-19 borderline. It is a schema gate, not a semantics lever.

## 3. Near-zero / gate analysis
Tests are not near 0, but a single gate cost 8 tests and 32 points. Gate: exact per-mode key set of each record object. It is stated clearly for raw only and is unstated for delta and dict. The agent's self-test could not see it: the agent round-tripped through its own encoder (step 10: 18208 captures, 0 failures; step 20), and that encoder ignores `wide_value` on non-raw records.

## 4. Judge
- The judge read the response: R10 (w3, "summarizes the completed work and names where the produced artifacts were written") passed.
- The judge passed R4 (w5, critical: "implements raw mode, delta mode, dictionary mode, and the running-value and state semantics") and R5 (w5, critical: "handles delta records, dictionary records, long UTF-8 keys, and signed i16/i32 boundary values as the specification defines"). That agrees with the confirmation run and contradicts the test outcome on the same observable (JD-8 overlap).
- Only R11 failed (w3): "implements exactly decode.py and encode.py ... and adds no auxiliary or renamed modules". The agent created `/app/build_artifacts.py` (step 11) and `/app/AGENTS.md` (step 22). Neither is imported by the codec. The instruction (L22) forbids only that decode/encode "import helper modules you write alongside them". R11 therefore penalises a legitimate build script, so it is a preference/approach criterion (JD-15 conduct negative-style) and the loss is not genuine.

## 5. Permission setup
Robust, as described in item 1: the program is copied to mode 0644 and run as nobody. There is no read problem on /app/out, since the artifact tests passed (4 x 3).

## Points summary
- Genuine semantic test points lost: **0**.
- Schema-gate points lost: **32/72** (44.44 test-pct), on a key set that is implied, not stated.
- Genuine judge points lost: **0**. The 3 lost points are a preference criterion.
