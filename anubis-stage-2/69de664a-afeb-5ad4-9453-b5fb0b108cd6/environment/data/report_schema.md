# Report schema (authoritative)

This file fixes the shape of every artifact the reconciliation writes into
`OUT_DIR`. The contract in `reconciliation_contract.md` says how to compute the
numbers; this file says what to call them and how to lay them out. Both are
binding.

## Rules that hold for every artifact

- `report_id` is the literal string `detector-flux-reconciliation` in every JSON
  artifact that carries the field. It is a fixed label, never derived from a
  filename or a directory.
- Every flux, count and correction is a JSON integer. A value written as
  `25089.0`, as `"25089"` or as a boolean is a different value.
- Every JSON file is serialized with 2-space indentation, sorted keys and one
  trailing newline, exactly as `json.dumps(obj, indent=2, sort_keys=True)`
  followed by a newline produces.
- Object keys that name a band, an epoch, an instrument, a channel or a pixel
  are sorted ascending by that key.
- In a JSON object keyed by band, epoch, instrument or channel, a key is present
  only when that key has a contributing observation. Absent keys are OMITTED,
  never written with a zero. This is the opposite of the delimited rollups
  below, which carry a row for every key in a fixed order and zero-fill the
  ones with no live observation. The two exceptions, where all four instruments
  are always present because the weight table and not the data decides the key
  set, are `exposure_weight_micro` and `attributed_ujy` in
  `flux_attribution.json`.
- Only live (non-dropped) observations appear in any rollup, ranking, median or
  anomaly. Dropped observations appear only in `dropped_observations.json`.
- A saturated observation is live and appears in every rollup, ranking and
  total, but it is excluded from every band median and is never an anomaly.

## summary.json

Exactly these ten keys, nothing else:

| key | type |
|-----|------|
| `report_id` | string, the fixed label |
| `observation_count` | integer, every observation in the extract |
| `live_count` | integer, observations surviving adjudication |
| `dropped_count` | integer, observations the dossier adjudicated as disputed |
| `total_reconciled_flux_ujy` | integer, the total after dead-pixel closure |
| `band_flux_ujy` | object, band to integer |
| `epoch_flux_ujy` | object, epoch to integer |
| `instrument_flux_ujy` | object, instrument to integer |
| `channel_usage` | object, resolved channel to integer count |
| `band_median_ujy` | object, band to integer median of the eligible flux in that band |

`band_median_ujy` is quantized with the same banker's rounding as every other
figure, so a median that falls on an exact half resolves to the even integer.
Its eligible sample is the live, non-saturated observations of the band, so a
band whose live observations are all saturated carries no key here.

## reconciled_flux.json

`report_id`, then `observations`, a list sorted by `obs_id` ascending. Each
entry carries exactly:

`obs_id`, `instrument`, `band`, `epoch`, `resolved_channel`, `effective_counts`,
`saturated`, `net_counts`, `linearized`, `drift_ppm`, `drift_correction`,
`calibrated_flux_ujy`.

`resolved_channel` is the channel after the epoch fold, `effective_counts` is
the count after the full-well clip (equal to `raw_counts` when the reading is
below or at the full well), `saturated` is a JSON boolean and is `true` only
when the clip applied, `net_counts` is the dark-subtracted effective count,
`linearized` is the Horner result, and `drift_correction` is the subtracted
amount.

## calibration_audit.json

`report_id`, plus:

- `scale_factor_micro`: instrument to the integer the workbook publishes, as
  stored, before the divide by 1e6.
- `gain_micro_e_per_count`: channel to the stored integer micro-e-per-count.
- `drift_ppm`: key `<instrument>:<epoch>` (for example `G1:E1`) to integer ppm,
  for every instrument and epoch pair.
- `nonlinearity_coeffs`: instrument to the coefficient list, highest degree
  first.
- `epoch_windows`: epoch to a two-element list `[mjd_start, mjd_end]`.
- `fold_applied`: a sorted list of the folds that change a channel, each written
  `<written_label>:<epoch>-><resolved_channel>` (for example `A0:E2->A2`).
  A label that resolves to itself is left out.

## data_quality.json

`report_id`, `input_file_count` (integer, the number of files present in
`DATA_DIR`), `observation_count`, `disputed_count`, `masked_pixel_count`,
`distinct_pixels` (integer, pixels appearing in the closure),
`suspect_but_not_disputed`, a sorted list of the obs_ids the CSV flags suspect
and the dossier clears, `saturated_count` (integer, live observations the
full-well clip applied to) and `saturated_obs_ids`, a sorted list of those
obs_ids.

## instrument_G1.json, instrument_G2.json, instrument_G3.json, instrument_G4.json

`instrument` (string), `observation_count`, `flux_ujy` (integer total for that
instrument), `band_flux_ujy` and `epoch_flux_ujy`. These four carry no
`report_id`.

## epoch_totals.json

`report_id`, `epoch_flux_ujy`, `epoch_observation_count`.

## deadpixel_closure.json

`report_id`, `masked_pixel_count`, `resolved_pixel_flux_ujy` (pixel to integer
flux after the closure, masked pixels present with 0) and
`total_after_closure_ujy`.

## anomaly_ledger.json

`report_id`, `rule` set to the literal string
`flux > 3 * band median (live, non-saturated only)`, and `anomalies`, a list
sorted by `obs_id` ascending whose entries carry `obs_id`, `band`,
`calibrated_flux_ujy` and `band_median`.

## ordered_flux_index.json

`report_id`, `order` set to the literal string
`calibrated_flux_ujy desc, obs_id asc`, and `index`, a list whose entries carry
`rank` (integer starting at 1), `obs_id` and `calibrated_flux_ujy`.

## dropped_observations.json

`report_id`, `source` set to the literal string `adjudication_dossier.pdf`, and
`dropped_obs_ids`, a sorted list of obs_ids.

## provenance_manifest.json

`report_id` plus these fixed values, which record the decisions the contract
mandates:

| key | value |
|-----|-------|
| `scale_factor_source` | `gain_scale_workbook.xlsx` |
| `disputed_source` | `adjudication_dossier.pdf` |
| `raw_counts_source` | `obs_capture_index.csv` |
| `full_well_source` | `full_well_capacity.tsv` |
| `exposure_weight_source` | `exposure_weight_micro.tsv` |
| `attribution_method` | `largest_remainder` |
| `pipeline_order` | `["clip", "dark", "nonlinearity", "gain", "scale", "drift", "quantize"]` |
| `rounding` | `half_even` |
| `drift_operation` | `subtract` |
| `deadpixel_resolution` | `least_fixed_point` |
| `source_precedence` | `["adjudication_dossier.pdf", "csv_quality_flag"]` |
| `total_reconciled_flux_ujy` | integer, the same total as summary.json |

## flux_attribution.json

`report_id`, plus:

- `pool_ujy`: integer, the total reconciled flux after dead-pixel closure, the
  same figure `summary.json` carries.
- `exposure_weight_micro`: instrument to the integer weight the exposure table
  publishes, as stored. All four instruments are present.
- `attributed_ujy`: instrument to the integer attributed amount. All four
  instruments are present, including one with no live observation, and the four
  amounts sum to `pool_ujy` exactly.
- `remainder_recipients`: a list of the instruments that received one additional
  micro-jansky from the leftover, sorted ASCENDING by instrument name rather
  than in award order. It is empty when the leftover is 0, and it never holds
  more than three entries.

## relay_audit.json

`report_id`, `masked_pixel_count`, and `relays`, a list with one entry per
masked pixel sorted by `pixel` ascending. Each entry carries exactly:

- `pixel`: the masked pixel.
- `relayed_ujy`: integer, the fully accumulated amount the pixel relays.
- `targets`: the pixel's relay targets, sorted ascending.
- `per_target_ujy`: object, target to the integer amount this pixel sent it. The
  amounts sum to `relayed_ujy`, and the first target in `targets` carries the
  leftover of the even split.
- `terminal_pixels`: a sorted list of the unmasked pixels the flux reaches from
  this pixel, following relay edges transitively through any masked hops.

## The delimited rollups

Each carries a header row and one row per key in the fixed order below.

- `band_rollup.csv`: header `band,flux_ujy,observation_count`, rows for bands
  u, g, r, i, z in that order.
- `epoch_rollup.tsv`: header `epoch`, `flux_ujy`, `observation_count` separated
  by tabs, rows for E1, E2, E3.
- `instrument_rollup.psv`: header `instrument|flux_ujy|observation_count`, rows
  for G1, G2, G3, G4.

A band, epoch or instrument with no live observation is written with 0 in both
numeric columns.

## The remaining artifacts

- `flagged_observations.xml`: root element `flagged_observations` holding one
  self-closing `observation` element per anomaly, in the anomaly ledger order,
  with attributes `obs_id`, `band`, `calibrated_flux_ujy` and `band_median`.
- `objective_summary.yaml`: `report_id`, `total_reconciled_flux_ujy`,
  `live_count`, `dropped_count`, `anomaly_count` and `band_flux_ujy`, keys
  sorted.
- `reconciliation_report.md`: a human-readable summary carrying the report id,
  the observation, live, dropped, masked-pixel and anomaly counts, the total
  reconciled flux, and the per-band and per-epoch flux.
- `run_status.txt`: plain `key: value` lines carrying `status`, `observations`,
  `live`, `dropped` and `total_reconciled_flux_ujy`.

## Settlement artifacts

These eight artifacts carry the settlement layer of the contract. The rules at
the top of this file hold for them too, with one addition: a settlement list or
delimited row set ordered by band follows the photometric order u, g, r, i, z of
contract section S4, not alphabetical order.

## settlement_summary.json

Exactly these seven keys, nothing else:

| key | type |
|-----|------|
| `report_id` | string, the fixed label |
| `settled_pool_ujy` | integer, contract S5 |
| `settlement_digest` | integer, contract S7, already reduced by the modulus |
| `settled_count` | integer, observations surviving S2 |
| `rejected_count` | integer, observations S2 rejected |
| `zero_exposure_count` | integer, observations held out by S1 |
| `near_saturated_count` | integer, observations S8 marks |

## settled_rates.json

Two keys, `report_id` and `rates`. `rates` is a list carrying one object per
observation that S1 settled, ordered by `obs_id` ascending, each object holding
exactly `obs_id`, `instrument`, `band`, `exposure_ms`, `calibrated_flux_ujy`
and `rate_ujy_per_ks`. An observation S2 rejected still appears here with its
rate, because S1 settled it; only `settled_pool_ujy` excludes it.

## zero_exposure.json

Two keys, `report_id` and `observations`. `observations` is a list ordered by
`obs_id` ascending, each object holding exactly `obs_id` and `shutter_state`.
A dropped observation never appears here even when its shutter aborted.

## cosmic_ray_rejects.json

Two keys, `report_id` and `rejects`. `rejects` is a list ordered by `obs_id`
ascending, each object holding exactly `obs_id`, `instrument`, `band`,
`rate_ujy_per_ks`, `group_median`, `group_mad` and `threshold`.

## near_saturation.json

Two keys, `report_id` and `observations`. `observations` is a list ordered by
`obs_id` ascending, each object holding exactly `obs_id`, `instrument`,
`raw_counts` and `full_well_counts`.

## settled_attribution.json

Three keys, `report_id`, `settled_pool_ujy` and `attributed_ujy`.
`attributed_ujy` is an object carrying all four instruments, as in
`flux_attribution.json`, whose values sum to `settled_pool_ujy` exactly.

## band_settlement.csv

A comma-separated rendering with the header
`band,settled_count,settled_pool_ujy` and one row for each of the five bands in
the photometric order u, g, r, i, z. A band with no surviving settled
observation carries a row of zeros rather than being omitted.

## settlement_order.json

Two keys, `report_id` and `order`. `order` is the list contract S7 ranks, each
object holding exactly `position`, `obs_id` and `rate_ujy_per_ks`, where
`position` is the one-based index the digest multiplies by.

## Per-dimension rollups

Three families of per-dimension rollup carry the same reconciled figures cut
along different pairs of dimensions. Every cell of every family counts only live
observations, so a dropped observation reaches none of them, and a saturated
observation is counted in `observation_count` and in `flux_ujy` exactly as the
rules above require while also being counted in `saturated_count` wherever that
field appears.

Each family is always written in full. A cell with no live observation is
written with its counts and fluxes at zero rather than being omitted, because
the file set is fixed and does not vary with the data. This is the behaviour of
the delimited rollups above, and it holds here for the JSON family as well.

For any instrument and band, the `flux_ujy` of section D1 equals the sum of the
`flux_ujy` of that band across the three section D3 tables of that instrument,
and equals the sum of the `flux_ujy` of that instrument across the three
section D2 tables of that band. The three families are three cuts of one set of
figures and reconcile exactly.

## D1: cell_<instrument>_<band>.json

Twenty files, one for each of the four instruments paired with each of the five
bands, named with the instrument first, for example `cell_G3_r.json`. Each holds
exactly these six keys and nothing else: `instrument`, `band`,
`observation_count`, `flux_ujy`, `saturated_count` and `obs_ids`. `obs_ids` is
the list of contributing observation identifiers ordered ascending. This family
carries no `report_id`, as the per-instrument files above carry none.

## D2: grid_<epoch>_<band>.psv

Fifteen files, one for each of the three epochs paired with each of the five
bands, named with the epoch first, for example `grid_E2_i.psv`. Each is a
pipe-separated rendering with the header
`instrument|flux_ujy|observation_count` and one row for each of the four
instruments in the instrument order G1, G2, G3, G4.

## D3: span_<instrument>_<epoch>.tsv

Twelve files, one for each of the four instruments paired with each of the three
epochs, named with the instrument first, for example `span_G1_E3.tsv`. Each is a
tab-separated rendering with the header `band`, `flux_ujy` and
`observation_count` and one row for each of the five bands in the photometric
order u, g, r, i, z, which is the order section S4 fixes and not the
alphabetical order of the band letters.
