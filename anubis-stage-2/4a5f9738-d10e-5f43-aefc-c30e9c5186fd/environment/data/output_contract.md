# Output contract

Write nine json documents and one python module under the output directory.
Every json document is a single object, written with sorted keys and two space
indentation, and every measure is an exact integer count of kilohertz seconds.
No floating point value appears in any document.

## summary.json

Keys: `horizon` (object with `start`, `end`, `as_of`), `assignments_total`,
`assignments_measurable`, `rectangles`, `area_total_assigned`, `area_union`,
`area_exclusive`, `area_shared`, `area_excess`, `excess_charge_total`,
`shared_ratio_ppm`, `zone_area_union`, `zone_share_bp`, `segment_area_union`,
`segment_share_bp`, `cross_segment_shared_area`, `guard_subtracted_area`.

`assignments_total` counts the grant identifiers that carry at least one
visible record in at least one of the three grant layers. A grant counts as
measurable when it carries at least one final extent of positive measure, and
`assignments_measurable` counts those grants.
A final extent set is reduced before it is counted. Extents of one grant that
touch in frequency and share both time bounds become one extent, then extents
of one grant that touch in time and share both frequency bounds become one
extent, and the pair of passes repeats until nothing merges.
`rectangles` counts the reduced final extents over every zone. `area_total_assigned`
sums the final extents with multiplicity. `area_union` measures the covered
set, where zone, frequency and time are all coordinates. `area_exclusive`
measures the part of the covered set that exactly one extent covers and
`area_shared` measures the part that at least two extents cover.
`area_excess` is `area_total_assigned` less `area_union`.
`excess_charge_total` sums the charges described below.
`shared_ratio_ppm` scales `area_shared` by `ppm_scale` of `measure_config.ini`,
divides by `area_union`, and rounds once under the configured rounding mode.
`zone_share_bp` and `segment_share_bp` hold integer basis points that sum to
`share_total_bp`, allocated by largest remainder, with ties on the remainder
broken by the ascending key name. Zone shares are taken on `area_union`.
Segment shares are taken on the sum of the two segment union measures, which
exceeds `area_union` by `cross_segment_shared_area`.

## region_<Zone>.json for North, South, West and East

Keys: `zone`, `utc_offset_standard_sec`, `utc_offset_summer_sec`,
`summer_window_utc` (a two element list of stamps, or null),
`assignments_measurable`, `rectangles`, `area_total_assigned`, `area_union`,
`area_exclusive`, `area_shared`, `area_excess`, `guard_occurrences`,
`guard_subtracted_area`, `excess_charge_top`, `band_area_union`,
`month_area_union`.

`band_area_union` maps every band identifier of the band plan to the union
measure inside that band. `month_area_union` maps every local calendar month
of the zone that meets the horizon, keyed `YYYY-MM`, to the union measure
inside that month; the values sum to `area_union`. `excess_charge_top` lists
the `top_excess` highest charged grants of the zone as two element lists of
grant identifier and charge, ordered by descending charge then ascending
identifier. Within any smallest cell of the covered set that carries two or
more extents, the covering grants are ordered by descending final own measure
then ascending identifier; the first keeps the cell and every other covering
grant is charged the measure of the cell.

## segment_commercial.json and segment_public.json

Keys: `segment`, `holders`, `assignments_measurable`, `area_union`,
`area_exclusive`, `area_shared`, `zone_area_union`, `top_holders`,
`duty_deficit_months`, `duty_carry_end`. `top_holders` lists the `top_holders`
largest holders of the segment as two element lists of canonical identifier and
union measure, ordered by descending measure then ascending identifier.
`duty_carry_end` sums the carry leaving the last audited month of every audited
holder of the segment. `holders` counts the canonical holders of the segment
that carry at least one measurable grant.

## policy_audit.json

Keys: `as_of`, `precedence_exception` (object with `segment`, `field_group`,
`layer`), `duplicate_tiebreak` (one of `earliest_recorded_at` or
`latest_recorded_at`), `clock_keying` (one of `local_standard` or `utc`),
`layer_governing_counts`, `alias_fixpoint_depth`, `alias_cycles`,
`parent_chain_max_depth`, `parent_rejects`, `duty`, `guard`.

`layer_governing_counts` counts, per layer, the field group decisions that the
layer won across every grant that reached the fault tests.
`alias_fixpoint_depth` is the largest number of redirections applied to any
holder reference seen in the sources. `parent_chain_max_depth` is the longest
acyclic parent chain of a measurable grant, counting the grant itself as one.
`parent_rejects` maps the three parent reject codes to their counts. `duty`
holds `holders_audited`, `months_in_deficit`, `total_allowance`,
`total_consumed`, `carry_forward_end`, `carry_resets` and `top_deficit`, where
`top_deficit` lists the `top_deficit` largest single month deficits as three
element lists of holder, month key and deficit, ordered by descending deficit
then ascending holder then ascending month. `guard` holds `occurrences`,
`cancelled`, `added` and `subtracted_area`.

## data_quality.json

Keys: `assignments_total`, `rows_read_total`, `rejects`, `notes`, `retracted`,
`zero_span`, `manifest_mismatches`, `source_counts`.

`retracted` counts the withdrawn grants and `zero_span` counts the grants
that pass every reject test and whose two effective bounds are equal.

`rejects` maps every reject code of `reason_codes.md` to its count, including
codes that fired on nothing. `notes` maps every note of `reason_codes.md` to
its count. `source_counts` maps every record file of the corpus to an object
with `rows_read`, the data rows of the file, `rows_visible`, the rows the
cutoff admits, and `rows_governing`, the rows that became a governing record of
their layer; only the three grant layers report the last two figures and every
other record file reports zero for both. `manifest_mismatches` lists, in ascending order, the record files whose
declared row count in `source_manifest.md` differs from `rows_read`.
`rows_read_total` sums `rows_read` over every record file.

## derive_report.py

A python module that the registry can rerun. Invoked as
`python3 derive_report.py <corpus_dir> <output_dir>` it must read a corpus laid
out exactly like this one and write the same nine json documents into the
output directory. It must use only the python standard library, must not read
any path outside the corpus directory it is given, must not write outside the
output directory it is given, and must leave the corpus unchanged.
