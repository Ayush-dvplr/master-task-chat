# QC push bde868c4: Anubis bundle migration report

Run 21 Oct 2026 16:30 to 16:38 IST (11:00 to 11:08 UTC). Harness HEAD `bde868c46994f4916e245b40d14f302b1341244a` (starts with bde868c4, checked before work). Edit authorised by Ayush 21 Oct 2026 16:15 IST for exactly the four listed folders. 16 bundles. Nothing committed or staged.

## Result

All 16 bundles: judge_qc 0 FAIL after. structure_qc, tests_qc and instruction_qc show no new FAIL (FAIL line sets compared byte for byte, before vs after). The only remaining FAILs are the pre-existing structure_qc S3/S5 on the three Pass@1 bundles (the `trajectories/` folder, left untouched as instructed).

| # | Bundle | Criteria migrated | Annotation keys deleted | Type chosen without category | judge_qc FAIL before / after | structure/tests/instruction FAIL before / after | Files changed |
|---|---|---|---|---|---|---|---|
| 1 | `QC_Fixed_19_10_2026/Ayush_Sah/match-replay-desync-audit` | 18 | 90 | none | 36 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 2 | `QC_Fixed_18_10_2026/Ayush_Sah/numeric-reduction-benchmark-forge` | 21 | 105 | none | 42 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 3 | `QC_Fixed_18_10_2026/Ayush_Sah/pcggc-multi-state-rec-settlement` | 11 | 61 | none | 22 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, solution/TRUTH.md, tests/test.sh |
| 4 | `QC_Fixed_18_10_2026/Ayush_Sah/season-ladder-settlement` | 16 | 92 | none | 32 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 5 | `QC_Fixed_18_10_2026/Ayush_Sah/sensor-network-lsq-correlated-adjustment` | 21 | 110 | none | 42 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 6 | `QC_Fixed_18_10_2026/Ayush_Sah/sentinel-policy-recompute` | 13 | 73 | none | 26 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 7 | `QC_Fixed_18_10_2026/Ayush_Sah/specdec-verification-engine` | 12 | 64 | none | 24 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, solution/TRUTH.md, tests/test.sh |
| 8 | `QC_Fixed_17_10_2026/Ayush_Sah/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec` | 11 | 61 | none | 22 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 9 | `QC_Fixed_17_10_2026/Ayush_Sah/caldermoor-commitment-closure` | 28 | 125 | none | 56 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, solution/TRUTH.md, tests/test.sh |
| 10 | `QC_Fixed_17_10_2026/Ayush_Sah/cohort-retention-reconciliation` | 18 | 90 | none | 36 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 11 | `QC_Fixed_17_10_2026/Ayush_Sah/cohort-uplift-reconciliation` | 9 | 49 | none | 18 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 12 | `QC_Fixed_17_10_2026/Ayush_Sah/dispatch-plan-reoptimization` | 25 | 132 | none | 50 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, tests/test.sh |
| 13 | `QC_Fixed_17_10_2026/Ayush_Sah/emberforge-vault-settlement` | 12 | 67 | none | 24 / 0 | 0/0/0 / 0/0/0 | tests/judge.toml, solution/TRUTH.md, tests/test.sh |
| 14 | `Pass@1/Sugam_Agrawal/Ayush sah/cohort-retention-reconciliation` | 18 | 90 | none | 36 / 0 | 3/0/0 / 3/0/0 | tests/judge.toml, tests/test.sh |
| 15 | `Pass@1/Sugam_Agrawal/Ayush sah/dispatch-plan-reoptimization` | 25 | 132 | none | 50 / 0 | 3/0/0 / 3/0/0 | tests/judge.toml, tests/test.sh |
| 16 | `Pass@1/Sugam_Agrawal/Ayush sah/sensor-network-lsq-correlated-adjustment` | 21 | 110 | none | 42 / 0 | 3/0/0 / 3/0/0 | tests/judge.toml, tests/test.sh |

Totals: 279 criteria migrated, every one had a `category`, so no type choices were needed. Old `type` values (VALUE 79, EFFECT 75, ORDERING 48, DIVERGENCE 27, INVARIANT 25, ABSENCE 25) were replaced by the old `category` value.

## Per bundle detail

- 1 `QC_Fixed_19_10_2026/Ayush_Sah/match-replay-desync-audit`: deleted keys evidence x18, residue x18, kind x18, category x18, contract_sentence x7, contract_file x7, serves x4; test.sh `chmod 700` to `755` x1
- 2 `QC_Fixed_18_10_2026/Ayush_Sah/numeric-reduction-benchmark-forge`: deleted keys evidence x21, residue x21, kind x21, category x21, contract_sentence x3, contract_file x3, serves x15; test.sh `chmod 700` to `755` x1
- 3 `QC_Fixed_18_10_2026/Ayush_Sah/pcggc-multi-state-rec-settlement`: deleted keys evidence x11, residue x11, kind x11, category x11, contract_sentence x6, contract_file x6, serves x5; test.sh `chmod 700` to `755` x1; TRUTH Provenance line removed: `status: active`
- 4 `QC_Fixed_18_10_2026/Ayush_Sah/season-ladder-settlement`: deleted keys evidence x16, residue x16, kind x16, category x16, contract_sentence x12, contract_file x12, serves x4; test.sh `chmod 700` to `755` x1
- 5 `QC_Fixed_18_10_2026/Ayush_Sah/sensor-network-lsq-correlated-adjustment`: deleted keys evidence x21, residue x21, kind x21, category x21, contract_sentence x5, contract_file x5, serves x16; test.sh `chmod 700` to `755` x1
- 6 `QC_Fixed_18_10_2026/Ayush_Sah/sentinel-policy-recompute`: deleted keys evidence x13, residue x13, kind x13, category x13, contract_sentence x8, contract_file x8, serves x5; test.sh `chmod 700` to `755` x1
- 7 `QC_Fixed_18_10_2026/Ayush_Sah/specdec-verification-engine`: deleted keys evidence x12, residue x12, kind x12, category x12, contract_sentence x5, contract_file x5, serves x6; test.sh `chmod 700` to `755` x1; TRUTH Provenance line removed: `status: complete`
- 8 `QC_Fixed_17_10_2026/Ayush_Sah/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec`: deleted keys evidence x11, residue x11, kind x11, category x11, contract_sentence x6, contract_file x6, serves x5; test.sh `chmod 700` to `755` x1
- 9 `QC_Fixed_17_10_2026/Ayush_Sah/caldermoor-commitment-closure`: deleted keys evidence x28, residue x28, kind x28, category x28, contract_sentence x4, contract_file x4, serves x5; test.sh `chmod 700` to `755` x1; TRUTH Provenance digests refreshed for tests/judge.toml, tests/test.sh
- 10 `QC_Fixed_17_10_2026/Ayush_Sah/cohort-retention-reconciliation`: deleted keys evidence x18, residue x18, kind x18, category x18, serves x16, contract_sentence x1, contract_file x1; test.sh `chmod 700` to `755` x1
- 11 `QC_Fixed_17_10_2026/Ayush_Sah/cohort-uplift-reconciliation`: deleted keys evidence x9, residue x9, kind x9, category x9, contract_sentence x4, contract_file x4, serves x5; test.sh `chmod 700` to `755` x1
- 12 `QC_Fixed_17_10_2026/Ayush_Sah/dispatch-plan-reoptimization`: deleted keys evidence x25, residue x25, kind x25, category x25, contract_sentence x7, contract_file x7, serves x18; test.sh `chmod 700` to `755` x1
- 13 `QC_Fixed_17_10_2026/Ayush_Sah/emberforge-vault-settlement`: deleted keys evidence x12, residue x12, kind x12, category x12, contract_sentence x7, contract_file x7, serves x5; test.sh `chmod 700` to `755` x1; TRUTH Provenance line removed: `status: complete`
- 14 `Pass@1/Sugam_Agrawal/Ayush sah/cohort-retention-reconciliation`: deleted keys evidence x18, residue x18, kind x18, category x18, serves x16, contract_sentence x1, contract_file x1; test.sh `chmod 700` to `755` x1
- 15 `Pass@1/Sugam_Agrawal/Ayush sah/dispatch-plan-reoptimization`: deleted keys evidence x25, residue x25, kind x25, category x25, contract_sentence x7, contract_file x7, serves x18; test.sh `chmod 700` to `755` x1
- 16 `Pass@1/Sugam_Agrawal/Ayush sah/sensor-network-lsq-correlated-adjustment`: deleted keys evidence x21, residue x21, kind x21, category x21, contract_sentence x5, contract_file x5, serves x16; test.sh `chmod 700` to `755` x1

## Consistency checks (all already held, nothing adjusted)

- importance vs |weight|: no mismatch in any criterion (J13 pass everywhere).
- description opening vs evaluation_target: no mismatch (J9 pass everywhere). No evaluation_target or description wording was changed.
- JD-16: all 88 `kind = constraint` criteria carry type `instruction following`; no outcome (32) or conduct (159) criterion carries it.
- `safety and boundaries` (3 criteria) is written with "and"; no "&" found.
- `[judge]`, `[scoring]` and every criterion's id, name, description, type ("binary") and weight are unchanged: the migration script compared the parsed TOML before and after and stopped on any difference outside `[criterion.annotations]`.

## Change 2 (TRUTH.md)

- `status:` removed from the Provenance yaml block in pcggc-multi-state-rec-settlement (`status: active`), specdec-verification-engine and emberforge-vault-settlement (`status: complete`). No other forbidden key (authored_by, archetype, generator_seed, trailer_token) occurs in any TRUTH.md.
- No sentence describing how a bundle was generated was found (grep for the validator's TRUTH_NARRATION_RE terms plus generator, template, authored, built by, changelog, reviewer; the hits are task content, such as "The reference is authored in Python" and generated test extracts). No prose changed.
- caldermoor-commitment-closure: its Provenance lists sha256 digests of shipped files, including tests/test.sh and tests/judge.toml. Both files changed in this migration, so those two digest lines were updated to the new digests (otherwise TRUTH would pin stale bytes). Every other digest line is unchanged. No TRUTH lists its own digest. No other bundle's TRUTH, task.toml, instruction.md, solution/ or tests/ file pins a digest of a changed file (checked by fixed-string search for all 48 before hashes).

## Change 3 (test.sh)

All 16 test.sh files had `chmod 700 /logs/verifier`; each now reads `chmod 755 /logs/verifier`. No other line changed. tests_qc WARN count dropped by 1 in every bundle after this change (FAIL count stayed 0).

## Not run

- Oracle / harbor runs: not run (no test, data or solution code change).
- validate_bundle.py: not run, as instructed.
- Untouched: tests/test_output.py, tests/reward.toml, environment/data, solution code, instruction.md, task.toml, trajectories/.

## Files

- before.sha256 / after.sha256 (this folder): 48 entries each (judge.toml, TRUTH.md, test.sh per bundle). 36 files differ: 16 judge.toml, 16 test.sh, 4 TRUTH.md.
- QC logs: /tmp/opencode-logs/qc-push-bde868c4-anubis-20261021T1630/{before,after}/

## Pre-existing FAILs (unchanged, not caused by this migration)

- 14 `Pass@1/Sugam_Agrawal/Ayush sah/cohort-retention-reconciliation`:
  - FAIL [S3] unexpected entry trajectories: the bundle root holds only ['environment', 'instruction.md', 'solution', 'task.toml', 'tests']. Delete it.
  - FAIL [S5] forbidden file: trajectories/claude-opus-5/run_1/verifier/ctrf.json
  - FAIL [S5] forbidden file: trajectories/claude-opus-5/run_1/verifier/reward.json
- 15 `Pass@1/Sugam_Agrawal/Ayush sah/dispatch-plan-reoptimization`:
  - FAIL [S3] unexpected entry trajectories: the bundle root holds only ['environment', 'instruction.md', 'solution', 'task.toml', 'tests']. Delete it.
  - FAIL [S5] forbidden file: trajectories/claude-opus-5/run_1/verifier/ctrf.json
  - FAIL [S5] forbidden file: trajectories/claude-opus-5/run_1/verifier/reward.json
- 16 `Pass@1/Sugam_Agrawal/Ayush sah/sensor-network-lsq-correlated-adjustment`:
  - FAIL [S3] unexpected entry trajectories: the bundle root holds only ['environment', 'instruction.md', 'solution', 'task.toml', 'tests']. Delete it.
  - FAIL [S5] forbidden file: trajectories/claude-opus-5/run_1/verifier/ctrf.json
  - FAIL [S5] forbidden file: trajectories/claude-opus-5/run_1/verifier/reward.json

## git status --short (Anubis_Tasks_Samples, after edits; it was empty before)

```
 M "Pass@1/Sugam_Agrawal/Ayush sah/cohort-retention-reconciliation/tests/judge.toml"
 M "Pass@1/Sugam_Agrawal/Ayush sah/cohort-retention-reconciliation/tests/test.sh"
 M "Pass@1/Sugam_Agrawal/Ayush sah/dispatch-plan-reoptimization/tests/judge.toml"
 M "Pass@1/Sugam_Agrawal/Ayush sah/dispatch-plan-reoptimization/tests/test.sh"
 M "Pass@1/Sugam_Agrawal/Ayush sah/sensor-network-lsq-correlated-adjustment/tests/judge.toml"
 M "Pass@1/Sugam_Agrawal/Ayush sah/sensor-network-lsq-correlated-adjustment/tests/test.sh"
 M QC_Fixed_17_10_2026/Ayush_Sah/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec/tests/judge.toml
 M QC_Fixed_17_10_2026/Ayush_Sah/7ef8d80a-fea7-5d9e-b426-bcabfc6802ec/tests/test.sh
 M QC_Fixed_17_10_2026/Ayush_Sah/caldermoor-commitment-closure/solution/TRUTH.md
 M QC_Fixed_17_10_2026/Ayush_Sah/caldermoor-commitment-closure/tests/judge.toml
 M QC_Fixed_17_10_2026/Ayush_Sah/caldermoor-commitment-closure/tests/test.sh
 M QC_Fixed_17_10_2026/Ayush_Sah/cohort-retention-reconciliation/tests/judge.toml
 M QC_Fixed_17_10_2026/Ayush_Sah/cohort-retention-reconciliation/tests/test.sh
 M QC_Fixed_17_10_2026/Ayush_Sah/cohort-uplift-reconciliation/tests/judge.toml
 M QC_Fixed_17_10_2026/Ayush_Sah/cohort-uplift-reconciliation/tests/test.sh
 M QC_Fixed_17_10_2026/Ayush_Sah/dispatch-plan-reoptimization/tests/judge.toml
 M QC_Fixed_17_10_2026/Ayush_Sah/dispatch-plan-reoptimization/tests/test.sh
 M QC_Fixed_17_10_2026/Ayush_Sah/emberforge-vault-settlement/solution/TRUTH.md
 M QC_Fixed_17_10_2026/Ayush_Sah/emberforge-vault-settlement/tests/judge.toml
 M QC_Fixed_17_10_2026/Ayush_Sah/emberforge-vault-settlement/tests/test.sh
 M QC_Fixed_18_10_2026/Ayush_Sah/numeric-reduction-benchmark-forge/tests/judge.toml
 M QC_Fixed_18_10_2026/Ayush_Sah/numeric-reduction-benchmark-forge/tests/test.sh
 M QC_Fixed_18_10_2026/Ayush_Sah/pcggc-multi-state-rec-settlement/solution/TRUTH.md
 M QC_Fixed_18_10_2026/Ayush_Sah/pcggc-multi-state-rec-settlement/tests/judge.toml
 M QC_Fixed_18_10_2026/Ayush_Sah/pcggc-multi-state-rec-settlement/tests/test.sh
 M QC_Fixed_18_10_2026/Ayush_Sah/season-ladder-settlement/tests/judge.toml
 M QC_Fixed_18_10_2026/Ayush_Sah/season-ladder-settlement/tests/test.sh
 M QC_Fixed_18_10_2026/Ayush_Sah/sensor-network-lsq-correlated-adjustment/tests/judge.toml
 M QC_Fixed_18_10_2026/Ayush_Sah/sensor-network-lsq-correlated-adjustment/tests/test.sh
 M QC_Fixed_18_10_2026/Ayush_Sah/sentinel-policy-recompute/tests/judge.toml
 M QC_Fixed_18_10_2026/Ayush_Sah/sentinel-policy-recompute/tests/test.sh
 M QC_Fixed_18_10_2026/Ayush_Sah/specdec-verification-engine/solution/TRUTH.md
 M QC_Fixed_18_10_2026/Ayush_Sah/specdec-verification-engine/tests/judge.toml
 M QC_Fixed_18_10_2026/Ayush_Sah/specdec-verification-engine/tests/test.sh
 M QC_Fixed_19_10_2026/Ayush_Sah/match-replay-desync-audit/tests/judge.toml
 M QC_Fixed_19_10_2026/Ayush_Sah/match-replay-desync-audit/tests/test.sh
```

For Ayush to review and commit himself (not run): `git -C "/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples" diff` then add/commit the 36 paths above.
