# TRUTH.md - 12ce5ca8-825b-58b3-a3a5-3b19e34482a6

## Defect

Nothing is corrupted and nothing is hidden. `/app/data` holds a written contract
at `schema.md` plus 70 flat files spanning eighteen formats, and the deliverable
is an optimizer at `/app/out/optimize.py` together with ten exact artifacts. The
core defect is a numerically wrong precomputed rollup shipped as
`rollup_summary_prev.json`: it reports per-account energy usage, kWh figures, and
tariff costs that were produced by a legacy pipeline that made five interacting
computation mistakes. The task is faulty-computation correction, not recovery:
the authoritative inputs are all present and readable, but they are reachable
only through a dependency chain, and the correct numbers require the exact
algorithm documented in `schema.md`. A model that trusts the precomputed summary,
takes the first plausible coefficient file, or sums the vendor delta column will
produce confidently wrong artifacts. The workloads, coefficient tables, and
identifier space are drawn from a fixed canonical seed, so nothing below can be
recalled from training, and the grader regenerates the load-bearing corpus in its
own container from that same canonical seed and never reads `/app/data`.

1. (focal) The reporting window is half-open, `[window_start, window_end)`. A row
   is included when `window_start <= ts < window_end`. The legacy summary and the
   decoy `legacy_window_policy.txt` treat the window as inclusive on both ends,
   pulling an extra boundary row into any scenario that has one. In the shipped
   corpus the `visible` and `burst` windows (both ending at 9000) each carry two
   admitted rows sitting exactly on `window_end`, so the off-by-one shifts
   `event_count`, the totals and the rolling checksum for those two scenarios. It is defeated by
   `test_scenario_counts_and_checksums_match_reference` and the data_quality
   tests.

2. (focal) Per-account energy usage must be recovered from a cumulative meter that
   wraps at `meter_modulus`. Walking each account's windowed rows in admitted
   corpus order and starting from the walk start of item 7, usage
   accumulates `(meter - prev) % meter_modulus`.
   The shipped `energy_wh` column is the vendor's naive signed delta `meter - prev`
   with no modulus, so it goes negative on every rollover; summing it, as the
   legacy pipeline and `vendor_delta_dump.csv` do, undercounts by
   `wraps * meter_modulus`. The correct path ignores `energy_wh` entirely and
   recomputes from `meter`. This is the single hardest lever and is defeated by
   `test_hidden_*_workload` and
   `test_scenario_usage_and_energy_match_reference`.

3. (focal) The active coefficient set is chosen by supersession, not by first
   match. The binding ledger lists six candidate coefficient files: generation 1
   superseded, generation 2 active, generation 3 active (`coeff_active_g3.json`,
   whose name and `pipeline_run.log` both suggest it is current), a generation 3
   draft, generation 11 active, and a generation 12 draft. The rule is
   active-only, highest integer generation wins, so `coeff_rollup_g11.json`
   (label `ROLLUP-ACTIVE-G11`, `epsilon` weight 13) is authoritative for the
   parameters no dedicated role supplies (item 15); a string comparison of generations picks "3". A naive "first active row" pick lands on the generation 2
   hotfix `coeff_hotfix_g2.json`, which carries subtly different `kind_weights`,
   `region_offsets`, and an off-by-one `scenario_windows` entry. Using the wrong
   generation poisons every score. Defeated by
   `test_scenario_envelope_matches_reference`, the other
   `test_scenario_*_match_reference` tests and
   `test_data_quality_*_match_reference`.

4. (drift) Unit scaling from watt-hours to kilowatt-hours and the tariff cost are
   each a single rounding at the end, using `Decimal` with `ROUND_HALF_UP`.
   `account_energy_kwh = half_up(usage_wh, unit_divisor)` and
   `account_cost_cents = half_up(tier_sum, 10000)` (item 11), both computed once
   on the summed per-account usage. The legacy pipeline rounds per event and then
   sums, and `energy_export_kwh.tsv` mislabels an already-floored column as kWh.
   Rounding drift of a single cent fails
   `test_scenario_usage_and_energy_match_reference` or
   `test_scenario_cost_matches_reference`.

5. (trap) Tariff rates are basis points, not percent. The decoy
   `tariff_schedule_percent.json` presents a rate as `14.5` percent (with an
   `alt_tariff_bps_if_needed` of 1450) and invites feeding a percent where a bps
   rate belongs, which is off by a factor of one hundred. The active rates are the
   tiers of the `tiers_2025Q4` sheet of `tariff_book.xlsx` (item 15). Any model that binds the percent
   decoy fails `test_scenario_cost_matches_reference`, and a run that fabricates
   the performance figures rather than measuring them is caught by rubric
   criterion `R14`.

6. (focal) Row admission, schema.md section 3a. The raw corpus of
   2752 rows carries 72 vendor re-sends (repeated ids; some first occurrences lie
   at ts >= 9000, outside every window, with the re-send moved inside one; some
   re-send a quarantined row with a valid kind), 22 rows of retired kinds
   (`omega`, `zeta`, `Theta`, `kappa`), 9 rows of unknown regions, and ~260 fields
   with stray whitespace or wrong case. Normalise, then drop replays over the
   whole file (first occurrence wins, before quarantine and before the window),
   then quarantine unknown kinds, then apply the 40 void notices (item 13):
   2588 admitted. A first occurrence carrying the void flag is still an ordinary
   row; only a later replay carrying that flag is a notice. Dedup-within-window, last-write
   -wins (the `replay_journal.log` decoy) or quarantine-before-replay each change
   every scenario's counts, checksums and totals. Graded by
   `test_hidden_normalisation_workload`, `test_hidden_replay_workload`,
   `test_hidden_quarantine_workload`, the canonical scenario tests and
   `test_data_quality_admission_counts_match_reference`.

7. (focal) Meter walk start. Each account's walk starts from the meter of its
   last admitted row with ts < window_start (admitted corpus order), else from its
   `meter_seed_overrides` value (item 10), else `meter_seed`. The corpus spans ts
   600..9999, so every window, including `visible` and `latency` that start at
   1000, has pre-window readings. Graded by `test_hidden_meter_seed_override_workload`,
   `test_hidden_interaction_workload` and every canonical usage figure.

8. (trap) Meter order is admitted corpus order, not timestamp or id order. The
   generator advances each account's cumulative counter in ingestion order while
   assigning independent timestamps, so per-account timestamps routinely move
   backwards. Sorting readings produces plausible but much larger modular deltas.
   Graded by `test_hidden_meter_corpus_order_workload` and the canonical usage and
   cost tests.

9. (trap) Header-driven CSV reading. Shard 05 lists its columns in a
   different order plus an extra `ingest_batch` column, shard 02 has an extra
   quoted `note` column, shard 08 has a UTF-8 BOM and CRLF endings, shard 10 has
   blank lines. `aggregate` must read by header name; a positional reader that
   only ever sees the agent's own re-serialised corpus passes the scenario
   artifacts but fails `test_hidden_file_format_workload`.

10. (focal) Per-account meter seed overrides, ledger role `meterseeds`:
   generation 9 active, generation 10 active (`meter_seed_overrides_g10.json`,
   the winner), generation 11 draft. Its 15 keys are written loosely (`" a011"`,
   `"A017 "`, `"a024"`) and must be normalised like `account`. An override seeds a
   walk only when the account has no admitted pre-window reading, so its effect
   depends on the replay/quarantine and pre-window steps two hops earlier. In the
   shipped corpus one override account lacks a pre-window reading in the
   `visible` and `latency` windows; `test_hidden_meter_seed_override_workload`
   exercises the rule at scale.

11. (focal) Block tariff `tariff_tiers` `[[40000, 3050], [0, 1500],
   [12000, calibrate]]` from the tariff book (listed out of order; sort by
   start; the held-back rate is recovered as 2230, item 16). Each watt-hour is billed
   at its tier's rate and rounded once per account; `tariff_bps` is only the
   fallback when the key is absent (the visible sample, tie and shuffled-checksum
   tests use the fallback). Which tier a usage crosses depends on the anchored
   walk, so tier cost is the end of the override -> anchor -> usage -> tier chain.
   `tier_sum` is the sum over the sorted tiers of the watt-hours falling in each
   tier times its bps. Graded by `test_hidden_tiered_tariff_workload` and
   `test_scenario_cost_matches_reference`; `test_hidden_interaction_workload`
   combines items 6 to 11 on one unseen workload.

12. (trap) Unknown flags. Section 3a step 3 admits a row whose `flag` is not a
   key of `flag_penalties`: it scores with a penalty of 0 and gets its own
   `flag_counts` key. The shipped corpus carries no such flag, so a solver that
   indexes `flag_penalties[flag]` passes every canonical artifact and fails only
   `test_hidden_quarantine_workload`.

13. (focal) Void notices, section 3a step 2. The corpus carries 40 void notices:
   re-sends flagged `void` (written `void`, ` VOID`, `Void `), each withdrawing
   its admitted first occurrence. The contract states only the withdrawal; the
   consequences follow from "only admitted rows take part in anything in
   section 5": a withdrawn row leaves every total and the checksum, shifts the
   1-based checksum positions of every later windowed row, and when it was an
   account's last pre-window reading the walk start falls back to the previous
   admitted pre-window reading, else to the override, else to `meter_seed`. A
   single-pass reader that treats a void notice as an ordinary replay keeps the
   row. Graded by `test_hidden_replay_void_notice_workload`, the canonical scenario
   tests and `test_data_quality_admission_counts_match_reference`
   (`withdrawn_row_count` 30).

14. (focal) Cumulative tier position, section 5. The window's usage is billed at
   the tiers it occupies after the account's pre-window usage `pre_wh`, walked
   over its admitted pre-window rows from its override or `meter_seed`. The
   override therefore matters even for accounts that have a pre-window reading
   (it seeds `pre_wh`, while the window walk still starts at the reading), and
   void notices and replays change `pre_wh` too. Graded by
   `test_hidden_tier_position_workload` and `test_scenario_cost_matches_reference`.

15. (focal) Heterogeneous sources and precedence, schema.md sections 1, 3 and 4b.
   The ledger adds four roles. `regions` -> `region_registry.sqlite` (active
   rows north 12, south 17, east 23, west 29, central 31; retired and draft rows
   are decoys). `tariff` -> `tariff_book.xlsx`: the sheet rule picks
   `tiers_2025Q4` over the older `tiers_2025Q3` and the newer
   `tiers_2026Q1_draft`, and the superseded `tariff_schedule_2025.md` is a
   decoy. `seedaddendum` -> `meter_seed_addendum.docx`, whose table amends the
   generation-10 overrides (` a011` -> 2500, `A005 ` -> 7777 new, `A040` ->
   16500 new, `a072` removed; 16 overrides result). `policy` ->
   `admission_policy.yaml` (`void_flag: revoke`; the draft policy says `void`).
   The precedence rule makes the registry and the tariff book win over the
   stale `region_offsets` and `tariff_tiers` still inside `coeff_rollup_g11.json`.
   Shards 03 and 07 are pipe-separated `.psv` files (shard 03 with a reordered
   header), and shards 06 and 11 are `.ndjson` (integer-typed `ts`/`meter`, an
   extra key). A CSV-only shard reader stops at the first `.psv` shard. The
   held-out CSV and PSV workloads also write column names with surrounding
   whitespace, which section 3 says is not part of the name (canonical shards
   never do), so a reader keyed on raw header text loses every row there. Graded by
   every canonical test and `test_hidden_file_format_workload`.

16. (focal) Calibrated parameters, schema.md section 4c. `unit_divisor` appears in
   no source (the coefficient file no longer carries it; the decoy coefficient
   files say 1000), and the `tiers_2025Q4` sheet marks the 12000 Wh tier rate
   `calibrate`. Both are recovered from `calibration_controls.json` (ledger role
   `calibration`; generation 1 `calibration_controls_old.json` is superseded and
   points at 1000 and 2200): the smallest `D` with `half_up(U, D) == K` on every
   energy control is 1024, and the smallest tier rate reproducing every cost
   control is 2230. Held-out workloads hold back different values in the rules'
   `calibration` key (divisors 1013, 1009 and 1003 in the interaction, boundary-mix
   and alias-reset workloads, 21 in the zero-output case, and a tier rate above one
   million bps in the large-rate case), so a constant copied from the canonical
   corpus fails them. Graded by
   `test_hidden_calibrated_divisor_workload`,
   `test_hidden_calibrated_tier_workload`, the interaction workload and every
   canonical kWh and cost figure.

17. (focal) `resolve_rules(data_dir, scenario)`, schema.md section 6b. The
   module must also resolve a whole data tree into the rules object of one
   scenario. Held-out data trees each change one source representation that the
   contract allows but the shipped tree never uses: a tariff book with absolute
   part paths (/xl/worksheets/...) and cells without an `r` attribute; tier
   cells stored as text in shared strings; registry region names with stray
   case and whitespace plus an extra nullable column; addendum cells split
   across text runs; and a policy whose key and value are quoted and carry a
   trailing comment. Each tree also carries different values (other tiers and a
   regenerated calibration, other offsets, other amendments, `void_flag`
   `cancel`), so constants copied from the shipped tree fail. Graded by five
   checks, one per representation: `test_resolve_xlsx_absolute_parts`,
   `test_resolve_xlsx_text_numbers`, `test_resolve_region_registry_names`,
   `test_resolve_docx_split_runs` and `test_resolve_yaml_quoted_policy`.

18. (focal) The reusable rules contract has a second, independent layer that
   narrow implementations tend to skip: one-step aliases for all four textual
   dimensions, case-insensitive replay ids with arbitrary letter prefixes,
   void-marked first occurrences versus later replay notices, case-insensitive input column
   names, wildcard seed overrides, meter-reset rows, and per-account meter,
   energy and tariff profiles. The canonical corpus exercises aliases, forward
   voids, mixed-case ids and headers, resets, account-specific divisors and
   tariffs, and tariff credits. Separate held-out workloads isolate each rule.

Scenario cost totals (sum of account_cost_cents): visible 2117520, peak
1261661, steady 1742286, burst 1392986, latency 1765591.

Scenario score totals (sum of account_totals): visible 74565147, peak 17761861,
steady 27974330, burst 19529601, latency 35660583.

Expected corpus figures: corpus 2752, admitted 2588, replayed 112, quarantined
22, withdrawn 30; visible 2208 / 1635622438, peak 515 / 592422758, steady 818 /
1319450893, burst 587 / 1091379234, latency 1062 / 207770016 (event_count /
checksum).

## Load-bearing work

The submission must deliver a reusable stdlib module at `/app/out/optimize.py`
exposing `aggregate(events_path, rules_path)` and a two-argument CLI, plus ten
artifacts: `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`,
`/app/out/scenario_steady.json`, `/app/out/scenario_burst.json`,
`/app/out/scenario_latency.json`, `/app/out/perf_report.json`,
`/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json`, and
`/app/out/data_quality.json`. The five scenario artifacts are the corrected
rollup over five windows read from the active coefficient set; the four summary
artifacts describe the optimization, the bottleneck, the recommendations, and a
name census of every file under `/app/data`.

## Verification

The test channel has 37 checks: 33 positive with a positive-weight total of 123
(reward weight 0.5/123) and four negative tests (-5, -5, -5, -3; total 18).
Floor: first-occurrence void semantics 5, cli
canonical (with a byte-identical rerun) 3, scenario_envelope 1, config_reports
(with the measured ratio a float within the ceiling) 3, speed 3. Hidden
one-rule workloads at 5 each: first-occurrence voids, one-step aliases,
quarantine withdrawal counts, unknown flags, replay void notices, tariff-credit
clamping, zero-output divisor calibration, unbounded held-back tier recovery,
normalized per-account maps, tariff profiles, meter moduli, resets,
case-insensitive headers and keys, wildcard seeds, two fresh mixed-boundary
workloads, and the all-rules interaction workload. Held-out source checks cover
xlsx absolute parts and unreferenced cells, shared-strings tier cells, registry
region-name normalisation, split docx runs and quoted YAML.
Canonical corpus: counts and checksums 5, score totals 5, usage and kWh 5,
tiered cost 5, contract key sets with sorted-key JSON 1, data_quality file census
1, data_quality admission counts 5, and data_quality scenario checks 1.

The test runner executes the submitted module as `nobody` from a temporary copy
(directory 0755, files 0644); checks run one at a time under a global lock.

The judged channel has 36 criteria, positive total 68 (reward weight 0.5/68),
negative total 18 (R4 -3, R5 -3, R8 -1, R13 -5, R14 -3, R15 -3). Closing-message
and reproducibility checks carry weight 1; the two instruction constraints carry
weight 3. The load-bearing independent-rescan validation carries weight 5. The
remaining behavior criteria cover edited-source probes for absolute xlsx paths,
xlsx cells without coordinates and ordered seed removals, plus compact workloads
for admission, meter, calibration, tariff, ordering and rollover boundaries.

All scores quoted for the oracle are test-channel scores: the reference solution
scores 123 of 123 on the tests. No judged-channel oracle score exists.

## Root cause

The legacy rollup was computed by a pipeline that (a) treated the reporting window
as closed on both ends, (b) summed the vendor `energy_wh` delta column instead of
recovering usage from the wrapping meter, (c) sorted cumulative readings by event
time instead of preserving their ingestion order, (d) bound the first active
coefficient row rather than the highest active generation, (e) rounded units and
tariff per event before summing, and (f) read the tariff as a percent. Each mistake alone is
plausible; together they compound so that no single decoy value can be trusted and
the only reliable path is to resolve the chain and recompute exactly.

## Solution shape

Read `schema.md`. Resolve the chain: read the catalog reference out of
`ingest_handoff_notes.txt`, open the referenced sqlite catalog, look up the
`binding_registry` key to reach the binding ledger, apply the supersession rule to
pick the active highest-generation coefficient file, segment manifest, meter
seed overrides and the six configuration files, drop superseded manifest
entries, sort the remaining segments by sequence, and concatenate the shard CSVs
in that order, reading each by column name in its own format (CSV, PSV,
NDJSON). Read the dedicated sources (region registry, tariff book sheet, seed
addendum, admission policy) and let them win over the coefficient file's copies. Implement one fast single-pass
`aggregate()` that reads its events file by header name, admits rows by section
3a (normalise, drop replays over the whole file, withdraw rows named by void
notices, then quarantine unknown kinds),
applies each alias once, distinguishes void-marked first occurrences from replay
void notices, filters on the half-open
window, groups the account, region, and kind totals and
flag counts, folds the order-dependent checksum over the windowed rows in file
order, walks each account's meter in admitted corpus order from its pre-window
reading, exact or wildcard override, or seed, honors reset rows and per-account
moduli, and applies the single end-of-pipeline `half_up` rounding for kWh and
the applicable per-account or default tariff billed from the credited
cumulative tier position. Build all ten artifacts
with canonical sorted-key JSON.

## Ordered plan

1. Parse `schema.md` for the resolution order and the corrected algorithm.
2. Resolve the entrypoint, catalog, ledger, coefficient set, manifest, and shards.
3. Discard the generation 1, generation 2, and draft coefficient decoys.
4. Implement `aggregate()` as a fast structural pass matching the contract exactly,
   including row admission, the walk start and the block tariff, and probe it on
   hand-built edge cases such as a quarantined id that is re-sent later.
5. Compute the five scenario artifacts over the five active windows.
6. Compute the four summary artifacts, using the file-name census for data quality.
7. Deliver a stdlib-only module, measure the relative median from outside it with
   warmups and repeated batches, and write that measured ratio into the report.

## Pitfalls

Trusting `rollup_summary_prev.json`; summing `energy_wh`; binding
`coeff_hotfix_g2.json`; reading `tariff_schedule_percent.json` as percent; using an
inclusive window end; rounding per event; reordering rows before the checksum
fold; importing non-stdlib modules; reading a clock inside `optimize.py` rather
than benchmarking from outside it; writing an assumed constant into
`observed_relative_median` rather than the ratio the run actually measured;
reading shard columns by position; deduplicating replays only inside the window
or keeping the last write; quarantining before replay detection; sorting meter
readings by timestamp or id; comparing ledger generations as strings; seeding every walk from `meter_seed`; using the
raw override keys; treating wildcard seeds as exact keys; missing replay void
notices; using the global meter modulus, energy divisor or tariff for every
account; charging reset rows as usage; and billing the whole usage at one tier
rate.

## Provenance

```yaml
uuid: 12ce5ca8-825b-58b3-a3a5-3b19e34482a6
instance_id: 12ce5ca8-825b-58b3-a3a5-3b19e34482a6
task_name: terminal-bench/12ce5ca8-825b-58b3-a3a5-3b19e34482a6
solve_py_sha256: 74d227fadacbc3bdaf9c42e87e0ed5ee8d9dfb3742072d495bf677687bf28f02
language: python
```
