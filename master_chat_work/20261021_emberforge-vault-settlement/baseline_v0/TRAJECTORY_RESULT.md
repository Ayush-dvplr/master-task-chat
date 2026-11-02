# emberforge v0 trajectory (1 run, claude-opus-5, job 2026-10-21__18-45-30)
Source (copied, read only): Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/emberforge-vault-settlement -> ./trajectory_job/
(This job folder replaced the 20 Oct pre-harden run there: tests 68, rubric 100, combined 84; numbers kept in registry.)

| channel | reported | note |
|---|---|---|
| tests | 1.94% (3/155) | INVALID: verifier could not read the agent's program |
| rubric (judge ran) | 84.21% (16/19) | real: R1-R5 met; R9 (-3) fired: final message claims a check the trajectory does not show |
| combined | 43.07 | INVALID (tests channel) |

## Verifier bug (REAL)
- The agent's /app/out/settle_vault.py is mode 0600 (written by the OpenHands file editor); every other artifact is 0644.
- test_output.py runs the program as uid 4001 via setpriv (_run_delivered, _drop_privileges) and never opens PROGRAM to the sandbox user. uid 4001 cannot read it, every run-based check fails; only the 3 root-side reads pass (program delivered, records delivered, canonical form).
- QC Step 10 oracle passed in Docker because solve.sh writes the program 0644; the trap only hits editor-written files.
- The agent's program reproduces its own delivered visible-season records byte for byte (local run, 4.9 s). Its hidden-season score is UNKNOWN until a Docker re-score with the program at 0644.
