# KP-24 output contract

This document fixes the shape of every file the KP-24 rebuild delivers. What the values mean is set by the FPS-4 standard in `/app/data/fps4_rules.md`; this document only says how they are written.

## General rules

- All files are UTF-8 with LF line endings and end with exactly one newline.
- CSV files are comma separated with a header row, quoted only where a value needs quoting, and have exactly the columns listed, in that order.
- JSON files are written with two-space indentation, sorted keys, no ASCII escaping, and nothing after the closing brace except the final newline.
- Instants are `YYYY-MM-DDTHH:MM:SSZ`, dates are `YYYY-MM-DD`.
- In CSV an empty value is an empty cell. In JSON an empty value is `null`; it is never `0` and never an empty string.
- Decimal values are written as strings with exactly the stated places (for example `"0.050000"`); integers and counts are JSON numbers; flags in CSV are `true` or `false`.
- A decimal value that rounds to zero is written without a sign (`"0.0000"`, never `"-0.0000"`), in CSV and JSON alike.

## Phase 1 (`/app/out/p1/`)

### asset_registry.csv

Columns: `asset_id,site,model,oem,serial,commissioned_on,decommissioned_at,criticality,setpoint_bar,rated_flow_m3h,holdout`. One row per asset (FPS-4 3.1), sorted by asset_id. State at the freeze: site, criticality, setpoint_bar (3 places), rated_flow_m3h (2 places, empty when none), decommissioned_at (instant of the decommission in force, empty when active). commissioned_on is a date, holdout a flag.

### sensor_daily.csv

Columns: `asset_id,day,site,availability,vib_mean_mm_s,vib_max_mm_s,temp_c,pressure_bar,flow_m3h,current_a,setpoint_bar,rated_flow_m3h,alarms,readings,quarantined`. One row per asset day (FPS-4 5.1), sorted by asset_id then day. Places: vibration 3, temperature 2, pressure 3, flow 2, current 2, setpoint 3, rated flow 2. availability is one of `ok`, `embargo`, `outage`, `standby`, `hold`. alarms, readings and quarantined are integers.

### failure_events.csv

Columns: `event_id,asset_id,failed_at,failed_day,status,mode,decided_at,pending_decision,pending_mode,pending_at`. One row per failure notification (FPS-4 7.1), sorted by event_id. status is `confirmed` or `unconfirmed`; decided_at is the instant of the deciding decision, empty when there is none. The three pending columns carry the deferred amendment of FPS-4 7.2 (pending_mode only for `reclassify`), all empty when there is none.

### maintenance_log.csv

Columns: `asset_id,event_at,event_day,kind,value,ref`. One row per service (kind is the work order kind, ref the work order number, value empty) and per counted oil sample (kind `oil`, value the iron in ppm as an integer, ref the sample number), sorted by asset_id, event_at, ref.

### site_days.csv

Columns: `site,day,shifts_operating,operating,ambient_c`. One row per site and window day, sorted by site then day. ambient_c has 2 places.

### run_parameters.json

Keys: `run_id` (`KP-24`), `freeze` (instant), `telemetry_window` (list of the first and last day), `parameters` (object of every effective run parameter except holdout_assets, name to value text as written in the run sheet), `holdout_assets` (sorted list of asset ids), `regions` (object, site code to region), `sources` (list, one object per file of the input directory, sorted by file, with `file`, `role` (`in_scope` or `reference_copy`), `records` (integer) and `digest`).

The records of a source are its data records: every record of every segment, every entry of a profile register, every row of Appendix A. The digest is the lowercase SHA-256 hex digest of the canonical lines of those records joined with LF plus one final LF, before errata. A canonical line joins the canonical text (FPS-4 2.4) of the fields in field register order with `|`; a profile register entry is written as `file|segment|revision|status|inherit|dims`, where inherit is empty when absent and dims joins `name=value` pairs sorted by name with `;`.

## Phase 2 (`/app/out/p2/`) and phase 3 (`/app/out/p3/`)

Every phase 2 and phase 3 file is a JSON object that, besides its own keys, carries:

- `upstream_digest`: SHA-256 hex digest over the files the phase read. For each file, in order of its label, the text `<label>` LF `<sha256 of the file bytes>` LF is fed to one SHA-256. Labels are `p1/<name>` for phase 1 files and `p2/<name>` for phase 2 files; phase 2 reads the six phase 1 files, phase 3 reads the six phase 1 and the six phase 2 files.
- `upstream_controls`: an object keyed by the same labels. Each value has `rows` (integer), `total` (string) and `last_key` (string of the last row). For the phase 1 CSV files, rows counts data rows and total is the sum of rated_flow_m3h (asset_registry), readings (sensor_daily), the number of confirmed rows (failure_events), value (maintenance_log) or shifts_operating (site_days); last_key is asset_id, `asset_id|day`, event_id, ref or `site|day`. For run_parameters.json rows counts sources, total sums their records, last_key is the last file. For label_table.json and feature_matrix.json rows counts rows, total sums label or alarms_7d, last_key is `asset_id|day` of the last row. For scaler_stats.json and bin_edges.json rows counts features, total sums n or the number of edges, last_key is the last feature by name. For class_balance.json rows counts splits, total sums rows, last_key is the last split by name. For quarantine_summary.json rows counts sites, total sums samples_kept, last_key is the last site by name. Totals are plain decimal text.

Feature order everywhere is: vib_mean_7d, vib_max_7d, temp_rise_7d, pressure_dev_3d, flow_ratio_7d, current_7d, days_since_service, age_days, iron_ppm, alarms_7d. The last four are integers; the others are strings with 4 places.

### label_table.json

`rows`: one object per kept sample (FPS-4 8), sorted by asset_id then day, with `asset_id`, `day`, `split` (`train`, `val` or `test`) and `label` (0 or 1).

### feature_matrix.json

`features`: the feature order. `rows`: the same samples in the same order, each with `asset_id`, `day` and one key per feature.

### scaler_stats.json

`fit_split`: `train`. `features`: object keyed by feature with `n` (integer), `mean` and `std` (strings, 6 places; null when n is below 2).

### class_balance.json

`splits`: object keyed by split with `rows`, `positives`, `negatives` (integers) and `prevalence` (6 places). `class_weights`: `positive` and `negative` (6 places).

### quarantine_summary.json

`sites`: object keyed by site with `readings_quarantined`, `samples_kept` (integers) and `excluded`, an object with every reason of FPS-4 8.1 (`non_operating`, `embargo`, `outage`, `standby`, `hold`, `low_coverage`, `blackout`, `maintenance`, `purge`) as an integer, zero included.

### bin_edges.json

`features`: object keyed by feature, each a list of nine edge strings (4 places, or plain digits for the integer features), or an empty list.

### train_ready.json

`features`: the feature order. `rows`: one object per kept sample in label_table order with `asset_id`, `day`, `split`, `label`, `z` (object keyed by feature, 4 places or null) and `sample_weight` (6 places).

### baseline_metrics.json

`val`: `rows`, `positives` (integers), `auc`, `threshold`, `f1` (6 places). `test`: `rows`, `positives`, `tp`, `fp`, `fn`, `tn` (integers), `auc`, `precision`, `recall`, `f1` (6 places).

### drift_report.json

`features`: object keyed by feature with `psi`, `null_share_train` and `null_share_test` (6 places).

### site_allocation.json

`budget`, `site_cap`, `region_cap`, `unallocated` (integers) and `sites`: object keyed by site with `region`, `train_positives`, `allocated` (integers except region), `quota` (4 places) and `capped` (JSON boolean).

### amendment_impact.json

`events_with_pending_amendment` (integer), `label_changes` (list sorted by asset_id then day of objects with `asset_id`, `day`, `split`, `old_label`, `new_label`) and `by_split` (object keyed by split with `flipped_up` and `flipped_down` integers).

### release_manifest.json

`run_id`, `files` (object keyed by the twelve upstream labels, each the SHA-256 hex digest of that file), `rows` (object with `train`, `val`, `test` row counts) and `features` (the feature order).

## The program `/app/out/build.py`

```
python3 /app/out/build.py phase1 DATA_DIR P1_DIR
python3 /app/out/build.py phase2 P1_DIR P2_DIR
python3 /app/out/build.py phase3 P1_DIR P2_DIR P3_DIR
```

Each stage reads only the directories it is given, creates its output directory when missing, writes only the six files of its phase into it, and exits 0. Wrong arguments (no stage, an unknown stage, a wrong number of directories) exit 2. A missing or unreadable input or upstream directory, or one lacking a file the stage needs, exits 3. On exit 2 or 3 the program prints exactly one line starting with `error:` to standard error and writes nothing.
