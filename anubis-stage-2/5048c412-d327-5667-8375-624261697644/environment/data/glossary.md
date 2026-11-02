# Season extract glossary

The export names in this extract are operational codes of the basin authority's hydrometric office, not descriptions. The first table maps each code to the role of the file. The term list after it defines the words the documents use; a term defined here carries its defined meaning wherever it appears in the documents.

| Code | Role |
|---|---|
| `stn_core.sqlite` | Station register database: station code, name and catchment of every reservoir for the season (tables `station` and `register_meta`). |
| `xw_codes.csv` | Station code to gauge number crosswalk. |
| `ob_s3.bin` | Meter records of the season: readings, corrections and meter replacements, by gauge number (binary container). |
| `spec_meter.md` | Meter file grammar. |
| `sv_survey.csv` | Storage survey of the season: surveyed reaches and their totals. |
| `bs_map.xml` | Catchment to basin map. |
| `stn_mirror.csv` | Station register export in comma-separated form, produced for the regional depots. |
| `ob_backup.csv` | Meter reading export in comma-separated form, produced for the regional depots. |
| `gx_a.csv` | Canal gauging export from the field crews' upload portal. |
| `gx_b.tsv` | Canal gauging export from the telemetry gateway. |
| `gx_c.jsonl` | Canal gauging export from the contractor feed. |
| `rv_log.psv` | Gauging revision log of the hydrometric office. |
| `lc_register.json` | Delivery licence register: licence code, supply scheme and order date of every licence of the season. |
| `sc_k2.docx` | Supply scheme classes (the segment of every supply scheme) and the basin operating parameters. |
| `tab_h3.xlsx` | Method tables workbook: the head offset table (sheet `offset`). |
| `mt_loss.pdf` | Conveyance loss rate schedule. |
| `lr_depot.csv` | Loss rate export in comma-separated form, produced for the regional depots. |
| `basin_cfg.ini` | Season label and revision cutoff. |
| `prior_balance.json` | Summary kept from an earlier balancing run. |
| `dict_register.md` | Register dictionary. |
| `dict_gaugings.md` | Gauging and revision dictionary. |
| `std_pipeline.md` | Pipeline contract. |
| `std_balancing.md` | Basin storage balancing standard. |
| `std_precision.md` | Precision standard. |
| `std_loss.md` | Conveyance loss standard. |
| `cfg_reference.md` | Parameter and method-table reference. |
| `layout_reports.md` | Report layout standard. |

## Terms

- **Balanced storage**: the storage a basin reports for a reservoir when its balancing has ended.
- **Basin**: one of the four closed storage basins North, South, West and East. Water moves between reservoirs of one basin only.
- **Basin residual**: defined in `std_balancing.md` (Residual).
- **Catchment**: a catchment code `C` followed by two digits; every reservoir lies in one catchment and every catchment in one basin (`bs_map.xml`).
- **Canal**: a channel joining two reservoirs of one basin; every gauging is made on a canal.
- **Damping percentage**: the share, in whole percent, of a residual that a round moves.
- **Draw points**: the points a reservoir scores in a gauging (`dict_gaugings.md`).
- **Draw share**: defined in `std_balancing.md` (Target).
- **Exit**: the way a basin's balancing ends: `balanced`, `stalled`, `cycle` or `budget`.
- **Furthest from target**: in a round, the reservoir whose residual has the largest absolute value; when several reservoirs share that largest absolute value, the one of them that comes last in register order.
- **Gauging**: one measured canal run between two reservoirs, recorded in exactly one gauging export.
- **Gauging id**: `GX` followed by five digits.
- **Gauge number**: `G` followed by four digits; it identifies the meter of a reservoir and keys the meter readings.
- **Head offset**: the storage, in megalitres, that the `offset` sheet of `tab_h3.xlsx` adds to a reservoir's target for its draw share; negative below a share of 0.50.
- **In force**: a dated rate is in force on a day when its row has the latest `revised_on` date earlier than that day among the rows of its segment; a revised rate first applies on the day after its `revised_on` date.
- **Kilolitre (kL)**: one thousandth of a megalitre; losses are stated in whole kilolitres.
- **Licence**: a delivery licence of the licence register; every gauging names the licence under which the canal ran.
- **Loss**: the conveyance loss of a net gauging (`std_loss.md`).
- **Megalitre (ML)**: the unit of storage; storages are whole megalitres.
- **Net gauging**: a gauging of the season in its net state after the revisions that apply, voided gaugings left out (`dict_gaugings.md`).
- **Datum offset**: the storage, in megalitres, by which a catchment's meters read below the reservoirs' storage (`dict_register.md`).
- **Opening state**: the opening storages of a basin's reservoirs (`dict_register.md`).
- **Survey date**: the date every row of `sv_survey.csv` carries.
- **Partners**: of a reservoir, the reservoir at the other end of each of its net gaugings, taken once for every such gauging, so that a reservoir gauged three times against the same reservoir has that reservoir among its partners three times.
- **Patience**: the `patience` value of the basin's row in the basin operating parameters table of `sc_k2.docx`, a positive integer.
- **Register authority**: the station register database `stn_core.sqlite` (`dict_register.md`).
- **Register order**: the order of reservoirs by the number in their station code (the digits after `RS-`) read as an integer, smallest first.
- **Reservoir**: a storage of the register authority; each belongs to exactly one basin.
- **Revision**: a line of the revision log (`dict_gaugings.md`).
- **Revision cutoff**: the `revision_cutoff` value of `basin_cfg.ini`, section `season`.
- **Round**: one pass of balancing over a basin (`std_balancing.md`).
- **Round budget**: the `round_budget` value of the basin's row in the basin operating parameters table of `sc_k2.docx`.
- **Round count**: the number a basin reports for its rounds under its exit (`std_balancing.md`).
- **Rounded**: taken to the nearest whole number (or, for a value rounded to hundredths, the nearest multiple of 0.01); a value exactly halfway between two of them goes to the one farther from zero, so 2.5 becomes 3 and -2.5 becomes -3.
- **Scheme**: a supply scheme code `SC-` followed by two digits; every licence is issued under one scheme.
- **Season**: 2026-07-01 to 2026-09-30 inclusive; its label is the `label` of `basin_cfg.ini`, section `season`.
- **Segment**: the water-use class of a supply scheme, and so of every licence issued under it: `commercial` (irrigation and industrial orders) or `public` (town supply orders).
- **Slack**: a round is slack when its basin residual is greater than or equal to the basin residual of the round before it; round 0 has no round before it and is never slack.
- **Standing**: the standing value of a quantity in a round is its value after every change that the round's own slack judgement brings about, including a halving made in that round.
- **Station code**: `RS-` followed by three digits; it identifies a reservoir.
- **Station name**: the reservoir's name as the register authority records it.
- **Storage**: the water a reservoir holds, in whole megalitres.
- **Tally**: a count kept over the whole of a basin's balancing; it rises by one with each event it counts and returns to zero only where a standard says that it does.
- **Yield**: what a round moves for a reservoir: its transfer after the closure of that round has been taken.
