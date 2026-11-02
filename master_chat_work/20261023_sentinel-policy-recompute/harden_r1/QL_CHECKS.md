# QL rule: checks changed in `git diff 2690e960 HEAD -- Input_Bundle_QC/` (HEAD 71a653b2)

| Commit | Check | Status on this bundle | Evidence |
|---|---|---|---|
| a74bda85 | K8 litellm pin in verifier image | FIXED | tests/Dockerfile line 5 `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`; tests_qc `pass [K8]` |
| c9e3454a | H6 agent program readable before uid drop | FIXED | test_output.py `_grant_read` on extracted tool and corpus; tests_qc `pass [H6]` |
| c9e3454a | TS-30 agent file modes survivable (owner-only oracle) | FIXED | Docker block: oracle `--owner-only` and oracle with programs chmod 600 (see HARDEN_REPORT) |
| d9f94333 | G2 judge mode batched | FIXED | judge.toml line 3 `mode = "batched"`; judge_qc `pass [G2]` |
| f3765e67 | H6 skips interpreter switches (`-I`) | PASS | runs use `sys.executable -I cli.py`; tests_qc `pass [H6]` |
| 3fb1650b | T14 author name shape (FC-S18) | PASS | structure_qc `pass [T14]` |
| 71a653b2 | S3 / S5 shipped trajectories dir and forbidden files | PASS | structure_qc 0 fail; no cheat/, reward files, .DS_Store, caches in bundle |
| a72c20a4 | validator aligned with QC; playground.py removed | PASS (validator advisory) | validate_bundle: 37 pass, 3 fail (§15.5-15.7 yaml provenance block, pre-existing in SOURCE); playground not run (removed) |

QC scripts: structure_qc 17 pass 1 warn (X1 binary files, advisory) 0 fail; instruction_qc 5 pass 0 fail; tests_qc 37 pass 0 fail; judge_qc 19 pass 0 fail.
