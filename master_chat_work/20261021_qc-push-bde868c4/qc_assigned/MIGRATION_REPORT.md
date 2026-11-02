# Migration report: QC change bde868c4 on QC assigned/converted tasks

Date: 21 Oct 2026, about 16:30 to 16:45 IST (11:00 to 11:15 UTC). Harness HEAD checked: `bde868c46994f4916e245b40d14f302b1341244a` (starts with bde868c4).
Scope: 14 bundles under `/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/`, edited in place under Ayush's 16:15 IST authorisation.
Not touched: tests/test_output.py, reward.toml, data, solution code, instruction.md, task.toml. Not run: oracle, validate_bundle.py (none of the TRUTH files identify a generator bundle).

## Per bundle

judge_qc column is FAIL count before / after. Other column is structure/tests/instruction FAIL counts, before / after.

| Bundle | Criteria migrated | Keys deleted | New `type` (= old category) | judge_qc FAIL | Other FAIL | Files changed |
|---|---|---|---|---|---|---|
| 07d51b69-db0c-57ed-9208-bcb7a5a3fd47 | 13 | category 13, contract_file 3, contract_sentence 3, evidence 13, kind 13, residue 13, serves 10 | agent behavior 1, factuality and hallucination 1, instruction following 3, task completion 6, tool use 2 | 26 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| 7ef8d80a-fea7-5d9e-b426-bcabfc6802ec | 11 | category 11, contract_file 6, contract_sentence 6, evidence 11, kind 11, residue 11, serves 5 | agent behavior 2, factuality and hallucination 2, instruction following 6, tool use 1 | 22 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| caldermoor-commitment-closure | 28 | category 28, contract_file 4, contract_sentence 4, evidence 28, kind 28, residue 28, serves 5 | agent behavior 3, factuality and hallucination 2, instruction following 4, task completion 19 | 56 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh, TRUTH.md |
| cohort-retention-reconciliation | 18 | category 18, contract_file 1, contract_sentence 1, evidence 18, kind 18, residue 18, serves 16 | agent behavior 14, factuality and hallucination 2, instruction following 1, task completion 1 | 36 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| cohort-uplift-reconciliation | 9 | category 9, contract_file 4, contract_sentence 4, evidence 9, kind 9, residue 9, serves 5 | agent behavior 2, factuality and hallucination 2, instruction following 4, tool use 1 | 18 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| dispatch-plan-reoptimization | 25 | category 25, contract_file 7, contract_sentence 7, evidence 25, kind 25, residue 25, serves 18 | agent behavior 4, factuality and hallucination 2, instruction following 7, task completion 10, tool use 2 | 50 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| emberforge-vault-settlement | 12 | category 12, contract_file 7, contract_sentence 7, evidence 12, kind 12, residue 12, serves 5 | agent behavior 3, factuality and hallucination 1, instruction following 7, task completion 1 | 24 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh, TRUTH.md |
| match-replay-desync-audit | 18 | category 18, contract_file 7, contract_sentence 7, evidence 18, kind 18, residue 18, serves 4 | agent behavior 2, factuality and hallucination 4, instruction following 7, safety and boundaries 1, task completion 4 | 36 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| numeric-reduction-benchmark-forge | 21 | category 21, contract_file 3, contract_sentence 3, evidence 21, kind 21, residue 21, serves 15 | agent behavior 4, factuality and hallucination 5, instruction following 3, task completion 3, tool use 6 | 42 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| pcggc-multi-state-rec-settlement | 11 | category 11, contract_file 6, contract_sentence 6, evidence 11, kind 11, residue 11, serves 5 | agent behavior 4, instruction following 6, safety and boundaries 1 | 22 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh, TRUTH.md |
| season-ladder-settlement | 16 | category 16, contract_file 12, contract_sentence 12, evidence 16, kind 16, residue 16, serves 4 | agent behavior 3, instruction following 12, safety and boundaries 1 | 32 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| sensor-network-lsq-correlated-adjustment | 21 | category 21, contract_file 5, contract_sentence 5, evidence 21, kind 21, residue 21, serves 16 | agent behavior 13, factuality and hallucination 2, instruction following 5, task completion 1 | 42 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| sentinel-policy-recompute | 13 | category 13, contract_file 8, contract_sentence 8, evidence 13, kind 13, residue 13, serves 5 | agent behavior 4, factuality and hallucination 1, instruction following 8 | 26 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh |
| specdec-verification-engine | 12 | category 12, contract_file 5, contract_sentence 5, evidence 12, kind 12, residue 12, serves 6 | agent behavior 4, factuality and hallucination 2, instruction following 5, task completion 1 | 24 / 0 | 0/0/0 / 0/0/0 | judge.toml, test.sh, TRUTH.md |

Total: 228 criteria migrated in 14 files.

## Change 1: judge.toml
- Every annotations table now holds exactly mode, type, evaluation_target, importance, in that order. The old `type` (VALUE, EFFECT, ORDERING, ABSENCE, DIVERGENCE, INVARIANT) was replaced by the old `category` value, and kind, category, serves, residue, evidence, contract_sentence and contract_file were deleted.
- Type choices where there was no category: none. All 228 criteria had a category.
- Checked before editing, and no change was needed: evaluation_target matches the description opening for all 228 criteria (The response for final_answer and user_facing_message, The agent for trajectory and state_change). Importance matches |weight| for all 228. No "&" spelling was present. JD-16: all 78 `kind = constraint` criteria carried "instruction following", and no outcome or conduct criterion did. No description wording or evaluation_target was changed.
- The edit was line-level inside annotations blocks only. A tomllib comparison confirmed that [judge], [scoring], every criterion's id, name, description, type ("binary") and weight, and the new annotations all equal the expected values.

## Change 2: TRUTH.md
- Forbidden keys (validate_bundle.py `TRUTH_FORBIDDEN_KEYS`) found only as `status:` in the Provenance YAML of emberforge, pcggc and specdec. Those lines were removed. No authored_by, archetype, generator_seed or trailer_token appeared anywhere.
- Generation narrative: there were no hits for the validator's `TRUTH_NARRATION_RE` or for phrases like "built by" or "generated by". One borderline sentence was reviewed and kept, because it describes how the grader works and not how the bundle was produced: dispatch-plan-reoptimization TRUTH.md lines 150 to 153 ("produced by running the oracle solver offline at bundle-author time, so the verifier holds no reference implementation"). Flag for Ayush if DS-27 should cover it.
- caldermoor-commitment-closure: the Provenance block lists sha256 values of shipped files. The tests/test.sh and tests/judge.toml lines were updated to the new digests (5302b9b8..., 2a1027d9...) so TRUTH still matches the shipped bytes. Every other digest line is unchanged. No TRUTH lists its own digest.

## Change 3: test.sh
- All 14 had `chmod 700 /logs/verifier`, now `chmod 755 /logs/verifier`. No other line changed.

## Verification (run once before, once after; scripts from Input_Bundle_QC/ with absolute paths)
- judge_qc: before 456 FAIL total (228 J6, 228 J7), after 0 FAIL in all 14 bundles (exit 0).
- structure_qc, tests_qc, instruction_qc: 0 FAIL before and after in all 14. No new FAIL or WARN. The tests_qc H5 warn (chmod 700) is gone in all 14. Pre-existing warns are unchanged: tests_qc A3 (37 to 47 checks above the 35 cap, 5 bundles, approved up to 70) and structure_qc X1 (binary files skipped, 3 bundles).
- Changed files: exactly the 32 listed in after.sha256 vs before.sha256 (14 judge.toml, 14 test.sh, 4 TRUTH.md). A find for files newer than before.sha256 shows nothing else.
- Logs: `/tmp/opencode-logs/qc-assigned-bde868c4-20261021T1630/before/` and `/tmp/opencode-logs/qc-assigned-bde868c4-20261021T1630/after/`.

## For Ayush
- No upstream conflict found. Nothing was committed or pushed.
