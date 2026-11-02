# UPSTREAM CHANGED: P8 recheck r1 stopped before work

Written 2026-10-22 09:22 IST (03:52 UTC). Stopped because of _COMMON_RULES.md "Always" rule 1.

## What was compared
- Fingerprints: master_chat_tasks/knowledge/fingerprints/qc.json and pl_generator.json, both `git_head` 9b8229f6f66123a8a8b5f779f7a9b3d5a58c2e9b (generated 2026-10-21 00:43 IST).
- Live clone HEAD: bde868c46994f4916e245b40d14f302b1341244a (the same commit the QC report v1 records as "QC kit commit").

## Commits between fingerprint and live
- bde868c4 QC + generator: drop the chmod 755 rationale comment from test.sh
- 8c37863a QC + generator: use chmod 755 on the verifier log dir, fix retired annotation refs and whole-context COPY detection
- 95401d0e Tasks_INPUT: add cf9b2067-1ba0-5bab-a1ea-83e976851e6c with four-key judge annotations
- f0579497 Input Bundle Generator: multi input dirs, sampled playground ablation, semantic check on reward.json, DS-27 TRUTH provenance, four-key judge annotations
- 4f7f760b QC: allow named input directories under environment/, slim judge annotations to mode/type/evaluation_target/importance

## QC files whose sha256 differs from qc.json (9 of 12)
01_Instruction_QC.md, 02_Data_Solution_QC.md, 03_Tests_QC.md, 04_Judge_QC.md, 05_Alignment_Integrity_QC.md, Final_checklist.md, judge_qc.py, structure_qc.py, tests_qc.py.
Unchanged: Starter.md, exe_copy.py, instruction_qc.py.
`git diff --stat 9b8229f6 bde868c4 -- Input_Bundle_QC`: 9 files, +172 / -134.

## GEN differences from pl_generator.json
- Tracked: 59 files changed between the two commits (+746 / -821), including generate_bundle.py, validate_bundle.py, playground.py, task_memory.py, README.md, CHEAT_VECTORS.md and every template's archetype.toml, TRUTH.md, judge.toml and test.sh; repo-patch and service-interaction templates moved input dirs out of `data/`.
- Untracked (not in the fingerprint, 63 files): `Input Bundle Generator New/ayush sah tasks/` and `Input Bundle Generator New/memory/`.

## Note for the master chat
The QC report under recheck was itself produced at bde868c4, so the report and the live QC agree on version. The stale items are the fingerprint files and the checklist map named for 9b8229f6. No RECHECK.md or recheck.json was written; nothing was read or run against the bundle.

To continue: refresh both fingerprints (and the checklist map) to bde868c4, or confirm explicitly that P8 r1 should run on live bde868c4 as is, and re-issue.
