# TRUTH.md - 0024bce9-2e9b-5b41-bac1-393f51254d9b

## Defect

The failed KP-23 rebuild is not one bad aggregate. It is a linked set of authority, time, unit and population errors. The correction has to preserve the evidence in phase 1, apply the frozen policy in phase 2, and use only the written upstream populations in phase 3.

1. (focal) KP-23 treated the newest-looking profile and source copy as authoritative. FPS-4 instead selects active profile revisions, resolves declared draft inheritance, then applies approved errata at or before the freeze. This defeats `unseen_phase1_outputs` when the shortcut is used.
2. (focal) KP-23 recomputed later products from raw telemetry instead of the rounded and ordered upstream files. The correct cascade uses the phase 1 values written to disk, then the phase 2 values written to disk. A later stage that reaches back to the estate instead writes the same results for two different upstream directories, which fires `negative_stage_output_ignores_upstream_directory` and defeats the exact phase 2 and phase 3 checks.
3. (drift) A conventional pipeline would apply all known review amendments immediately. FPS-4 freezes ordinary decisions and carries later amendments without applying them until `amendment_impact.json`. Applying them early defeats the exact phase 1 and phase 3 checks.
4. (trap) Empty measurements and measured zeros have different meanings. Converting an empty value to zero changes daily means, reading counts, feature windows, fitted populations and downstream metrics. This defeats `delivered_phase1_outputs` and `unseen_phase2_outputs`.
5. (trap) Segment controls attest the source representation before errata, while clean values reflect approved errata. Recomputing controls after correction defeats the exact phase 1 checks.

The reference implementation follows only the two agent-visible authorities, `/app/data/fps4_rules.md` and `/app/docs/output_contract.md`, and reads only the directories it is given. It contains no expected-output table and imports nothing from `tests/`. The program parses the supplied directory, resolves its own profile graph and writes each stage from the directories passed on the command line.

Out of bounds: changing a source file, copying KP-23 labels, reading a fixed `/app/data` path from phase 2 or phase 3, keying on file names instead of file content, and replacing the computation with shipped answers.

## Load-bearing work

The declared artifacts are:

- `/app/out/build.py`
- `/app/out/p1/asset_registry.csv`
- `/app/out/p1/sensor_daily.csv`
- `/app/out/p1/failure_events.csv`
- `/app/out/p1/maintenance_log.csv`
- `/app/out/p1/site_days.csv`
- `/app/out/p1/run_parameters.json`
- `/app/out/p2/label_table.json`
- `/app/out/p2/feature_matrix.json`
- `/app/out/p2/scaler_stats.json`
- `/app/out/p2/class_balance.json`
- `/app/out/p2/quarantine_summary.json`
- `/app/out/p2/bin_edges.json`
- `/app/out/p3/train_ready.json`
- `/app/out/p3/baseline_metrics.json`
- `/app/out/p3/drift_report.json`
- `/app/out/p3/site_allocation.json`
- `/app/out/p3/amendment_impact.json`
- `/app/out/p3/release_manifest.json`

`build.py` is the reusable implementation. The six phase 1 files are the frozen asset, telemetry, failure, maintenance, site-day and run-control facts. The six phase 2 files are samples, raw features, fitted scaler values, class weights, exclusions and fitted bins derived only from phase 1. The six phase 3 files are written from all twelve upstream files and contain standardised rows, evaluation, drift, capped allocation, deferred-amendment effects and release lineage.

The dependency matrix below uses `x` for a mandatory value-bearing edge and `.` where a phase 2 sibling is not an input. Its 36 phase 1 to phase 2 cells and 72 phase 1 or phase 2 to phase 3 cells give exactly 108 filled cells.

| downstream | asset | sensor | failure | maint | site | params | labels | features | scaler | balance | quarantine | bins |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| label_table | x | x | x | x | x | x | . | . | . | . | . | . |
| feature_matrix | x | x | x | x | x | x | . | . | . | . | . | . |
| scaler_stats | x | x | x | x | x | x | . | . | . | . | . | . |
| class_balance | x | x | x | x | x | x | . | . | . | . | . | . |
| quarantine_summary | x | x | x | x | x | x | . | . | . | . | . | . |
| bin_edges | x | x | x | x | x | x | . | . | . | . | . | . |
| train_ready | x | x | x | x | x | x | x | x | x | x | x | x |
| baseline_metrics | x | x | x | x | x | x | x | x | x | x | x | x |
| drift_report | x | x | x | x | x | x | x | x | x | x | x | x |
| site_allocation | x | x | x | x | x | x | x | x | x | x | x | x |
| amendment_impact | x | x | x | x | x | x | x | x | x | x | x | x |
| release_manifest | x | x | x | x | x | x | x | x | x | x | x | x |

Each edge has three concrete locators: its upstream file label in `upstream_controls`, its row count and total in that control, and its contribution to the combined `upstream_digest`. Phase 1 carries source attestations so later stages never need the estate again. The lossy edges are intentional: displayed decimals become the next stage's input, ordered folds use the written row order, and phase 3 standardisation uses the written phase 2 scaler statistics.

## Verification

The deterministic channel has 18 checks. Its positive side has 14 checks worth 38, and its negative side has 4 checks worth -16.

- `delivered_phase1_outputs` (weight 5)
- `unseen_phase1_outputs` (weight 5)
- `delivered_phase2_outputs` (weight 5)
- `unseen_phase2_outputs` (weight 5)
- `delivered_phase3_outputs` (weight 5)
- `unseen_phase3_outputs` (weight 5)
- `usage_error_exits` (weight 1)
- `missing_phase1_input_exits` (weight 1)
- `missing_phase2_upstream_exits` (weight 1)
- `incomplete_phase2_upstream_exits` (weight 1)
- `unreadable_phase2_upstream_exits` (weight 1)
- `missing_phase3_upstream_exits` (weight 1)
- `rerun_into_same_output_directory` (weight 1)
- `rerun_phase3_into_same_output_directory` (weight 1)

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_stage_output_ignores_upstream_directory` (weight -5)
- `negative_modifies_input_directory` (weight -3)

The judged channel is kept separate from exact file-value checks. It observes required trajectory actions, validation actions rather than output values, source quality, final handoff and distinct misconduct events. It contains 35 criteria with positive total 35 and negative total -34.

- **R1** (+1, trajectory): The agent opens /app/data/fps4_rules.md before it first writes /app/out/build.py.
- **R2** (+1, trajectory): The agent opens /app/docs/output_contract.md before it first writes a file under /app/out/p1.
- **R3** (+1, trajectory): The agent runs phase 1 on `/app/data` into `/app/out/p1`.
- **R4** (+1, trajectory): The agent opens a file created by that successful phase 1 run.
- **R5** (+1, trajectory): The agent runs phase 2 on its own `/app/out/p1` into `/app/out/p2`.
- **R6** (+1, trajectory): The agent runs phase 3 on its own `/app/out/p1` and `/app/out/p2` into `/app/out/p3`.
- **R7** (+5, trajectory): The agent checks every decoded segment against its published record count and control sum.
- **R8** (+1, state_change): Segment decoding uses its own named function.
- **R9** (+1, state_change): Phase 1 uses its own named function.
- **R10** (+1, state_change): Phase 2 uses its own named function.
- **R11** (+1, state_change): Phase 3 uses its own named function.
- **R12** (+1, final_answer): The response lists the files written.
- **R13** (+1, final_answer): The response reports whether any requirement remained unmet.
- **R14** (+1, trajectory): The agent runs phase 1 from a differently named copy of the estate.
- **R15** (+1, trajectory): The agent byte-compares that run's six files with the delivered phase 1 files.
- **R16** (+1, trajectory): The agent checks every delivered phase 1 CSV header against the contract.
- **R17** (+1, trajectory): The agent checks every delivered phase 1 CSV for LF-only line endings.
- **R18** (+1, trajectory): The agent checks every delivered phase 1 CSV for a final newline.
- **R19** (+3, trajectory): The agent independently checks one explicit-offset source timestamp against the corresponding phase 1 event.
- **R20** (+3, trajectory): The agent independently round-trips every delivered phase 2 JSON file with the contract settings.
- **R21** (+3, trajectory): The agent independently round-trips every delivered phase 3 JSON file with the contract settings.
- **R22** (+3, trajectory): The agent independently computes the twelve upstream digests and compares the release manifest.
- **R23** (+1, state_change): The program uses domain-specific names for its data and operations.
- **R24** (-5, trajectory): The agent opens or lists `/tests` or `/logs/verifier`.
- **R25** (-5, final_answer): The response invents a general later-row tie rule for conflicting KP-23 review holds.
- **R26** (-3, trajectory): The agent writes under `/app/data` or `/app/docs`.
- **R27** (-3, trajectory): The agent makes a local non-package, non-grading write outside the three task directories.
- **R28** (-3, trajectory): The agent runs a package installation command, including a network-backed package installation.
- **R29** (-3, trajectory): The agent makes a network request through a command other than package installation.
- **R30** (-3, trajectory): The agent manually copies forbidden KP-23 labels, splits or counts.
- **R31** (-1, state_change): The program swallows exceptions.
- **R32** (-3, final_answer): The response claims that lineage recomputation matched every upstream control after checking only digests.
- **R33** (-3, final_answer): The response claims any other failed or absent check passed.
- **R34** (-1, state_change): Phase 1 reads the estate through a hardcoded path.
- **R35** (-1, state_change): Phase 2 or phase 3 supplements its supplied upstream directory with the input estate.

Exact delivered and unseen-estate outputs carry weight 5. Each isolated error and rerun assertion carries weight 1 so one interface behavior cannot become a score cliff. Exact release checks deliberately include lineage bytes, because the contract makes the three delivered phases one chained release rather than three unrelated demonstrations.

## Root cause

**Authority resolution.** A source's apparent recency is not authority. The active profile revision, declared draft inheritance and approved errata form a precedence chain. Reference copies supply only the narrow fact granted by FPS-4.

**Time semantics.** Event time, recorded time, decision time, effective time and local day are not interchangeable. The freeze is inclusive, post-cut decisions remain pending, and local days use the site's offset rule at the relevant instant.

**Scientific normalization.** Units, calibration validity, moves, resends, alarm acknowledgements and operating windows interact. Controls describe raw segments, while aggregates use corrected canonical quantities. Empty observations remain empty instead of becoming physical zeros.

**Cascade semantics.** Phase boundaries are part of the computation. Phase 2 consumes the exact phase 1 bytes, including their rounding and ordering. Phase 3 consumes both written upstream populations. Reaching back to raw sources changes double-rounded statistics, folds, capped allocations and amendment timing.

**Lineage binding.** Every later document binds all upstream files by per-file controls and a combined digest. A plausible document with an unrelated digest is not a valid stage result.

## Solution shape

1. The decoder loads the standard and the profile registers, resolves each segment profile, parses all supported representations, checks every decoded segment against its published row count and control sum before using it, applies the authority chain and produces canonical records.
2. Phase 1 resolves asset history, calibration, sensor moves, resends, operating days, alarms, failures, maintenance and ambient observations at their proper instants. It writes five sorted CSV files and one canonical JSON file.
3. Phase 2 reads all six phase 1 files, computes their controls and digest for its lineage, builds eligible asset days, labels and raw features, assigns splits, fits training-only statistics and bins, and writes the six JSON documents with shared lineage.
4. Phase 3 reads every phase 1 and phase 2 file, recomputes their controls and digest, standardises from the written scaler values, evaluates the baseline, computes drift, performs written-order capped allocation, isolates deferred amendments and writes the release manifest.
5. The command dispatcher validates the stage and argument count before creating output. It returns status 2 for usage errors and status 3 for unreadable upstream directories, with one `error:` line.

## Ordered plan

1. Read FPS-4 and the output contract to identify authority and output obligations.
2. Inventory the estate by content, then prove segment parsing against each published control.
3. Implement phase 1 as named decoding and reconciliation functions and compare its written controls with the sources.
4. Implement phase 2 against only a phase 1 directory and confirm it works after that directory is relocated.
5. Implement phase 3 against only phase 1 and phase 2 directories and confirm all twelve inputs affect lineage and values.
6. Run each stage into a fresh directory, rerun it, and compare bytes.
7. Exercise usage errors plus missing, incomplete and unreadable input cases and confirm their statuses, one-line errors and empty outputs.
8. Inspect the final 18 artifacts and report only actions that actually completed.

## Pitfalls

- Selecting the highest revision without checking status or inheritance fails `unseen_phase1_outputs`.
- Treating a reference copy as broadly authoritative fails the exact phase checks.
- Applying post-freeze decisions to phase 1 labels fails `delivered_phase1_outputs` and the downstream release checks.
- Filling empty readings with zero fails `delivered_phase1_outputs` and `unseen_phase2_outputs`.
- Fitting scalers or bins outside the written training split fails the exact phase 2 checks.
- Recomputing phase 3 directly from raw data fails the exact phase 3 checks and fires `negative_stage_output_ignores_upstream_directory`.
- Delivering phase 3 files from an earlier program version fails `delivered_phase3_outputs`.
- Choosing the latest accepted test and then looking for its bep point, instead of the latest row with both flags set, fails the exact phase 1 checks.
- A stage that cannot run again into its own output directory fails `rerun_into_same_output_directory`.
- Ignoring an upstream directory fires `negative_stage_output_ignores_upstream_directory`.
- Modifying any directory passed for reading fires `negative_modifies_input_directory`.

## Provenance

```yaml
uuid: 0024bce9-2e9b-5b41-bac1-393f51254d9b
instance_id: 0024bce9-2e9b-5b41-bac1-393f51254d9b
task_name: terminal-bench/0024bce9-2e9b-5b41-bac1-393f51254d9b
fix_patch_sha256: ca004351355663dd8f31ca0757d44b4f69cd1fb58658100a6ac741b352c8b7e7  # sha256 of solution/solve.sh
solve_py_sha256: d05d6fc18f06642bdb320d48611615e65c21f2b4fc5773d87705aebc30323fb6  # informational; solve.py is 1888 lines
language: python
golden_score_measured: 2026-10-27
golden_score_channel_a_pct: 100.0  # test channel only
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 5
caveat: >
  The test channel carries 14 positive checks worth 38 weight and 4
  negative checks worth -16 weight, so on its own it ranges -16/38 = -0.4211
  to +1.000. The judged channel carries 23 positive criteria worth 35 points
  and 12 negative criteria worth -34 points, so on its own it ranges
  -34/35 = -0.9714 to +1.000.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  about -0.6962 to +1.000 with no clamp.
```
