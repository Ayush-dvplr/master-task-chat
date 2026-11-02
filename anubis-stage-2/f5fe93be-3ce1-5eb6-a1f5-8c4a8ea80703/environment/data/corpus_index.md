# Corpus index

This directory is one close extract of the Halvard playout centre. It covers five channel weeks, called workloads, named `visible`, `peak`, `steady`, `burst` and `latency`. Every file is listed here with its layout. Row order inside a record file carries no meaning unless this index says otherwise, and blank lines carry nothing.

The rule documents are `reconciliation_rules.md`, `timecode_and_clock.md`, `source_precedence.md`, `makegood_policy.md` and `billing_rules.md`. Artifact shapes and the closing figures are in `output_contract.md`. `legacy_traffic_runbook.md` describes the engine retired before this close; it is kept for history, it is not authoritative, and where it disagrees with the rule documents the rule documents govern. `mcr_desk_crib_sheet.md` is an informal set of desk notes kept for reference only; it is not authoritative either, and where it disagrees with the rule documents the rule documents govern.

## Shared reference files

`channels.ini` has one section per workload. Keys: `channel` (channel code), `frame_rate` (`30000/1001` or `25`), `timecode` (`drop` or `nondrop`), `zone` (a key of `utc_offsets.json`), `week_start` (first broadcast date, ISO), `broadcast_days` (number of broadcast dates in the workload), `broadcast_day_start` (local label `HH:MM:SS` at which a broadcast day opens), `daypart_set` (a key of `dayparts.json`) and `sync_tolerance_frames` (integer frames).

`utc_offsets.json` holds `zones`, mapping a zone name to a list of transitions `{"from_utc": "YYYY-MM-DDTHH:MM:SSZ", "offset_minutes": N}`. An offset is local time minus UTC and is in force from its `from_utc` instant until the next transition.

`dayparts.json` holds `sets`, mapping a set name to its dayparts in broadcast clock order, each `{"daypart", "start", "end"}` with `HH:MM` bounds on the broadcast clock. The dayparts of a set cover the whole broadcast day without overlap.

`holidays.json` holds `blackout_broadcast_dates`, mapping a channel code to the broadcast dates on which no recurring commitment runs.

`close_policy.json` holds `cutoff_utc` (workload name to `YYYY-MM-DDTHH:MM:SSZ`), `makegood_grace_days` (integer) and `commission_rounding` (always `half_up_per_order_line`).

`advertisers.json` holds `advertisers`, mapping an advertiser code to `{"name", "commission_bps"}`.

`orders.csv` columns: `order_line, workload, advertiser, daypart, weekdays, spots_per_day, flight_start, flight_end, unit_rate_cents, priority, house_id`. `weekdays` is a space separated subset of `MO TU WE TH FR SA SU`. `flight_start` and `flight_end` are broadcast dates and the flight is the half open range from start up to but not including end. `priority` 1 is the most urgent. `house_id` is the order line's own copy, always a canonical registry id.

`order_amendments.jsonl` has one JSON object per line: `order_line, effective_from` (broadcast date), `spots_per_day, recorded_at` (UTC instant), `note`.

`copy_registry.csv` columns: `house_id, advertiser, title, master_rate, frames, length_class`. `frames` counts frames of the master at `master_rate` frames per second (25 or 30). `length_class` is the nominal length in seconds and is descriptive only.

`house_aliases.csv` columns: `old_house_id, new_house_id, effective_from` (broadcast date). Each old id appears on one row at most.

`prior_close_decisions.jsonl` is the decision record of the previous close, one JSON object per line, described in `reconciliation_rules.md`.

## Per workload files

Each workload `W` has seven files.

The thirty five per workload files of this extract are:

| workload | schedule | breaks | chain A | chain B | switcher | probes | corrections |
|---|---|---|---|---|---|---|---|
| visible | `visible_schedule.csv` | `visible_breaks.tsv` | `visible_asrun_a.log` | `visible_asrun_b.log` | `visible_switcher.log` | `visible_sync_probes.log` | `visible_corrections.jsonl` |
| peak | `peak_schedule.csv` | `peak_breaks.tsv` | `peak_asrun_a.log` | `peak_asrun_b.log` | `peak_switcher.log` | `peak_sync_probes.log` | `peak_corrections.jsonl` |
| steady | `steady_schedule.csv` | `steady_breaks.tsv` | `steady_asrun_a.log` | `steady_asrun_b.log` | `steady_switcher.log` | `steady_sync_probes.log` | `steady_corrections.jsonl` |
| burst | `burst_schedule.csv` | `burst_breaks.tsv` | `burst_asrun_a.log` | `burst_asrun_b.log` | `burst_switcher.log` | `burst_sync_probes.log` | `burst_corrections.jsonl` |
| latency | `latency_schedule.csv` | `latency_breaks.tsv` | `latency_asrun_a.log` | `latency_asrun_b.log` | `latency_switcher.log` | `latency_sync_probes.log` | `latency_corrections.jsonl` |

`W_schedule.csv` columns: `spot_id, break_id, position, order_line, house_id, broadcast_date`. One row per scheduled spot. `house_id` is the scheduled copy as traffic typed it. `broadcast_date` is the scheduled broadcast date.

`W_breaks.tsv` is tab separated with columns `break_id, broadcast_date, local_date, open_tc, capacity_frames`. `open_tc` is the local label at which the break opens on `local_date`; `capacity_frames` counts channel frames.

`W_asrun_a.log` and `W_asrun_b.log` are the as-run logs of playout chains A and B. Each line is `|` separated `key=value` pairs: `seq` (line sequence number, zero padded), `date` (local date of the label), `tc` (local start label), `evt` (event id, unique within its chain), `type` (`SPOT`, `PROG` or `PROMO`), `spot` (scheduled spot id), `house` (copy id as the automation logged it), `frames` (channel frames played), `status` (`CUED`, `PLAYED` or `SKIPPED`).

`W_switcher.log` is the master control switcher log. Each line is `<UTC instant with milliseconds> BUS=<PGM or PST> SRC=<source> NOTE=<text>`. Sources are `A`, `B`, `LIVE1`, `LIVE2` and `SLATE`.

`W_sync_probes.log` lines are `<UTC instant with milliseconds> PROBE chain=<A or B> lock=<OK, RELOCK or STALE> offset_frames=<signed integer>`.

`W_corrections.jsonl` has one JSON object per line: `correction_id, kind` (`reattribute`, `restore` or `retract`), `target, rev, desk` (`traffic` or `mcr`), `recorded_at, payload`. A `reattribute` targets a `spot_id` and its payload names `order_line`. A `restore` targets a `spot_id` and returns it to its scheduled order line. A `retract` targets `<chain>:<evt>`.
