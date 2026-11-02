# QC terminal prompts, 2026-10-21 (kit bde868c4)

Paste one prompt into one fresh terminal session. Each prompt runs the full QC from the live `Input_Bundle_QC/Starter.md` (commit `bde868c4`) on a copy in `QC_2026-10-21/bundles/<slug>/`, runs Step 10 with the kit's exe_copy.py tests-only copies (oracle ×5, nop, stub), writes `QC_2026-10-21/qc_report/<slug>/vN.md` (v1 first, then v2 on a re-run), and changes nothing in any bundle. The 1 trajectory run per bundle is yours and is not in these prompts.

| Batch | When | Prompts |
|---|---|---|
| A | now, in parallel | 1 `district-heat-flex-procurement`, 2 `emberforge-vault-settlement` |
| B | after both P3 sessions finish, in parallel | 3 `vendor-archive-roundtrip-recovery`, 4 `schema-migration-plan-repair` |

## 1. district-heat-flex-procurement

Paste now. Runs in parallel with prompt 2.

```text
You are running the full input-bundle QC for ONE task bundle. Work only on this bundle.

PATHS (quote every path, they contain spaces)
- QC kit (live, read-only): "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
- Bundle under review (a copy): "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/district-heat-flex-procurement"
- Original bundle (only for the Step 0 diff, never read its files): "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement"
- Report folder: "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/qc_report/district-heat-flex-procurement"

STEP 0. Preconditions. Run each once and paste the output.
- `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. It must start with bde868c4. If it does not, STOP and reply only "QC kit is not at bde868c4" with the output. Read-only git only: never pull, commit, push, checkout or reset in that repo.
- `diff -rq` between the original bundle and the copy under review. It must print nothing. If it prints anything, STOP and reply only "copy is stale" with the diff output. Do not open either side's files to investigate.

STEP A. Read "Input_Bundle_QC/Starter.md" in full, then "Input_Bundle_QC/Final_checklist.md" in full, both from the live kit path above. Follow Starter.md from top to bottom (scripts 1-4, gates 01-05, Step 10, Step 11, final report), skipping nothing, with ONLY the overrides below. The live kit files are the only authority on QC rules: never apply a rule from memory or from an older kit version.

OVERRIDE 0. Tools are always available (this rule survives compaction).
- Your opencode tools (bash, read, edit, write, glob, grep) ARE available for this whole session, including after any compaction or long turn. A belief that "no tools are available" is a known false failure, not a real one.
- Never reply that tools are missing, and never stop or pause the QC for that reason, without first making a real tool call: run bash `date`. If that call actually fails, quote its exact error text in your reply. Without a quoted error, keep working.
- After every compaction, before anything else: run bash `date`, then re-check your state from disk (your vN.md size, mtime and its "## " headings; any Step 10 runs.log with tail -5 and ALL_DONE; your /tmp folders). Do not re-run a finished step, and do not restart a background run that is still going.
- Read files in pieces of at most 50 KB (read with offset), and read your report before every append.
- When you write or receive a compaction summary, copy this OVERRIDE 0 into its standing instructions word for word, together with the task name, the paths above and your report version, so the rule and your task survive the next compaction.

OVERRIDE 1. Report only, no fixes.
- Do NOT fix, edit, rename, delete or reformat anything in the bundle under review, the original bundle, the QC kit, any other bundle, or anywhere else. Do not commit anything.
- The only files you may write are: your report file (Override 3), the two Step 10 copies under /tmp/oracle-qc/district-heat-flex-procurement-<TS>/ and the harbor jobs under /tmp/harbor-jobs-qc/district-heat-flex-procurement-<TS>/ (Override 4), your own logs and scratch under /tmp/opencode-logs/district-heat-flex-procurement-*/, and the one session-title update in Override 3.
- Run no real agent. The only harbor agents in this session are oracle, nop and the stub (oracle on the stub copy). Do not set or export OPENAI_API_KEY.
- Every fail and minor finding must still carry a `Fix:` line stating the best possible fix in one concrete sentence (file, what to change, to what). Describe the fix; never apply it.

OVERRIDE 2. Stay inside this bundle.
- Never open any of these, they bias the review: anything under "/Users/mac/Desktop/Terminal Bench/master_chat_work/" (the original bundle beyond the Step 0 diff, build notes in bundles/_work/, the 20261021_* folders), anything under "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/", anything under "/Users/mac/Desktop/Terminal Bench/QC assigned/" (old kit copy, old bundles and old reports), "Input Bundle Generator New/ayush sah tasks/", other bundles in "QC_2026-10-21/bundles/", other task folders in "QC_2026-10-21/qc_report/", "QC_2026-10-21/QC_2026-10-21.md" and "QC_2026-10-21/QC_Terminal_Prompts.md".
- Never use "QC assigned/Input_Bundle_QC" or "Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC": they are stale copies (old judge annotation keys, data/-only input, chmod 700) and give wrong verdicts.
- Do not open earlier report versions in your own report folder until your new report is fully written (see Override 3).
- Do every gate yourself in this session, one at a time, as Starter.md says. Do not hand gates to subagents.
- In gate 02, open solution/TRUTH.md last, as Starter.md requires.

OVERRIDE 3. Report file and versioning.
- Create the report folder if it does not exist. List it. Count only files named exactly vN.md (v1.md, v2.md, ...); ignore every other file. If there is no vN.md, your file is v1.md. Otherwise find the highest N and write v(N+1).md. Never overwrite an existing version.
- Rename this session as soon as you know N: title it `district-heat-flex-procurement_vN_qc` (for example `district-heat-flex-procurement_v1_qc`). opencode has no rename command, so run this one bash command with your N filled in:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '{\"type\":\"text\"%You are running the full input-bundle QC%QC_2026-10-21/qc_report/district-heat-flex-procurement%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='district-heat-flex-procurement_vN_qc' WHERE id='$SID'"; opencode session list | head -5
  Check that the list shows `district-heat-flex-procurement_vN_qc` on the newest session. If it does not, note it in the report header and carry on; never retry the update on another session ID. The terminal header may show the old title until the session is reopened.
- First line block of the file: bundle name, bundle path, report version, date and time in IST (UTC+5:30), QC kit commit (from Step 0), harbor version.
- Write as you go so nothing is lost if the session runs long: after each script run and after each gate, append that step's full section (its checklist copied verbatim, every item marked, with quoted evidence) to the report file before starting the next step.
- When everything is done, put the consolidated report from Starter.md "Final report" at the TOP of the file: verdict line, per-gate summary table, Findings (with Fix: lines), consolidated sign-off checklist. The per-step sections stay below it as the evidence appendix.
- Only after the report is complete, if an earlier version exists, read it and append a short "Compared with v(N-1)" section at the end: findings fixed, findings still open, new findings, by check ID.

OVERRIDE 4. Step 10 follows the kit's exe_copy.py flow exactly (Starter.md Step 10 and Final_checklist.md Step 10), with only the additions below.
The scores are TESTS-ONLY, as the kit says: exe_copy.py validates tests/judge.toml against the rewardkit 0.2.1 schema and never executes it. Use Harbor 0.24.0 and harbor-rewardkit 0.2.1.
1. Preflight as the kit says: `harbor --version`, `docker ps`, and list the bundle path. Paste the output.
2. Run `date +%Y%m%dT%H%M` once and call the result TS. Write its literal value into every path below (shell variables may not survive between tool calls). exe_copy.py refuses a destination that already exists, so never reuse an older folder.
   RUN copy:  "/tmp/oracle-qc/district-heat-flex-procurement-<TS>/run/district-heat-flex-procurement"
   STUB copy: "/tmp/oracle-qc/district-heat-flex-procurement-<TS>/stub/district-heat-flex-procurement"
   Jobs:      "/tmp/harbor-jobs-qc/district-heat-flex-procurement-<TS>"
   Logs:      "/tmp/opencode-logs/district-heat-flex-procurement-step10-<TS>"
3. Build both copies with the kit script, running Python from /tmp with PYTHONDONTWRITEBYTECODE=1 so no __pycache__ lands in the bundle or the kit:
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/district-heat-flex-procurement" "/tmp/oracle-qc/district-heat-flex-procurement-<TS>/run/district-heat-flex-procurement"
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/district-heat-flex-procurement" "/tmp/oracle-qc/district-heat-flex-procurement-<TS>/stub/district-heat-flex-procurement" --stub
   Paste both outputs in full, with their exit codes. P is the positive total exe_copy.py prints in its reward.toml line.
   If either exits 1 (REFUSED), do NOT build a copy by hand and do NOT work around it: record each REFUSED line as a ❌ finding with a Fix: line, mark Step 10 ⏸️ NOT RUN (refused by exe_copy.py, quoting its output), and continue with Step 11. Exit 2 is a usage error in your command: fix the command and run it again.
4. Confirm the flags with `harbor run --help`, then run the kit's seven commands in this order, each with -o "/tmp/harbor-jobs-qc/district-heat-flex-procurement-<TS>": oracle-1 to oracle-5 (--agent oracle on the RUN copy), nop-1 (--agent nop on the RUN copy), stub-1 (--agent oracle on the STUB copy). For example:
   harbor run --path "/tmp/oracle-qc/district-heat-flex-procurement-<TS>/run/district-heat-flex-procurement" --agent oracle --env docker --job-name oracle-1 -o "/tmp/harbor-jobs-qc/district-heat-flex-procurement-<TS>" -y
   Never run them in the foreground. `mkdir -p` the logs folder, then chain all seven inside one `nohup bash -c '...; echo ALL_DONE' > "/tmp/opencode-logs/district-heat-flex-procurement-step10-<TS>/runs.log" 2>&1 &`. Poll with waits under 4 minutes (for example `sleep 200; tail -5 <log>`) until ALL_DONE appears. Other sessions' harbor runs may share Docker: never touch their processes or folders.
5. For each run, read the reward from the trial directory's result.json `verifier_result.rewards.reward` and verifier/reward.json. A run with `exception_info` or an exception.txt errored and has no score. Never read the score from console output.
6. Expected, as the kit requires: all five oracle runs exactly 1.000 (report each number), nop exactly 0.000.
   - Oracle below 1.0: solve.sh fails a check, or a check has a bug. Name the failing checks from verifier/reward-details.json.
   - Nop not 0.0: a positive check passes on an empty run, or a negative check fires on one. Name the check.
   - No reward.json: rewardkit crashed, usually because a check raised an exception. Quote the error from verifier/test-stdout.txt.
   - Different scores across the five oracle runs: the checks are non-deterministic. Find the cause (gate 03 TS-11), do not re-run until they agree.
7. Run `diff -rq` between the bundle under review and each copy and paste both outputs. Allowed differences: tests/judge.toml (only in the bundle under review), tests/reward.toml, task.toml, environment/Dockerfile, and, for the STUB copy only, the contents of solution/. Anything else is a ❌ finding.
8. Stub judgement (Final_checklist.md "The stub run"):
   a. Paste the STUB copy's solution/solve.sh in full.
   b. From stub-1's verifier/reward-details.json, list every check whose value is not 0, with its weight.
   c. If stub-1 errored instead of scoring (for example a declared artifact the kit stub writes in a form the checks cannot even open), edit only the STUB copy's solution/solve.sh to create what the instruction names there (empty files, {} for JSON), nothing more, and run it again as stub-2. Report every attempt and the change.
   d. Judge the score: near zero or negative is healthy; a substantial share means tests pay for filenames rather than content. Report it as a share of P, the checks that paid and why, and your judgement with reasons, and compare it with the CL-2 forgery price you computed in gate 05. A stub score near the range a genuine partial attempt would earn, or any check that paid while it claims to grade content, is a ❌ finding with a Fix: line.
9. Cleanup: delete only "/tmp/oracle-qc/district-heat-flex-procurement-<TS>" (never the /tmp/oracle-qc parent or any sibling folder). Keep the jobs and logs folders as evidence. Confirm the bundle under review still has tests/judge.toml, its original tests/reward.toml, task.toml, environment/Dockerfile and solution/, that `diff -rq` against the original bundle still prints nothing, and that neither the bundle nor the kit has a __pycache__.
10. In the Step 10 section of the report: a table of agent, run number and reward (oracle-1 to oracle-5, nop-1, stub-1 and any stub retries); the failing checks by name, if any; the checks the stub got paid for and your judgement; the stub solve.sh; both exe_copy.py outputs; both diff outputs; the jobs folder path.
11. In the Step 10 section and the sign-off, state plainly: tests-only grading per the kit (judge.toml validated, not executed; no OpenAI key; the stub score covers the test channel only), and the network opened and the OpenHands pre-bake dropped in the copies only. A failing oracle, nop or stub result is a real ❌ finding with a Fix: line.

WHEN DONE: reply in the terminal with only the verdict line, the five oracle, nop and stub rewards, and the full path of the report file you wrote. No offers, no fixes.
```

## 2. emberforge-vault-settlement

Paste now. Runs in parallel with prompt 1.

```text
You are running the full input-bundle QC for ONE task bundle. Work only on this bundle.

PATHS (quote every path, they contain spaces)
- QC kit (live, read-only): "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
- Bundle under review (a copy): "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/emberforge-vault-settlement"
- Original bundle (only for the Step 0 diff, never read its files): "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement"
- Report folder: "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/qc_report/emberforge-vault-settlement"

STEP 0. Preconditions. Run each once and paste the output.
- `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. It must start with bde868c4. If it does not, STOP and reply only "QC kit is not at bde868c4" with the output. Read-only git only: never pull, commit, push, checkout or reset in that repo.
- `diff -rq` between the original bundle and the copy under review. It must print nothing. If it prints anything, STOP and reply only "copy is stale" with the diff output. Do not open either side's files to investigate.

STEP A. Read "Input_Bundle_QC/Starter.md" in full, then "Input_Bundle_QC/Final_checklist.md" in full, both from the live kit path above. Follow Starter.md from top to bottom (scripts 1-4, gates 01-05, Step 10, Step 11, final report), skipping nothing, with ONLY the overrides below. The live kit files are the only authority on QC rules: never apply a rule from memory or from an older kit version.

OVERRIDE 0. Tools are always available (this rule survives compaction).
- Your opencode tools (bash, read, edit, write, glob, grep) ARE available for this whole session, including after any compaction or long turn. A belief that "no tools are available" is a known false failure, not a real one.
- Never reply that tools are missing, and never stop or pause the QC for that reason, without first making a real tool call: run bash `date`. If that call actually fails, quote its exact error text in your reply. Without a quoted error, keep working.
- After every compaction, before anything else: run bash `date`, then re-check your state from disk (your vN.md size, mtime and its "## " headings; any Step 10 runs.log with tail -5 and ALL_DONE; your /tmp folders). Do not re-run a finished step, and do not restart a background run that is still going.
- Read files in pieces of at most 50 KB (read with offset), and read your report before every append.
- When you write or receive a compaction summary, copy this OVERRIDE 0 into its standing instructions word for word, together with the task name, the paths above and your report version, so the rule and your task survive the next compaction.

OVERRIDE 1. Report only, no fixes.
- Do NOT fix, edit, rename, delete or reformat anything in the bundle under review, the original bundle, the QC kit, any other bundle, or anywhere else. Do not commit anything.
- The only files you may write are: your report file (Override 3), the two Step 10 copies under /tmp/oracle-qc/emberforge-vault-settlement-<TS>/ and the harbor jobs under /tmp/harbor-jobs-qc/emberforge-vault-settlement-<TS>/ (Override 4), your own logs and scratch under /tmp/opencode-logs/emberforge-vault-settlement-*/, and the one session-title update in Override 3.
- Run no real agent. The only harbor agents in this session are oracle, nop and the stub (oracle on the stub copy). Do not set or export OPENAI_API_KEY.
- Every fail and minor finding must still carry a `Fix:` line stating the best possible fix in one concrete sentence (file, what to change, to what). Describe the fix; never apply it.

OVERRIDE 2. Stay inside this bundle.
- Never open any of these, they bias the review: anything under "/Users/mac/Desktop/Terminal Bench/master_chat_work/" (the original bundle beyond the Step 0 diff, build notes in bundles/_work/, the 20261021_* folders), anything under "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/", anything under "/Users/mac/Desktop/Terminal Bench/QC assigned/" (old kit copy, old bundles and old reports), "Input Bundle Generator New/ayush sah tasks/", other bundles in "QC_2026-10-21/bundles/", other task folders in "QC_2026-10-21/qc_report/", "QC_2026-10-21/QC_2026-10-21.md" and "QC_2026-10-21/QC_Terminal_Prompts.md".
- Never use "QC assigned/Input_Bundle_QC" or "Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC": they are stale copies (old judge annotation keys, data/-only input, chmod 700) and give wrong verdicts.
- Do not open earlier report versions in your own report folder until your new report is fully written (see Override 3).
- Do every gate yourself in this session, one at a time, as Starter.md says. Do not hand gates to subagents.
- In gate 02, open solution/TRUTH.md last, as Starter.md requires.

OVERRIDE 3. Report file and versioning.
- Create the report folder if it does not exist. List it. Count only files named exactly vN.md (v1.md, v2.md, ...); ignore every other file. If there is no vN.md, your file is v1.md. Otherwise find the highest N and write v(N+1).md. Never overwrite an existing version.
- Rename this session as soon as you know N: title it `emberforge-vault-settlement_vN_qc` (for example `emberforge-vault-settlement_v1_qc`). opencode has no rename command, so run this one bash command with your N filled in:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '{\"type\":\"text\"%You are running the full input-bundle QC%QC_2026-10-21/qc_report/emberforge-vault-settlement%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='emberforge-vault-settlement_vN_qc' WHERE id='$SID'"; opencode session list | head -5
  Check that the list shows `emberforge-vault-settlement_vN_qc` on the newest session. If it does not, note it in the report header and carry on; never retry the update on another session ID. The terminal header may show the old title until the session is reopened.
- First line block of the file: bundle name, bundle path, report version, date and time in IST (UTC+5:30), QC kit commit (from Step 0), harbor version.
- Write as you go so nothing is lost if the session runs long: after each script run and after each gate, append that step's full section (its checklist copied verbatim, every item marked, with quoted evidence) to the report file before starting the next step.
- When everything is done, put the consolidated report from Starter.md "Final report" at the TOP of the file: verdict line, per-gate summary table, Findings (with Fix: lines), consolidated sign-off checklist. The per-step sections stay below it as the evidence appendix.
- Only after the report is complete, if an earlier version exists, read it and append a short "Compared with v(N-1)" section at the end: findings fixed, findings still open, new findings, by check ID.

OVERRIDE 4. Step 10 follows the kit's exe_copy.py flow exactly (Starter.md Step 10 and Final_checklist.md Step 10), with only the additions below.
The scores are TESTS-ONLY, as the kit says: exe_copy.py validates tests/judge.toml against the rewardkit 0.2.1 schema and never executes it. Use Harbor 0.24.0 and harbor-rewardkit 0.2.1.
1. Preflight as the kit says: `harbor --version`, `docker ps`, and list the bundle path. Paste the output.
2. Run `date +%Y%m%dT%H%M` once and call the result TS. Write its literal value into every path below (shell variables may not survive between tool calls). exe_copy.py refuses a destination that already exists, so never reuse an older folder.
   RUN copy:  "/tmp/oracle-qc/emberforge-vault-settlement-<TS>/run/emberforge-vault-settlement"
   STUB copy: "/tmp/oracle-qc/emberforge-vault-settlement-<TS>/stub/emberforge-vault-settlement"
   Jobs:      "/tmp/harbor-jobs-qc/emberforge-vault-settlement-<TS>"
   Logs:      "/tmp/opencode-logs/emberforge-vault-settlement-step10-<TS>"
3. Build both copies with the kit script, running Python from /tmp with PYTHONDONTWRITEBYTECODE=1 so no __pycache__ lands in the bundle or the kit:
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/emberforge-vault-settlement" "/tmp/oracle-qc/emberforge-vault-settlement-<TS>/run/emberforge-vault-settlement"
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/emberforge-vault-settlement" "/tmp/oracle-qc/emberforge-vault-settlement-<TS>/stub/emberforge-vault-settlement" --stub
   Paste both outputs in full, with their exit codes. P is the positive total exe_copy.py prints in its reward.toml line.
   If either exits 1 (REFUSED), do NOT build a copy by hand and do NOT work around it: record each REFUSED line as a ❌ finding with a Fix: line, mark Step 10 ⏸️ NOT RUN (refused by exe_copy.py, quoting its output), and continue with Step 11. Exit 2 is a usage error in your command: fix the command and run it again.
4. Confirm the flags with `harbor run --help`, then run the kit's seven commands in this order, each with -o "/tmp/harbor-jobs-qc/emberforge-vault-settlement-<TS>": oracle-1 to oracle-5 (--agent oracle on the RUN copy), nop-1 (--agent nop on the RUN copy), stub-1 (--agent oracle on the STUB copy). For example:
   harbor run --path "/tmp/oracle-qc/emberforge-vault-settlement-<TS>/run/emberforge-vault-settlement" --agent oracle --env docker --job-name oracle-1 -o "/tmp/harbor-jobs-qc/emberforge-vault-settlement-<TS>" -y
   Never run them in the foreground. `mkdir -p` the logs folder, then chain all seven inside one `nohup bash -c '...; echo ALL_DONE' > "/tmp/opencode-logs/emberforge-vault-settlement-step10-<TS>/runs.log" 2>&1 &`. Poll with waits under 4 minutes (for example `sleep 200; tail -5 <log>`) until ALL_DONE appears. Other sessions' harbor runs may share Docker: never touch their processes or folders.
5. For each run, read the reward from the trial directory's result.json `verifier_result.rewards.reward` and verifier/reward.json. A run with `exception_info` or an exception.txt errored and has no score. Never read the score from console output.
6. Expected, as the kit requires: all five oracle runs exactly 1.000 (report each number), nop exactly 0.000.
   - Oracle below 1.0: solve.sh fails a check, or a check has a bug. Name the failing checks from verifier/reward-details.json.
   - Nop not 0.0: a positive check passes on an empty run, or a negative check fires on one. Name the check.
   - No reward.json: rewardkit crashed, usually because a check raised an exception. Quote the error from verifier/test-stdout.txt.
   - Different scores across the five oracle runs: the checks are non-deterministic. Find the cause (gate 03 TS-11), do not re-run until they agree.
7. Run `diff -rq` between the bundle under review and each copy and paste both outputs. Allowed differences: tests/judge.toml (only in the bundle under review), tests/reward.toml, task.toml, environment/Dockerfile, and, for the STUB copy only, the contents of solution/. Anything else is a ❌ finding.
8. Stub judgement (Final_checklist.md "The stub run"):
   a. Paste the STUB copy's solution/solve.sh in full.
   b. From stub-1's verifier/reward-details.json, list every check whose value is not 0, with its weight.
   c. If stub-1 errored instead of scoring (for example a declared artifact the kit stub writes in a form the checks cannot even open), edit only the STUB copy's solution/solve.sh to create what the instruction names there (empty files, {} for JSON), nothing more, and run it again as stub-2. Report every attempt and the change.
   d. Judge the score: near zero or negative is healthy; a substantial share means tests pay for filenames rather than content. Report it as a share of P, the checks that paid and why, and your judgement with reasons, and compare it with the CL-2 forgery price you computed in gate 05. A stub score near the range a genuine partial attempt would earn, or any check that paid while it claims to grade content, is a ❌ finding with a Fix: line.
9. Cleanup: delete only "/tmp/oracle-qc/emberforge-vault-settlement-<TS>" (never the /tmp/oracle-qc parent or any sibling folder). Keep the jobs and logs folders as evidence. Confirm the bundle under review still has tests/judge.toml, its original tests/reward.toml, task.toml, environment/Dockerfile and solution/, that `diff -rq` against the original bundle still prints nothing, and that neither the bundle nor the kit has a __pycache__.
10. In the Step 10 section of the report: a table of agent, run number and reward (oracle-1 to oracle-5, nop-1, stub-1 and any stub retries); the failing checks by name, if any; the checks the stub got paid for and your judgement; the stub solve.sh; both exe_copy.py outputs; both diff outputs; the jobs folder path.
11. In the Step 10 section and the sign-off, state plainly: tests-only grading per the kit (judge.toml validated, not executed; no OpenAI key; the stub score covers the test channel only), and the network opened and the OpenHands pre-bake dropped in the copies only. A failing oracle, nop or stub result is a real ❌ finding with a Fix: line.

WHEN DONE: reply in the terminal with only the verdict line, the five oracle, nop and stub rewards, and the full path of the report file you wrote. No offers, no fixes.
```

## 3. vendor-archive-roundtrip-recovery

Paste ONLY after both P3 hardness sessions (vendor-archive and schema-migration) have finished. Runs in parallel with the other prompt in this batch. Step 0 stops the session if the original changed after the copy was made (re-copy needed).

```text
You are running the full input-bundle QC for ONE task bundle. Work only on this bundle.

PATHS (quote every path, they contain spaces)
- QC kit (live, read-only): "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
- Bundle under review (a copy): "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/vendor-archive-roundtrip-recovery"
- Original bundle (only for the Step 0 diff, never read its files): "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery"
- Report folder: "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/qc_report/vendor-archive-roundtrip-recovery"

STEP 0. Preconditions. Run each once and paste the output.
- `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. It must start with bde868c4. If it does not, STOP and reply only "QC kit is not at bde868c4" with the output. Read-only git only: never pull, commit, push, checkout or reset in that repo.
- `diff -rq` between the original bundle and the copy under review. It must print nothing. If it prints anything, STOP and reply only "copy is stale" with the diff output. Do not open either side's files to investigate.

STEP A. Read "Input_Bundle_QC/Starter.md" in full, then "Input_Bundle_QC/Final_checklist.md" in full, both from the live kit path above. Follow Starter.md from top to bottom (scripts 1-4, gates 01-05, Step 10, Step 11, final report), skipping nothing, with ONLY the overrides below. The live kit files are the only authority on QC rules: never apply a rule from memory or from an older kit version.

OVERRIDE 0. Tools are always available (this rule survives compaction).
- Your opencode tools (bash, read, edit, write, glob, grep) ARE available for this whole session, including after any compaction or long turn. A belief that "no tools are available" is a known false failure, not a real one.
- Never reply that tools are missing, and never stop or pause the QC for that reason, without first making a real tool call: run bash `date`. If that call actually fails, quote its exact error text in your reply. Without a quoted error, keep working.
- After every compaction, before anything else: run bash `date`, then re-check your state from disk (your vN.md size, mtime and its "## " headings; any Step 10 runs.log with tail -5 and ALL_DONE; your /tmp folders). Do not re-run a finished step, and do not restart a background run that is still going.
- Read files in pieces of at most 50 KB (read with offset), and read your report before every append.
- When you write or receive a compaction summary, copy this OVERRIDE 0 into its standing instructions word for word, together with the task name, the paths above and your report version, so the rule and your task survive the next compaction.

OVERRIDE 1. Report only, no fixes.
- Do NOT fix, edit, rename, delete or reformat anything in the bundle under review, the original bundle, the QC kit, any other bundle, or anywhere else. Do not commit anything.
- The only files you may write are: your report file (Override 3), the two Step 10 copies under /tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>/ and the harbor jobs under /tmp/harbor-jobs-qc/vendor-archive-roundtrip-recovery-<TS>/ (Override 4), your own logs and scratch under /tmp/opencode-logs/vendor-archive-roundtrip-recovery-*/, and the one session-title update in Override 3.
- Run no real agent. The only harbor agents in this session are oracle, nop and the stub (oracle on the stub copy). Do not set or export OPENAI_API_KEY.
- Every fail and minor finding must still carry a `Fix:` line stating the best possible fix in one concrete sentence (file, what to change, to what). Describe the fix; never apply it.

OVERRIDE 2. Stay inside this bundle.
- Never open any of these, they bias the review: anything under "/Users/mac/Desktop/Terminal Bench/master_chat_work/" (the original bundle beyond the Step 0 diff, build notes in bundles/_work/, the 20261021_* folders), anything under "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/", anything under "/Users/mac/Desktop/Terminal Bench/QC assigned/" (old kit copy, old bundles and old reports), "Input Bundle Generator New/ayush sah tasks/", other bundles in "QC_2026-10-21/bundles/", other task folders in "QC_2026-10-21/qc_report/", "QC_2026-10-21/QC_2026-10-21.md" and "QC_2026-10-21/QC_Terminal_Prompts.md".
- Never use "QC assigned/Input_Bundle_QC" or "Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC": they are stale copies (old judge annotation keys, data/-only input, chmod 700) and give wrong verdicts.
- Do not open earlier report versions in your own report folder until your new report is fully written (see Override 3).
- Do every gate yourself in this session, one at a time, as Starter.md says. Do not hand gates to subagents.
- In gate 02, open solution/TRUTH.md last, as Starter.md requires.

OVERRIDE 3. Report file and versioning.
- Create the report folder if it does not exist. List it. Count only files named exactly vN.md (v1.md, v2.md, ...); ignore every other file. If there is no vN.md, your file is v1.md. Otherwise find the highest N and write v(N+1).md. Never overwrite an existing version.
- Rename this session as soon as you know N: title it `vendor-archive-roundtrip-recovery_vN_qc` (for example `vendor-archive-roundtrip-recovery_v1_qc`). opencode has no rename command, so run this one bash command with your N filled in:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '{\"type\":\"text\"%You are running the full input-bundle QC%QC_2026-10-21/qc_report/vendor-archive-roundtrip-recovery%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='vendor-archive-roundtrip-recovery_vN_qc' WHERE id='$SID'"; opencode session list | head -5
  Check that the list shows `vendor-archive-roundtrip-recovery_vN_qc` on the newest session. If it does not, note it in the report header and carry on; never retry the update on another session ID. The terminal header may show the old title until the session is reopened.
- First line block of the file: bundle name, bundle path, report version, date and time in IST (UTC+5:30), QC kit commit (from Step 0), harbor version.
- Write as you go so nothing is lost if the session runs long: after each script run and after each gate, append that step's full section (its checklist copied verbatim, every item marked, with quoted evidence) to the report file before starting the next step.
- When everything is done, put the consolidated report from Starter.md "Final report" at the TOP of the file: verdict line, per-gate summary table, Findings (with Fix: lines), consolidated sign-off checklist. The per-step sections stay below it as the evidence appendix.
- Only after the report is complete, if an earlier version exists, read it and append a short "Compared with v(N-1)" section at the end: findings fixed, findings still open, new findings, by check ID.

OVERRIDE 4. Step 10 follows the kit's exe_copy.py flow exactly (Starter.md Step 10 and Final_checklist.md Step 10), with only the additions below.
The scores are TESTS-ONLY, as the kit says: exe_copy.py validates tests/judge.toml against the rewardkit 0.2.1 schema and never executes it. Use Harbor 0.24.0 and harbor-rewardkit 0.2.1.
1. Preflight as the kit says: `harbor --version`, `docker ps`, and list the bundle path. Paste the output.
2. Run `date +%Y%m%dT%H%M` once and call the result TS. Write its literal value into every path below (shell variables may not survive between tool calls). exe_copy.py refuses a destination that already exists, so never reuse an older folder.
   RUN copy:  "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>/run/vendor-archive-roundtrip-recovery"
   STUB copy: "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>/stub/vendor-archive-roundtrip-recovery"
   Jobs:      "/tmp/harbor-jobs-qc/vendor-archive-roundtrip-recovery-<TS>"
   Logs:      "/tmp/opencode-logs/vendor-archive-roundtrip-recovery-step10-<TS>"
3. Build both copies with the kit script, running Python from /tmp with PYTHONDONTWRITEBYTECODE=1 so no __pycache__ lands in the bundle or the kit:
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/vendor-archive-roundtrip-recovery" "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>/run/vendor-archive-roundtrip-recovery"
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/vendor-archive-roundtrip-recovery" "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>/stub/vendor-archive-roundtrip-recovery" --stub
   Paste both outputs in full, with their exit codes. P is the positive total exe_copy.py prints in its reward.toml line.
   If either exits 1 (REFUSED), do NOT build a copy by hand and do NOT work around it: record each REFUSED line as a ❌ finding with a Fix: line, mark Step 10 ⏸️ NOT RUN (refused by exe_copy.py, quoting its output), and continue with Step 11. Exit 2 is a usage error in your command: fix the command and run it again.
4. Confirm the flags with `harbor run --help`, then run the kit's seven commands in this order, each with -o "/tmp/harbor-jobs-qc/vendor-archive-roundtrip-recovery-<TS>": oracle-1 to oracle-5 (--agent oracle on the RUN copy), nop-1 (--agent nop on the RUN copy), stub-1 (--agent oracle on the STUB copy). For example:
   harbor run --path "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>/run/vendor-archive-roundtrip-recovery" --agent oracle --env docker --job-name oracle-1 -o "/tmp/harbor-jobs-qc/vendor-archive-roundtrip-recovery-<TS>" -y
   Never run them in the foreground. `mkdir -p` the logs folder, then chain all seven inside one `nohup bash -c '...; echo ALL_DONE' > "/tmp/opencode-logs/vendor-archive-roundtrip-recovery-step10-<TS>/runs.log" 2>&1 &`. Poll with waits under 4 minutes (for example `sleep 200; tail -5 <log>`) until ALL_DONE appears. Other sessions' harbor runs may share Docker: never touch their processes or folders.
5. For each run, read the reward from the trial directory's result.json `verifier_result.rewards.reward` and verifier/reward.json. A run with `exception_info` or an exception.txt errored and has no score. Never read the score from console output.
6. Expected, as the kit requires: all five oracle runs exactly 1.000 (report each number), nop exactly 0.000.
   - Oracle below 1.0: solve.sh fails a check, or a check has a bug. Name the failing checks from verifier/reward-details.json.
   - Nop not 0.0: a positive check passes on an empty run, or a negative check fires on one. Name the check.
   - No reward.json: rewardkit crashed, usually because a check raised an exception. Quote the error from verifier/test-stdout.txt.
   - Different scores across the five oracle runs: the checks are non-deterministic. Find the cause (gate 03 TS-11), do not re-run until they agree.
7. Run `diff -rq` between the bundle under review and each copy and paste both outputs. Allowed differences: tests/judge.toml (only in the bundle under review), tests/reward.toml, task.toml, environment/Dockerfile, and, for the STUB copy only, the contents of solution/. Anything else is a ❌ finding.
8. Stub judgement (Final_checklist.md "The stub run"):
   a. Paste the STUB copy's solution/solve.sh in full.
   b. From stub-1's verifier/reward-details.json, list every check whose value is not 0, with its weight.
   c. If stub-1 errored instead of scoring (for example a declared artifact the kit stub writes in a form the checks cannot even open), edit only the STUB copy's solution/solve.sh to create what the instruction names there (empty files, {} for JSON), nothing more, and run it again as stub-2. Report every attempt and the change.
   d. Judge the score: near zero or negative is healthy; a substantial share means tests pay for filenames rather than content. Report it as a share of P, the checks that paid and why, and your judgement with reasons, and compare it with the CL-2 forgery price you computed in gate 05. A stub score near the range a genuine partial attempt would earn, or any check that paid while it claims to grade content, is a ❌ finding with a Fix: line.
9. Cleanup: delete only "/tmp/oracle-qc/vendor-archive-roundtrip-recovery-<TS>" (never the /tmp/oracle-qc parent or any sibling folder). Keep the jobs and logs folders as evidence. Confirm the bundle under review still has tests/judge.toml, its original tests/reward.toml, task.toml, environment/Dockerfile and solution/, that `diff -rq` against the original bundle still prints nothing, and that neither the bundle nor the kit has a __pycache__.
10. In the Step 10 section of the report: a table of agent, run number and reward (oracle-1 to oracle-5, nop-1, stub-1 and any stub retries); the failing checks by name, if any; the checks the stub got paid for and your judgement; the stub solve.sh; both exe_copy.py outputs; both diff outputs; the jobs folder path.
11. In the Step 10 section and the sign-off, state plainly: tests-only grading per the kit (judge.toml validated, not executed; no OpenAI key; the stub score covers the test channel only), and the network opened and the OpenHands pre-bake dropped in the copies only. A failing oracle, nop or stub result is a real ❌ finding with a Fix: line.

WHEN DONE: reply in the terminal with only the verdict line, the five oracle, nop and stub rewards, and the full path of the report file you wrote. No offers, no fixes.
```

## 4. schema-migration-plan-repair

Paste ONLY after both P3 hardness sessions (vendor-archive and schema-migration) have finished. Runs in parallel with the other prompt in this batch. Step 0 stops the session if the original changed after the copy was made (re-copy needed).

```text
You are running the full input-bundle QC for ONE task bundle. Work only on this bundle.

PATHS (quote every path, they contain spaces)
- QC kit (live, read-only): "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
- Bundle under review (a copy): "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/schema-migration-plan-repair"
- Original bundle (only for the Step 0 diff, never read its files): "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair"
- Report folder: "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/qc_report/schema-migration-plan-repair"

STEP 0. Preconditions. Run each once and paste the output.
- `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD`. It must start with bde868c4. If it does not, STOP and reply only "QC kit is not at bde868c4" with the output. Read-only git only: never pull, commit, push, checkout or reset in that repo.
- `diff -rq` between the original bundle and the copy under review. It must print nothing. If it prints anything, STOP and reply only "copy is stale" with the diff output. Do not open either side's files to investigate.

STEP A. Read "Input_Bundle_QC/Starter.md" in full, then "Input_Bundle_QC/Final_checklist.md" in full, both from the live kit path above. Follow Starter.md from top to bottom (scripts 1-4, gates 01-05, Step 10, Step 11, final report), skipping nothing, with ONLY the overrides below. The live kit files are the only authority on QC rules: never apply a rule from memory or from an older kit version.

OVERRIDE 0. Tools are always available (this rule survives compaction).
- Your opencode tools (bash, read, edit, write, glob, grep) ARE available for this whole session, including after any compaction or long turn. A belief that "no tools are available" is a known false failure, not a real one.
- Never reply that tools are missing, and never stop or pause the QC for that reason, without first making a real tool call: run bash `date`. If that call actually fails, quote its exact error text in your reply. Without a quoted error, keep working.
- After every compaction, before anything else: run bash `date`, then re-check your state from disk (your vN.md size, mtime and its "## " headings; any Step 10 runs.log with tail -5 and ALL_DONE; your /tmp folders). Do not re-run a finished step, and do not restart a background run that is still going.
- Read files in pieces of at most 50 KB (read with offset), and read your report before every append.
- When you write or receive a compaction summary, copy this OVERRIDE 0 into its standing instructions word for word, together with the task name, the paths above and your report version, so the rule and your task survive the next compaction.

OVERRIDE 1. Report only, no fixes.
- Do NOT fix, edit, rename, delete or reformat anything in the bundle under review, the original bundle, the QC kit, any other bundle, or anywhere else. Do not commit anything.
- The only files you may write are: your report file (Override 3), the two Step 10 copies under /tmp/oracle-qc/schema-migration-plan-repair-<TS>/ and the harbor jobs under /tmp/harbor-jobs-qc/schema-migration-plan-repair-<TS>/ (Override 4), your own logs and scratch under /tmp/opencode-logs/schema-migration-plan-repair-*/, and the one session-title update in Override 3.
- Run no real agent. The only harbor agents in this session are oracle, nop and the stub (oracle on the stub copy). Do not set or export OPENAI_API_KEY.
- Every fail and minor finding must still carry a `Fix:` line stating the best possible fix in one concrete sentence (file, what to change, to what). Describe the fix; never apply it.

OVERRIDE 2. Stay inside this bundle.
- Never open any of these, they bias the review: anything under "/Users/mac/Desktop/Terminal Bench/master_chat_work/" (the original bundle beyond the Step 0 diff, build notes in bundles/_work/, the 20261021_* folders), anything under "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/", anything under "/Users/mac/Desktop/Terminal Bench/QC assigned/" (old kit copy, old bundles and old reports), "Input Bundle Generator New/ayush sah tasks/", other bundles in "QC_2026-10-21/bundles/", other task folders in "QC_2026-10-21/qc_report/", "QC_2026-10-21/QC_2026-10-21.md" and "QC_2026-10-21/QC_Terminal_Prompts.md".
- Never use "QC assigned/Input_Bundle_QC" or "Input Bundle Generator New/ayush sah tasks/_qc/Input_Bundle_QC": they are stale copies (old judge annotation keys, data/-only input, chmod 700) and give wrong verdicts.
- Do not open earlier report versions in your own report folder until your new report is fully written (see Override 3).
- Do every gate yourself in this session, one at a time, as Starter.md says. Do not hand gates to subagents.
- In gate 02, open solution/TRUTH.md last, as Starter.md requires.
- environment/data/repo.zip is the shipped repository. To read its contents for gates 02 and 05, run `date +%Y%m%dT%H%M` once (call it TS0) and unpack it only into "/tmp/opencode-logs/schema-migration-plan-repair-repo-<TS0>/", never inside the bundle. Never modify the zip. Delete that scratch folder in the Step 10 cleanup.

OVERRIDE 3. Report file and versioning.
- Create the report folder if it does not exist. List it. Count only files named exactly vN.md (v1.md, v2.md, ...); ignore every other file. If there is no vN.md, your file is v1.md. Otherwise find the highest N and write v(N+1).md. Never overwrite an existing version.
- Rename this session as soon as you know N: title it `schema-migration-plan-repair_vN_qc` (for example `schema-migration-plan-repair_v1_qc`). opencode has no rename command, so run this one bash command with your N filled in:
  SID=$(opencode db "SELECT s.id FROM session s JOIN part p ON p.session_id = s.id WHERE s.parent_id IS NULL AND p.data LIKE '{\"type\":\"text\"%You are running the full input-bundle QC%QC_2026-10-21/qc_report/schema-migration-plan-repair%' ORDER BY s.time_created DESC LIMIT 1" | tail -n +2); echo "$SID"; opencode db "UPDATE session SET title='schema-migration-plan-repair_vN_qc' WHERE id='$SID'"; opencode session list | head -5
  Check that the list shows `schema-migration-plan-repair_vN_qc` on the newest session. If it does not, note it in the report header and carry on; never retry the update on another session ID. The terminal header may show the old title until the session is reopened.
- First line block of the file: bundle name, bundle path, report version, date and time in IST (UTC+5:30), QC kit commit (from Step 0), harbor version.
- Write as you go so nothing is lost if the session runs long: after each script run and after each gate, append that step's full section (its checklist copied verbatim, every item marked, with quoted evidence) to the report file before starting the next step.
- When everything is done, put the consolidated report from Starter.md "Final report" at the TOP of the file: verdict line, per-gate summary table, Findings (with Fix: lines), consolidated sign-off checklist. The per-step sections stay below it as the evidence appendix.
- Only after the report is complete, if an earlier version exists, read it and append a short "Compared with v(N-1)" section at the end: findings fixed, findings still open, new findings, by check ID.

OVERRIDE 4. Step 10 follows the kit's exe_copy.py flow exactly (Starter.md Step 10 and Final_checklist.md Step 10), with only the additions below.
The scores are TESTS-ONLY, as the kit says: exe_copy.py validates tests/judge.toml against the rewardkit 0.2.1 schema and never executes it. Use Harbor 0.24.0 and harbor-rewardkit 0.2.1.
1. Preflight as the kit says: `harbor --version`, `docker ps`, and list the bundle path. Paste the output.
2. Run `date +%Y%m%dT%H%M` once and call the result TS. Write its literal value into every path below (shell variables may not survive between tool calls). exe_copy.py refuses a destination that already exists, so never reuse an older folder.
   RUN copy:  "/tmp/oracle-qc/schema-migration-plan-repair-<TS>/run/schema-migration-plan-repair"
   STUB copy: "/tmp/oracle-qc/schema-migration-plan-repair-<TS>/stub/schema-migration-plan-repair"
   Jobs:      "/tmp/harbor-jobs-qc/schema-migration-plan-repair-<TS>"
   Logs:      "/tmp/opencode-logs/schema-migration-plan-repair-step10-<TS>"
3. Build both copies with the kit script, running Python from /tmp with PYTHONDONTWRITEBYTECODE=1 so no __pycache__ lands in the bundle or the kit:
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/schema-migration-plan-repair" "/tmp/oracle-qc/schema-migration-plan-repair-<TS>/run/schema-migration-plan-repair"
   cd /tmp && PYTHONDONTWRITEBYTECODE=1 python3 "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/exe_copy.py" "/Users/mac/Desktop/Terminal Bench/QC_2026-10-21/bundles/schema-migration-plan-repair" "/tmp/oracle-qc/schema-migration-plan-repair-<TS>/stub/schema-migration-plan-repair" --stub
   Paste both outputs in full, with their exit codes. P is the positive total exe_copy.py prints in its reward.toml line.
   If either exits 1 (REFUSED), do NOT build a copy by hand and do NOT work around it: record each REFUSED line as a ❌ finding with a Fix: line, mark Step 10 ⏸️ NOT RUN (refused by exe_copy.py, quoting its output), and continue with Step 11. Exit 2 is a usage error in your command: fix the command and run it again.
4. Confirm the flags with `harbor run --help`, then run the kit's seven commands in this order, each with -o "/tmp/harbor-jobs-qc/schema-migration-plan-repair-<TS>": oracle-1 to oracle-5 (--agent oracle on the RUN copy), nop-1 (--agent nop on the RUN copy), stub-1 (--agent oracle on the STUB copy). For example:
   harbor run --path "/tmp/oracle-qc/schema-migration-plan-repair-<TS>/run/schema-migration-plan-repair" --agent oracle --env docker --job-name oracle-1 -o "/tmp/harbor-jobs-qc/schema-migration-plan-repair-<TS>" -y
   Never run them in the foreground. `mkdir -p` the logs folder, then chain all seven inside one `nohup bash -c '...; echo ALL_DONE' > "/tmp/opencode-logs/schema-migration-plan-repair-step10-<TS>/runs.log" 2>&1 &`. Poll with waits under 4 minutes (for example `sleep 200; tail -5 <log>`) until ALL_DONE appears. Other sessions' harbor runs may share Docker: never touch their processes or folders.
5. For each run, read the reward from the trial directory's result.json `verifier_result.rewards.reward` and verifier/reward.json. A run with `exception_info` or an exception.txt errored and has no score. Never read the score from console output.
6. Expected, as the kit requires: all five oracle runs exactly 1.000 (report each number), nop exactly 0.000.
   - Oracle below 1.0: solve.sh fails a check, or a check has a bug. Name the failing checks from verifier/reward-details.json.
   - Nop not 0.0: a positive check passes on an empty run, or a negative check fires on one. Name the check.
   - No reward.json: rewardkit crashed, usually because a check raised an exception. Quote the error from verifier/test-stdout.txt.
   - Different scores across the five oracle runs: the checks are non-deterministic. Find the cause (gate 03 TS-11), do not re-run until they agree.
7. Run `diff -rq` between the bundle under review and each copy and paste both outputs. Allowed differences: tests/judge.toml (only in the bundle under review), tests/reward.toml, task.toml, environment/Dockerfile, and, for the STUB copy only, the contents of solution/. Anything else is a ❌ finding.
8. Stub judgement (Final_checklist.md "The stub run"):
   a. Paste the STUB copy's solution/solve.sh in full.
   b. From stub-1's verifier/reward-details.json, list every check whose value is not 0, with its weight.
   c. If stub-1 errored instead of scoring (for example a declared artifact the kit stub writes in a form the checks cannot even open), edit only the STUB copy's solution/solve.sh to create what the instruction names there (empty files, {} for JSON, or an empty but valid zip for /app/out/patched-repo.zip), nothing more, and run it again as stub-2. Report every attempt and the change.
   d. Judge the score: near zero or negative is healthy; a substantial share means tests pay for filenames rather than content. Report it as a share of P, the checks that paid and why, and your judgement with reasons, and compare it with the CL-2 forgery price you computed in gate 05. A stub score near the range a genuine partial attempt would earn, or any check that paid while it claims to grade content, is a ❌ finding with a Fix: line.
9. Cleanup: delete only "/tmp/oracle-qc/schema-migration-plan-repair-<TS>" (never the /tmp/oracle-qc parent or any sibling folder), and the repo.zip scratch folder "/tmp/opencode-logs/schema-migration-plan-repair-repo-<TS0>/". Keep the jobs and logs folders as evidence. Confirm the bundle under review still has tests/judge.toml, its original tests/reward.toml, task.toml, environment/Dockerfile and solution/, that `diff -rq` against the original bundle still prints nothing, and that neither the bundle nor the kit has a __pycache__.
10. In the Step 10 section of the report: a table of agent, run number and reward (oracle-1 to oracle-5, nop-1, stub-1 and any stub retries); the failing checks by name, if any; the checks the stub got paid for and your judgement; the stub solve.sh; both exe_copy.py outputs; both diff outputs; the jobs folder path.
11. In the Step 10 section and the sign-off, state plainly: tests-only grading per the kit (judge.toml validated, not executed; no OpenAI key; the stub score covers the test channel only), and the network opened and the OpenHands pre-bake dropped in the copies only. A failing oracle, nop or stub result is a real ❌ finding with a Fix: line.

WHEN DONE: reply in the terminal with only the verdict line, the five oracle, nop and stub rewards, and the full path of the report file you wrote. No offers, no fixes.
```

