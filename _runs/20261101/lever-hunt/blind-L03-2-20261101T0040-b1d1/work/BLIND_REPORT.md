# BLIND REPORT — blind-L03-2 (sha 85a4df3, slug lever-hunt-L03, step P13)

## Files read, in order

1. `instruction.md`
2. `environment/data/panel_contract.md`
3. `environment/data/source_rules.md`
4. `environment/data/output_schema.json`
5. `environment/data/corpus/transmissions/*.csv` (listing + `ACM_2026-01.csv` head + a one-off census of all 41 files: row count, lab/depot/assay value sets, date range, duplicate check)

## Timeline

- Session start / first `date`: 00:36 IST.
- First full write of `app/derive_report.py` complete: ~00:43 IST.
- **Minutes to first full write: 7.**

## What was built

`app/derive_report.py` (stdlib only, no hard-coded absolute paths), run as
`python3 derive_report.py <corpus_dir> <out_dir>`. It reads every `.csv` under
`<corpus_dir>/transmissions/`, validates in contract order
(UNKNOWN_DEPOT → UNKNOWN_ASSAY → OUT_OF_PERIOD), resolves
`(sample_id, assay)` contests by lab tier then latest `reported_at`
(`transmission_id` kept only as a determinism guard), and writes `panel.json`,
`depots/<DEPOT>.json` x4, `assays/<ASSAY>.json` x5, `quarters.csv`,
`measurements.csv`, `rejected.csv`. All declared depots/quarters/assays are
emitted whether or not data exists; means and worst ratios use `decimal` with
ROUND_HALF_UP to three decimals; empty cells use `null`, empty summary figures
use `-1`. A copy of the program sits at `out/derive_report.py`.

## Self-check (shipped corpus only) — PASS

One run, `real 0.05 s` under the 600 s alarm cap. Verified: all 13 expected
output files exist; ledger identity `191 = 162 + 17 + 12`; 12 panel rows in
depot→quarter order with all five assay keys in declared order; sum of every
cell `n` equals `accepted` (162); `measurements.csv` has 162 rows with the exact
header and is sorted by `sample_id` then assay order; `rejected.csv` has 12 rows
(UNKNOWN_DEPOT 5, UNKNOWN_ASSAY 5, OUT_OF_PERIOD 2) sorted by id;
`quarters.csv` per-quarter samples equal the sum of that quarter's panel-row
samples (13 / 13 / 17); every assay report `n` equals both its panel column
total and the sum of its `by_quarter` values; every depot `total_samples`
equals the distinct sample ids for that depot in `measurements.csv`
(KES 11, MAR 9, OSS 11, TAL 12); CSVs are `\n`-terminated with a header. The
contract's own control — the `source_rules.md` worked example — is reproduced
exactly: CS268129 / HG accepted from BLX `T67576` at 0.115, ACM `T63530`
superseded. No assertion failed.

Key figures: all five assays EXCEEDED; all three quarters BREACH; depots
KES/OSS/TAL BREACH, MAR COMPLIANT; worst ratio 1.335 (TAL 2026-Q1).

## Crash fixed

None — the program ran clean on its first execution, and no logic was changed
after the self-check.

## Lessons for the master

- Lab priority covers only four labs; an extract with an undeclared `lab` has no
  defined tier (I fell back to worst tier) — the contract should say.
- `reported_at` ties inside a tier are declared unbreakable ("no other field");
  a deterministic last resort should be named.
- `output_schema.json`'s `example_measured_cell` (max 0.327, exceedances 0) is
  impossible for PB's 0.300 limit; harmless, but it reads as a real cell.
- "`samples` = sum of those rows' samples" in `quarters.csv` is ambiguous about
  samples spanning two depots; I summed row values as written.
- Program-copy destination under `out/` is not named by the instruction; I used
  `out/derive_report.py`.
