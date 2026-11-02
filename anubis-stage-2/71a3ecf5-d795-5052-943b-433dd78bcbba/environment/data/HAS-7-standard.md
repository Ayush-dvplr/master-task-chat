# HAS-7 Household Activity Statistics Standard, revision 7

This standard defines how a Regional Household Activity Survey extract is turned
into weighted estimates and into a disclosure controlled publication set. It is
the complete rule set. Anything this document does not state is not part of the
standard. Its sections are grouped by subsystem; the order of the sections is
not the order in which the rules are applied.

## 1. Scope and reference points

The survey reference period is `2026-H1`. The reference wave is wave `3`. Waves
`1` and `2` are prior waves and are used only where a rule names them.

Every figure this standard defines is derived from the extract alone. The field
index `HAS-7-field-dictionary.psv` lists every file of the extract and every
field each file carries.

## 2. Identifiers, text and arithmetic

A unit identifier in canonical form is `RH-<REGION>-<SERIAL>` where `<REGION>` is
two upper case letters and `<SERIAL>` is exactly six digits with leading zeros.
Identifiers appear in the extract in other spellings: lower case, with `_` or `.`
in place of `-`, with surrounding whitespace, and with the serial written without
its leading zeros. All of these denote the same unit and fold onto the canonical
form. Identifiers, codes and names are compared after Unicode normalisation form
NFC. Every file the standard defines is written UTF-8 with no byte order mark
and with `\n` line endings.

Weights, control totals and estimates are carried as whole numbers of
micro-units. One micro-unit is one millionth of one person, so a weight of one
person is the integer `1000000`. Rates and shares are carried as whole numbers of
basis points, so one hundred percent is the integer `10000`.

Division rounds to the nearest whole number with halves away from zero. Where a
rule applies division more than once the rounding happens at every division the
rule names, not once at the end. The raking section is the one exception: it
fixes its own rounding point.

## 3. Reading the corpus

Wherever a file carries an `active` column, an `active` field or an `active`
property, a row whose active marker is not `Y`, `yes` or `true` is out of scope
and takes no part in any figure.

Where a register defines a `sort_rank`, that rank fixes the order in which its
levels appear in any artifact that lists them.

## 4. Benchmarks and control totals

Benchmark files publish a series per dimension. Only rows whose
`reference_period` equals the survey reference period are in scope.

For each dimension and level the control total is the offer with the greatest
`rank`; where that ties, the one with the greatest `published_date`; where that
also ties, the one with the greatest `source_id`.

A benchmark value is written in the unit its file declares and is converted to
persons through the conversion register before it is used.

The three dimensions are `region_tenure`, whose level key is the region code and
the tenure joined by `|`; `activity`, whose level key is the activity code; and
`band`, whose level key is the band code.

Worked example, on levels no report carries: offers for one level of rank 2
dated `2026-03-01` from `BEN-Q`, rank 2 dated `2026-03-01` from `BEN-R` and rank 1
dated `2026-08-01` from `BEN-S`. Rank leaves the first two, the date ties, and
`BEN-R` is the greater source, so its value is the control total.

## 5. Closure

The following must hold and each is reported with the evidence behind it.

Raking converged. The final weight total is within the raking tolerance of the
control grand total. Trimming left the sum of all final weights equal to the sum
of all raked weights. For every table, the published total plus the suppressed
total equals the table total, so the conservation residual over the four tables
is zero.

The post trim margin deviation is the greatest absolute difference, over every
level of every margin, between the final weight sum of the level and its control
total. It is reported and it is not required to be zero.

## 6. Contact history and dispositions

Contact attempts for a unit and a wave arrive across several files. The final
disposition for that unit and wave is the attempt with the greatest
`severity_rank`; where that ties, the attempt at the latest instant; where that
also ties, the attempt with the greatest `attempt_no`.

Timestamps arrive with an offset and may carry fractional seconds. The canonical
instant is UTC with the fractional part truncated, never rounded.

An instant is written as `YYYY-MM-DDTHH:MM:SSZ`, with the `Z` suffix and no
offset and no fractional part.

A contact log line that carries a `correction` field in place of an `outcome`
field is a correction, not an attempt. It names a unit, a wave and an attempt
number, and its correction is `void` or `reinstate`. For each unit, wave and
attempt number, the in scope correction at the latest instant gives the net
state; where two share an instant, the reinstatement gives it. An attempt whose
net state is void takes no part in resolving the disposition, in whichever
contact file it appears, and it still counts as an attempt record. An attempt no
correction names stands.

Worked example, on a unit no report carries: attempts 1 `refusal` and 2
`complete` at wave 3. A void of attempt 2 at `10:00Z` followed by a reinstatement
at `11:00Z` leaves attempt 2 standing, so the unit settles on `complete`. A
second void at `12:00Z` voids it again, and the unit settles on `refusal`.

A disposition carries three flags from the precedence register: whether the unit
is eligible, whether it responded, and whether it is superseded. A superseded
unit takes no part in estimation and still appears in the response status record;
where its disposition is flagged eligible it stays in the eligible set and in its
adjustment cell as a unit that did not respond.

A unit is eligible at the reference wave when its resolved disposition is
eligible and its `dwelling_units` is not zero. A unit is responding when it is
eligible, its resolved disposition is responding, it is not superseded, and an
interview record for the reference wave exists.

## 7. Design weights

Let `N` be the population units of a stratum and `n` the number of resolved frame
units in that stratum. The design weight of a unit in that stratum is `N` divided
by `n`, in micro-units.

Where the subsample register marks a unit as subsampled, its design weight is
divided by the subsample factor the subsample register declares, expressed as a
share.

## 8. Disclosure screening and suppression

A cell is suppressed as a primary suppression when its count is below the minimum
publishable count, or its coefficient of variation is above the maximum
publishable coefficient of variation, or its dominance is above the dominance
limit. Every reason that applies is recorded.

A published table must not let a suppressed value be recovered by subtraction. So
where a row of a table or a column of a table holds exactly one suppressed cell,
one further cell of that same row or column is suppressed. The cell chosen is the
one with the smallest count; where that ties, the one whose cell key sorts
first. Rows are considered in their registry order before columns, and the whole
pass repeats until no row and no column holds exactly one suppressed cell, or
until the cascade round limit is reached.

The reported number of cascade rounds counts every pass made over a table,
including the final pass that suppressed nothing, and it is reported for each
table separately.

The screening rank of a cell orders every cell of every table by coefficient of
variation descending, then by table name ascending, then by cell key ascending,
and numbers them from one.

## 9. Estimates

Four tables are published. Their row and column levels, and the order of those
levels, come from the cell registry.

```
activity_by_region     rows activity at the reference wave   columns region
tenure_by_wquintile    rows tenure                           columns weight quintile
hours_by_sector        rows sector at the reference wave     columns band at the reference wave
band_transition        rows band at wave one                 columns band at the reference wave
```

The weight quintile of a unit follows from ordering the responding units by final
weight ascending and, where that ties, by canonical identifier ascending. A unit
at position `i` of `n`, counting from zero, sits in quintile `1 + (5 * i) // n`.
The quintile is a property of the full sample and is the same in every replicate.

A cell carries the sum of the final weights of the responding units that fall in
it, the count of those units, the greatest single final weight among them, and
the jackknife standard error.

The jackknife variance of a cell is the sum, over every replicate, of `k` minus
one, multiplied by the square of the difference between the cell total under that
replicate and the cell total under the full sample, divided by `k`, where `k` is
the size of the replicate's group and the division keeps only the whole part. The
standard error is the square root of that variance rounded to the nearest whole
micro-unit.

The coefficient of variation of a cell is its standard error over its total, in
basis points. Its dominance is the greatest single final weight in it over its
total, in basis points. A cell with a total of zero carries zero for both.

## 10. Frame resolution

The frame arrives as three registers: `frame__register-a.csv`,
`frame__register-b.tsv` and `frame__register-c.fwf`. `frame__register-d.jsonl`
is a reissue copy: none of its records is a frame record, and it lends the frame
only the one fact this section names below. A frame record is identified by the
pair `(region_code, serial)` after the repairs in this section. The `record_id` is not
part of the identity.

Where more than one record shares an identity, one record survives. The surviving
record is the one with the greatest `vintage_rank`; where that ties, the one with
the greatest `edit_timestamp`; where that also ties, the one with the greatest
`record_id` compared as text. Every record that does not survive is discarded and
its `record_id` is recorded.

The following malformations are repaired rather than rejected. A repaired record
stays in the frame and each repair is counted once per record it is applied to.
M1, M2, M3 and M7 are counted on every register record inside the frame, losing
copies included; M4, M5 and M6 are counted once per resolved unit from the
address register.

```
M1  serial carries leading or trailing whitespace   strip the whitespace
M2  serial is shorter than six digits               pad on the left with zeros
M3  region_code is not upper case                   upper case it
M4  dwelling_units is absent                        treat the unit as carrying one
M5  parent_unit names the unit itself               record the unit, drop the link
M6  parent_unit names a unit absent from the frame  record the unit, drop the link
M7  stratum is written as a name                    map it through the stratum register
M8  identity duplicate                              keep the survivor, record the rest
```

A record whose stratum is neither a known code nor a known name is outside the
frame and contributes nothing, its repairs included.

An absent `dwelling_units` is not the same as a `dwelling_units` of zero. Absent
means unknown and the unit carries one dwelling. Zero means the dwelling is
vacant and the unit is never eligible.

A stratum name is the region name and the stratum group joined by one space, for
example `Northreach urban`.

Where the surviving record leaves `psu_code` blank, the unit's primary sampling
unit is the `psu_code` of the reissue copy that names the unit. That is the only
fact the reissue copy carries into the frame.

## 11. Interviews, hours and bands

Interview records arrive across twelve files covering three waves. A record
carries an activity code, a sector code and hours worked.

The band of a unit at a wave follows from its hours through the band register,
whose edges are inclusive at both ends. Where hours are absent the band carries
forward. For the reference wave it is the band of the unit's wave two interview
hours; where that interview is absent or carries no hours, the `prior_band` of
the unit's in scope row in the wave two prior band file; where that is absent,
the `prior_band` of its row in the wave one prior band file; and where neither
exists, the band of zero hours. A wave two interview that carries hours governs
over the wave two prior band file. A wave one band whose interview carries no hours is the
`prior_band` of the unit's in scope row in the wave one prior band file, and
where that file holds no such row it is the band of zero hours. A unit with no
interview record at a wave has no band at that wave and falls in no cell that
the band at that wave classifies.

## 12. Nonresponse adjustment

An adjustment cell is keyed by the stratum code, the tenure class and the contact
band. The contact band of a unit is the band of the contact band register whose
attempt range, inclusive at both ends, holds the number of attempt records the
contact files carry for the unit at waves one and two together, repeated records
included. The `Contact-Band` field of the address register records the band at
sampling and takes no part in any figure. Its parent cell is keyed by the stratum code and the tenure class. Its
grandparent cell is keyed by the stratum code alone.

A cell holds every eligible unit assigned to it. Its response rate is the design
weight of its responding units over the design weight of its eligible units.

A cell passes when its response rate is at or above the minimum response rate and
its responding count is at or above the minimum cell count. A cell that does not
pass moves every one of its units to the next key up. That test repeats for at
most the stated number of collapse rounds, and a unit never moves past the
grandparent key.

The reported number of collapse rounds counts every pass the test made,
including the final pass that found nothing left to move.

The adjustment factor of a cell is the eligible design weight of the cell over
the responding design weight of the cell. A cell with no responding weight
carries a factor of zero.

The adjusted weight of a responding unit is its design weight multiplied by the
factor of the cell it ended in, that is the design weight times
`adjustment_factor_uw` over `1000000`, rounded once.

## 13. Raking

The adjusted weights are raked onto the control totals.

One iteration applies every margin once. Applying a margin visits each of its
levels and multiplies the weight of every unit in that level by the control total
of the level over the current weight sum of the level. A level with no units and
a level with no control total are both skipped. Weights are whole micro-units
between iterations. Inside an iteration the round rounds at one of two points:
either every weight is rounded to the nearest whole micro-unit each time a margin
rescales it, or the weights are carried exactly through the margins of the
iteration and rounded once when the iteration ends. Halves round away from zero
at either point.

At the end of an iteration the deviation is the greatest absolute difference,
over every level of every margin that carries a control total, between the
rounded weight sum of the level and its control total. Raking stops when that deviation is at or below the tolerance, and
that iteration count is the iterations used. Raking also stops at the maximum
iteration count, in which case the weights of the last completed iteration stand
and the run is recorded as not converged.

The margins are applied in one fixed order, the same in every iteration and in
every replicate. The rule files state neither that order nor the rounding point.
The pilot record holds a pilot population with its adjusted weights, its own
control totals and the figures the pilot round published after raking: the
number of iterations it used and the raked total of every level of every margin.
The pilot round was raked under every rule of this section with the tolerance,
the maximum iteration count, the margin order and the rounding point of the
round. Of the twelve combinations of the six orders of the three margins and the
two rounding points, exactly one reproduces every published pilot figure, and
it gives the margin order and the rounding point of the round.

## 14. Replicate design

Variance is estimated by dropping one primary sampling unit at a time.

A stratum holding fewer than two primary sampling units cannot support this, so
it merges into the stratum its `collapse_partner` names and the two are treated
as one replication group, which carries the code of the stratum the merge leads
into. A replication group is otherwise one stratum and carries its code.

A group of size `k` produces `k` replicates, one per primary sampling unit in it.
In the replicate that drops a primary sampling unit, every unit in that primary
sampling unit carries a design weight of zero, every other unit of that group
carries its design weight multiplied by `k` over `k` minus one, and every unit
outside the group carries its design weight unchanged.

A unit carrying a replicate design weight of zero takes no part in that
replicate. It is absent from that replicate's adjustment cells, so it counts
toward neither the cell's responding count nor either of its weight sums; it is
absent from the raking; and it is absent from the trimming, so it does not enter
the stratum median or the stratum design effect and is never itself trimmed. It
contributes nothing to any estimate under that replicate.

A replicate weight is what the design weights of that replicate become after the
nonresponse adjustment, raking and trimming sections are applied again to them.
The adjustment cells are formed again from the replicate design weights, the
raking runs again, and the trimming runs again. A replicate is not the full
sample weight rescaled.

## 15. Trimming

After raking, each stratum has a ceiling: the trim ratio applied to the median
raked weight of its responding units. The median of an even number of values is
the lower of the two central values.

Trimming applies to a stratum only when the design effect of its raked weights is
above the trim trigger. That design effect is `10000` times the stratum's
responding count times the sum of the squared raked weights of its responding
units, over the square of their sum, rounded once. A stratum at or below the
trigger keeps its raked weights, and its ceiling is still computed and reported.

Worked example, on a stratum no report carries: raked weights `2000000`,
`2000000` and `5000000` give `10000 * 3 * 33000000000000 / 81000000000000`, which
is `12222` basis points.

In a stratum that trimming applies to, a unit above the ceiling is set to the
ceiling. The weight removed from the stratum is handed back to the units of that
stratum that were at or below the ceiling, in proportion to their weight: each
share is the removed weight times the unit's weight over the sum of their
weights, rounded to the nearest micro-unit with halves away from zero. Where the
shares do not add up to the removed weight, the difference, which may be
negative, goes to the unit with the greatest weight after its share, and where
that ties, to the one with the smallest canonical identifier. The hand-back is a
single pass.

The total weight of a stratum is the same before and after trimming. The weight
sums of the raked margins are not, because a margin crosses strata, and the
deviation that leaves is reported rather than corrected.

## 16. Artifacts

Every artifact is written into the output directory. JSON artifacts are written
with keys sorted, an indent of two spaces and a trailing newline. Delimited
artifacts carry the header row this section gives, in this column order, with one
trailing newline and no quoting. Integers are written with no decimal point and
no thousands separator. Booleans in delimited artifacts are written `Y` and `N`.

```
frame_audit.json          repair_counts, self_referencing_units,
                          dangling_parent_units, discarded_record_ids,
                          resolved_unit_count, subsample_factor_bp
control_totals.json       reference_period, grand_total_uw, dimensions,
                          level_counts
response_status.json      reference_wave, disposition_counts, eligible_count,
                          responding_count, superseded_units, units
design_weights.csv        unit_id,stratum,psu_code,subsampled,design_weight_uw
control_margins.tsv       dimension,level_key,control_total_uw,chosen_rank,
                          chosen_source
adjustment_cells.json     collapse_rounds, cell_count, cells, depth_counts
adjusted_weights.csv      unit_id,cell_key,adjustment_factor_uw,
                          adjusted_weight_uw
raking_trace.json         margin_order, tolerance_uw, max_iterations,
                          iterations_used, converged, final_max_deviation_uw,
                          per_iteration
final_weights.csv         unit_id,stratum,raked_weight_uw,trimmed,
                          final_weight_uw
weight_diagnostics.json   responding_count, final_weight_total_uw,
                          design_effect_bp, median_weight_uw, maximum_weight_uw,
                          minimum_weight_uw, trimmed_count, trimmed_units,
                          stratum_totals_uw, stratum_ceilings_uw
replicate_design.json     replicate_count, group_count, groups, merged_groups
replicate_summary.csv     replicate_id,group,dropped_psu,group_size,
                          iterations_used,converged,trimmed_count,final_total_uw
estimates_<table>.csv     cell_key,row_level,column_level,point_estimate_uw,
                          unweighted_count,standard_error_uw,cv_bp,dominance_bp
variance_components.json  replicate_count, tables
cv_screening.json         min_publish_count, max_publish_cv_bp, dominance_bp,
                          tables
primary_suppression.json  tables, counts, total
secondary_suppression.json tables, cascade_rounds, counts, total
disclosure_audit.tsv      screening_rank,table_name,cell_key,status,reason,
                          point_estimate_uw,unweighted_count,cv_bp
closure_report.json       post_trim_margin_deviation_uw, final_weight_total_uw,
                          control_grand_total_uw, conservation_residual_uw,
                          final_total_gap_uw, responding_count, replicate_count,
                          primary_suppression_total, secondary_suppression_total,
                          tables, checks, all_checks_pass
```

Row order is `unit_id` ascending in the three weight artifacts, `replicate_id`
ascending in the replicate summary, registry order of the row level and then of
the column level in the four estimate tables, and screening rank ascending and
then table name and then cell key in the disclosure audit. In
`control_margins.tsv` the rows run by dimension name ascending and then by level
key ascending.

A cell key is the row level and the column level joined by `|`. A replicate
identifier is the group and the dropped primary sampling unit joined by `::`.

In `frame_audit.json` the three unit lists and the discarded record list are
sorted ascending. In `weight_diagnostics.json` `trimmed_units` is sorted
ascending. In `cv_screening.json` each table holds its cells in screening rank
order; everywhere else a list of cells runs in cell key order.

In `adjustment_cells.json` each cell carries `cell_key`, `depth`,
`eligible_weight_uw`, `responding_weight_uw`, `responding_count`,
`response_rate_bp` and `adjustment_factor_uw`, where `depth` is the number of
`|` separators in the key. `depth_counts` maps the depths `0`, `1` and `2`,
written as text, to how many cells carry them.

The control grand total is the sum of the `region_tenure` control totals, and
`final_total_gap_uw` is the final weight total less that grand total.

In `control_totals.json` `dimensions` maps each dimension name to an object from
level key to control total in micro-units, and `level_counts` maps each dimension
name to its number of levels.

In `frame_audit.json` `repair_counts` is keyed by the upper case repair class
code, `M1` through `M8`, and carries a count for every one of the eight whether
or not it fired.

In `raking_trace.json` `margin_order` lists the three dimension names in the
order the round applied them, and `per_iteration` is a list holding one object
per iteration, each carrying `iteration` and `max_deviation_uw`, in iteration
order.

In `replicate_design.json` `groups` maps each replication group to an object
carrying `psus`, the sorted primary sampling units of the group, `size`, how
many of them there are, and `strata`, the sorted stratum codes the group holds.
`merged_groups` carries only those groups that hold more than one stratum, and
maps each to the same sorted list of stratum codes.

In `secondary_suppression.json` `cascade_rounds` maps each table name to the
number of passes that table took.

`design_weights.csv` carries one row for every resolved unit in the frame.
`adjusted_weights.csv` and `final_weights.csv` carry one row for every
responding unit, which is the smaller set.

In `weight_diagnostics.json` `design_effect_bp` is `10000` times the responding
count times the sum of the squared final weights, over the square of the final
weight total, rounded once; it is `0` when the final weight total is zero.
`stratum_ceilings_uw` maps every stratum with a responding unit to its ceiling,
whether or not trimming applied to it.

In `response_status.json` `disposition_counts` maps each disposition that some
unit resolved to at the reference wave to the number of units that resolved to
it, and `superseded_units` lists, sorted ascending, every unit whose resolved
disposition at the reference wave is flagged superseded. `units` maps every
canonical unit identifier that has a
resolved disposition at the reference wave to `disposition`, `attempt_no`,
`resolved_utc` and `attempts`. `attempts` counts every attempt record for that
unit and wave across all the contact files, so a record that repeats an attempt
already carried by another file counts again.

In `cv_screening.json` each cell carries `cell_key`, `screening_rank`, `cv_bp`,
`dominance_bp`, `unweighted_count` and `reasons`, where `reasons` lists `count`,
`cv` and `dominance` in that order for each that applies.

In `primary_suppression.json` each entry carries `cell_key` and `reasons`. In
`secondary_suppression.json` each entry carries `cell_key`, `axis`, `axis_level`
and `round`, where `axis` is `row` or `column`.

In `variance_components.json` each table carries `summed_cell_variance_uw2` and
`by_group`, which maps each replication group to the part of that sum its
replicates contributed.

In `closure_report.json` `tables` maps each table to `total_uw`, `published_uw`,
`suppressed_uw`, `residual_uw` and `coverage_gap_uw`, where the coverage gap is
the final weight total less the table total. `checks` lists, in this order,
`raking_converged`, `final_total_within_tolerance`, `trimming_preserves_total`
and `suppression_conservation`, each carrying `name`, `expected`, `observed` and
`verdict`, where the observed value is `1` when the condition holds and `0` when
it does not and the verdict is `pass` or `fail`. `all_checks_pass` is true only
when all four pass.

In `disclosure_audit.tsv` the status is `published` or `suppressed` and the
reason is `primary`, `secondary` or `none`.
