# Detector Flux Reconciliation Contract

This corpus is a reconciliation extract from a four-instrument detector array
(G1..G4) over three observing epochs (E1, E2, E3). Raw analog-to-digital counts
must be reconciled into a calibrated flux in integer micro-jansky
(`calibrated_flux_ujy`). The extract ships a set of reference tables and a
faulty pre-computed pipeline. Your job is to compute the correct reconciliation.

## Records

Each observation carries: `obs_id`, `instrument`, `band` (one of u,g,r,i,z),
`mjd` (modified Julian date), a written gain label, `raw_counts`, a `pixel`, and
a CSV quality flag. The observation stream appears in more than one file; where
two files disagree on a column name, the value is the same reading under a
different name (see the glossary).

## Pipeline (correct application order)

The correction stages are documented across separate files. THE
ORDER THOSE FILES APPEAR IN IS NOT THE ORDER THEY APPLY IN. The correct
application order is:

1. CLIP: a reading above the detector's full well is not a measurement, it is a
   ceiling. Read `full_well_counts(instrument)` from the full-well capacity
   table. When `raw_counts > full_well_counts`, the observation is SATURATED and
   `effective_counts = full_well_counts`; otherwise it is not saturated and
   `effective_counts = raw_counts`. Clipping happens BEFORE dark subtraction, so
   every later stage works on `effective_counts`, never on `raw_counts`.
2. DARK: `net = effective_counts - dark_current_counts(instrument, band, epoch)`.
   The authoritative dark-current value is the `authoritative` row for each
   (instrument, band, epoch); `informational` rows are repeat readings.
3. NONLINEARITY: apply the per-instrument Horner polynomial to `net`
   (`response_curve_horner`), BEFORE gain. Coefficients are stored x1e6 and the
   result is divided back by 1e6 with banker's rounding.
4. GAIN: multiply by the quantum yield of the RESOLVED channel. The gain label
   written in the observation is not always the channel that applies: labels
   were folded across epochs (`channel_lineage_fold`). Resolve the channel by
   (written label, mjd) first, then look up the micro-e-per-count value and
   divide by 1e6.
5. SCALE: multiply by the per-instrument scale factor. This factor is stored
   x1e6 and must be divided by 1e6. The authoritative scale factor is published
   only in the scale workbook.
6. DRIFT: compute `drift_correction = round_half_even(scaled * drift_ppm / 1e6)`
   and SUBTRACT it (`thermal_drift_ppm`). The correction is subtracted, not
   added.
7. QUANTIZE: `calibrated_flux_ujy = round_half_even(value)` (banker's rounding).

## Saturation

Saturation is a measurement limit, not a dispute: a saturated observation stays
live, keeps the flux computed from its clipped counts, and contributes that flux
to every rollup, ranking and total exactly as an unsaturated observation does.
Saturation changes two things and nothing else:

- A saturated observation is NOT ELIGIBLE for a band median. Each band median is
  the median of the live, non-saturated observations of that band. A band whose
  live observations are all saturated has no eligible sample, so it carries no
  median at all.
- A saturated observation is NEVER FLAGGED as an anomaly, however large its flux
  is. A clipped reading exceeding three times its band median is the ceiling
  showing through, not a detection.

An observation exactly at full well (`raw_counts == full_well_counts`) is NOT
saturated: the clip applies only above the ceiling.

## Exposure attribution

The reconciled total must also be attributed back to the four instruments in
proportion to their published exposure weight, as whole micro-jansky that sum to
the total exactly. The weights are integers stored x1e6 in the exposure weight
table; their scale cancels in the ratio, so they are used as published.

With `pool` the total reconciled flux after dead-pixel closure, `w(i)` the
weight of instrument `i` and `W` the sum of all four weights:

1. `exact(i) = pool * w(i) / W`, kept as an exact rational, never as a float.
2. `base(i) = floor(exact(i))`, rounding toward negative infinity.
3. `leftover = pool - sum(base(i))`, which is at least 0 and less than 4.
4. Order the instruments by the fractional part `exact(i) - base(i)`
   DESCENDING, breaking ties by instrument name ASCENDING. The first `leftover`
   instruments in that order each receive one additional micro-jansky.

The result is the largest-remainder apportionment: every attributed amount is an
integer and the four amounts sum to `pool` exactly. Rounding each share on its
own and hoping the parts add up is wrong, and so is giving the leftover to the
largest share rather than to the largest remainder. All four instruments are
attributed, including an instrument with no live observation.

## Relay audit

The dead-pixel redistribution must also be reported hop by hop, so the closure
can be audited rather than taken on trust. For each masked pixel, in ascending
pixel order, record the amount it relays, how that amount split across its
targets, and where the flux finally lands:

- `relayed_ujy` is the FULLY ACCUMULATED amount the pixel relays: its own base
  flux plus everything relayed into it by pixels resolved before it. It is the
  amount the least fixed point gives that pixel, not its base flux.
- The split is the one the closure already uses: each target receives
  `floor(relayed_ujy / target_count)`, and the leftover
  `relayed_ujy - floor(relayed_ujy / target_count) * target_count` goes to the
  FIRST target in ascending target order. The per-target amounts sum to
  `relayed_ujy`.
- `terminal_pixels` is where the flux ends up: every UNMASKED pixel reachable
  from this pixel by following relay edges, transitively, through any number of
  masked hops. A target that is itself masked is not a terminal pixel; its own
  targets are followed instead.

## Epoch resolution

`epoch` is resolved from `mjd` against half-open intervals `[start, end)`
(`epoch_window_bounds`). A reading whose mjd equals an interval end belongs to
the next epoch.

## Dead-pixel redistribution

Some pixels are masked (`occlusion_relay_graph`). A masked pixel contributes
zero to its own totals; its flux is redistributed to its target pixels. Targets
may themselves be masked, so redistribution is a least-fixed-point resolved in
ascending pixel order: a masked pixel distributes its fully-accumulated flux to
its targets, split evenly with any remainder going to the first target. A
single redistribution pass that uses only base (pre-redistribution) flux is
wrong wherever a chain is longer than one hop.

## Source precedence (disputed observations)

The CSV quality flag and the disputed-observation adjudication log disagree on
some observations. The adjudication log (the PDF dossier) OVERRIDES the CSV
flag. An observation adjudicated `disputed` is DROPPED from every rollup and
recorded in the dropped-observations artifact; the CSV `suspect` flag alone does
not drop an observation.

## Determinism

All JSON output must be serialized with sorted keys and a trailing newline and
use integer micro-jansky throughout. Output must be byte-identical across reruns
and independent of input row order.

## Settlement layer

The reconciled flux of an observation is an instrument reading taken over
whatever integration time that frame happened to get. Settling the extract turns
those readings into comparable rates and removes the readings that are not
measurements of the sky. The settlement layer runs AFTER dead-pixel closure and
reads the per-observation `calibrated_flux_ujy` computed above. It never revises
the reconciliation layer: every total, rollup, median, ranking and attribution
specified above keeps the value it already has.

### S1 Exposure normalisation

Every observation carries an integration time in milliseconds in the exposure
ledger. The settled rate of an observation is

    rate_ujy_per_ks = floor(calibrated_flux_ujy * 1000000 / exposure_ms)

This stage is the one place in this contract that does NOT use banker's
rounding. The division is a floor division toward negative infinity, so a
negative numerator moves away from zero rather than toward it.

An observation whose `shutter_state` reads `aborted` carries an `exposure_ms` of
0. Its integration never completed, so it is not a measurement of anything: it
is held out of the settlement layer entirely, carries no settled rate, takes no
part in any settlement median, and is recorded in the zero-exposure artifact.

A dropped observation is not settled either, for the reason it was dropped.

### S2 Cosmic ray rejection

Within each pair of instrument and band, let `med` be the median of the settled
rates of that group and let `mad` be the median of the absolute deviations
`abs(rate - med)` over the same group. Both medians follow S3. The rejection
threshold of the group is

    threshold = med + 6 * mad

A settled observation whose rate is STRICTLY GREATER than the threshold of its
own group is a cosmic ray hit. It is recorded in the cosmic-ray artifact and held
out of the settled pool. The median absolute deviation enters the threshold as
published, with no consistency scaling applied to it.

Two exemptions apply, and both are absolute:

- A group holding fewer than four settled observations is too small a sample to
  reject from, so every observation in it survives however large its rate is.
- A near-saturated observation as defined in S8 survives, because its rate is
  the ceiling of the detector showing through rather than a cosmic ray.

### S3 Median convention

Every median in the settlement layer, the group medians of S2 included, is taken
over the sorted sample. A sample of odd size takes its middle value. A sample of
EVEN size takes the LOWER of its two middle values and never their mean. This is
a different convention from the band median of the reconciliation layer above,
which keeps the banker's rounding of its two middle values.

### S4 Photometric band order

Wherever the settlement layer puts bands in order, the order is the photometric
order u, g, r, i, z. Alphabetical order of the band letters is never the order of
a settlement artifact.

### S5 The settled pool

`settled_pool_ujy` is the sum of the settled rates of every settled observation
that survives S2.

### S6 Settled attribution

The settled pool is attributed across the four instruments by the
largest-remainder method of the exposure attribution section above, reading the
same published exposure weights, applied to `settled_pool_ujy` in place of the
reconciled total. All four instruments are attributed and the four attributed
amounts sum to `settled_pool_ujy` exactly.

### S7 Settlement digest

Put the observations that survive S2 in order of settled rate DESCENDING,
breaking a tie by band in the photometric order of S4 and breaking a remaining
tie by `obs_id` ASCENDING. With `r(i)` the settled rate at one-based position
`i` of that order and `n` the number of surviving observations,

    settlement_digest = (sum over i from 1 to n of i * r(i)) mod 1000003

### S8 Near-saturation

An observation whose `raw_counts` reach or exceed 98 percent of
`full_well_counts(instrument)` while staying at or below that ceiling is NEAR
SATURATED. The comparison is the integer test
`raw_counts * 100 >= full_well_counts * 98`, and a saturated observation is not
near saturated because it is already above the ceiling. A near-saturated
observation is a real measurement: it is settled normally, it keeps its place in
every rollup, and S2 never rejects it. Near saturation is recorded in the
near-saturation artifact.
