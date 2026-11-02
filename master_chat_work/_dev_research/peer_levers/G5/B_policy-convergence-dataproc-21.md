# B (design notes only, verdict ARTEFACT): policy-convergence-dataproc-21

Inventory:
- Same template as cli-config-01, plus a HARDENING_V2 addendum (contract L201-249, 2153 words in total).
- validation_rules.json 4503 B, with `_hardening_v2`, `dynamic_bounds`, `zone_matching`, `ops.touch`.
- Instruction 739 words, with requirements 22-24 appended after the time-budget line (L27-31).
- 40 tests (positive total 104); 16 judge criteria in `batched` mode; split 50/50 (1/208, 1/108).
- All 9000 journal ops are env base.

Worth noting:
1. **The stateful replay lever did NOT cost points.** The rules: max_sessions ≤ floor(rekey / handshake) evaluated against the running state (contract L205-210), and `touch` semantics (L214-218). The agent got rejected_ops (8574) and config exactly right. Both rules are plain sentences mirrored in validation_rules.json `dynamic_bounds`. This is another instance of the DIAGNOSIS leak: an explicit rule plus a rules-file copy is solved on the first write.
2. **Addenda that add output keys without saying so.** 12 points rode on five keys that the posture and validation_report specs never mention (A file). This is the cheapest-looking "lever" here and it is NOT ALLOWED (IN-15/TS-19).
3. **The command list contradicts the test.** The contract lists the commands to record without `compile`, and the test requires a `compile` token. Do not copy this.
4. **Byte-exact homoglyph rule is stated three times** (instruction, contract L244-248, validation_rules `zone_matching`) and the test's negatives did not fire. The judge then demanded the agent "shows the per-byte comparison used" (#16), which is process the spec never asks for.
5. Judge #14 (stateful max_sessions demo) and #15 (Z shift and byte-stable ZIP) passed. These are outcome-explanation criteria, a pattern we could reuse, but they did not discriminate.
6. Policy failed none of the genuine levers seen in cli/firewall: the journal has no non-base env, so the spine scope lever is absent.
