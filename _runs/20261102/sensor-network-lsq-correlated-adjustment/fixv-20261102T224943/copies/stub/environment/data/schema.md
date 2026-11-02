# SNLSQ Data Contract (authoritative)

This extract describes one district geodetic sensor-network adjustment. This
document is the contract for reading the extract and for the reports derived
from it. All load-bearing arithmetic is exact: the design coefficients are
shipped as exact rationals, so no trigonometry, square root or floating point
is needed for any reported figure.

## 1. The unknowns and the network

The unknowns are per-station coordinate corrections `dx, dy` in metres for the
six stations, in this fixed order: `ALPHA, BRAVO, CIVET, DELTA, EAGLE, FICUS`.
The unknown index of a station's `dx` is `2*ordinal`, of its `dy` is
`2*ordinal+1` (ALPHA ordinal 0 ... FICUS ordinal 5), giving 12 unknown columns.
`station_registry.csv` lists each station's exact nominal coordinates as
`nominal_x_num/den` and `nominal_y_num/den` (the `display_coord_*` columns are
rounded for reading), and the instrument setup of the campaign in `mount` and
`centring_mm`. Rows with `mark_status=abandoned` describe historical monuments
and are not used; the remaining rows of a station agree with each other.
`control_mark_register.csv` lists the control marks by `mark_id` with `mount`,
`centring_mm` and `set_out_from`. In `station_registry.csv` and in that
register, a filled `set_out_from` names the control mark the setup was
transferred from; blank means none. The centring variance of a station or of a
control mark is `(centring_mm / 1000)^2` square metres when its own `mount` is
`tripod` and zero when it is `pillar`, plus, when its `set_out_from` is filled,
the centring variance of the mark it names.

## 2. Observation shards (source of record)

The four files `obs_source_district_north.csv`, `obs_source_district_south.tsv`,
`obs_source_district_west.psv`, `obs_source_district_east.jsonl` are the source
of record for all observations. Each carries, per row: `obs_id`, `kind`
(`length` or `angle`), `observed_value`, `computed_nominal`, `apriori_sigma`,
`unit`, `sigma_kind`, `dir`, `partials`, `epoch`, `region`. The `partials`
column lists the exact rational design-row coefficients as
`index:num/den;index:num/den`. Every other file restates, cross-checks, or
decoys these observations; none of the other files is a source of observation
values. The CSV shard is written to RFC 4180, so any of its fields may be
enclosed in double quotes; the quotes are not part of the value.

Each shard's header block declares the conventions that shard uses as
`key=value` tokens: `revision`, `length_unit`, `angle_unit`, `sigma_stored_as`,
`sign_flip_rev`, `azimuth_wrap` and `transpose_ids` (the last three are `true` or
`false`). The JSON-lines shard carries the same keys in the metadata object on
its first line, and abbreviates the row fields as `id` (obs_id), `k` (kind), `v`
(observed_value), `c` (computed_nominal), `s` (apriori_sigma), `u` (unit), `sk`
(sigma_kind), `d` (dir), `A` (partials), `e` (epoch) and `reg` (region). The
conventions vary by shard and between extracts; apply each shard's own
declaration.

An observation can be carried by more than one shard when a district re-issued
it. Records are matched by their true `obs_id` (section 7). The record in the
shard with the higher `revision` is the observation; any other record of that
`obs_id` is superseded, is not counted, and contributes nothing to the solve.
The district of an observation is the district of the shard that holds its
kept record: `obs_source_district_north.csv` is North,
`obs_source_district_south.tsv` is South, `obs_source_district_west.psv` is
West and `obs_source_district_east.jsonl` is East.

## 3. Units

Convert every `observed_value`, `computed_nominal`, and `apriori_sigma` to base
units before it is used: metre for `length`, gon for `angle`.
`reference_unit_registry.csv` gives the exact rational factor
(`factor_num/factor_den`) that multiplies a shard-unit value to the base unit.
Use only rows with `status=authoritative`; rows with `unit_scope=informational`
are display-only restatements.

## 4. Uncertainty and weight

Each shard declares `sigma_stored_as` = `stddev` or `variance` (also mirrored,
per shard, in `sigma_convention_manifest.json` with a YAML mirror
`sigma_convention_manifest_b.yaml`; if the two disagree the JSON is
authoritative). The base-unit variance of an observation, `variance_base`, is
formed as follows. Convert to base units first, then, if `sigma_kind=stddev`,
square the base-unit sigma; if `sigma_kind=variance`, multiply the stored value
by the square of the unit factor. A length observation is also affected by the
centring of the instrument and target over the marks: for every station with a
non-zero coefficient in its `partials`, add that station's centring variance
(section 1) to its `variance_base`. The weight is `1 / variance_base`.

## 5. Sign convention

All differenced observations are `FROM minus TO`. Rows whose `dir` field is `R`
are stored reversed (`sign_flip_rev=true` declares that a shard contains such
rows): negate BOTH `observed_value` and `computed_nominal` for those rows before
any further use. Rows with `dir=F` are already correct.

## 6. Azimuth reduction

Some shards declare `azimuth_wrap=true`: their raw angular values may be
negative or may exceed 400 gon. For those shards, reduce every angular
`observed_value` and `computed_nominal` (after unit conversion and any sign
restoration) modulo 400 gon into the range `[0, 400)`.
`azimuth_reference_table.tsv` restates, per observation, whether reduction
applies; `grad` and `gon` are the same unit.

## 7. Identifier transposition

Some shards declare `transpose_ids=true`: for rows with `epoch=2` the `obs_id` is
stored with its 3-character head and its tail swapped (a 7-character id `OB00262`
appears as `0262OB0`). Restore the true id by moving the last 3 characters to
the front. Shards without this declaration store ids verbatim.

## 8. Misclosure (reduced observation)

The value that enters the adjustment for each observation is the misclosure
`l = observed_value_base - computed_nominal_base`, in base units, after sections
3 and 5-7 have been applied. For an angle the difference is a direction
difference: it is reduced modulo 400 gon into the half-open range
`(-200, 200]` gon.

## 8b. Traverse closure

`traverse_closure_register.csv` gives, for each district (section 2) and
epoch, a signed `closure_micrometres` and a `floor_micrometres`. The closure of
a district and epoch is absorbed by the length observations of that district
and epoch. The basis of a length observation is the magnitude of its
`computed_nominal` in metres, rounded down to a whole number. When the summed
basis of the group is at or below the closure magnitude, each length absorbs
its own basis in micrometres and the rest of the closure is left unabsorbed.
When the summed basis exceeds the closure magnitude, the closure magnitude is
shared in whole micrometres in proportion to basis by largest remainder, a tie
between two remainders going to the lower `obs_id`. A length whose share then
falls below the floor absorbs nothing, and every micrometre of the closure
magnitude is shared again, in proportion to basis by largest remainder, ties
settled as above, across only the lengths whose share was the floor or more;
when none was, every length absorbs nothing. An absorbed amount carries the
sign of the closure and is subtracted, in metres, from that length's
misclosure `l` (section 8) before section 10.

## 9. Minimal datum and the constrained-component count u

`datum_constraint_spec.json` lists the constrained coordinate components of
the minimal datum by station, axis and unknown index; any component it does not
list is free. The number of constrained components `u` is recorded in the
control workbook `adjustment_control_workbook.xlsx` (sheet `datum`, cell
labelled `u_constrained`). It counts constrained components, not whole
stations. The degrees of freedom are `dof = n_observations - u`.

## 10. Weighted least squares

Form the normal equations `N = A^T P A`, `b = A^T P l`, with `P` the weight
matrix (sections 4, 11 and 11b) and `A` the design rows from the `partials`
column. Assemble observations in ascending `obs_id` order
(`observation_provenance.psv` gives `row_order_key`). Solve `N x = b` exactly by
Gaussian elimination. All arithmetic is exact rational.

## 11. Robust reweighting (IRLS)

`iteration_policy.yaml` documents the policy: run exactly `irls_iterations`
reweighting iterations after the initial solve, and quantize every weight to
`weight_quant_decimal_places` decimal places. Quantizing a weight `p` to `d`
places means taking the exact rational `p`, rounding `p * 10^d` to an integer
with `ROUND_HALF_EVEN`, and dividing by `10^d`. The base a-priori weight of
every observation is the quantized `1/variance_base`, formed once before the
initial solve. The downweight rule is: observation `i` is downweighted iff
`v_i^2 * p_i > k^2`, where `v_i` is the current residual, `p_i` the base
a-priori weight, and `k` the robust tuning constant; a downweighted
observation's weight is the base weight multiplied by `k^2 / (v_i^2 * p_i)`,
quantized. Each iteration starts again from the base weights. The rule applies
only to observations outside an authoritative correlated session (section 11b):
a session member is never tested for downweighting, is never reported as
downweighted, and keeps its quantized block weight through every pass. The
tuning constant `k` is the workbook cell labelled `tuning_k` (sheet `datum`).
Residuals are `v = A x - l`. This is stage 1.

## 11b. Correlated observation sessions (block-diagonal weights)

Some length baselines were observed in correlated 2-member sessions, so the
weight matrix is block-diagonal. `session_correlation.csv` lists, per
authoritative session (`status=authoritative`), the two member observations by
their `obs_id` (`member_a_obs_id`, `member_b_obs_id`) and the exact rational
covariance `cov = cov_num/cov_den` between their misclosures. For each session,
form `C = [[var_a, cov], [cov, var_b]]`, where `var_a` and `var_b` are the
members' `variance_base` (section 4). The session's weight is the exact inverse
`C^{-1}`, placed as a 2x2 block that couples the two members' rows in both `N`
and `b`, including the off-diagonal cross term; a member takes its block weight
instead of a diagonal weight. Quantize each block-inverse entry as in section
11. Rows with `status=decoy` are retired sessions and are ignored; an
observation belongs to at most one authoritative session. A session applies only
while both members are in the network: if one member is removed as a blunder
(section 12), the surviving member takes the ordinary diagonal weight in stage 2
and is subject to the robust downweight rule like any other observation.
`session_orientation_notes.yml` and `session_orientation_notes_b.yml` are
commentary.

## 12. Data-snooping blunder removal and stage-2 re-solve

After the stage-1 robust solve, an observation `i` is a blunder when
`v_i^2 * p_i` exceeds `blunder_crit^2`, where `p_i` is the base a-priori weight
of section 11 (used for session members too) and `blunder_crit` is the workbook
cell labelled `blunder_crit`. Remove every flagged observation and re-solve the
reduced network with the same robust reweighting of section 11. All reported
figures are the stage-2 figures.

## 13. Datum S-transformation

The stage-2 solve is a free-network solution. Transform it to the working datum
whose origin is the station whose index is the workbook cell
`datum_origin_station` (`0` is ALPHA, `5` is FICUS): subtract the origin
station's `dx` and `dy` corrections from the `dx` and `dy` corrections of every
station, so the origin station ends with zero correction in both axes. The
reported adjusted state is the datum-shifted correction vector; the free-network
vector is reported as well.

## 14. Global model test

After the stage-2 solve, compute the quadratic form `vTPv` with the stage-2 final
weights and the variance of unit weight `sigma0^2 = vTPv / (n - u)`, where `n` is
the stage-2 observation count. Take the acceptance interval from the row of
`chi_square_bounds_table.csv` whose `dof` equals `n - u`: `center_num/center_den`
minus and plus 1/2. The verdict is `PASS` if `lo <= vTPv <= hi`, else
`REJECT_LOW` or `REJECT_HIGH`.

## 15. Files that are not sources

- `deprecated_precorrection_coords.csv`: retired coordinate offsets.
- `stale_cached_solution.json`: a prior-epoch cached solve.
- `legacy_orientation_offsets.tsv`: already folded into `computed_nominal`.
- `residual_prior_epoch.tsv`: prior-epoch residual history.
- `observation_weight_manifest.csv` column `naive_weight`: the earlier faulty
  weights.
- `scale_factor_table.csv`: no scale is applied (`scale_applied=none`).
- `archive_backfill.db`: backfill echoes of shard rows.
- Rows anywhere flagged `status=duplicate`, `status=void`, `status=superseded`,
  `status=retired`, `mark_status=abandoned`, `provenance=superseded`, or
  `ledger_status=void` are informational and are not a source of any value.

## 16. Output shape

Every numeric field is the exact rational value rendered deterministically with
`ROUND_HALF_EVEN`: a field with `d` decimals is the exact value rounded half-even
to `d` places. Residuals and coordinate corrections are signed integer
micrometres: the exact value times 10^6, rounded half-even to an integer. Every
sum in a rollup or summary (`sum_abs_residual_micrometres`,
`sum_signed_micrometres`) is taken over the exact residuals and rounded once at
the end. All JSON is serialized with sorted keys and a trailing newline. The
twelve unknown labels are, in order, `ALPHA.x`, `ALPHA.y`, `BRAVO.x`, `BRAVO.y`,
`CIVET.x`, `CIVET.y`, `DELTA.x`, `DELTA.y`, `EAGLE.x`, `EAGLE.y`, `FICUS.x`,
`FICUS.y` (station order from section 1, dx then dy). Residual micrometres are
in the observation's base unit (micrometres for a length, micro-gon for an
angle).

The residual rollups come in three families. The four district rollups key on
the observation's district (section 2) and the three epoch rollups key on the
observation `epoch` field. The six derived-key
rollups key on the pair `(frame, campaign)`: `station_frame_map.csv` maps a
station to its `frame` and `epoch_campaign_map.csv` maps an `epoch` to its
`campaign`; each observation belongs to the frame of its primary station (the
lowest station index among its `partials`) and the campaign of its `epoch`. In
both maps the first occurrence per key is authoritative. Write exactly these
artifacts, each with exactly these fields:

- `adjusted_state.json`: `unknowns` (label to correction in metres, a string with
  10 decimals), `unknowns_micrometres` (label to integer micrometres),
  `n_observations` (int, the stage-2 count), `u_constrained` (int),
  `degrees_of_freedom` (int), `variance_of_unit_weight` (string, 10 decimals),
  `quadratic_form_vtpv` (string, 10 decimals), `tuning_constant_k` (string, 6
  decimals), `blunder_critical_value` (string, 6 decimals), `blunders_removed`
  (int), `datum_origin_station` (string, the origin station name),
  `model_test_verdict` (string, one of `PASS`, `REJECT_LOW`, `REJECT_HIGH`). The
  `unknowns` are the datum-shifted corrections.
- `model_test.json`: `degrees_of_freedom` (int), `quadratic_form_vtpv` (string, 10
  decimals), `acceptance_low` (string, 6 decimals), `acceptance_high` (string, 6
  decimals), `verdict` (string), `passed` (boolean, true only when the verdict is
  `PASS`).
- `downweighted_observations.json`: `count` (int) and `obs_ids` (array of obs_id
  strings in ascending order).
- `residual_summary.json`: `n` (int), `sum_signed_micrometres` (int),
  `max_abs_residual_micrometres` (int), `max_abs_residual_obs_id` (string; on an
  exact tie the lowest obs_id).
- `unknowns.csv`: comma-separated, header
  `unknown_index,label,correction_metres,correction_micrometres`, one row per
  unknown index 0 to 11; `correction_metres` has 10 decimals.
- `residuals.csv`: comma-separated, header
  `obs_id,kind,residual_micrometres,downweighted`; `downweighted` is `1` or `0`.
- `residuals.tsv`: tab-separated, header row `obs_id` and `residual_micrometres`
  joined by a tab.
- `final_weights.psv`: pipe-separated, header `obs_id|weight_num|weight_den`, one
  row per stage-2 observation; the weight is its exact integer numerator and
  denominator in lowest terms. For an observation outside any session it is the
  final quantized robust weight; for a session member it is the quantized
  diagonal entry of its session's block `C^{-1}` on that member's own row.
- `district_North.json`, `district_South.json`, `district_West.json`,
  `district_East.json`: `district` (string), `observation_count` (int),
  `downweighted_count` (int), `sum_abs_residual_micrometres` (int).
- `epoch_1.json`, `epoch_2.json`, `epoch_3.json`: `epoch` (int),
  `observation_count` (int), `sum_abs_residual_micrometres` (int).
- `rollup_FrameA_Campaign1.json`, `rollup_FrameA_Campaign2.json`,
  `rollup_FrameB_Campaign1.json`, `rollup_FrameB_Campaign2.json`,
  `rollup_FrameC_Campaign1.json`, `rollup_FrameC_Campaign2.json`: `frame`
  (string), `campaign` (string), `observation_count` (int), `downweighted_count`
  (int), `sum_abs_residual_micrometres` (int).
- `normal_matrix_trace.json`: `trace_num` (int) and `trace_den` (int), the
  exact trace as a fraction in lowest terms, and `trace_decimal` (string, 6
  decimals); the trace of the normal matrix `N` assembled for the last stage-2
  solve, session blocks included.
- `provenance_summary.json`: `control_values_source` (string, exactly the bare
  file name `adjustment_control_workbook.xlsx`), `u_constrained` (int),
  `tuning_constant_k` (string, 6 decimals), `blunder_critical_value` (string, 6
  decimals), `datum_origin_station` (string, origin station name),
  `superseded_records` (array, one object per superseded shard record with
  `obs_id` (the true id), `kept_shard` and `superseded_shard` (shard file
  names), ordered by `obs_id` then `superseded_shard`; empty when there are
  none), and `decoys_ignored` (array of at least three strings naming files or
  columns you did not use as sources; each string is an exact shipped file name,
  or `file_name:column` for a column, and the file must be one of
  `deprecated_precorrection_coords.csv`, `stale_cached_solution.json`,
  `legacy_orientation_offsets.tsv`, `residual_prior_epoch.tsv`,
  `observation_weight_manifest.csv`, `scale_factor_table.csv`,
  `archive_backfill.db`, `iteration_policy.yaml`, `reference_unit_registry.csv`,
  `session_correlation.csv`, `azimuth_reference_table.tsv`, `epoch_calendar.csv`,
  `network_topology.xml`, `instrument_calibration_log.csv`,
  `station_registry.csv` or `observation_provenance.psv`).
- `status.txt`: one line
  `verdict=<verdict> dof=<dof> u=<u> n=<n> blunders_removed=<count> datum_origin=<name> sigma0_sq=<variance> downweighted=<count>`
  where the variance is rendered with 10 decimals.
- `removed_blunders.json`: `count` (int), `obs_ids` (array of obs_id strings in
  ascending order, the stage-1 gross errors removed before stage 2),
  `critical_value` (string, 6 decimals).
- `datum_transformation.json`: `origin_station` (string), `origin_station_index`
  (int), `free_corrections_micrometres` (label to integer micrometres, the
  free-network stage-2 solution), `shifted_corrections_micrometres` (label to
  integer micrometres, after the S-transformation).
- `adjustment_report.xml`: an `<adjustment>` root carrying `<verdict>`,
  `<degrees_of_freedom>`, `<u_constrained>`, `<variance_of_unit_weight>` (10
  decimals), and an `<unknowns>` block with one
  `<unknown label=... correction_micrometres=.../>` per unknown.
- `adjustment_summary.yaml`: keys `model_test_verdict`, `degrees_of_freedom`,
  `u_constrained`, `variance_of_unit_weight` (10 decimals), `downweighted_count`,
  `tuning_constant_k` (6 decimals).
- `adjustment_report.md`: a short human-readable report stating the verdict,
  degrees of freedom (integer), variance of unit weight (10 decimals),
  downweighted count and tuning constant (6 decimals), each figure written
  exactly as it appears in `adjusted_state.json`.
- `observation_stream.jsonl`: one JSON object per line with `obs_id`, `kind`,
  `residual_micrometres` (int) and `downweighted` (boolean).
- `observation_stream.ndjson`: one JSON object per line with `id` (obs_id) and
  `r` (residual micrometres).
- `derive_report.py`: the reusable program itself, runnable as
  `python3 derive_report.py DATA_DIR OUT_DIR`.
