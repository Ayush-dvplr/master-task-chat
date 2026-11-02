# TRUTH.md - depot-charge-plan

## Defect

There is no broken program to repair. `/app/data` holds 13 files
(21860 lines) describing one evening at a city bus operator: a fleet register, a
duty roster, next-day trips, bus types, four depots with charging cabinets, a grid feeder
shared by all four depots, service classes and contracts, a tariff with dated versions, a
settled meter history, the published plan and a disruption notice. The rule register is
`/app/data/docs/charging_rules.md` (rules 1 to 22). The deliverable is
`/app/out/derive_report.py`, a program that builds the one day plan the rules define and
writes nine JSON reports, and that is run again on fresh data folders in the same layout.

The shipped folder is a weak instance: the cabinets never bind, the feeder binds only in
the derated window of the disruption notice (so the plan there differs from the published
plan), three depot meters apply the tariff as written and the East meter reads it shifted by 28
slots, which its settlements pin uniquely. The fresh folders are not degenerate, and three
rules decide them:

- (focal) Meter convention, charging_rules.md:27: each depot's meter applies the tariff with its own
  fixed convention, the one under which every `settlements.csv` row of that depot is billed
  exactly its cents by the version in force on its settled date. The convention is a
  whole-slot shift of the tariff (0 to 95, wrapping past midnight); on fresh folders it is a
  different non-zero shift per depot, and the settlements allow exactly one. A program that prices slots with the tariff as written plans every fresh
  folder at the wrong prices.
- (focal) Shared limits, charging_rules.md:22 and charging_rules.md:23: per slot, a depot draws at most its
  cabinets in service times the cabinet kWh, and all four depots together draw at most
  the feeder limit (derated slots from the disruption notice replace it). Planning each
  bus or each depot on its own breaks a limit or loses energy.
- (focal) Order of goals and tie-break, charging_rules.md:33 and charging_rules.md:34: least class-weighted
  unmet energy, then least cost, then least moved energy, and among plans still equal the
  one whose kWh list in slot then bus id order is greater at the first difference. On
  fresh folders many plans tie on all three goals; only the stated tie-break picks one.
- (drift) The shipped folder shows the three only weakly: one meter is shifted, the feeder
  binds in one derated window and the tie-break never decides, so a program checked only
  against the shipped reports looks finished.
- (trap) The published plan looks like a starting point to repair. It only enters the
  third goal (moved energy, charging_rules.md:29); copying or patching it is not the optimum once
  the limits bind.

## Load-bearing work

1. Read the plan day: `grid.ini` gives the plan date, the first slot (12:00), 15-minute
   slots and 96 slots; spans "from X to Y" cover slots starting at or after X and before Y
   (charging_rules.md:8).
2. Accept roster rows in the stated rejection order (charging_rules.md:13): unknown_vehicle,
   retired_vehicle, duplicate_roster_row, bad_window; window and depot from the accepted
   row (charging_rules.md:14); type rate and reserve from `bus_types.json` (charging_rules.md:15).
3. Need = trips of the day after the plan date + extra trips for that date in the notice +
   reserve - arrival charge, floored at 0 (charging_rules.md:16); class through `contracts.json`,
   unlisted or blank = commercial (charging_rules.md:17); weights from `service_classes.ini`.
4. Fit each depot's meter convention to `settlements.csv` under the tariff version in force
   on each settled date and price the plan day with the current version through it
   (charging_rules.md:27; `solve.py:205`).
5. Build the plan for all four depots together under the per-bus rate, cabinet and feeder
   limits and the lexicographic order, then settle ties by the stated list order
   (`solve.py:423`, `solve.py:469`).
6. Write the reports in the exact schemas of rules 17 to 21 (`solve.py:525`).
7. Stop with a non-zero exit and a message naming the file when a declared input is
   missing or unreadable (charging_rules.md:48; `solve.py:610`).

## Verification

Grader entrypoint: `tests/test.sh`, which runs
`rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit scores
the test channel from the `@criterion` checks in `tests/test_output.py`, each weighted by
its `criteria.<name>(weight=W)` registration, and the judged channel from
`tests/judge.toml`, read against `/logs/agent/trajectory.json`. `tests/reward.toml`
divides each channel's weighted sum by its positive total and gives each half of the
reward.

The test channel declares 45 positive checks (positive weight total 197) and
3 negative checks (total -9). The fresh folders are generated inside
`tests/test_output.py` from seeds that live only there (three regular folders h1 to h3 and
one larger folder h4, plus one folder placed several folders deep and one placed at
`/app/data` for a run of the bare command with no flags) and the delivered program is run on
each as an unprivileged user from a foreign working directory with the stated command and
a 120 second limit. Every document
is compared whole with the reference; the message names the first differing path. The
generated tier of 160 weight (weight 5 checks) is 81.2% of
the positive weight; all checks that run the program on generated or altered folders hold
91.9%.

Positive checks (45):

- `program_and_reports_present` (weight 1)
- `shipped_policy_audit_exact` (weight 3)
- `shipped_summary_exact` (weight 3)
- `shipped_data_quality_exact` (weight 3)
- `shipped_segment_public_exact` (weight 3)
- `shipped_region_east_exact` (weight 3)
- `fresh_h1_policy_audit_exact` (weight 5)
- `fresh_h1_region_north_exact` (weight 5)
- `fresh_h1_region_south_exact` (weight 5)
- `fresh_h1_region_west_exact` (weight 5)
- `fresh_h1_region_east_exact` (weight 5)
- `fresh_h1_segment_commercial_exact` (weight 5)
- `fresh_h1_segment_public_exact` (weight 5)
- `fresh_h1_summary_exact` (weight 5)
- `fresh_h1_data_quality_exact` (weight 3)
- `fresh_h2_policy_audit_exact` (weight 5)
- `fresh_h2_region_north_exact` (weight 5)
- `fresh_h2_region_south_exact` (weight 5)
- `fresh_h2_region_west_exact` (weight 5)
- `fresh_h2_region_east_exact` (weight 5)
- `fresh_h2_segment_commercial_exact` (weight 5)
- `fresh_h2_segment_public_exact` (weight 5)
- `fresh_h2_summary_exact` (weight 5)
- `fresh_h3_policy_audit_exact` (weight 5)
- `fresh_h3_region_north_exact` (weight 5)
- `fresh_h3_region_south_exact` (weight 5)
- `fresh_h3_region_west_exact` (weight 5)
- `fresh_h3_region_east_exact` (weight 5)
- `fresh_h3_segment_commercial_exact` (weight 5)
- `fresh_h3_segment_public_exact` (weight 5)
- `fresh_h3_summary_exact` (weight 5)
- `fresh_h3_data_quality_exact` (weight 3)
- `fresh_h4_policy_audit_exact` (weight 5)
- `fresh_h4_region_north_exact` (weight 5)
- `fresh_h4_region_south_exact` (weight 5)
- `fresh_h4_region_west_exact` (weight 5)
- `fresh_h4_region_east_exact` (weight 5)
- `fresh_h4_segment_commercial_exact` (weight 5)
- `fresh_h4_segment_public_exact` (weight 5)
- `fresh_h4_summary_exact` (weight 5)
- `reordered_copy_policy_audit_exact` (weight 3)
- `relocated_fresh_summary_exact` (weight 3)
- `default_paths_run_summary_exact` (weight 3)
- `missing_settlements_stops_naming_file` (weight 3)
- `malformed_tariff_stops_naming_file` (weight 3)

Negative checks (3):

- `negative_outside_library_or_network_import` (weight -3)
- `negative_hardcoded_sample_answers` (weight -5)
- `negative_run_writes_outside_output_folder` (weight -1)

Judged channel: 17 criteria, positive weight 38, negative weight -15:

- `r1_small_feeder_witness` (weight 3)
- `r2_lowered_feeder_run` (weight 3)
- `r3_recompute_summary` (weight 3)
- `r4_recompute_region_limits` (weight 3)
- `r5_meter_uniqueness_witness` (weight 3)
- `r6_altered_copy_rerun` (weight 3)
- `r7_relocated_rerun` (weight 3)
- `r8_missing_input_run` (weight 3)
- `r9_exception_handling` (weight 3)
- `r10_lists_rejected_records` (weight 5)
- `r11_final_run_after_last_edit` (weight 3)
- `r12_unrun_check_claim` (weight -3)
- `r13_figure_differs_from_file` (weight -5)
- `r14_overstated_check_size` (weight -1)
- `r15_reads_grader_files` (weight -5)
- `r16_changes_data_folder` (weight -1)
- `r17_names_summary_figures` (weight 3)

Oracle: `solution/solve.sh` copies `solve.py` to `/app/out/derive_report.py`, runs it on
`/app/data` and then runs its embedded self-check stage, which prints `check <id> ok` and one
witness line for each of its nine self-checks. Expected test-channel score: 1.000 for the
oracle, 0.000 for a no-op run.

## Root cause

The rules are stated once each in the rule register; the difficulty is that the shipped
folder exercises the three deciding rules only weakly. A careful first program that
tries a few readings of the meter instead of every whole-slot shift (charging_rules.md:27), plans
buses in turn (the shipped limits bind only in one derated window) or takes the first optimal plan it finds
(the shipped optimum is unique) can match most shipped reports and still fails every
fresh document of the plan family. The coupling quantity is the
feeder load per slot of the joint optimum: it is carried into every depot file, both
segment files and the summary, so one wrong reading moves rows in every plan document.

## Solution shape

`solution/solve.py` (624 lines, standard library only):

- reading with named-file errors: `solve.py:25`, `solve.py:35`, `solve.py:77`;
- plan day and spans: `solve.py:87`, `solve.py:118`, `solve.py:131`, `solve.py:138`;
- tariff versions and meter fit: `solve.py:174`, `solve.py:198`, `solve.py:205`;
- buses, need, class, published plan and rejections: `solve.py:249`;
- cabinet capacity per depot and slot: `solve.py:322`;
- the joint plan: `solve.py:343` (capacitated network with successive shortest paths),
  `solve.py:423` (unmet energy priced above any cost, cost above moved energy) and
  `solve.py:469` (fixes slot then bus id positions in order, raising each as far as an
  equal-objective change allows);
- reports: `solve.py:507`, `solve.py:525`; entry point `solve.py:610`.

The heredoc inside `solution/solve.sh` is the oracle's self-check stage (missing and malformed input, a
two-bus witness on a 30 kWh feeder, a lowered-feeder copy, an altered copy, a relocated
copy, recomputation of the summary and the region limits, meter uniqueness).

## Ordered plan

1. Read `charging_rules.md` in full, then every data file it names.
2. Parse the plan day, spans, notice, tariff versions and settlements; fit one meter
   convention per depot and fail loudly if none or several fit.
3. Accept roster rows in the stated order and derive need, class, weight and the
   published kWh per slot.
4. Build one plan for all four depots with the per-bus, cabinet and feeder limits, by the
   stated order of goals, then apply the tie-break.
5. Write the nine reports; run once on `/app/data`.
6. Build small folders where the feeder, a cabinet and a tie actually decide, and a copy
   whose settlements only fit a shifted meter; check the plan against a hand result.

## Pitfalls

- (trap) Pricing slots with the tariff as written because three shipped depots' settlements
  agree with it (charging_rules.md:27).
- (trap) Planning one bus or one depot at a time; on fresh folders the shared feeder
  (charging_rules.md:23) and the cabinets (charging_rules.md:22) bind in many slots.
- (trap) Returning the first optimal plan found; the tie-break (charging_rules.md:33) decides on
  every fresh folder.
- (drift) Testing only against the shipped reports, where the limits and the tie-break never decide.
- Naming the wrong reason for a roster row that meets two rejection conditions at once
  (charging_rules.md:13 names the order), counting extra trips of other dates, keeping published rows
  outside the window, or
  ordering `data_quality.json` by anything but file then line (charging_rules.md:16, charging_rules.md:28,
  charging_rules.md:44).

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: depot-charge-plan
task_name: terminal-bench/depot-charge-plan
fix_patch_sha256: 5a972d0c198bc817f3c37c7c9e3d339153bede5c44efea10353529dcc8e4c0d0
solve_py_sha256: e32ec307086d43fa9198180c975eee89ebc7166f52d63720edac8487c1d81c6c
test_output_py_sha256: eb64acda51cd733eb4a278d96ed8cb3876c06941b42c5df4e9195e03fa77a387
judge_toml_sha256: fa935db2208941c4820f3061fe9c3ef5ab9a9c710322723b2efe6534447a276d
reward_toml_sha256: fa383a586a15d4c6950884c0f90ec5cf453d43beffe3e6d8682cef8613957651
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured on a harness trial. Local runs of the oracle score 1.000 and a
  no-op run scores 0.000 on the test channel in tests/test_output.py only; the
  judged channel has no oracle score.
caveat: >
  The test channel carries 45 positive checks worth 197 weight and
  3 negative checks worth -9 weight. The judged channel carries
  17 criteria worth 38 positive and -15 negative points.
  tests/reward.toml divides each channel's weighted sum by its positive total
  and gives each half of the reward.
```
