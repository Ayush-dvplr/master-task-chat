# Cold-Storage Contaminant Panel CSP-2026: reporting contract

The authority publishes one panel per extract of laboratory transmissions. This
contract governs the shipped extract in `corpus/` and every other extract the
program is run on.

## Declared universe

The panel is defined over fixed, declared lists. Order matters wherever lists
are written out.

Depots (in this order):

| code | name |
|------|------|
| KES | Kestrel Quay |
| MAR | Marlow Cross |
| OSS | Ossory Basin |
| TAL | Tallis Yard |

Quarters (in this order), assigned by `collected_on`, both ends inclusive:

| quarter | first day | last day |
|---------|-----------|----------|
| 2026-Q1 | 2026-01-01 | 2026-03-31 |
| 2026-Q2 | 2026-04-01 | 2026-06-30 |
| 2026-Q3 | 2026-07-01 | 2026-09-30 |

Assays (in this order) with their limits in mg/kg:

| code | analyte | limit |
|------|---------|-------|
| PB | lead | 0.300 |
| CD | cadmium | 0.100 |
| HG | mercury | 0.500 |
| AS | inorganic arsenic | 0.200 |
| HIS | histamine | 100.000 |

The panel always has one row for every declared depot and every declared
quarter (4 x 3 = 12 rows), and every row has a cell for every declared assay,
whether or not any transmission in the extract refers to that depot, quarter
or assay. Likewise every declared depot gets a depot report, every declared
assay gets an assay report, and every declared quarter appears in
`quarters.csv` and in each report's quarter list. A cell with no accepted
measurement has status `NO_SAMPLE` with `n` 0, `mean` null, `max` null and
`exceedances` 0. A row, quarter or depot with no accepted measurement has
status `NO_DATA`. In the summary files (depot reports, assay reports) a mean,
max or worst ratio with nothing to summarise is written as the number `-1`.

## Input

`<corpus_dir>/transmissions/*.csv`: every `.csv` file in that directory is
part of the extract (file names carry no meaning). Columns:

`transmission_id,lab,sample_id,depot,collected_on,assay,result,reported_at`

- `collected_on` is `YYYY-MM-DD`; `reported_at` is `YYYY-MM-DDTHH:MM:00Z` (UTC).
- `result` is a decimal string in mg/kg with three decimals.
- One transmission is one lab's result for one assay on one physical sample.

## Validation

Each transmission is checked in this order and rejected at the first failure:

1. `UNKNOWN_DEPOT`: `depot` is not a declared depot code.
2. `UNKNOWN_ASSAY`: `assay` is not a declared assay code.
3. `OUT_OF_PERIOD`: `collected_on` falls in no declared quarter.

Rejected transmissions are listed in `rejected.csv` and contribute nothing
else. Valid transmissions that compete for the same `(sample_id, assay)` are
resolved by `source_rules.md`; exactly one per key is accepted, the rest are
superseded.

## Aggregation

All statistics use accepted measurements only.

- Cell `(depot, quarter, assay)`: `n` = number of accepted measurements;
  `mean` = arithmetic mean of their results; `max` = largest result;
  `exceedances` = how many results are strictly greater than the assay limit.
  A cell with `n` > 0 has status `MEASURED`.
- Row `samples` = number of distinct `sample_id` with at least one accepted
  measurement in that depot and quarter. Row status: `NO_DATA` if samples is 0,
  else `BREACH` if any cell has exceedances > 0, else `COMPLIANT`.
- Depot report quarter entry: `samples` and `status` copy the panel row;
  `worst_ratio` = the largest `max / limit` over the row's measured cells.
  Depot `total_samples` = distinct sample ids over all quarters;
  `breach_quarters` = number of BREACH entries; depot status `NO_DATA` if
  total_samples is 0, else `BREACH` if breach_quarters > 0, else `COMPLIANT`.
- Assay report: `n`, `mean`, `max`, `exceedances` over all accepted
  measurements of that assay; status `NO_SAMPLE` if n is 0, else `EXCEEDED` if
  exceedances > 0, else `WITHIN`. Each `by_quarter` entry carries the same
  four statistics for that quarter plus `depots_sampled` = number of depots
  with n > 0 for the assay in that quarter.
- `quarters.csv`: `depots_reporting` = rows of that quarter with samples > 0;
  `samples` = sum of those rows' samples; `breach_rows` = BREACH rows;
  `no_data_rows` = NO_DATA rows; status `NO_DATA` if samples is 0, else
  `BREACH` if breach_rows > 0, else `COMPLIANT`.
- Means and ratios are computed exactly in decimal and rounded half-up to
  three decimals. `max` is the result value itself.

## Output

`/app/derive_report.py <corpus_dir> <out_dir>` writes into `<out_dir>`:

| file | content |
|------|---------|
| `panel.json` | `panel` (`"CSP-2026"`), `ledger`, `rows` |
| `depots/<DEPOT>.json` | one per declared depot |
| `assays/<ASSAY>.json` | one per declared assay |
| `quarters.csv` | one line per declared quarter |
| `measurements.csv` | every accepted measurement |
| `rejected.csv` | every rejected transmission |

`ledger` has `rows_read` (all transmissions), `accepted`, `superseded`,
`rejected`; `rows_read = accepted + superseded + rejected`.
Panel rows are ordered by depot then quarter; quarter lists by quarter; cells
by assay order. `measurements.csv` columns
`sample_id,depot,quarter,assay,lab,transmission_id,result`, sorted by
`sample_id` then assay order, `result` copied verbatim. `rejected.csv` columns
`transmission_id,reason`, sorted by `transmission_id`. Exact keys and types are
in `output_schema.json`. CSV files have a header line and `\n` line endings.
