# Ad hoc: migrate 4 bundles to the QC push bde868c4 (issued 21 Oct 2026 16:20 IST)
Run this in a NEW session in `/Users/mac/Desktop/Terminal Bench` ONLY after: (1) Ayush has pulled the clone to bde868c4, and (2) the sessions working on these bundles have finished (district-heat and emberforge harden, both P3 hardness runs). Paste everything below the line.

=== PASTE BELOW ===

You are applying one upstream QC change to 4 Harbor bundles. Change only what is listed here; do not touch tests, data, solution code or the instruction.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Ignore its "Always 1" fingerprint stop for this session only: the upstream change is the reason for this session. Instead, confirm `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` starts with `bde868c4`; if not, stop and report.

Bundles (edit in place):
- `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery/`
- `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair/`
- `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement/`
- `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement/`
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_qc-push-bde868c4/MIGRATION_REPORT.md`

Before editing, write the sha256 tree of each bundle to OUT.

## Change 1: tests/judge.toml annotations (QL instruction)
Every `[criterion.annotations]` table must carry EXACTLY these four keys, in this order, and nothing else:
- `mode`: always "judged"
- `type`: one of task completion | instruction following | tool use | agent behavior | factuality and hallucination | safety and boundaries
- `evaluation_target`: one of final_answer | user_facing_message | trajectory | state_change
- `importance`: one of critically_important | important

Delete wherever they appear: kind, category, serves, residue, evidence, contract_sentence, contract_file.
Migration: the old `category` value becomes the new `type` (replacing VALUE, EFFECT, ABSENCE, INVARIANT, ORDERING, DIVERGENCE), then `category` is deleted. If a criterion had no `category`, choose the type that matches what it measures, and list each such choice in the report.
Write "safety and boundaries" with "and", never "&".
Do not touch `[judge]` or `[scoring]`. Each `[[criterion]]` keeps exactly id, name, description, type, weight; the criterion's own `type` stays "binary".
Keep consistent: importance by |weight| (critically_important for 3 or 5, important for 1 or 3); description starts with "The response" for final_answer or user_facing_message and "The agent" for trajectory or state_change. If a description's opening does not fit its evaluation_target, fix the evaluation_target to match what the criterion reads; change description wording only if no target fits, and list it.
A constraint criterion carries type "instruction following" (JD-16); an outcome or conduct criterion never does.

## Change 2: TRUTH.md provenance (resolves OPEN CONFLICT Q18)
The validator now forbids these keys in `solution/TRUTH.md`: authored_by, status, archetype, generator_seed, trailer_token. Remove them, and any sentence describing how the bundle was generated (DS-27: TRUTH describes the task, not how it was made). Keep every other section, mark and sha256 value. TRUTH.md's own content changing does not change other files' digests; if TRUTH lists its own digest, leave that line out or follow what the validator requires.

## Change 3: tests/test.sh
If a bundle's `tests/test.sh` has `chmod 700 /logs/verifier`, change it to `chmod 755 /logs/verifier` (upstream template change). Change nothing else in test.sh.

## Verify, once
For each bundle run, from `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`: judge_qc.py, structure_qc.py, tests_qc.py, instruction_qc.py (all 0 FAIL). For the two generator bundles (vendor-archive with `--archetype format-recovery`, schema-migration with `--archetype repo-patch`) also run validate_bundle.py (gate pass). Use the env vars from common rule 2. No oracle re-run is needed: no test, data or solution file changes.
Then write the sha256 tree after, and list the changed files per bundle (expected: judge.toml, TRUTH.md, maybe test.sh only).

Final reply: per bundle, the counts of criteria migrated and keys deleted, type choices you made, FAIL counts per script, files changed, and the OUT path.
