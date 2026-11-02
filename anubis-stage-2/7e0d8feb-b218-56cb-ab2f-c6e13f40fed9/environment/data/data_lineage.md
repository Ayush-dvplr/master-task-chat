# Data lineage

Which file feeds which stage, and which files feed nothing.

| file | stages | note |
|---|---|---|
| `channel_config.json` | all | the transmission date, the day start and the live control set |
| `ingest_attempt_register.csv` | V1, V2, V3 | one row per ingest attempt |
| `rate_code_register.csv` | V2, V3, V4 | the exact rationals and the drop frame permission |
| `segment_part_manifest.tsv` | V5 | the parts of an asset |
| `transmission_schedule.csv` | V7, V8 | the day, the junctions and the flexible parts |
| `break_plan_register.csv` | V6, V9 | the nominal break offsets and the avail seconds |
| `gop_index_channel.psv` | V6 | the index frames a break can be taken at |
| `filler_library.csv` | V8 | the ordered filler predicates |
| `market_register.csv` | V9, V10, V13 | the four markets |
| `blackout_rule_set.xml` | V10 | the settled blackout rules |
| `substitution_library.csv` | V10 | the substitute break plans |
| `spot_order_book.jsonl` | V9, V11, V12 | one record per sold spot |
| `clearance_state_journal.csv` | V9 | several rows per clearance reference |
| `advertiser_register.csv` | V11, V12 | the settlement currency per advertiser |
| `rate_card_book.csv` | V9, V11, V12 | several dated rows per card reference |
| `currency_minor_units.json` | V11 | the minor unit exponent per currency |
| `daypart_calendar.csv` | V13 | the daypart of each clock hour |
| `contract_terms_workbook.xlsx` | V6, V11, V12 | the snap tolerance, the commission terms and the make good cap |
| `regulatory_minutage_memo.pdf` | V9, V11, V13 | the separation minimum, the billing grain, the regulatory minutes, and the permitted minutes per market hour |
| `prior_conform_register.csv` | V14 only | reported against, never consumed |

## The decoys

| file | why it is here | what it must not be used for |
|---|---|---|
| `legacy_commission_table.csv` | the retired commission schedule, kept for audit | it is a percentage in a different parameter space; the settled workbook sheet is the commission |
| `blackout_overlay_drafts.xml` | a draft overlay that was never signed off | its root element says `draft-superseded`; V10 reads `blackout_rule_set.xml` only |
| `prior_conform_register.csv` | the previous automated conform of this day | V14 reports against it; no other stage reads it |
| the two superseded workbook sheets | the terms of the other control sets | the settled sheet is the one whose control set cell matches the configuration |
| the `nominal_fps` column | the traffic system's display label | it is a rounded label, never a rate |

## The corroborating stores

`playout_audit.sqlite` and `traffic_audit.db` carry copies of the ingest
register, the schedule, the order book and the clearance journal. They
corroborate the flat files and add nothing to them.
