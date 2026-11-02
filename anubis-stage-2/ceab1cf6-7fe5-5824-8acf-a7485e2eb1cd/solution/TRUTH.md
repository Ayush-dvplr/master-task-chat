# TRUTH.md - ceab1cf6-7fe5-5824-8acf-a7485e2eb1cd

## Defect

The bundle ships a broken offline budget-envelope allocation ledger tool, `task-ctl`, packed inside `/app/data/tool.zip`. The tool is meant to read the rule layers under `/app/data` (or under the directory named by `TASK_CTL_DATA`), select the single active allocation band from `active_band = (max_records // 13) % 7` using the base record count in `defaults.json` (`460` in the shipped corpus, so band 0), and derive one flat, fully scalar configuration whose every number is an exact integer. Its derivation logic is wrong in ten ways, and every rule table mixes the one `CANONICAL` value per band with `DEPRECATED`, `PHANTOM`, `ARCHIVE` and `INACTIVE` decoy rows.

1. (focal) Rounding is half-up through floating-point division, `int(math.floor(num / den + 0.5))`, everywhere a divide-and-round appears. The contract is integer round-half-even from the division remainder.
2. (focal) Every per-band table is read through `rows[0][field]`, the first row of the file, instead of the row whose band equals the active band and whose status is `CANONICAL`. Several shipped constants (`fps_num = 7000`, `bpp_milli = 244`, `eff_permille = 6000`, `min_kbps = 300`, `max_kbps = 5200`) are also written into the code as literals, so the shipped corpus masks the defect; a corpus with another band, or with decoy rows ahead of the canonical ones, exposes it.
3. The column width is never evened; the repair must add one when the rounded width is odd so the width is even (each band's width is marked even in `width_even.html2`, whose single CANONICAL `<rule>` row gives `apply="width + 1"` among DEPRECATED, PHANTOM and ARCHIVED alternatives), before `luma_pixels = width * height`.
4. Granularity is applied with a floor onto a step of 50, `(value // 50) * 50`, instead of round-half-even quantisation onto the canonical step of 25 from `granularity.kv`.
5. Profiles are scaled after granularity quantisation instead of scaling the pre-clamp average first, then clamping, then quantising.
6. The priority step `qp` comes from `round(63 - 4 * log2(avg / 1000 + 1))` instead of the integer staircase in `qp_stair.psv` (the largest canonical threshold at or below the average gives the band offset; `qp = clamp(63 - offset, 10, 63)`).
7. The reserve envelope is built from the average allocation instead of the ceiling allocation: `vbv_buffer_kbits = round_half_even(max_bitrate_kbps * vbv_seconds_milli, 1000)`. The ceiling ratio is also a wrong literal (1450 per mille instead of the canonical 1375).
8. The cycle span and minimum interval use `ceil` instead of round-half-even over `fps_num * seconds / fps_den`.
9. (trap) The argument parser never marks a subcommand required, so a bare invocation dies with an `AttributeError` traceback; the repair passes `required=True` so argparse prints a usage error.
10. (trap) `derive` writes a nested `{"ladder": {...}}` object; the contract demands a flat object of scalars under the `config` member of the derive output.
11. (drift) `schema.json` inside the archive stores `required_keys` as one comma-separated string while `config_schema.json` stores the same 31 keys as a JSON array. The repaired validator keeps splitting the comma string.

On the shipped corpus alone, defects 1, 2, 3 and 8 change no graded value: band 0 is the first row of every table, its width is already even, no graded division lands on an exact half, and `ceil` equals rounding for its cycle spans. The three held-back grading corpora described under Verification are what make each of them cost reward, including corpus c3, whose minimum interval rounds to a different integer than `ceil` gives.

## Load-bearing work

Every graded value is derivable from `instruction.md` and the 62 files under `/app/data`, including `output_contract.md` (artifact shapes, the repaired tool's command surface and the `TASK_CTL_DATA` variable) and the README inside `tool.zip`. The base numbers live in `defaults.json`; every rule value lives in its own decoy-heavy file: geometry (`precision_ladder.tsv`, `aspect_table.csv`), clamps (`min_kbps.ini`, `max_kbps.properties`), cadence (`fps_num.ndjson`, `fps_den.jsonl`), effort per slot (`bpp.env`), efficiency (`eff_permille.conf`), ceiling ratio (`maxrate_ratio.toml`), granularity (`granularity.kv`), staircase and bounds (`qp_stair.psv`, `qp_base.txt`, `qp_floor_ceil.edn`), batch depth, sharding, rounding buffer, confidence target and helpers (`batch_frames.scsv`, `shard_cols.tsv2`, `shard_rows.csv2`, `dither_scale.caret`, `fidelity_target.tilde`, `threads.fixed`), ledger classes (`color_primaries.rst`, `color_transfer.sexp`, `color_matrix.html`), lookahead and pass count (`lookahead_seconds.conf2`, `pass_count.env2`), and the profile deltas (`env_overrides.json`). Deleting `/app/data` leaves nothing to derive from.

The work is a general repair: the delivered tool is run against corpora it has never seen, so a tool that reproduces the shipped answers without deriving them scores on the shipped artifacts only. The 23 artifacts under `/app/out` re-express or audit the same derivation, and their exact layouts are in `output_contract.md`.

## Verification

`tests/test_output.py` registers 39 rewardkit checks: 36 positive with weights summing to 76 and 3 negative summing to -11.

- Weight 5: `config_matches_derived_ladder`, `profile_dev_matches_derived`, `profile_prod_matches_derived`, and six runs of the delivered tool against held-back corpora: `tool_derives_held_corpus_c1`, `tool_derives_held_corpus_c2`, `tool_derives_held_corpus_c3`, `tool_profiles_held_corpus_c1`, `tool_profiles_held_corpus_c2`, `tool_profiles_held_corpus_c3`.
- Weight 3: `config_key_set_matches_spine`, `profile_delta_report_is_correct`.
- Weight 1: `artifacts_exist`, `artifacts_within_size_limit`, `allocation_chain_is_consistent`, `qp_follows_integer_staircase`, `report_matches_contract`, `tool_requires_a_subcommand`, `config_passes_the_tool_validator`, `validator_rejects_nested_config`, `tool_clamps_average_to_band_ceiling`, `gop_and_vbv_plans_are_correct`, `color_and_framerate_plans_are_correct`, `tiling_plan_is_correct`, `qp_curve_is_correct`, `bitrate_ladder_is_correct`, `ladder_solution_is_correct`, `rounding_audit_is_correct`, `ladder_ordering_is_correct`, `selection_trace_is_correct`, `validation_report_is_correct`, `summary_is_correct`, `reproducibility_manifest_is_correct`, `convergence_report_is_correct`, `derivation_provenance_is_correct`, `input_manifest_is_correct`, `tool_archive_is_deterministic`.
- Negative: `negative_hardcoded_answers` (-5, the delivered `cli.py` embeds the shipped corpus's derived reserve or ceiling numbers), `negative_nested_or_dynamic_config` (-3), `negative_network_access_in_tool` (-3, a network import or URL literal in the delivered `cli.py`, found by parsing it).

The held-back corpora are the shipped text files with their own `base_config` and with every decoy row moved ahead of the canonical rows. Corpus c1 has `max_records = 299`, `retry_limit = 35`, `timeout_ms = 1250` (band 2); corpus c2 has `max_records = 234`, `retry_limit = 2`, `timeout_ms = 1000` (band 4, whose width 1745 must be evened to 1746); corpus c3 has `max_records = 45`, `retry_limit = 37`, `timeout_ms = 1500` (band 3, whose cadence-scaled minimum interval rounds to 503 where `ceil` would give 504). Between them every defect above changes at least one graded value: half-up rounding (c1 reserve, c2 dev ceiling), odd width (c2), floor granularity (both), scale order (c1 dev), logarithm priority (all), reserve from the average (all), `ceil` cycle span (c1 dev), `ceil` minimum interval (c3), first-row or status-blind reads (all). The delivered tool runs as `nobody` under `setpriv` with a 60 second timeout, in its own process group, which is killed before the check returns. All comparisons of derived values are type-strict (every positive check uses the type-strict `_same` or an `int`-typed comparison), so `2350.0` or `True` never pass for an integer. The clamp to the band's allocation floor and ceiling is graded directly by `tool_clamps_average_to_band_ceiling`, which tightens a band's ceiling below its pre-clamp average, and the validator's flat-only rejection is graded by `validator_rejects_nested_config`. The transcript and the repeat run are graded against real runs, not only the agent's own claims: `report_matches_contract` replays every recorded init, set and validate step with the delivered tool in a scratch directory and requires the recorded return codes and stdout and a byte-identical `config.json`, and `convergence_report_is_correct` runs the delivered tool's derive twice on the shipped corpus and requires byte-identical outputs whose config equals the delivered `config.json`.

`tests/judge.toml` carries 15 binary criteria: 9 positive summing to 21 and 6 negative summing to -16. R1 and R2 grade running and reading the shipped tool before editing it; R3 to R6 grade naming the half-up rounding, logarithm priority, average-based reserve and first-row reads as defects; R7 grades running the repaired validator on `config.json`; R8 to R10 penalise installing a third-party package, leaving extra files under `/app/out` and writing `config.json` outside the repaired tool; R11 and R12 penalise unsupported numbers and success claims; R13 penalises weakening the validator; R14 and R15 judge the repaired `cli.py` for explicit error handling and for no dead or duplicated derivation code.

`tests/reward.toml` gives each channel half of the final reward: `test_output` weight `0.5 / 76` and `judge` weight `0.5 / 21`.

## Root cause

The tool was written against a floating-point prototype and a single-band, canonical-first corpus. Floats bring half-up rounding and float logarithms, and the first-row assumption plus the literal constants only hold for band 0 in the shipped file order. The fix is to compute only in integers with round-half-even from the remainder, select the active band and its canonical row in every table from the directory the tool is pointed at, and repair the tool's shape and control flow: a flat config, a required subcommand, the reserve from the ceiling allocation, the staircase priority, and profile scaling before clamp and granularity.

## Solution shape

`solve.py` extracts `tool.zip` into `/app/tool` with path and symlink guards, runs the shipped tool and checks its source for each of the ten defects, then writes the repaired `cli.py` in place. The repaired tool reads its rule files from `TASK_CTL_DATA` or `/app/data`, computes the band inputs once in `band_inputs()`, runs one shared `allocation_chain()` for the main config and both profiles, and exposes `derive`, `profile`, `init`, `set`, `validate` and `export-report`. The oracle drives `derive` twice and confirms the two outputs are byte-identical, assembles `config.json` with `init` and one `set` per key, validates it, exports the report, derives both profiles through `profile`, repackages the tool into `/app/out/tool.zip` with sorted members and fixed timestamps, and writes the remaining artifacts from the tool's values.

## Ordered plan

1. Extract the tool, run it, and read `cli.py` to list the ten defects and the schema drift.
2. Repair `cli.py`: integer round-half-even, even width, rounding onto the canonical granularity, scale before clamp and granularity in profiles, staircase priority, reserve from the ceiling allocation, rounded cycle spans, active-band canonical rows from the directory being read, a required subcommand, a flat config.
3. Run `derive` twice and compare the outputs.
4. Assemble `config.json` through `init`, one `set` per key, `validate`, and `export-report`.
5. Derive the dev and prod profiles through `profile` and write the signed delta report.
6. Package the tool deterministically and write every sidecar artifact.

## Pitfalls

- Trusting a decoy row, or the first matching band row without checking its status.
- Keeping the shipped literal constants, which only match band 0.
- Computing the priority step from a float logarithm.
- Building the reserve from the average allocation.
- Scaling a profile after quantisation.
- Copying `sample_config_dev.json` or `sample_config_prod.json`; the profile deltas live in `env_overrides.json`.
- Emitting a nested `ladder` object, or leaving the subcommand optional.
- Any timestamp, uuid or unsorted output that breaks reproducibility.

## Provenance

```yaml
instance_id: ceab1cf6-7fe5-5824-8acf-a7485e2eb1cd
task_name: terminal-bench/ceab1cf6-7fe5-5824-8acf-a7485e2eb1cd
trailer_token: harbor:cli-config:TASK:00000000013500bb
solve_py_sha256: 6dbfb7e8d5ced03617e149664154fc91ba55c62743beac2e1dce4b8aee97cb9e
test_output_py_sha256: 0b059a026dd3d04f1552d24f295aded13f964d5e19c5ec2a37096e1df758818e
judge_toml_sha256: e72bd250039f009e9957a763fcd75dd86c18ba70ab2ab90692760d8c2544bd75
tool_zip_sha256: e188021cd844d35d446e540f91d44155dd5a46ad3bb2d1b443d577a93bb8cfa3
```
