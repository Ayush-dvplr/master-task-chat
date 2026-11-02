# Final reply — lever-hunt L03-1 (sha 6c0c3d8)

**Status: DONE.** Self-check PASS, no crash.

## What I built

`app/derive_report.py` (also copied to `out/derive_report.py`), Python 3 standard library only,
run exactly as the contract states:

    python3 /app/derive_report.py <corpus_dir> <out_dir>

It reads every `*.csv` under `<corpus_dir>/transmissions/` (names carry no meaning), rejects at the
first failure in contract order (`UNKNOWN_DEPOT` → `UNKNOWN_ASSAY` → `OUT_OF_PERIOD`), resolves each
`(sample_id, assay)` by lab tier (NRL 1; ACM/BLX 2; FSK 3) and then latest `reported_at`, and
aggregates accepted measurements only. Every statistic is computed in `decimal.Decimal` and rounded
half-up to three decimals; `max` is the result value itself. The declared universe (4 depots, 3
quarters, 5 assays with their limits) is hard-coded from the contract, so the full 12-row panel, all
four depot reports, all five assay reports and all three quarters are always emitted even where no
transmission touches them — `NO_SAMPLE`/`null` in panel cells, `NO_DATA` for empty rows/quarters/depots,
and `-1` for empty means, maxima and worst ratios in the summary files. Nothing in the program
hard-codes a run-directory path, so it runs unchanged at `/app` on other extracts.

Outputs in `<out_dir>`: `panel.json`, `depots/{KES,MAR,OSS,TAL}.json`,
`assays/{PB,CD,HG,AS,HIS}.json`, `quarters.csv`, `measurements.csv`, `rejected.csv` — 13 files.

## What I checked (shipped corpus only, one run: real 0.04 s, exit 0)

- All 13 named files exist; CSVs have headers and `\n` endings (0 CR bytes).
- Ledger identity holds: **191 rows read = 162 accepted + 17 superseded + 12 rejected**.
- Cross-totals agree three ways: `measurements.csv` has 162 rows, the sum of all 60 panel cell `n`
  is 162, and the five assay reports' `n` sum to 162; each assay's `by_quarter` `n` sums to its total.
- Exact key sets/types and all declared orderings (rows depot-then-quarter, quarter lists, assay keys,
  measurements by `sample_id` then assay order, rejected by `transmission_id`).
- `quarters.csv` re-derived field by field from the panel rows — matched on all three lines.
- Depot `total_samples` sum 43 = distinct `sample_id` in `measurements.csv`.
- The control the shipped files define: the `source_rules.md` worked example reproduces exactly —
  `CS268129`/`HG` accepted as `T67576`, lab `BLX`, result `0.115`, `T63530` superseded.

## Key figures

- 191 transmissions, 162 accepted, 17 superseded, 12 rejected
  (6 `UNKNOWN_DEPOT`, 4 `UNKNOWN_ASSAY`, 2 `OUT_OF_PERIOD`); 43 distinct samples.
- Quarters: 2026-Q1 4 depots / 13 samples / 3 breach rows, 2026-Q2 4 / 13 / 2, 2026-Q3 4 / 17 / 1 — all `BREACH`.
- Depots: KES 11 samples / 2 breach quarters `BREACH`; MAR 9 / 0 `COMPLIANT`; OSS 11 / 3 `BREACH`; TAL 12 / 1 `BREACH`.
- Assays (n, mean, max, exceedances): PB 30 / 0.136 / 0.374 / 1; CD 31 / 0.053 / 0.126 / 2;
  HG 35 / 0.238 / 0.519 / 1; AS 30 / 0.090 / 0.267 / 1; HIS 36 / 43.686 / 125.005 / 2 — all `EXCEEDED`.

Report: `work/BLIND_REPORT.md`. Command log: `work/CHECKS.md`.
