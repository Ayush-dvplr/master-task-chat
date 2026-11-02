# Field book shard layouts

Every shard holds setup records of one layout. The catalog names the layout of each file.
Common to all layouts: one record is one setup revision; `rev` is the revision number; the run id style, reading
unit, distance unit, temperature unit and time style are given per layout. Rod tokens follow H7, run ids H6.

## Layout L01

- encoding: CSV, comma separated, lines starting with # are comments
- fields: run,setup,rev,void,time_utc,rod_bs,rod_fs,bs_m,fs_m,dist_bs_m,dist_fs_m,rod_temp_c
- run id style: R-26-dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: rod temperature in degC
- time: UTC, ISO 8601 with a Z suffix
- rods: rod tokens per record
- notes: void is 1 for a void record and 0 otherwise
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L02

- encoding: TSV, tab separated, blank lines carry no record
- fields: run, set, r, status, time, pair, bs_mm, fs_mm, dbs_dm, dfs_dm, dir_note
- run id style: R26dddd
- readings: millimetres, two decimals
- distances: integer decimetres
- temperature: no temperature field
- time: ISO 8601 local time with its UTC offset
- rods: rod pair id of the run
- notes: status VOID marks a void record; the rods follow from the pair (H7); dir_note is the observer's note and is not used
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L03

- encoding: PSV, pipe separated
- fields: RUN|SETUP|REV|VOIDED|LOCAL_TIME|BACK_ROD|FORE_ROD|BACK_READING_M|FORE_READING_M|BACK_DIST_M|FORE_DIST_M|TEMP_C
- run id style: R-26-dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: rod temperature in degC
- time: local wall clock YYYY-MM-DD HH:MM:SS
- rods: rod tokens per record
- notes: VOIDED is Y for a void record and empty otherwise
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L04

- encoding: fixed width text; the first two lines are a title and a column ruler
- fields: columns 1-8 run, 9-12 setup, 13-14 rev, 15 void flag V, 16-23 date, 24-29 time, 30-33 pair, 34-40 back reading, 41-47 fore reading, 48-51 back distance, 52-55 fore distance, 56-60 temperature
- run id style: R26dddd
- readings: integers in units of 0.00001 m
- distances: integer decimetres
- temperature: rod temperature in degC
- time: local wall clock YYYYMMDD HHMMSS
- rods: rod pair id of the run
- notes: the temperature is a sign and four digits in tenths of degC, blank when absent; the rods follow from the pair (H7)
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L05

- encoding: JSON Lines
- fields: objects with run.id, setup.n, setup.rev, setup.void, time, bs.rod, bs.r, bs.d, fs.rod, fs.r, fs.d, temp_c
- run id style: R-26-dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: rod temperature in degC
- time: ISO 8601 local time with its UTC offset
- rods: rod tokens per record
- notes: readings and distances are strings; temp_c is null when absent
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L06

- encoding: NDJSON
- fields: objects with run_ref, seq, rev, deleted, epoch_s, pair, bs_mm, fs_mm, dbs_m, dfs_m, temp_f
- run id style: 26/dddd
- readings: millimetres, two decimals
- distances: metres, one decimal
- temperature: rod temperature in degF
- time: UTC epoch seconds
- rods: rod pair id of the run
- notes: deleted true marks a void record; temp_f is an empty string when absent; the rods follow from the pair (H7)
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L07

- encoding: JSON document
- fields: export header plus a setups list of objects with run, seq, revision, state, utc, back and fore objects of rod, reading_m, distance_m
- run id style: R-26-dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: no temperature field
- time: UTC, ISO 8601 with a Z suffix
- rods: rod tokens per record
- notes: state void marks a void record
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L08

- encoding: XML, one setup element per record
- fields: attributes run, seq, rev, void, local, brod, frod, bs_mm, fs_mm, dbs_dm, dfs_dm, temp_c
- run id style: R-26-dddd
- readings: millimetres, two decimals
- distances: integer decimetres
- temperature: rod temperature in degC
- time: local wall clock YYYY-MM-DD HH:MM:SS
- rods: rod tokens per record
- notes: void true marks a void record; temp_c is empty when absent
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L09

- encoding: YAML list under setups, block or flow mappings
- fields: keys run, set, rev, void, time, pair, bs, fs, d_bs, d_fs, temp, dir
- run id style: R26dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: rod temperature in degC
- time: ISO 8601 local time with its UTC offset
- rods: rod pair id of the run
- notes: void yes marks a void record; temp ~ when absent; the rods follow from the pair (H7); dir is not used
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L10

- encoding: YAML, setups grouped under runs
- fields: each list item is seq, rev, void, epoch_s, back rod, fore rod, bs_mm, fs_mm, dbs_m, dfs_m
- run id style: R-26-dddd
- readings: millimetres, two decimals
- distances: metres, one decimal
- temperature: no temperature field
- time: UTC epoch seconds
- rods: rod tokens per record
- notes: void true marks a void record
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L11

- encoding: Markdown table
- fields: run, setup, rev, status, local time, back rod, fore rod, back m, fore m, back dist m, fore dist m, temp F
- run id style: 26/dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: rod temperature in degF
- time: local wall clock YYYY-MM-DD HH:MM:SS
- rods: rod tokens per record
- notes: status void marks a void record; temp F is empty when absent
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L12

- encoding: SQLite, table obs
- fields: run, seq, rev, void, epoch, pair, bs, fs, dbs, dfs, temp_c
- run id style: R-26-dddd
- readings: integers in units of 0.00001 m
- distances: integer decimetres
- temperature: rod temperature in degC
- time: UTC epoch seconds
- rods: rod pair id of the run
- notes: void 1 marks a void record; bs and fs in units of 0.00001 m, dbs and dfs in decimetres; temp_c NULL when absent; the rods follow from the pair (H7)
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L13

- encoding: SQLite, tables setup_key (uid, run, seq, rev) and setup_attr (uid, attr, value)
- fields: attributes time_utc, rod_b, rod_f, bs_m, fs_m, dist_b_m, dist_f_m, void, temp_c
- run id style: R-26-dddd
- readings: metres, five decimals
- distances: metres, one decimal
- temperature: rod temperature in degC
- time: UTC, ISO 8601 with a Z suffix
- rods: rod tokens per record
- notes: void 1 marks a void record; temp_c is missing when absent
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L14

- encoding: CSV, semicolon separated, decimal comma
- fields: run;opstelling;rev;vervallen;tijd;baak_a;baak_v;a_mm;v_mm;afst_a_m;afst_v_m;temp_c
- run id style: R26dddd
- readings: millimetres, two decimals
- distances: metres, one decimal
- temperature: rod temperature in degC
- time: local wall clock DD.MM.YYYY HH:MM:SS
- rods: rod tokens per record
- notes: vervallen ja marks a void record; baak_a is the back rod and baak_v the fore rod; a_mm and v_mm are back and fore readings
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L15

- encoding: TSV, tab separated
- fields: run, seq, rev, void, time, rod_b, rod_f, bs_m, fs_m, dist_b_ft, dist_f_ft, temp_f
- run id style: R-26-dddd
- readings: metres, five decimals
- distances: US survey feet, three decimals
- temperature: rod temperature in degF
- time: ISO 8601 local time with its UTC offset
- rods: rod tokens per record
- notes: void 1 marks a void record
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Layout L16

- encoding: XML, element per field
- fields: setup elements with run, seq, rev, void, utc, pair, bs, fs, dbs_ft, dfs_ft
- run id style: R-26-dddd
- readings: integers in units of 0.00001 m
- distances: US survey feet, three decimals
- temperature: no temperature field
- time: UTC, ISO 8601 with a Z suffix
- rods: rod pair id of the run
- notes: void 1 marks a void record; bs and fs in units of 0.00001 m; the rods follow from the pair (H7)
- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)
- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped
- setup number: an integer counted from 1 along the run

## Met station logs

- degC CSV: epoch_s, temp_c, rh_pct, station
- degF TSV: utc (ISO Z), temp (degF), wind_ms
- tenths JSON Lines: t (ISO local time with offset), ta (integer tenths of degC), qc

The unit of each log is the `unit` column of the station register.

