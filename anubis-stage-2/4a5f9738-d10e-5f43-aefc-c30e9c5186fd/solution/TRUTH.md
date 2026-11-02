# TRUTH.md - 4a5f9738-d10e-5f43-aefc-c30e9c5186fd

The corpus describes one year of a national band coexistence register. The work
is an exact integer measure over the three coordinate space of zone, frequency
in kilohertz and time in seconds. Everything below is derived from the shipped
corpus alone.

## Defect

The register publishes its policy notes and its records, but three governing
rules are stated only as "settled by the evidence", and the naive reading of the
remaining material is wrong in ways that still produce a well formed report.

Focal items, the ones the whole measurement turns on:

- (focal) The measure of the covered set is a union, not a sum. Grants overlap
  inside a zone, so `area_total_assigned` exceeds `area_union`. A solution that
  adds extent areas produces every document in the right shape with every number
  too large.
- (focal) Three rules are withheld and must be voted out of shipped observation
  records: the clock keying of the summer windows, the duplicate record
  tiebreak, and the single precedence exception. Each has two plausible
  settlements and the corpus decides between them.
- (focal) Visibility is bitemporal. Records carry an effective term and a
  `recorded_at` stamp, and only records recorded strictly before the as of
  instant may be read. Ignoring the cutoff moves `area_union` by 39110310300.
- (focal) Month buckets are keyed to the local calendar of the zone, not to
  universal time, so the South zone needs a 2030 12 key and the other three need
  a 2032 01 key.

Drift items, where a defensible but different reading silently changes a graded
number:

- (drift) Half open bounds. Frequency and time extents are `[low, high)`.
  Treating either end as closed changes every area by a thin margin and changes
  `rectangles`.
- (drift) Clip before aggregate. Frequency is trimmed to the usable channel runs
  and time to the horizon before any measure is taken, never after.
- (drift) Suspensions remove time from the measure but the grant stays
  measurable and stays in the duty audit.
- (drift) The two segment unions overlap, so their sum exceeds the total union
  by 996572639775 and the segment basis point split uses the summed denominator.
- (drift) `shared_ratio_ppm` is rounded half to even exactly once, at the end.

Trap items, planted conflicts that a careful reader resolves from the notes:

- (trap) `bandwidth` appears in kilohertz in the register extracts and in hertz
  in the office logs, under the same column name.
- (trap) Alias redirections form chains and eleven cycles, and 1937 of the 2100
  rows are self maps.
- (trap) Subordinate grants clip to parents, and parent cycles, unknown parents
  and withdrawn parents each take their own reject code.
- (trap) Reservation rules include retired rows, day 31 recurrences in months
  with no day 31, and windows crossing local midnight.
- (trap) The manifest declares row counts that are wrong for seven files.

## Load-bearing work

### The three withheld rules and how each is settled

**Clock keying of the summer windows.** `zone_time_rules.md` publishes each
summer window as a bare wall clock stamp and says the keying is uniform and
settled by `zone_clock_marks.csv`. Keep only rows whose jurisdiction is
`register`; the `neighbour` rows follow a different schedule and bind nothing.
For each candidate keying build the window on universal time, once by
subtracting the standard offset from the published stamp and once by reading the
stamp as universal time, then count the marks whose implied offset disagrees.
The shipped corpus admits `local_standard` with zero disagreements. The marks are
dense to fifteen minutes around each transition, and the two candidates differ by
a whole standard offset, so the vote is decisive.

**Duplicate record tiebreak.** `precedence_policy.md` states that the governing
record of a layer is the visible record of highest revision and that one uniform
tiebreak on `recorded_at` settles a tie. `register_governing_flags.csv` flags,
for a sample of grants, which of the tied rows the published register treated as
governing. Group its rows by grant and layer, keep the groups whose highest
revision is shared by two or more rows, and ask whether the flagged row carries
the earliest or the latest stamp of the group. The shipped corpus votes
`earliest`.

**Precedence exception.** The published ranks are `coord`, then `core`, then
`office`. One exception promotes a single layer to rank one for exactly one
segment and one field group and never touches the identity group, so holder
resolution and the licence segment are safe to settle first with the published
ranks. `precedence_observations.csv` records the layer the register actually
followed for a sample of grants and groups. For each observation compute the
layer the published ranks would pick, given which layers supply that group for
that grant, and keep the disagreements. The disagreements concentrate in exactly
one cell of segment by field group. For the shipped corpus that cell is the
`public` segment and the `time` group, and the layer the register followed there
is `office`. Over applying the exception to the commercial segment moves 2260
further grants that reach the fault tests, and under applying it returns the 1497
public grants that reach the fault tests to their published layer, so the two
mistakes cost different amounts.

### Why each shipped file carries weight

Every record file feeds either an extent, a reject, a note, the duty audit, the
reservation subtraction or a per file row tally, and every policy note is parsed
for a table the pipeline consumes: the band table, the zone clock table, the
precedence ranks and registry tie steps, the five normalisation steps and the
four effective end encodings, the state transition table, the reject order and
note vocabulary, the recurrence tokens, the four duty quantities, the document
headings of the contract, the file to layer index and the declared row counts.
Removing any one of them removes a parsed table or a measured input, so the
measurement cannot be reproduced without it.

## Verification

Three identities hold by construction and are checked on every corpus:

- `area_union = area_exclusive + area_shared`
- `area_excess = area_total_assigned - area_union`, and `excess_charge_total`
  equals `area_excess` exactly, because the charge rule distributes the excess
  cell by cell
- the four per zone unions sum to the total union, because zone is a coordinate
  and nothing cancels across zones

Local month buckets sum to the zone union, band buckets sum to the zone union,
and both basis point splits sum to 10000. These were checked on the shipped
corpus and on two further corpora built from different seeds, different band
plans, different zone clocks, a different horizon and a different settlement for
each of the three withheld rules.

The artifact channel registers checks whose positive weights total 67, and the
negative checks are `negative_hardcoded_sample_answers`,
`negative_area_union_equals_total_assigned`,
`negative_region_months_use_utc_calendar`,
`negative_measures_ignore_the_as_of_cutoff`,
`negative_reservation_exceptions_not_applied`,
`negative_output_independent_of_the_corpus`,
`negative_module_reads_a_fixed_corpus_path`,
`negative_module_writes_outside_the_output_directory`,
`negative_module_mutates_the_corpus`,
`negative_output_directory_has_extra_files`,
`negative_documents_carry_extra_keys`,
`negative_documents_contradict_each_other` and
`negative_module_imports_outside_the_standard_library`.

### Figures that live outside every document

| figure | value |
| --- | --- |
| grants with a visible governing record in all three layers | 3384 |
| union measure with no visibility cutoff | 4406036105000 |
| reservation occurrences with the exceptions file ignored | 3715 |
| grants the precedence exception moves, among the grants that pass every reject test | 1248 |
| alias identifiers needing three or more redirections | 9 |
| distinct frequency bounds among the East extents | 607 |
| grants splitting their time and frequency layers | 2401 |
| declared row total of the manifest | 109752 |
| grants carrying more than one final extent | 604 |

## Root cause

A grant contributes a set of axis aligned extents
`[f_low, f_high) x [t_lo, t_hi)` inside its zone. Zone is a coordinate, so the
total covered measure is the sum of the four per zone covered measures and
nothing cancels across zones. Inside a zone, however, grants from different
holders and different layers overlap freely, and the register has never
published an overlap free view of itself. Every quantity the task asks for is
therefore a property of a point set, not of a row set, and no amount of careful
row level bookkeeping reaches it.

The second cause is that the register is a record of records. A row is not a
fact; it is a claim filed at a moment, superseded by revision, retracted by
notice, and visible only if it was recorded before the as of instant. The
governing view has to be assembled per grant and per field group before any
geometry exists at all.

The third cause is that the coordinate of time is local. Zones carry standard
offsets, three of them carry summer windows, and one carries a half hour offset.
A measure taken on universal time is correct in total and wrong in every month
bucket.

## Solution shape

Three measures are taken per zone from one sweep:

- `area_union`, the measure of the covered set
- `area_exclusive`, the measure of the part exactly one extent covers
- `area_shared`, the measure of the part two or more extents cover

The sweep compresses frequency breakpoints, groups extents by the slabs they
span, and sweeps time inside each slab with the month boundaries of the zone
injected as zero width events. One pass therefore yields the union, the
multiplicity split, the per band buckets, the per local month buckets and the
per grant charges. All arithmetic is integer; the only rounding in the whole
pipeline is the single half to even step for `shared_ratio_ppm` and the largest
remainder step for the two basis point splits.

## Ordered plan

1. Parse `measure_config.ini`, `unit_declarations.ini` and the policy notes.
2. Settle the clock keying, then read every stamp to universal time. Office logs
   are local to the zone in their file name, minutes carry their own offset and
   register extracts and state events are universal.
3. Admit only records whose `recorded_at` is strictly before the as of instant.
4. Pick the governing record of each layer under the derived tiebreak.
5. Settle identity with the published ranks, normalise the holder reference,
   close the alias redirections, pick the registry row and read the status
   history. That yields the licence segment.
6. Settle the exception, then settle the time and frequency groups.
7. Withdraw retracted grants, then test the rest against the reject codes in the
   published order and record one code each.
8. Trim frequency to the usable channel runs, trim time to the horizon, cut the
   active intervals from the state events.
9. Expand the reservation recurrences, cancel then add from the exceptions file,
   subtract the reserved spectrum, and take the subtracted measure as the union
   before subtraction less the union after it.
10. Clip subordinate grants to their parents in dependency order.
11. Reduce the extents of each grant, then measure.
12. Run the duty audit, then write the documents.

## Pitfalls

| trap | where it fires | graded value that moves when handled wrongly |
| --- | --- | --- |
| half open frequency and time bounds | grants with bounds exactly on a horizon or band edge | every area measure and `rectangles` |
| band gap between B1 and B2 | 76 grants whose governing frequency bounds run from 429950 to 450050, 59 of them measurable | `band_area_union`, `area_union`, `SPLIT_BY_RASTER` |
| withdrawn channels in the raster | 24 channels across the four bands | `area_union`, `CLIPPED_TO_BAND`, `SPLIT_BY_RASTER` |
| raster misalignment | 149 grants with a bound off a channel edge | `rejects.RASTER_MISALIGNED`, `assignments_measurable` |
| hertz width columns in the office logs | every office row, 16480 of them | every frequency bound, `rejects.UNIT_AMBIGUOUS` |
| hertz width not a whole kilohertz | none in the shipped corpus, where office never governs the frequency group; 9 office rows of the shifted held out corpus and 1 of the edge corpus carry a 137 hertz remainder and reject 7 and 1 grants | `rejects.UNIT_AMBIGUOUS` |
| declared unit token in the minutes | minute rows with `kHz`, with `Hz`, with `MHz` and with the token absent | `rejects.UNIT_AMBIGUOUS`, frequency bounds |
| explicit upper bound against the stated width | 46 grants | `notes.WIDTH_MISMATCH`, `area_union` |
| absent upper bound | core rows whose index is four modulo nine | frequency bounds |
| three layer precedence per field group | every grant | `layer_governing_counts` and every measure |
| the promoted layer exception | 1497 public grants that reach the fault tests, 1248 of them passing every reject test | every time bound of those grants |
| duplicate highest revision | 1254 layer groups carry a duplicated top revision | every bound of those grants |
| records recorded on or after the as of instant | 6180 extract rows, 170 office rows and 135 minute rows | `area_union` moves by 39110310300 |
| retraction by record action or by a live notice | 182 grants withdrawn in all | `retracted`, `assignments_measurable` |
| retraction notice cancelled by a later notice | 135 notices of withdrawn scope | `retracted` |
| notices recorded after the as of instant | 126 notices | `retracted` |
| empty effective end | 56 grants | `notes.OPEN_ENDED`, `area_union` |
| json null effective end | 13 grants | `rejects.TERM_MISSING` |
| effective end equal to the start | 71 grants that pass every reject test, 88 among the grants that reach the fault tests | `zero_span`, `assignments_measurable` |
| inverted effective bounds | 94 grants | `rejects.SPAN_INVERTED` |
| holder reference forms | seven written forms across the sources | `HOLDER_UNKNOWN`, segment attribution |
| alias chains and cycles | 1937 self maps and 163 live redirections, 11 cycles, longest chain three hops | segment attribution, `alias_cycles` |
| registry conflicts | 116 superseded rows and 56 concurrent rows | segment attribution, `segment_area_union` |
| provisional holder filed against another zone | 135 grants | `rejects.ZONE_MISMATCH` |
| confirmed holder filed against another zone | 253 grants | `notes.ZONE_OF_RECORD_DIFFERS` |
| suspend and restore intervals | 1318 grants carry at least one visible suspension | `area_union`, `month_area_union` |
| restore without a suspension | 178 events | `notes.STATE_ANOMALY` |
| terminate as an absorbing state | 509 terminate events | `area_union` |
| events outside the effective term | 127 visible events before the effective start and 836 at or after the effective end, over the grants that reach the fault tests | `area_union` |
| events recorded after the as of instant | 96 events | `area_union` |
| parent clipping in dependency order | 150 subordinate grants with a resolved parent chain, 119 of them measurable | `area_union`, `parent_chain_max_depth` |
| parent cycles | 56 grants | `rejects.PARENT_CYCLE` |
| parent outside the register or in another zone | 25 grants | `rejects.PARENT_UNKNOWN` |
| parent withdrawn or rejected | 57 grants | `rejects.PARENT_RETRACTED` |
| retired reservation rules | 689 rows per zone | `guard_occurrences`, `guard_subtracted_area` |
| monthly day 31 recurrences | five months of the year have no day 31 | `guard_occurrences` |
| reservation crossing local midnight | the weekly rules starting at 23:30 | `guard_subtracted_area` |
| reservation exceptions | 42 cancellations and 12 additions inside the horizon | `guard` block, `area_union` |
| half hour zone offset | the West zone at 19800 and 23400 seconds | every West bound and month bucket |
| zone with no summer window | the South zone | `summer_window_utc` |
| local month boundaries | the South zone needs a 2030 12 key, the other three need a 2032 01 key | `month_area_union` keys and values |
| duty allowance in kilohertz minutes | 443 rows whose notes read the minute token | `total_allowance`, `months_in_deficit` |
| duty months outside the horizon | one row per audited holder | `total_allowance` |
| duty on the holder filing zone | audited holders filed against a zone other than their grants | `month` buckets of the audit |
| carry reset by a suspension | 281 months | `carry_forward_end`, `duty_carry_end` |
| union not sum for holder occupancy | holders with overlapping grants | `months_in_deficit`, `total_consumed` |
| largest remainder shares | zone and segment shares both sum to 10000 | `zone_share_bp`, `segment_share_bp` |
| segment share denominator | the two segment unions exceed the total union by 996572639775 | `segment_share_bp` |
| round half even once | `shared_ratio_ppm` | `shared_ratio_ppm` |
| manifest declarations that are wrong | seven record files | `manifest_mismatches` |
| self maps and dead aliases in the alias map | 1937 self maps among 2100 rows | `alias_fixpoint_depth` |
| duplicate consecutive state events | 1077 pairs of adjacent same kind events among the visible events, carried by 904 grants | `area_union` |

## Provenance

```yaml
uuid: 4a5f9738-d10e-5f43-aefc-c30e9c5186fd
instance_id: 4a5f9738-d10e-5f43-aefc-c30e9c5186fd
task_name: terminal-bench/4a5f9738-d10e-5f43-aefc-c30e9c5186fd
fix_patch_sha256: 2f71c69a1cedff8eea42c6281bf6d77c16befec0d9ff5c29864750bfd49ccc8e
solve_py_sha256: c185399f7165fa332a1302416e1ff0fc8e68726e127e9868569dd5d31cdafa92
language: python
```
