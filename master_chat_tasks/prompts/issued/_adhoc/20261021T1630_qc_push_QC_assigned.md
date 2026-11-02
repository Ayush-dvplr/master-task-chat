# Ad hoc: QC push migration, QC assigned/converted tasks (issued 21 Oct 2026 16:30 IST)
Run in a NEW session in `/Users/mac/Desktop/Terminal Bench`. Paste everything below the line.

=== PASTE BELOW ===

You are applying one upstream QC change (Terminal_2.0_Harbor_Harness at bde868c4) to every task bundle in the folders below. Change only what is listed; never touch tests/test_output.py, reward.toml, data, solution code, instruction.md or task.toml.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Two exceptions for this session only:
- Ayush authorised editing these folders on 21 Oct 2026 16:15 IST (this overrides "Never 1" for exactly the folders listed).
- Ignore the "Always 1" fingerprint stop; instead confirm `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` starts with `bde868c4`, else stop.

Folders (each direct subfolder with a task.toml is one bundle; edit in place):
- `/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/`

OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_qc-push-bde868c4/qc_assigned/MIGRATION_REPORT.md` and `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_qc-push-bde868c4/qc_assigned/before.sha256`, `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_qc-push-bde868c4/qc_assigned/after.sha256`.

Before editing, write the sha256 of every file you may change (judge.toml, TRUTH.md, test.sh) for every bundle to before.sha256.

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
For each bundle, from `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`, run judge_qc.py, structure_qc.py, tests_qc.py and instruction_qc.py with ABSOLUTE bundle paths. Target: judge_qc 0 FAIL; the other three must show no NEW FAIL compared with a run before your edits (record both). No oracle re-run: no test, data or solution file changes. Do not run validate_bundle.py (these are not generator bundles unless TRUTH says so).
Write after.sha256 and list changed files per bundle (expected: tests/judge.toml, maybe solution/TRUTH.md and tests/test.sh only).

Final reply: a table per bundle (criteria migrated, keys deleted, type choices made where there was no category, judge_qc FAIL before and after, other FAILs before and after, files changed), then the OUT path.