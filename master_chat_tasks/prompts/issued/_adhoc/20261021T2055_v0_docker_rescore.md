# v0 re-score in Docker (vendor-archive, emberforge) + sandbox-permission audit of all 4 verifiers

Read only on every source. Never pull, commit or push. Work only in scratch `/tmp/v0-rescore-20261021T2055/`. Long Docker steps run in the background with logs in `/tmp/opencode-logs/v0-rescore-20261021T2055/`.
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_v0-rescore/RESCORE_REPORT.md`

## Why
Two real trajectory runs scored near zero on tests because the verifier could not read files, not because the agent was wrong:
- emberforge: the agent's `/app/out/settle_vault.py` is mode 0600 (written by the OpenHands file editor). `tests/test_output.py` runs it as uid 4001 via setpriv (`_run_delivered`, `_drop_privileges`) and never makes PROGRAM readable. Reported tests 1.94%.
- vendor-archive: `_decode`/`_salvage`/`_stream` write inputs to root-owned NamedTemporaryFile/mkdtemp (0600/0700) and run `decode.py` as nobody. Reported tests 4.83%. A local non-root re-score gave 88.97% (129/145), not measured in Docker.

## Inputs
- Bundles (read only): `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/{emberforge-vault-settlement,vendor-archive-roundtrip-recovery,district-heat-flex-procurement,schema-migration-plan-repair}`
- Agent files: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_<slug>/baseline_v0/trajectory_job/trajectory/claude-opus-5/Run 1/artifacts/app/` (keep their file modes)
- Execution method: the QC kit's Step 10 (`/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`, exe_copy, tests only, judge removed, weights renormalised).

## Steps
1. For emberforge and vendor-archive, make a scratch copy of the bundle and replace `solution/solve.sh` with a replay that writes the agent's files into `/app` exactly as delivered (same paths, same modes; settle_vault.py stays 0600). Run it once through Harbor in Docker as the oracle agent. Expect to reproduce the reported tests score (1.94% / 4.83%); if not, stop and report.
2. Variant A (agent fixed): same replay but every agent file 0644. Score once.
3. Variant B (verifier fixed): scratch test_output.py patched minimally so the sandbox user can read what it must (emberforge: chmod PROGRAM and its parent dirs readable before `_run_delivered`; vendor: chmod temp inputs 0644 and temp dirs 0755). Replay the agent's files as delivered. Score once. Also run the real oracle once on Variant B to confirm 1.0, and nop once for 0.0.
4. Static audit of all 4 bundles' tests/test_output.py: list every place where the verifier runs agent code under a dropped uid and the code or its inputs may not be readable or writable by that uid (agent-written files with any mode, grader temp files, output dirs). Give file:line and the minimal fix. Do not edit any bundle.

## Done when
Report has a table: bundle | as delivered | Variant A | Variant B | checks lost in Variant B (names); plus the oracle/nop on Variant B, the audit table, and logs paths. Bundle sha256 trees unchanged before and after. Final reply: that table, the audit verdict per bundle, and the OUT path.
