# P4 rebuild r1: vendor-archive-roundtrip-recovery, issued 22 Oct 2026 10:25 IST (from template P4 v1)

This file is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/vendor-archive-roundtrip-recovery/P4_rebuild_r1.md`. After any compaction, re-read it in full.

You are strengthening one Harbor 0.24 bundle that both the hardness audit and a real run showed is far too easy. Edit the bundle in place. Never regenerate it and never use `--force`.

Read in full, in this order:
1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`
2. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md` (binding for this round; it overrides the template steps where they differ)
3. `WORK/DESIGN.md`, `WORK/LEVERS.md`, then the inputs below.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery/` (archetype `format-recovery`)
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/vendor-archive-roundtrip-recovery/`
- HARDNESS REPORT (P3 r1): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_vendor-archive-roundtrip-recovery/hardness_r1/HARDNESS_REPORT.md`
- PL QC v1 (FAIL 26) and its recheck (26 REAL, 1 UNSURE): `.../20261021_vendor-archive-roundtrip-recovery/baseline_v0/qc_report_v1.md`, `.../recheck_r1/RECHECK.md` and `recheck.json`
- Real run (claude-opus-5): `.../baseline_v0/TRAJECTORY_RESULT.md` and `.../baseline_v0/trajectory_job/trajectory/claude-opus-5/Run 1/` (trajectory.json, artifacts). Corrected score: tests 88.97, rubric 100. It lost only basic_delta, va1_cross_delta (both from the raw-frame contract bug), va4_overlong_bytes, report_decoded_examples.
- Docker re-score: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_v0-rescore/RESCORE_REPORT.md`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_vendor-archive-roundtrip-recovery/rebuild_r1/`

## Master's fixes (apply all)
1. Verifier permissions (round notes C): `_decode`, `_salvage`, `_stream`, `_encode` temp files 0644 and folders 0755 (`_encode`'s output folder must be writable by nobody); stage readable copies of `decode.py` and `encode.py` before `setpriv` (test_output.py:805-807). The P8 probe showed the oracle at 0.1241 until both halves are fixed.
2. Validity bugs from P3: make raw frames set the running total in the tests and solve.py exactly as format_contract.md says (a contract-following solver scored 0.9241); build every encode fixture by decoding a real segment and editing one field, so no fixture has `value: null` or a shape the appendix forbids.
3. Every REAL row in `recheck_r1/recheck.json`, with its listed fix (including: report_roundtrip must run encode.py on the agent's examples; the name-prefix check must use the documented prefixes; drop the duplicate determinism negative and the source-grep and rebind negatives; the 4 untriggered rules get fixtures; the unknown-long-key decode rule goes into format_contract.md; TRUTH counts and seed wording; verifier timeout fits task.toml). Leave the UNSURE row (JD-13) as is and list it in the report.
4. Hardness redesign from the round notes B (the real run scored 89 on tests, so isolated per-rule checks are not enough):
   - Instruction: remove the rule counts and the list of trap topics in the final-reply ask (study: vendor instruction lines 3 and 13); ask for computed figures instead. Keep it short and plain.
   - Composition: re-weight so that at most about 30% of positive test weight is on rule-isolating cases, and the rest grades whole decoded or re-encoded documents from hidden multi-segment streams where two or three rules meet (P3 named: interleaved streams needing per-stream state, revision change across segments, remap before alias on aliased streams; move basic cases to revisions 4 to 7).
   - Remove anything that confirms the full answer from the shipped data (worked examples whose outputs equal hidden results); keep evidence that decides each rule.
   - Add at least one rule placed by omission or split across two files, and one decoy default contradicted by the authoritative doc on a boundary the shipped captures show (study rules 4 and 5).
   - Judge: replace R1-R9 (they copy spec facts; the real run met all 12 criteria) with criteria per round notes B.12.
5. `tests/test.sh`: keep `chmod 755 /logs/verifier`; `tests/Dockerfile`: add `litellm==1.105.0` to the rewardkit pip line (K8).

## Steps
1. Write the change plan in `WORK/PLAN.md` under "Rebuild round 1 (22 Oct)": one line per fix, and what wrong reading each new check fails.
2. Apply the changes; update `LEVERS.md`, `DESIGN.md` ("Round 1 changes") and TRUTH.md; follow round notes E on the stale `_work` scripts.
3. Run the gates in round notes D, once each.
4. Write `OUT/REBUILD_REPORT.md`: changes per fix, files touched, new check count and positive-weight share per lever, isolated vs composed weight share, every gate result, and the judge-by-reading check.

Stop after 3 rebuild rounds in total for this bundle (this is round 1).

Final reply (12 lines max): DONE or BLOCKED, fixes applied, new check and judge counts, isolated-weight share, oracle x2 / oracle-0600 / nop / forgery scores, QC and validator results, what was not run, report path. Next step: Ayush runs the PL QC and 1 trajectory.
