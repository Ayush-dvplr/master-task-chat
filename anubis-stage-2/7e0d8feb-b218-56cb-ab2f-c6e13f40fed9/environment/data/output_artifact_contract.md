# Output artifact contract

Twenty five artifacts are written into the output directory, plus the
reusable program. Every one of them is derived from this directory alone.

| artifact | format | stage |
|---|---|---|
| `asset_register.csv` | csv | V1 to V3 |
| `segment_conform.csv` | csv | V4 and V5 |
| `break_positions.csv` | csv | V6 |
| `slot_placement.csv` | csv | V7 and V8 |
| `conform_trace.json` | json | V8 |
| `filler_plan.csv` | csv | V8 |
| `avail_plan.tsv` | tsv | V9 |
| `deferral_ledger.jsonl` | jsonl | V9 |
| `market_overrides.csv` | csv | V10 |
| `market_avails_mk_coast.json` | json | V10 |
| `market_avails_mk_metro.json` | json | V10 |
| `market_avails_mk_north.json` | json | V10 |
| `market_avails_mk_valley.json` | json | V10 |
| `market_avail_stream.jsonl` | jsonl | V10 |
| `settlement_ledger.psv` | psv | V11 |
| `makegood_ledger.json` | json | V12 |
| `exception_ledger.jsonl` | jsonl | V11 |
| `advertiser_summary.csv` | csv | V11 and V12 |
| `minutage_report.csv` | csv | V13 |
| `carry_ledger.json` | json | V4 |
| `reconciliation.xml` | xml | V14 |
| `playout_schedule.ini` | ini | V7 and V8 |
| `day_report.md` | md | all |
| `compliance_summary.md` | md | V13 |
| `manifest.json` | json | V14 |

The reusable program is written as `conform.py` in the same directory. It
takes an optional `--data` directory and an optional `--out` directory on
the command line, defaults to the container paths when given neither, reads
nothing else, and writes exactly the twenty five artifacts above. It is run
against transmission days it has never seen, so nothing about this
particular day may be built into it.
