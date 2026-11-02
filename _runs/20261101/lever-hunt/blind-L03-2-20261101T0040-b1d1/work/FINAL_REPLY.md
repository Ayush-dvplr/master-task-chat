# FINAL REPLY — blind-L03-2 (85a4df3)

**Status: DONE.**

## What I built

`app/derive_report.py` — a Python 3 standard-library program, run exactly as the
contract specifies:

    python3 /app/derive_report.py <corpus_dir> <out_dir>

It reads every `.csv` under `<corpus_dir>/transmissions/` (file names carry no
meaning), validates each transmission in contract order — `UNKNOWN_DEPOT`, then
`UNKNOWN_ASSAY`, then `OUT_OF_PERIOD` — and resolves competing valid
transmissions for a `(sample_id, assay)` by lab priority tier (NRL 1; ACM/BLX 2;
FSK 3), breaking ties inside the best tier by the latest `reported_at`. It then
writes the full panel into `<out_dir>`: `panel.json`, `depots/<DEPOT>.json` for
all four declared depots, `assays/<ASSAY>.json` for all five declared assays,
`quarters.csv`, `measurements.csv` and `rejected.csv`.

The declared universe is always written in full — 4 depots x 3 quarters = 12
panel rows, every row carrying all five assay cells in declared order — whether
or not the extract mentions them. Empty cells are `NO_SAMPLE` with `n` 0 and
`null` mean/max; empty summary figures in the depot and assay reports are the
number `-1`. Means and worst ratios are computed exactly with `decimal` and
rounded half-up to three decimals; `max` is the result value itself. CSVs have a
header and `\n` line endings. No absolute paths are hard-coded, so the same
program runs unchanged at `/app` against other extracts under this contract.
A copy is also at `out/derive_report.py`.

## What I checked

One run on the shipped corpus, `real 0.05 s`, exit 0, then a read-back of the
outputs against the contract's own controls:

- Ledger identity holds: `rows_read 191 = accepted 162 + superseded 17 + rejected 12`.
- The sum of every cell `n` across the 12 panel rows equals `accepted` (162), and
  `measurements.csv` has exactly those 162 rows, correct header, sorted by
  `sample_id` then assay order.
- `rejected.csv` has 12 rows sorted by id: UNKNOWN_DEPOT 5, UNKNOWN_ASSAY 5,
  OUT_OF_PERIOD 2.
- Cross-totals agree three ways: per-quarter samples in `quarters.csv` equal the
  sum of that quarter's panel-row samples (13 / 13 / 17); each assay report `n`
  equals both its panel column total and the sum of its `by_quarter` entries;
  each depot's `total_samples` equals the distinct sample ids for that depot in
  `measurements.csv`.
- The worked example in `source_rules.md` is reproduced exactly: for sample
  `CS268129`, assay `HG`, BLX `T67576` is accepted at 0.115 and ACM `T63530` is
  superseded.

Self-check: **PASS**. No crash, and no logic changed after the check.

## Key figures

- Transmissions read 191 → accepted 162, superseded 17, rejected 12.
- Distinct samples per depot: KES 11, MAR 9, OSS 11, TAL 12 (43 total).
- All three quarters are `BREACH` (breach rows 3 / 2 / 1, no NO_DATA rows).
- Depots: KES `BREACH` (2 breach quarters), OSS `BREACH` (3), TAL `BREACH` (1),
  MAR `COMPLIANT` (0).
- Every assay ends `EXCEEDED`: PB n=30 mean 0.136 max 0.374 (1 exceedance);
  CD n=31 mean 0.053 max 0.126 (2); HG n=35 mean 0.238 max 0.519 (1);
  AS n=30 mean 0.090 max 0.267 (1); HIS n=36 mean 43.686 max 125.005 (2).
- Worst ratio anywhere: 1.335 (TAL, 2026-Q1).
