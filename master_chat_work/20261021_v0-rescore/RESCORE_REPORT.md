# v0 re-score in Docker + sandbox-permission audit

Run 2026-10-21 23:36 to 23:49 IST (18:06 to 18:19 UTC). Harbor 0.24.0, Docker, QC kit Step 10 method: every copy built by `exe_copy.py` (judge.toml removed, tests-only weights `1/155` emberforge, `1/145` vendor, network opened). Scores are TESTS-ONLY. One run each.

## Result

Bottom line: both near-zero test scores were caused by the verifier, not by the agent. Once the sandbox uid can read the files, the agent scores 94.19% on emberforge and 88.97% on vendor-archive.

| bundle | as delivered | Variant A (agent files 0644) | Variant B (verifier fixed, files as delivered) | checks lost in Variant B |
|---|---|---|---|---|
| emberforge-vault-settlement | 0.0194 (3/155) | 0.9419 (146/155) | 0.9419 (146/155) | structure_findings_canonical_form (1), cap_and_floor_one_findings (5), quiet_rules_findings (3) |
| vendor-archive-roundtrip-recovery | 0.0483 (7/145) | 0.0483 (7/145) | 0.8897 (129/145) | basic_delta (3), va1_cross_delta (5), va4_overlong_bytes (5), report_decoded_examples (3) |

- Step 1 gate: the as-delivered replays reproduce the reported scores exactly (1.94% and 4.83%), so the replay is faithful. The oracle log of the emberforge replay shows `-rw------- agent agent 43009 settle_vault.py`. On vendor-archive, `negative_filename_dependent_behaviour` (-5) and `negative_nondeterministic_output` (-3) fired, as in the original run.
- Emberforge: A and B have identical pass sets. The mode-0600 program was the only blocker, and no negative check fired in either variant.
- Vendor-archive: Variant A equals as-delivered because every agent file was already 0644. The failure is entirely in the grader's own temp files. Variant B matches the earlier local non-root re-score exactly (129/145, the same 4 checks lost), and no negative check fired.

Oracle and nop on the Variant B verifier (the bundle's own solution/):

| bundle | oracle | nop |
|---|---|---|
| emberforge | 1.0 (155/155) | 0.0 |
| vendor-archive | 1.0 (145/145) | 0.0 |

No trial raised an exception (`exception_info` null, no `exception.txt`).

## Variant B patches (scratch copies only)

- emberforge `_run_delivered` (bundle L2192), inserted before `_drop_privileges`: when running as root, `PROGRAM |= 0o444`, and `/app/out` and `/app` get `|= 0o555`.
- vendor `_decode` and `_salvage`: the temp input is chmodded to 0644. `_stream`: the temp dir is set to 0755, and the segments and manifest to 0644. `_encode`: the temp dir is set to **0777** and doc.json to 0644.
  - The brief asked for 0755 dirs. `encode.py` must create `out.varc` inside that dir as nobody, so 0755 would still fail. 0777 is the same pattern district and schema already use for writable scratch dirs.

## Audit: agent code under a dropped uid (static, no bundle edited)

| bundle | site (tests/test_output.py) | runs as | gap | minimal fix |
|---|---|---|---|---|
| emberforge | L2186-2194 `_run_delivered` -> `_drop_privileges` L2107-2122; `PROGRAM` L1340 | uid 4001 | **REAL (hit in v0).** `/app/out/settle_vault.py` and its parents `/app/out` and `/app` are never opened to the sandbox uid, so an editor-written 0600 program cannot be read. `_open_to_sandbox` (L2125) only opens the data and out dirs the grader passes in. Side note: on the `pass_dirs=False` path (L2714), `_open_to_sandbox(OUT)` makes PROGRAM 0666 (world-writable) for that run. | Before `_drop_privileges` at L2193: `os.chmod(PROGRAM, mode\|0o444)`, and `os.chmod(d, mode\|0o555)` for `PROGRAM.parent` and `/app`. The Variant B scores above use exactly this fix. |
| emberforge | L2585, L2642, L2696-2860 (mkdtemp and TemporaryDirectory) | uid 4001 | none: `_open_to_sandbox` sets data to 0755/0644, out to 0777/0666, and the parent to 0711 | - |
| vendor-archive | L833-837 `_decode`, L851-855 `_salvage` (NamedTemporaryFile, 0600 root) | nobody (`_wrap` L804-808) | **REAL (hit in v0).** nobody cannot read the input. | `os.chmod(path, 0o644)` after writing |
| vendor-archive | L870-880 `_stream` (mkdtemp, 0700 root) | nobody | **REAL.** The dir is not traversable by nobody. | `os.chmod(tmp, 0o755)`; segments and manifest 0644 |
| vendor-archive | L889-895 `_encode` (mkdtemp, 0700 root) | nobody | **REAL.** nobody can neither read doc.json nor create out.varc. | `os.chmod(tmp, 0o777)`; doc.json 0644 |
| vendor-archive | L805 `/app/decode.py`, `/app/encode.py` | nobody | **LATENT.** The programs and `/app` are never opened, so the same editor-0600 trap as emberforge applies. The v0 agent's files happened to be 0644. | In `_wrap`, when running as root: program `\|= 0o444`, and `/app` `\|= 0o555` |
| district-heat-flex | L897-911 `run_agent`: `/app/out/derive_report.py` via `_untrusted` L889 (`_SETPRIV` L46) | nobody | **LATENT.** The script and its parents `/app/out` and `/app` are never opened, so a 0600 editor-written script fails every run-based check (same as emberforge). Inputs are fine: `_seal` L510 sets 0644/0755, `_scratch` L501 sets 0755, the run box L908 is 0777. | Before the Popen at L911: `script \|= 0o444`, and `script.parent` and `/app` `\|= 0o555` |
| schema-migration | L7102-7112 `_run` (`_SETPRIV` L53) from `_child` L7154, `_unit_results` L7876, `_cli_run_matches` L7916 | nobody | none. Agent code arrives only inside `patched-repo.zip`, which `_unpack` (L7071-7087) extracts with explicit 0644/0755, so the agent's file modes cannot matter. Every input is chmodded 0644/0755 (L7040-7044, L7160-7163, L7220-7221, L7612, L7880, L7919, L8222), and cwd is `_scratch` 0777. | - |

Verdict per bundle:
- emberforge: FAIL (real, scored v0 wrong)
- vendor-archive: FAIL (real, scored v0 wrong, plus a latent program-mode trap)
- district-heat-flex: FAIL (latent, same trap as emberforge, not yet hit)
- schema-migration: PASS

## Integrity

The sha256 and mode trees of all 4 bundles are identical before and after the run. Snapshots: `/tmp/v0-rescore-20261021T2055/{sha,modes}_{before,after}_<bundle>.txt`.

| bundle | files | sha256 of tree listing |
|---|---|---|
| district-heat-flex-procurement | 25 | d40d64c27d91d8bf... |
| emberforge-vault-settlement | 47 | 33c1ee78df531d3a... |
| schema-migration-plan-repair | 24 | ff44f45a98db0f77... |
| vendor-archive-roundtrip-recovery | 23 | ceb7fffb360f9ea2... |

Agent artifact folders were only read. Nothing was pulled, committed or pushed.

## Paths

- Scratch: `/tmp/v0-rescore-20261021T2055/`
  - copies: `ef_{asis,A,B,B_oracle}`, `va_{asis,A,B,B_oracle}`
  - exe_copy output: `exe_copy_<copy>.txt`
  - builder: `build.py`
  - summariser: `summ.py`
  - runner: `run_seq.sh`
- Jobs: `/tmp/v0-rescore-20261021T2055/jobs/<job>/<trial>/`
  - reward is read from `result.json` (`verifier_result.rewards.reward`)
  - per-check detail is in `verifier/reward-details.json`
  - job names: `ef-asis-oracle`, `ef-A-oracle`, `ef-B-oracle`, `ef-B_oracle-oracle`, `ef-B_oracle-nop`, and the same set prefixed `va-`.
- Logs: `/tmp/opencode-logs/v0-rescore-20261021T2055/`
  - `<job>.log`: harbor console output
  - `ef_seq.log`, `va_seq.log`: start and end times
