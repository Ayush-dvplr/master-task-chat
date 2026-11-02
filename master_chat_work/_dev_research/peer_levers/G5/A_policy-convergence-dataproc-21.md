# A: policy-convergence-dataproc-21. Is the low score genuine?

Recorded: overall 58.67, tests 43.27, rubric 74.07 (judge mode `batched`).

**Verdict: ARTEFACT.** The agent lost 59 of 104 positive test points, and every failing check fails for an artefact reason: a spec/test contradiction, a graded key that appears nowhere the agent can read, or a cascade. The agent did make one genuine naming slip (aggregate keys carry the file extension, worth 26 points), but the strip artefact fails those same checks anyway. All 14 judge points lost are rules that are stated nowhere.

The journal has no cross-env trap here: all 9000 ops are `env: base` (trajectory step 7 `Counter({'base': 9000})`). The agent's config and the stateful `touch`/`max_sessions` rejection logic passed (config_matches_policy, rejected_ops_match, rejected_ops_strictly_sorted, profile_trailer_embeds_config_sha_prefix). So the task's real hardening (the stateful replay) did NOT cost points.

Evidence:
- Harness: `exception_info` None. ~13.9 min of the 7200 s budget, 41 steps, final message. test-stdout holds only `reward: 0.5867`. ctrf has 40 tests, positive total 104, earned 45 = 43.27. test.sh is identical to cli-config-01 (root grader, CLI run as `nobody` from a 0o755 extract), so there is no permission artefact.
- Aggregate family (29) fails on the field-strip contradiction. The oracle solve.py strips (L119, 136, 148, 212-214, 238-241, 251, 664, 676, 680). The spec says byte-exact (instruction L12, contract canonical-int section). validation_rules.json goes further: `zone_matching.comparison = "byte-exact; no strip, no normalization, no casefold"`. Shipped example: c01 row `mgmt, 12,active`. On top of that, the agent keyed aggregates by file name (`c01_cve_severity.csv`) where the test expects the stem.
- manifest_correct (5): instruction L22 and the contract say "per delivered JSON artifact except `report.json`". The agent wrote 12 JSON lines. The test expects 19 names, including the 7 non-JSON views, and the oracle does the same. CONTRADICTION.
- report_transcript_real (5): the test requires a `compile` argv token (L694-702). Contract HARDENING_V2 L237-240 lists the commands to record as "`init`, every `set`, `validate`, and `export-report`" plus `aggregate`. The agent recorded 59 calls with rc 0 and no compile. CONTRADICTION / partly hidden.
- HARDENING_V2 checks, 4×3 = 12: `posture.zip_sha256`, `posture.config_sha256`, `posture.touch_rejected`, `checks.commands_through_cli`, `checks.zip_shift`. A grep of environment/ and instruction.md found none of these key names. Contract posture keys are only aggregate_total, corpus_count, max_corpus, max_value, nonzero_corpora. **HIDDEN RULE.**
- validation_report (5) and summary (3): the expected list types and order are not stated, plus the aggregate_total cascade. The agent wrote command_failures 0, rejected_ops 8574, and profiles as a dict. HIDDEN schema.
- Judge (16 criteria, 40/54). All four misses are rules stated nowhere (grep of instruction + contract):
  - #1 (3) observe the failing command before editing.
  - #10 (3) no auxiliary or renamed copies. The agent made /tmp/out_run1 and /tmp/scratch/config.json at steps 30 and 36, then deleted them.
  - #11 (5) name a concrete journal op by seq.
  - #16 (3) "shows the per-byte comparison used". The agent did name the four homoglyphs.
- The instruction itself is in poor shape: requirements 22-24 come after the "You have 7200 seconds" line (L27-31), and test descriptions cite a "requirement 26" that does not exist.

Phase B is reduced to design notes (B_policy-convergence-dataproc-21.md).
