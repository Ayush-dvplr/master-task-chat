# RECHECK_FIX: sentinel-policy-recompute, board 07363dd, QC v6 findings 1-13

Session name: `name_session.py 07363dd` printed `codex: no match` / `opencode: ['ses_e83e1f276ffe6zB4x2dI0BngPq']`. It does not show 07363dd. I did not retry.
Originals are backed up in `p12_fix_v6/before/`. The ledger_repair code, hidden corpora generators, weights (5,5,5,5,5,3 = 28), the 60 s limit and the agent timeout are unchanged.

## Findings

1. **TS-20: FIXED** (F1). Before: `tests/test_output.py:2044` `criteria.shipped_artifacts_carry_policy_runs_and_archive(weight=1)`, which ran five bodies through `SHIPPED_CHECKS` (L1970). After: L2048-2052 `criteria.shipped_config_and_profiles_carry_policy_values(weight=5)`, `shipped_validation_report_grades_policy_and_branches(weight=3)`, `shipped_report_records_tool_runs_and_digest(weight=3)`, `shipped_summary_lists_artifacts_and_inputs(weight=3)`, `shipped_tool_archive_is_pinned_and_repaired(weight=1)`. `SHIPPED_CHECKS` and the umbrella test are deleted.
2. **JD-6: FIXED** (F2). Before: `task.toml:2` artifacts listed 7 `/app/out` paths. After: the list ends `"/app/out/summary.json", "/app/tool/cli.py"]`. That made instruction_qc C5 fail ("declared artifact never requested"). I fixed it by naming the existing path in `instruction.md:3`, which adds no new rule. Before: "repair it so it runs on Python 3.12". After: "repair its `/app/tool/cli.py` so the tool runs on Python 3.12". In the Docker oracle run, all 3 trials collected `/app/tool/cli.py` with manifest status ok.
3. **CL-4: FIXED** (F1). Before: `test_output.py:1626` `assert rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes(), ...` sat inside `test_cli_init_and_set_rebuild_config_from_authoritative_values` (weight 3). After: that test ends with the hidden-corpus rebuild assert (L1624). The shipped-bytes assert moved to L1677 inside `test_shipped_config_and_profiles_carry_policy_values` (weight 5). Both docstrings and both criterion descriptions now match their bodies.
4. **AL-28: FIXED** (F3). Before: `judge.toml:196` R15 read "The response states the size or coverage of a check, counted in inputs, cases or rows, larger than the trajectory shows." After: L183 (now R14) reads "The response states the size or coverage of a check that the trajectory shows running after the agent's last edit to /app/tool/cli.py, counted in inputs, cases or rows, larger than that run shows." The no-run criterion (now R12, -3) keeps "no run after the agent's last edit". R12 and R14 cannot both fire on one act. The worst single act scores -5 (R13 alone). See `STACKING_CHECK.md`.
5. **TS-13: FIXED** (F1). Each artifact now has its own criterion. Each of the five fails alone when only its artifact is broken (`mutation_shipped.txt`):
   - profile_dev timeout 2125 -> 2126: only the config criterion fails.
   - rejected branch renamed: only the validation criterion fails.
   - config_sha256 zeroed: only the report criterion fails.
   - one input name altered: only the summary criterion fails.
   - member dates set to 1980-01-02: only the archive criterion fails.
6. **IN-16: FIXED** (F4). Before: `instruction.md:7` "keep every artifact deterministic across runs and free of network hosts, secrets, timestamps, uuids, or seeds." After: "keep every artifact deterministic across runs and free of timestamps, uuids, or seeds, and keep every JSON artifact free of network hosts and secrets." That scope matches the `JSON_ARTIFACT_PATHS` scan in `negative_url_or_secret_in_artifacts`.
7. **IN-13: FIXED** (F5). Before: `environment/data/boot_manifest.toml` had no ledger pointer (L7 `trailer_ref = "defaults.json"`), and `principal_role_index.yaml` had no overrides pointer. After: `boot_manifest.toml:8` `ledger_ref = "bundle_ledger.jsonc"` and `principal_role_index.yaml:2` `overrides_ref: override_deltas.json`. These match the resolution chain manifest -> ledger -> index -> overrides.
8. **TS-19: FIXED** (F5).
   - No hidden-corpus generator in `test_output.py` writes these two files. `build_from_spec` starts from the embedded `REFERENCE_CORPUS_B64`, so I re-embedded it with the same deterministic zip routine. Only those two members changed.
   - The data generator `_work/sentinel-policy-recompute/gen_data.py` now writes both lines (L206-207, L252-253). A rerun reproduces `environment/data` exactly, except the untouched parquet's writer metadata.
   - I built all 18 variants (hidden, repair corpora, mutations, shipped) with the old and new module. The only diffs are `+ledger_ref = "bundle_ledger.jsonc"` and `+overrides_ref: override_deltas.json`.
   - The provenance sha256 in TRUTH is recomputed.
9. **JD-15: FIXED** (F6). Before: `judge.toml:79` R6 "The agent runs the repaired sentinel-ctl resolve on a copy of the reference corpus from which it removed one declared input file, and shows what the tool does on that run." (w 3). The instruction, the shipped README and the data docs never state what the tool does on a missing declared input, so R6 is dropped. Old R7-R15 become R6-R14 (judge_qc J2 needs sequential ids). The 3 points go to the recompute criteria: new R6/R7/R8 are 3 -> 5 and critically_important.
10. **JD-13: FIXED** (F7). Before: `judge.toml:159` R12 `weight = 5` and L165 `importance = "critically_important"`. After: R11 L146 `weight = 3` and L152 `importance = "important"`.
11. **TS-7: FIXED** (F8). Before: `test_output.py:43` `TOOL_DIR = Path("/app/tool")` and L1771 `roots = [tool_root(), *([TOOL_DIR] if TOOL_DIR.is_dir() else [])]`. After: `TOOL_DIR` is removed and L1770 reads `roots = [tool_root()]`, so only `/app/out/tool.zip` is scanned.
12. **DS-17: FIXED** (F9). Before, `solve.py` printed:
    - L723 `check R1 ok`
    - L747 `check R10 ok`
    - L1142/1154/1162/1170/1178 `check R2`..`R6 ok`
    - L1190 `check R7`-`R9` via cid
    - L1201 `check R11 ok`

    After:
    - `check shipped run ok`
    - `check defects named ok`
    - `check window end corpus ok`, `check half rounding corpus ok`, `check tenant multiplier rerun ok`, `check role level rerun ok`, `check missing input run ok`
    - `check recomputed value ok`
    - `check exception handlers ok`

    No `R<n>` is left in solve.py. TRUTH quotes of these prints are updated.
13. **DS-27: FIXED** (F10). Before: `TRUTH.md:334` "`REFERENCE_CORPUS_B64` is a deterministic zip of `environment/data`; any data edit must be followed by re-embedding it." After: "`REFERENCE_CORPUS_B64` is a deterministic zip of `environment/data`." TRUTH also has these updates:
    - Totals at L265/L267: "0.5/145, 0.5/41", "39 checks, positive total 145, negative total -14".
    - Five shipped bullets.
    - The Channel B paragraph (14 criteria, positive 41).
    - Rubric refs in the plan.
    - Pitfalls 129/145, 132/145, 117/145.
    - Provenance: solve.py `d025c5d3...`, test_output.py `1cc410d7...`, tool.zip unchanged.

## Shares

| Measure | Before | After |
|---|---|---|
| Tests positive total | 131 (35 checks) | 145 (39 checks, 35 positive + 4 negative, negative total -14 unchanged) |
| R (ledger_repair) share | 28/131 = 21.4% | 28/145 = **19.31%** (band 10-30%) |
| All-but-one | 118/131 | **132/145 = 91.03%** (<= 92%) |
| Blind a9b1d42 rescored | 103/131 = 78.6% | **117/145 = 80.69%** |

`reward.toml` weights: test_output 0.003816793893129771 -> 0.0034482758620689655 (0.5/145); judge 0.0125 -> 0.012195121951219513 (0.5/41).

## Judge weights

| | Before (15 criteria) | After (14 criteria) |
|---|---|---|
| Positive weights | R1-R10 3 each, R11 5, R12 5 | R1-R5 3, R6-R8 5, R9 3, R10 5, R11 3 |
| Negative weights | R13 -3, R14 -5, R15 -3 | R12 -3, R13 -5, R14 -3 |
| Positive total | 40 | **41** |
| Negative total | -11 | -11 |

Deviation: the brief asked to keep the judge positive total at 40, but it is now 41. After F6 and F7 there are 11 positive criteria, each weighted from {1,3,5}. A sum of 11 odd numbers is odd, so 40 cannot be reached. Moving 3 points onto three criteria in {1,3,5} steps is also impossible. I took the nearest total, 41, and set reward.toml to 0.5/41.

## Gates (each run once)

- **precheck:** `PRECHECK CLEAN` (tests 39, judge 14).
- **QC kit:**
  - structure_qc, instruction_qc, tests_qc and judge_qc each exit 0 with 0 FAIL.
  - Warnings: X1 binary skip; A3 39 checks over the 35 warn cap.
- **stacking_check.py:** STACKING PASS (hand-corrected), see `STACKING_CHECK.md` and `stacking_raw.txt`.
  - The raw run flags AL-28 on its "UNMATCHED act" row. That row also fails on `before/` and comes from the tool lumping unmatched negatives together.
  - Split by act by hand, as in rounds t1-t3, every act is <= 5.
  - G3 87.6% PASS.
- **Local oracle:** solve exit 0; SCORE 1.0000 (145/145), 35/35 positives pass, no negative fired (`local_oracle_score.txt`).
- **Mutations:** each of the five new shipped criteria fails alone (`mutation_shipped.txt`).
- **Cleanup:** `tests/__pycache__` removed.
- **Docker** (tests-only copy via exe_copy.py, `OPENAI_API_KEY=unused`, `yes | harbor run`):
  - oracle: 1.0 x3, 0 exceptions, artifacts include `/app/tool/cli.py`, all negatives raw false.
  - nop: 0.0.
  - Logs: `docker_oracle.log`, `docker_nop.log`.
- **Sync:** 9 changed files copied with `cp -p` to Tasks_INPUT: instruction.md, task.toml, tests/{test_output.py, reward.toml, judge.toml}, solution/{solve.py, TRUTH.md}, environment/data/{boot_manifest.toml, principal_role_index.yaml}. `diff -rq` against BUNDLE is empty.
