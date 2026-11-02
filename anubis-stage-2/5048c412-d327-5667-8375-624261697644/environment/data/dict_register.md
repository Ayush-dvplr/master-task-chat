# Register dictionary

## Register authority

The register authority for every reservoir fact used in balancing is the station register database `stn_core.sqlite` together with the files it is joined to. `stn_core.sqlite` is an SQLite 3 database file. Table `station` holds one row per reservoir with the columns `stn` (text, the station code), `station_name` (text) and `catchment` (text, the catchment code). Table `register_meta` holds the season label and the row count of `station`.

A reservoir's basin is the basin that `bs_map.xml` gives for the reservoir's catchment. That file is XML in the namespace `urn:basin-authority:catchments`: one `catchment` element per catchment, with the code in its `code` attribute and the basin name in a `basin` child element.

## Opening storage

A reservoir's opening storage is its corrected meter reading plus the datum offset of its catchment, in megalitres.

`xw_codes.csv` (header `gauge_no,stn`) gives the current gauge number of every station code. The meter file `ob_s3.bin` holds readings, corrections and replacements; its grammar is stated in `spec_meter.md`. A reservoir's meter reading is the value of the reading record of its current gauge number; when the meter file holds more than one reading record for that number, the last of them in file order is the reading.

A reservoir's corrected meter reading is its meter reading, unless the meter file holds a correction for it dated on or before the survey date: then the value of that correction, or, when there are several, of the one with the latest date, and of several with that date, of the last of them in file order. A correction dated after the survey date is not applied. A correction filed under a gauge number that a replacement record retired is a correction for the reservoir whose current gauge number replaced it.

Every catchment's meters read against the catchment's own datum. The datum offset of a catchment is a multiple of 5 megalitres from -95 to 95 inclusive. No file records it; the storage survey fixes it.

## Storage survey

`sv_survey.csv` (header `reach,surveyed_on,stations,total_ml`) holds one row per surveyed reach: the reach code, the survey date, the station codes of the reach's reservoirs separated by `;`, and the reach's surveyed total. A reach's surveyed total is the sum of the opening storages of its reservoirs, rounded down to a multiple of 10 megalitres. Every row carries the same date, the survey date.

The datum offsets of an extract are the one assignment of a datum offset to every catchment holding a reservoir under which every row of the survey holds. When no assignment makes every row hold, or more than one does, the extract breaks the register rules.

## Depot copies

`stn_mirror.csv` is a copy of the joined facts (header `stn,station_name,basin,reading_ml`, `station_name` always double-quoted, `reading_ml` the meter reading) refreshed for the regional depots on their own schedule; a mirror row can lag the authority or hold a reservoir the authority does not. `ob_backup.csv` (header `gauge_no,reading_ml`) is a depot copy of meter readings in the same way. Where a depot copy and the register authority or the meter file differ, the register authority and the meter file govern.

## Basin membership

The reservoirs of a basin are the reservoirs whose basin, through their catchment, is that basin. A basin's opening state is the opening storages of its reservoirs.

## Register rules

Each station code occurs once in table `station`. The meter file follows its grammar (`spec_meter.md`), and every station code a survey row lists is a station code of table `station`. A gauging whose `from` or `to` station code is not a station code of table `station` breaks the register, and so does a gauging whose two reservoirs belong to different basins.
