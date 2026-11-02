# BLIND REPORT — lever-hunt-L03, step P13 (board e242361)

## Files read, in order

1. `instruction.md` — interface and the four things to read.
2. `environment/data/panel_contract.md` — declared universe, validation order, aggregation, output table.
3. `environment/data/source_rules.md` — lab tiers and the in-tier tie-break, plus the worked example.
4. `environment/data/output_schema.json` — exact key sets/types, the `-1` vs `null` split, the empty-quarter example.
5. `environment/data/corpus/transmissions/*.csv` — 41 files listed, all headers and first rows inspected, then one stdlib survey pass over all 191 data rows (distinct labs/depots/assays, date range, duplicate-key multiplicities, tie detection, sample consistency, result formatting).

Nothing outside the blind directory was opened. No web, no subagents, no Docker/pip/git.

## Minutes to first full write

Session started 00:36:37 IST; `app/derive_report.py` was written complete in one pass at ~00:39 IST → **3 minutes**.

## What I built

`app/derive_report.py`, run as `python3 /app/derive_report.py <corpus_dir> <out_dir>`, stdlib only, no absolute host paths. It reads every `.csv` under `<corpus_dir>/transmissions`, rejects in the contract's order (`UNKNOWN_DEPOT` → `UNKNOWN_ASSAY` → `OUT_OF_PERIOD`), resolves each `(sample_id, assay)` by lab tier then latest `reported_at`, and writes 13 files into `<out_dir>`: `panel.json`, `quarters.csv`, `measurements.csv`, `rejected.csv`, `depots/{KES,MAR,OSS,TAL}.json`, `assays/{PB,CD,HG,AS,HIS}.json`. All arithmetic is exact (`Fraction`/`Decimal`) with an explicit half-away-from-zero rounding to three decimals, so no float rounding ever reaches an output. The declared universe is emitted in full regardless of the data (12 rows, every cell, every quarter entry).

Two points the files left open, and the choice made (both documented in the code):
- a `lab` outside the priority table ranks below every listed tier (none occurs in the shipped extract);
- if tier and `reported_at` were both tied, `transmission_id` descending breaks it deterministically (the rules say no other field breaks ties; no such tie occurs here).

## Self-check (shipped data only)

One run of the program (`real 0.06 s`) plus one verification pass (`real 0.04 s`), both under `perl -e 'alarm 600'` and timed with `/usr/bin/time -p`; every command is logged in `work/CHECKS.md`.

The verification recomputed, independently and in exact decimal, from `measurements.csv` and the contract: the ledger identity (191 = 162 accepted + 17 superseded + 12 rejected); panel key sets, types, row order and cell order; every cell `n`/`mean`/`max`/`exceedances`/`status`; row `samples` and row status; `NO_SAMPLE` cells carrying `null`; the four depot reports (quarter entries copying the panel row, `worst_ratio` as the largest `max/limit`, `breach_quarters`, `total_samples`, depot status); the five assay reports (overall statistics equal to the union of their quarters, `depots_sampled`, `-1` sentinels); all six `quarters.csv` fields per line; `rejected.csv` length, sort and reason vocabulary; `measurements.csv` header, sort by `sample_id` then assay order, one row per key; CSV headers, `\n` endings, no CR; and the `source_rules.md` worked example (CS268129/HG → T67576, BLX, 0.115).

Result: **PASS**. Key figures — ledger 191/162/17/12; `quarters.csv` `2026-Q1,4,13,3,0,BREACH`, `2026-Q2,4,13,2,0,BREACH`, `2026-Q3,4,17,1,0,BREACH`; every assay `EXCEEDED` (PB 30/0.136/0.374/1, CD 31/0.053/0.126/2, HG 35/0.238/0.519/1, AS 30/0.090/0.267/1, HIS 36/43.686/125.005/2; the five `n` sum to 162); all four depots `BREACH`.

## Crash fixed

None — the program ran clean on its first invocation. The first verification pass did raise an `AssertionError` on `('MAR','2026-Q1','HG')`, but that was a bug in my *check script* (Python's `round()` is half-to-even, and 0.1485 must go to 0.149 under the contract's half-up). The program's value was correct; the check script was corrected and the program was not touched.

No python process of mine is left running (the three `python` entries visible under `ps` belong to another run's generator and the harness watcher, not to this session).

## Lessons for the master

- `output_schema.json`'s `example_measured_cell` shows `max 0.327, exceedances 0`, which contradicts the PB limit 0.300 if read as a PB cell; it is only decipherable as assay-agnostic filler.
- The contract gives `reported_at` as `YYYY-MM-DDTHH:MM:00Z` while the data and the worked example use full `HH:MM:SS`; harmless here, but the stated format is wrong.
- Nothing says what to do with a `lab` absent from the priority table, nor how to break a tier + `reported_at` tie even though "no other field breaks ties" forbids a rule; both are reachable on another extract.
- Nothing says whether a `sample_id` may appear with two different depots or `collected_on` values across labs; the shipped extract is consistent, so the ambiguity stays invisible until it is not.
