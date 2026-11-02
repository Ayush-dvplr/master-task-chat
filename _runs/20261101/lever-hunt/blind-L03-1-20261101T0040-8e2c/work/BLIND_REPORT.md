# BLIND REPORT — lever-hunt L03, step P13 (sha 6c0c3d8)

## Files read, in order

1. `instruction.md`
2. `environment/data/panel_contract.md`
3. `environment/data/source_rules.md`
4. `environment/data/output_schema.json`
5. `environment/data/corpus/transmissions/` — directory listing + line counts (41 csv files)
6. `environment/data/corpus/transmissions/ACM_2026-01.csv`, `NRL_2026-10.csv`, `ACM_2025-12.csv` (full), plus header uniqueness and column value tallies across all 41 files

## Minutes to first full write

Session start 00:36:37 IST; `app/derive_report.py` written complete at ~00:38 → **2 minutes**.

## What was built

`app/derive_report.py` (copied to `out/derive_report.py`), Python 3 standard library only,
invoked exactly as `python3 /app/derive_report.py <corpus_dir> <out_dir>`.
No absolute run-directory path appears in the source; depots, quarters, assays, limits and
lab tiers are the declared constants from the contract, so the same file runs on any extract.

- reads every `*.csv` under `<corpus_dir>/transmissions/` (file names ignored, sorted for determinism)
- rejects at the first failure in contract order: `UNKNOWN_DEPOT` → `UNKNOWN_ASSAY` → `OUT_OF_PERIOD`
- resolves each `(sample_id, assay)` by lowest lab tier, then latest `reported_at`
- all arithmetic in `decimal.Decimal`, means and ratios quantized half-up to 3 dp; `max` is the raw value
- writes `panel.json`, `depots/<DEPOT>.json` x4, `assays/<ASSAY>.json` x5, `quarters.csv`,
  `measurements.csv`, `rejected.csv` — 12 full panel rows and all declared quarters always present

## Self-check (on shipped data only) — PASS

Single run, `/usr/bin/time -p` under the 600 s alarm: **real 0.04 s**, exit 0.

Covered:
- all 13 named output files exist; CSVs have a header and `\n` endings (0 CR bytes)
- ledger identity: `rows_read 191 = accepted 162 + superseded 17 + rejected 12`
- `measurements.csv` row count = accepted; sum of all panel cell `n` = 162 = accepted; sum of the five assay reports' `n` = 162; each assay's `by_quarter` `n` sums to its total `n`
- exact key sets and value types for panel rows, cells, depot reports and assay reports; declared orderings (depot-then-quarter rows, quarter lists, assay keys)
- `quarters.csv` re-derived field by field from the panel rows — matched on all 3 lines
- depot `total_samples` sum 43 = distinct `sample_id` in `measurements.csv`
- sort orders: measurements by `sample_id` then assay order; rejected by `transmission_id`
- the control the files themselves define: the `source_rules.md` worked example reproduced exactly — `CS268129`/`HG` accepted as `T67576`, lab `BLX`, result `0.115`

Key figures: 191 transmissions read, 162 accepted, 17 superseded, 12 rejected
(6 `UNKNOWN_DEPOT`, 4 `UNKNOWN_ASSAY`, 2 `OUT_OF_PERIOD`); 43 distinct samples.
All three quarters `BREACH`; depots KES/OSS/TAL `BREACH`, MAR `COMPLIANT`; all five assays `EXCEEDED`.

## Crash fixed

None — the first run exited 0. Two pre-run edits of my own draft (a leftover condition in the
depot check and a cleaner tier/tie-break selection) were made before any run, not after the self-check.

## Lessons for the master

- The contract never says what to do with a `lab` outside `source_rules.md`; I ranked unknown labs last. Worth declaring.
- `output_schema.json`'s `example_measured_cell` has `max 0.327` with `exceedances 0`, which breaks the PB limit 0.300 — a deliberately generic example reads as a contradiction.
- Malformed `collected_on` has no stated reason; "falls in no declared quarter" makes `OUT_OF_PERIOD` the natural catch-all, but it is inferred.
- `-1` for empty summary stats vs `null` for empty panel cells is easy to mix up; the schema example saved it.
- It is unstated whether `worst_ratio` is rounded before or after the max over cells; I rounded each cell ratio then took the max.
