# RUN_LOG: beta-task-generator analysis (2026-10-20 IST)

Source (read-only): `/Users/mac/Desktop/Terminal Bench/beta-task-generator/` @ `17e9f70`.
Scratch: `/tmp/beta-analysis-20261020T2228/`. Logs: `/tmp/opencode-logs/beta-analysis-20261020T2228/`.
Python on host: 3.14.8 (`python3`) and 3.13.16 (`python3.13`). The project wants 3.12 (`pyproject.toml:5`); 3.12 is not installed, so it was not used.

Nothing was executed inside SOURCE. Every run used a copy in SCRATCH.

| # | Command (cwd) | Exit | Result |
|---|---|---|---|
| 1 | `cp -R SOURCE /tmp/beta-analysis-20261020T2228/src` | 0 | copy for execution |
| 2 | python sha256 walk of SOURCE (excludes `.git/`) -> `fingerprint.json` | 0 | 353 files |
| 3 | `python3 -m unittest discover -s tests -v` (src, py3.14) | 1 | Ran 173: failures=5, errors=33 |
| 4 | `python3.13 -m unittest discover -s tests -v` (src, py3.13) | 1 | Ran 173: failures=5, errors=33 (same) |
| 5 | `snapshot_digest()` over the 3 configured components (src) | 0 | all 3 MISMATCH `config/source_components.json` |
| 6 | same, after converting snapshot text files LF->CRLF (temp copy) | 0 | all 3 MATCH -> pinned digests were computed on CRLF (Windows) checkouts |
| 7 | `python3 -m unittest discover -s tests -v` (src_crlf = src with CRLF snapshot, py3.14) | 1 | Ran 173: failures=3, errors=1 (169 pass) |
| 8 | `python3.13 -m unittest discover -s tests -v` (src_crlf, py3.13) | 1 | Ran 173: failures=3, errors=1 (169 pass) |
| 9 | `--help` for root + all 93 sub-paths (`--root src_crlf`) | 0 x94 | every parser path builds and prints help |
| 10 | `core --root runroot status` | 0 | `state: needs_init`, `release_ready: false`, `runtime_evaluation: NOT_EVALUATED` |
| 11 | `core --root runroot init` then `status` | 0, 0 | `initialized`, then `state: ready` |
| 12 | `core --root runroot settings view` | 0 | 22 keys of defaults.json + `revision: 1` |
| 13 | `core --root runroot tasks create example-task --domain logistics` | 0 | revision 1; skeleton bundle has only `instruction.md` ("# PENDING_AUTHORING") and a 3-line `task.toml` |
| 14 | `core --root runroot tasks create Bad_Name` | 2 | JSON error `invalid_task_name` |
| 15 | `core --root runroot tasks verify example-task` | 0 | returns bundle hash only (read-only) |
| 16 | `core --root runroot qc status <example bundle>` | 0 | `input_qc/output_qc/solvability: NOT_RUN`, `difficulty_target: NOT_EVALUATED` |
| 17 | `core --root runroot host doctor` | 0 | claude 2.1.304, opencode 1.19.0, git 2.54.0, python 3.14.8; `macos_verification: VERIFIED_ON_THIS_HOST` |
| 18 | `core --root runroot qc verify <example bundle> --kind input` | 0 | ran pinned `structure_qc.py` etc.; the skeleton fails S2/T2 (expected) |
| 19 | `core --root runroot tasks adopt dp-template <copy of templates/data-pipeline>` | 0 | adopted as revision 1 |
| 20 | `core --root runroot qc verify <dp-template bundle> --kind input` | 0 | receipt written, verdict FAIL; structure 37 FAIL lines / 23 WARN (template placeholders plus CRLF warnings caused by step 6), instruction 2 FAIL, tests 2 FAIL, rubric 0 FAIL |
| 21 | `core --root runroot qc status <dp-template bundle>` | 0 | `input_qc: FAIL`, release_ready false |
| 22 | `ideas start dp-template logistics` -> `ideas submit` (3 example candidates from `prompts/idea-workshop.md` A2) -> `ideas select candidate-1` | 0,0,0 | flow works as documented |
| 23 | `ideas submit` (B2 example review) before writing the evidence record | 2 | `unverified_acceptance` |
| 24 | `Store.write('workspace/review-evidence/source.json', {...})`, then sha256 of it | 0 | `ddf35011...9f11`, the same hash the prompt documents |
| 25 | `ideas submit` (B2 review) again | 0 | accepted; `refinement_rounds` moves to 1 |
| 26 | `runs schema`, `runs status <bundle>` | 0, 0 | Harbor mapping printed; `model_verdict: NOT_EVALUATED` |
| 27 | `release check <dp-template bundle>` | 2 | `invalid_bundle: package folder does not match the pinned contract` |
| 28 | LF root (plain copy): `init`, `tasks adopt dp`, `qc verify <dp> --kind input` | 0 | verdict `BLOCKED`, finding `runner:SNAPSHOT_INTEGRITY`, `checker_runs: []` |
| 29 | LF root: `qc-repair open --bundle <dp> --report-text "FAIL [S2] x"` | 2 | `snapshot_integrity: snapshot digest mismatch for input_bundle_qc` |
| 30 | re-hash SOURCE (all files except `.git/`) and compare to `fingerprint.json` | 0 | 353 files; 0 added, 0 removed, 0 changed; no `workspace/` in SOURCE |
| 31 | `rm -rf /tmp/beta-analysis-20261020T2228` (SCRATCH) | 0 | deleted after the report was assembled; logs kept in `/tmp/opencode-logs/beta-analysis-20261020T2228/` |

## Failures that are left once the CRLF digest problem is removed (runs 7 and 8)

| Test | Cause |
|---|---|
| `test_archives.ProductionArchiveTests.test_catalog_is_portable_complete_and_hash_verified` (ERROR) | `references/archive/` is git-ignored (`.gitignore`) and not in the repo, so `FileNotFoundError` on `hard_task_analysis/CROSS_TASK_SUMMARY.txt` |
| `test_archives...test_beta_git_root_has_no_commit_or_remote` (FAIL) | the test asserts the repo has no HEAD; the repo now has 3 commits |
| `test_foundation_common...test_safe_child_rejects_absolute_parent_and_empty_paths` (FAIL) | macOS `/var` -> `/private/var` symlink: `safe_child` resolves and the test compares unresolved |
| `test_integration_cli...test_default_root_is_the_copied_package_root` (FAIL) | same `/private/var` resolution mismatch |

## Failures from the plain checkout (runs 3 and 4)

33 ERRORs all raise `core.common.BetaError: snapshot_integrity: snapshot digest mismatch for input_bundle_qc`. They cover all qc-repair intake, selection, verification and workflow tests, plus 2 qc_runner tests. Two more FAILs come from the same cause: `test_original_input_checkers_run_and_preserve_failures` and `test_folder_evidence_rejects_sensitive_paths`. On a macOS or Linux LF checkout, `qc verify` and every `qc-repair` route refuse to run until `config/source_components.json` is regenerated or the snapshot is checked out with CRLF.
