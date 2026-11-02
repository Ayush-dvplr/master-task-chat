# A: slo-credit-closeout — is the low score genuine?

Recorded: overall 38.69 / tests 2.38 / rubric 75.00. Run dir `trajectories/claude-opus-5/run_1/`.

## Verdict: GENUINE (amplified by whole-record-set projection digests; exact wrong values cannot be listed because only digests ship)

## Evidence

1. **Harness health**
   - `result.json`: `exception_info` null. Agent ran 18:43:40Z to 19:47:02Z (~63 min of a 14400 s budget; env setup took ~28 min before that). Verifier ~10 min.
   - `verifier/test-stdout.txt` is only the reward line. `ctrf.json`: 48 tests, none skipped, all messages empty. No traceback, `Errno 13`, `No such file` or timeout anywhere.
2. **Did the verifier run the agent's program?** Yes.
   - `eval_held_close_exact` (w3) PASSED. Per `tests/test_output.py:6311` it regenerates the next month (Sep 2026) from the embedded generator, deletes one support file, and runs the agent's `/app/out/transform.py` as uid 65534 under `setpriv`. A pass needs the exact HELD digest, so the program executed in the verifier on unseen data, read its inputs and wrote readable output.
   - `outputs_have_documented_shape` (w1, `:6073`) and `outputs_use_documented_encoding` (w1) PASSED: every record has exactly the documented sorted key set, and the JSON/JSONL encodings match `instruction.md:11`. There is no location, permission, schema or encoding gate.
3. **Wrong VALUES**
   - All 8 concept checks (ingestion, time, schema, eligibility, attribution, entities, credits, controls), all 16 trap slices, all 15 decoy checks (`decoy_d01`..`d15`, one per decoy file) and both `eval_next_month_*` checks failed. Each one is a digest over values (`_project` `:5747-5770`, `_slice_ok` `:5811`).
   - Expected values are stored only as SHA-256 digests, and TRUTH.md has no measured aggregates (`grep` for expected counts returns nothing). So I cannot name a specific wrong number.
   - Direct sign of a value error: the agent's own control harness printed `cdn_attestations.xlsx ... blocks=101 expblocks=101 bad=101` at trajectory steps 49 and 113. Its final `data_quality.json` nonetheless reports that file as `control_ok: true`. `transform.py:1021-1035` reaches that by trying sheet permutations until the control sums match. TRUTH inventory row 6 (`solution/TRUTH.md:60`) puts 20 traps in this file.
4. **Why tests sit near 0**
   - Every concept projection includes `[subscription_id] + concept fields` for every normalized record, plus summary status and period (`:5747-5770`). One wrong record-set membership (exclusion or active-day rule) therefore fails all 8 concepts at once.
   - TRUTH.md:347: "With one data_quality source count wrong the channel reads 0.9762 (only concept_controls is lost)". The design isolates source counts, but it does not isolate the record set.
   - The hidden next-month checks seed from the agent's own `/app/out` via `--prior` (quarter-to-date caps), so visible errors propagate (family B).
   - Not a gate. The only checks passed are the three that are value-independent (shape, encoding) or that use the HELD path (which writes no records).
5. **Rule text stated?** TRUTH.md:349: "No single file determines any graded value ... not hidden information". The instruction says the register and charter define the rules (`instruction.md:1`). Phase B checks this per rule.
6. **Judge**: it read the trajectory; 75.00.
   - R7 (3) failed: the final report claims every file passed the harness, but step 113 shows `cdn_attestations.xlsx bad=101`. This is a genuine false claim.
   - R10 (3) failed: broad `except Exception` returns None or passes silently. This is genuine and visible at `transform.py:1009`.
   - Both are meetable by the oracle (JD-7 holds).
7. **Permissions**: `tests/test.sh` runs `chown root:root` and `chmod 755 /logs/verifier`, then `chmod -R go-rwx /tests`, then rewardkit with workspace `/app`. It does not chmod `/app/out`. Hidden runs use a test-made shared dir (`os.chmod(SHARED, 0o755)`, `:5702`) plus read-only, root-owned inputs. The HELD pass proves the uid-65534 run could read and write.
