# Check your prompts against the latest QC push (bde868c4)

The live QC in `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` changed in the pushes 9b8229f6..bde868c4 (5 commits) and bde868c4..bfe40804 (a merge that reverted part of it; the clone is now at bfe40804). Check whether any prompt you write or keep is now out of date.

1. Read the change yourself, using read-only git only: `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" log --oneline 9b8229f6..bfe40804` and `git diff 9b8229f6..bfe40804 -- Input_Bundle_QC "Input Bundle Generator New"`. The live files are the authority. Never pull, commit or push.
2. These are the changes I know of. Confirm each one against the diff, and add any I missed:
   - judge.toml annotations are now exactly `mode, type, evaluation_target, importance`, in that order. `kind, category, serves, residue, evidence, contract_sentence, contract_file` are retired, and the old `category` value becomes `type`.
   - `importance` must match the weight: critically_important uses |weight| 3 or 5, and important uses 1 or 3.
   - A description starts with "The response" when the target is final_answer or user_facing_message, and with "The agent" when it is trajectory or state_change.
   - TRUTH.md must not contain `authored_by`, `status`, `archetype`, `generator_seed` or `trailer_token`.
   - test.sh: the live rule (a74bda85, commit 2690e960) is `chown root:root` + `chmod 755 /logs/verifier`; H5 warns on 700 (Harbor cannot read reward.json on Linux). tests/Dockerfile must pin `harbor-rewardkit==0.2.1 litellm==1.105.0` (new K8). playground.py and task_memory.py were removed (a72c20a4).
   - `data/` is no longer compulsory, so multiple input dirs are allowed. `--semantic` reads reward.json.
3. Go through every prompt you have and find anything that still uses the old rules: the old judge keys, the old annotation order, provenance keys in TRUTH, `chmod 755`, a required `data/`, or `reward.txt`.

Do not edit anything yet. Reply with a short table: prompt | outdated line or rule | exact change needed. Add a line listing any change from step 2 that turned out to be wrong, and any new change you found. I'll tell you which changes to apply.
