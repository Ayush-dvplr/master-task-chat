# TRUTH.md - f5fe93be-3ce1-5eb6-a1f5-8c4a8ea80703

## Defect

Nothing ships broken here: the agent writes the reconciler from the rule documents. What sinks a run is a set of wrong instincts that each still produce a well formed, believable scenario object. Each item names the check that catches it.

1. (focal) What went to air is decided by the `BUS=PGM` lines of the switcher log, not by `status=PLAYED` in the as-run logs. Chain A plays during failovers that never reached air, and both chains keep playing under `LIVE1` and `SLATE`. Trusting chain A or counting `PST` lines moves hundreds of spots between `AIRED`, `MISSED` and `PREEMPTED`. Caught by `heldout_spot_dispositions_exact`, `shipped_scenario_spots_exact` and every settlement check downstream.
2. (focal) Withheld straddle rule: a span that puts the other chain on air carries on to the copy and window checks when the partner play exists, is complete and sits within `sync_tolerance_frames` inclusive; otherwise `PARTIAL`. Only the `failover_straddle` records of the prior close decide it. Caught by `heldout_spot_dispositions_exact`, `boundary_fixture_dispositions_exact`, `heldout_third_channel_exact`.
3. (focal) Withheld window rule: the whole spot, `bc` to `bc + E`, must lie inside the daypart. The legacy runbook's start time reading is the common prior. Caught by `heldout_spot_dispositions_exact`, `shipped_scenario_spots_exact`.
4. (focal) Withheld tie rule: among admitted corrections sharing the highest `rev`, the `traffic` desk governs. Caught by `heldout_spot_dispositions_exact` (order line field) and `shipped_scenario_settlement_exact`.
5. (focal) Chain B labels are corrected by the latest `chain=B` probe at or before the uncorrected instant; `RELOCK` sets zero whatever it prints and `STALE` is skipped. Caught by `heldout_second_channel_exact` (40 frame drift, one frame tolerance) and `boundary_fixture_dispositions_exact`.
6. (trap) Drop frame counting: labels convert with the drop frame formula, `DROPPED_LABEL` lines are rejected, and a wrong count shifts UTC by up to 86 seconds against the switcher log. Caught by `heldout_rejects_exact`, `heldout_spot_dispositions_exact`.
7. (trap) Broadcast days open at `broadcast_day_start` (05:00:00 on `latency` and on the held out 25 fps channel), and a corrected chain B label one frame before the opening belongs to the previous broadcast date. Caught by `heldout_second_channel_exact`, `heldout_deliveries_exact`.
8. (trap) The cutoff is strict and per workload; a correction or amendment stamped exactly at it is late. `rev 0` corrections are drafts. Caught by `shipped_scenario_spots_exact`, `data_quality_exact`, `heldout_deliveries_exact`.
9. (trap) House ids normalize before comparison, aliases resolve as of the scheduled broadcast date, follow chains of two links, and an alias dated after the spot does not apply. Caught by `heldout_spot_dispositions_exact`, `data_quality_exact`.
10. (trap) Registry `frames` count master frames at `master_rate`; as-run `frames` count channel frames. Expected frames are `ceil(frames * nominal / master_rate)`. Caught by `shipped_scenario_spots_exact`, `exhausted_capacity_makegoods_exact`.
11. (trap) An `UNRESOLVED` spot is held off its commitment and is never a shortfall. Caught by `heldout_deliveries_exact`, `heldout_makegoods_exact`.
12. (trap) Billable is clamped per order line and broadcast date before summing; bonus never offsets another day. Caught by `heldout_deliveries_exact`, `perf_report_exact`.
13. (trap) Make-good units settle in priority, date, rate descending, order line, unit order, each into the first open break with room; spare is clamped at zero per break before any sum. Caught by `exhausted_capacity_makegoods_exact`, `heldout_makegoods_exact`, `bottleneck_analysis_exact`.
14. (trap) Commission is half up once per order line. Caught by `heldout_billing_and_totals_exact`, `perf_report_exact`.
15. (trap) Retraction removes lines before validation, identical lines collapse, and the first failing check gives the reason code. Caught by `heldout_rejects_exact`, `data_quality_exact`.
16. (drift) The retired runbook is internally consistent and wrong on eight points; following any of them is silent. Caught by the checks of items 1, 3, 4, 7, 12, 13 and 14, and by judge criterion R27.
17. (drift) A per record scan of the probe or break lists is correct but quadratic on the 28 day workload. Caught by `month_workload_within_time_budget`.
18. (trap) Record row order carries no meaning: the second held out directory ships every record file shuffled. Caught by `heldout_second_channel_exact`, `heldout_third_channel_exact`.

Trap incidence over the shipped corpus (five workloads):

| trap | firing records | graded value that changes |
|---|---|---|
| PGM authority | 2,005 spots whose disposition changes under a chain A only reading (closing figure 3) | `disposition`, deliveries, make-goods |
| PST decoys | 12,457 `BUS=PST` lines, 69 retakes | `disposition` when PST is read as PGM |
| failover and live windows | 92 failovers, 34 `LIVE1`/`SLATE` takes | `chain`, `disposition` |
| chain B as reference | 4,230 spots whose reference play is chain B | `broadcast_date`, window membership |
| B probe correction | 55 `RELOCK`, 71 `STALE` probe lines | `disposition` (closing figures 4 and 5) |
| drop frame and validation | 100 `DROPPED_LABEL`, 284 `BAD_TIMECODE`, 116 `MISSING_FIELD` lines | `rejects`, `disposition` |
| duplicates and re-airs | 1,253 repeated lines, 153 re-airs, 178 retracted lines | `data_quality`, `disposition` |
| window edges | 1,899 `OUT_OF_WINDOW`, 87 decided only by the whole spot reading | `disposition` |
| corrections | 4,320 reattributions, 1,043 drafts, 539 late, 462 equal rev desk ties | `order_line` |
| amendments | 447 late, 1,903 recorded after their effective date | `committed` |
| aliases | 6,799 spots resolved through an alias, 174 alias rows dated 2026, 95 lower case rows | `disposition` |
| master rate | 718 copies mastered at 25 fps, 67 with frames that do not divide evenly | `disposition`, make-good need |
| held spots | 388 `UNRESOLVED` | `held`, `shortfall` |
| capacity | 1,039 overbooked breaks, 3,524 breaks left at zero spare | `makegoods`, `bottleneck_analysis` |
| prior close | 548 aired straddles (complete and within tolerance), 282 window records out, 217 equal rev ties | the three settled readings |

Out of bounds: the agent is not asked to repair a shipped program, decode a format, recover lost data or infer a hidden constant. Every rule is stated in the five rule documents except three points that the prior close records decide uniquely. No expected output, checksum or worked composite example ships anywhere the agent can read.

## Load-bearing work

The ten artifacts are `/app/out/optimize.py`, `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json`, `/app/out/scenario_latency.json`, `/app/out/perf_report.json`, `/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json` and `/app/out/data_quality.json`.

- `optimize.py`: `reconcile(data_dir, workload)` and the CLI print the scenario object; it is run unprivileged on generated directories: a drop frame week with a summer time change, a 25 fps week with a 05:00 day start and shuffled rows beside a drop frame week on another zone, a boundary fixture, an exhausted capacity fixture and a 28 day workload.
- scenario files: `spots` (one per schedule row), `deliveries`, `makegoods`, `billing`, `rejects`, `totals`, exactly the program's output for `/app/data`.
- `perf_report.json`: workload rows, advertiser rows with `delivery_bps`, totals.
- `bottleneck_analysis.json`: per workload and daypart inventory after allocation, plus `worst`.
- `recommendations.json`: per order line make-good outcome and break span.
- `data_quality.json`: per workload counters, disposition partition, three identity residuals.

## Verification

`tests/test.sh` hardens the verifier and hands over to rewardkit. Reward is `0.5 * test fraction + 0.5 * judge fraction`.

Test channel: 27 checks, 19 positive with a positive weight total of 67 and 8 negatives with a total of -24.

Positive: `heldout_spot_dispositions_exact` 5, `heldout_deliveries_exact` 5, `heldout_makegoods_exact` 5, `heldout_billing_and_totals_exact` 5, `heldout_second_channel_exact` 5, `heldout_third_channel_exact` 5, `shipped_scenario_spots_exact` 5, `shipped_scenario_settlement_exact` 5, `heldout_rejects_exact` 3, `boundary_fixture_dispositions_exact` 3, `exhausted_capacity_makegoods_exact` 3, `perf_report_exact` 3, `bottleneck_analysis_exact` 3, `recommendations_exact` 3, `data_quality_exact` 3, `month_workload_within_time_budget` 3, `rollup_identities_hold` 1, `cli_matches_function` 1, `artifacts_parse` 1.

Negative: `negative_hardcoded_sample_answers` -5, `negative_ignores_workload_argument` -3, `negative_nondeterministic_output` -3, `negative_modifies_input_directory` -3, `negative_output_on_missing_input` -3, `negative_program_writes_files` -1, `negative_output_depends_on_input_path` -3, `negative_scenario_artifact_differs_from_program` -3.

Judge channel: 29 criteria, 21 positive totalling 81 and 8 negative totalling -26. R1 to R9 are the nine closing figures at weight 5; R10 to R18 are derivation evidence at weight 3; R19 is honest reporting; R20 judges the delivered code; R21 to R28 are negatives; R29 judges the quality of the delivered code at weight 3.

The tests-only oracle, recomputed in a scratch harness against this bundle's checks, scores 67 of 67 with no negative firing; an empty `/app/out` scores 0. No judged-channel oracle score exists.

Reference closing figures (total, largest workload, its count): `dropframe_as_nondrop` 62, burst, 32; `start_only_window` 87, visible, 21; `chain_a_always_on_air` 2005, peak, 528; `chain_b_uncorrected` 28, latency, 14; `relock_printed_offset` 15, latency, 8; `late_corrections_admitted` 497, visible, 127; `weekly_clamp_extra_billable` 752, peak, 177; `aliases_undated` 88, burst, 34; `unconverted_frames` 1499, latency, 798.

Traceability:

| requirement | artifact | checks (weight) | criteria |
|---|---|---|---|
| program path, function and CLI | optimize.py | cli_matches_function (1), artifacts_parse (1) | R20 |
| stdlib only, no installs | optimize.py | every held out run | R25 |
| unseen directories, parameters from input | optimize.py | heldout_second_channel_exact (5), heldout_third_channel_exact (5) | R20 |
| time budget on 28 days | optimize.py | month_workload_within_time_budget (3) | none |
| determinism | optimize.py | negative_nondeterministic_output (-3) | none |
| row order irrelevant | optimize.py | heldout_second_channel_exact (5), heldout_third_channel_exact (5) | none |
| path independence | optimize.py | negative_output_depends_on_input_path (-3) | none |
| writes nothing, missing input fails | optimize.py | negative_program_writes_files (-1), negative_output_on_missing_input (-3), negative_modifies_input_directory (-3) | none |
| PGM bus authority | scenario files | heldout_spot_dispositions_exact (5), shipped_scenario_spots_exact (5) | R14 |
| chain B correction | scenario files | heldout_second_channel_exact (5), boundary_fixture_dispositions_exact (3) | R15 |
| broadcast day start, drop frame | scenario files | heldout_deliveries_exact (5), heldout_rejects_exact (3) | R16 |
| cutoff | scenario files, data_quality | shipped_scenario_spots_exact (5), data_quality_exact (3) | none |
| prior close settlements | scenario files | heldout_spot_dispositions_exact (5), boundary_fixture_dispositions_exact (3) | R10, R11, R12, R13 |
| unresolved held | scenario files | heldout_deliveries_exact (5) | none |
| per day clamp | scenario files, perf_report | heldout_deliveries_exact (5), perf_report_exact (3) | none |
| make-good order | scenario files | heldout_makegoods_exact (5), exhausted_capacity_makegoods_exact (3) | none |
| commission rounding | scenario files | heldout_billing_and_totals_exact (5) | none |
| scenario files equal program output | scenario files | shipped_scenario_settlement_exact (5), negative_scenario_artifact_differs_from_program (-3) | none |
| roll-ups | perf_report, bottleneck, recommendations | perf_report_exact (3), bottleneck_analysis_exact (3), recommendations_exact (3) | none |
| identities from written files | data_quality | data_quality_exact (3), rollup_identities_hold (1) | R18 |
| exactness bar | all | every exact check | none |
| leave /app/data unchanged | none | none | R26 |
| no online lookup | none | none | none |
| no grader paths | none | none | R21 |
| closing figures | closing message | none | R1 to R9, R19, R22, R23, R24 |
| retired runbook not authoritative | none | the checks of Defect item 16 | R27 |

## Root cause

**Crux.** A spot's disposition sits where three clocks meet that never agree on their own (local drop frame labels, the skewed chain B clock and the UTC switcher log), and every settlement figure inherits it.

**Spine.** The per spot disposition and governing order line. Deliveries count `AIRED` spots, holds count `UNRESOLVED` spots, break occupancy counts occupying spots, make-goods consume what occupancy leaves, credits and billing follow the make-goods, and the four roll-ups sum all of it. One wrong spot class moves a deliveries row, which moves the make-good queue, which moves credits, net, the bottleneck table and the recommendation spans.

**Interaction matrix.** PGM authority interacts with chain B correction (B is the reference only while on air), with the straddle rule (the partner check concerns the other chain's on air segment) and with occupancy. Drop frame counting interacts with UTC conversion (switcher lookup), with the broadcast day start and with daypart bounds. Corrections interact with window membership (a reattributed spot changes daypart) and with the cutoff. Aliases interact with expected frames (the successor copy's master rate) and with `UNRESOLVED` holds, which interact with the commitment and the make-good queue.

**Withheld rule evidence.** Straddle outcome and tolerance: `failover_straddle` records in `prior_close_decisions.jsonl`, including complete partners exactly at the tolerance and labels across a skipped drop frame minute start. Window membership: `window_edge` records with a spot straddling the end, a spot straddling the start, exact fits and labels after local midnight. Correction ties: `correction_tie` records where the traffic version was recorded earlier and records where it was recorded later. Each point has exactly one surviving reading; the records carry outcomes only, never a graded quantity.

**Red lines.** No expected output, worked composite example or checksum ships to the agent. The verifier recomputes every compared value from its own embedded corpus and its own generated directories, and runs the delivered program as `nobody`.

## Solution shape

1. Read `channels.ini`, zones, dayparts, holidays, cutoffs, advertisers, registry, aliases, orders and admitted amendments.
2. Settle the three prior close points by scoring every candidate reading against every record and keeping the one that survives.
3. Load chain B probes (OK sets, RELOCK zeroes, STALE skipped) and the PGM timeline.
4. Load admitted corrections: retractions, then the governing reattribution per spot.
5. Parse both as-run logs: collapse identical lines, drop retracted lines, validate with the three reason codes, keep `PLAYED` lines, correct chain B, keep the earliest play per spot and chain.
6. Classify each scheduled spot through the seven step disposition order.
7. Build deliveries with holds and the per day clamp.
8. Compute break occupancy and spare, then settle make-good units through a max segment tree per daypart lane.
9. Bill per order line, total, and print the scenario object.
10. With `--rollup DATA_DIR NAME`, run the five workloads and print one of the four roll-ups. The program never writes a file: `solve.sh` redirects the printed scenario objects and roll-ups into the nine artifact files.

## Ordered plan

1. Read `corpus_index.md` and the five rule documents; note the three points left to the prior close.
2. Read `output_contract.md` for every key, order and the closing figures.
3. Write timecode helpers and check them on labels at minute 10 and minute 11 of a drop frame hour.
4. Score straddle readings against the `failover_straddle` records.
5. Score window readings against the `window_edge` records.
6. Score tie readings against the `correction_tie` records.
7. Parse `channels.ini`, zones and dayparts; implement the broadcast day mapping.
8. Implement probe correction from `*_sync_probes.log`.
9. Implement the PGM timeline from `*_switcher.log`.
10. Implement corrections and amendments from `*_corrections.jsonl` and `order_amendments.jsonl`.
11. Implement as-run parsing from `*_asrun_a.log` and `*_asrun_b.log`.
12. Implement the disposition order against `*_schedule.csv`, the registry and the aliases.
13. Implement deliveries, `*_breaks.tsv` occupancy and make-goods.
14. Implement billing and totals; run one workload and check the partition residual.
15. Write the five scenario files from the program's own output.
16. Write the four roll-ups and check the three identity residuals.
17. Time the program on a synthetic month built by repeating a workload; remove any per record scans.
18. Compute the nine closing figures by rerunning with one rule changed at a time and report them with the run that produced them.

## Pitfalls

| rank | failure mode | rule violated | caught by | weight at stake |
|---|---|---|---|---|
| 1 | start time window membership | withheld whole spot rule | heldout_spot_dispositions_exact, shipped_scenario_spots_exact, boundary_fixture_dispositions_exact and the settlement checks | 61 |
| 2 | trusting chain A status or PST lines | PGM authority | the same set | 58 to 61 |
| 3 | straddles always partial or an exclusive tolerance | withheld straddle rule | the same set, heldout_third_channel_exact | 58 to 61 |
| 4 | latest recorded correction wins | withheld tie rule | the same set | 61 |
| 5 | chain B labels used raw or the RELOCK printed value applied | probe rule | heldout_second_channel_exact and the shipped checks | 53 to 61 |
| 6 | calendar day attribution | broadcast day start | heldout_deliveries_exact and the shipped checks | 61 |
| 7 | unresolved spots counted as shortfall | held rule | heldout_deliveries_exact, heldout_makegoods_exact, roll-ups | 45 |
| 8 | weekly netting of bonus and shortfall | per day clamp | heldout_deliveries_exact, perf_report_exact | 31 |
| 9 | make-good order or same day placement | allocation order | exhausted_capacity_makegoods_exact, heldout_makegoods_exact | 40 |
| 10 | commission on the advertiser total | per line rounding | heldout_billing_and_totals_exact, perf_report_exact | 26 |

The top three together put more than a third of the 67 positive test weight at stake.

## Provenance

```yaml
uuid: f5fe93be-3ce1-5eb6-a1f5-8c4a8ea80703
instance_id: f5fe93be-3ce1-5eb6-a1f5-8c4a8ea80703
task_name: terminal-bench/f5fe93be-3ce1-5eb6-a1f5-8c4a8ea80703
fix_patch_sha256: c4f4725d37511b8a88727ef397b9f5d9ad3833c2e410fa8129383761e56e501e
solve_py_sha256: 81b16d4be1682cbdc72e37b900201ccbea7638086d68c6647a205772645a2245
language: python
status: ready
```
