# Intake of assets, requests and control-room events

## Assets

`assets.jsonl` holds one JSON object per line with `asset_id`, `region`, `kind` and `crew_type`. A request takes the region and crew type of its asset from this file. Regions are `North`, `South`, `West` and `East`; crew types are `line`, `substation` and `protection`.

## Season and request records

`requests.json` holds `season` (`first_day` and `last_day`; days are whole numbers counted from 1) and the list `requests`. Each record carries `asset_id`, `duration_days`, `earliest_start`, `latest_finish` and `crews`.

The whole of `requests.json` is read, in list order, before the control-room log. Each record is checked against these tests in this order, and the first test it fails is its rejection reason:

1. `unknown_asset`: its `asset_id` is not in `assets.jsonl`.
2. `out_of_season`: its `earliest_start` is before `first_day` or its `latest_finish` is after `last_day`.
3. `window_too_short`: `latest_finish - earliest_start + 1` is less than `duration_days`.
4. `duplicate_request`: an earlier accepted record names the same `asset_id`. Records accepted from `requests.json` and from the control-room log both count, and a record still counts after its request is withdrawn.

A record that fails no test is accepted. A rejected record takes no further part in the replan.

## Published plan

`published_plan.json` holds `published_at` (a timestamp) and `plan`, one entry per record accepted from `requests.json`: either `status` `scheduled` with its `start` day, or `status` `deferred`.

## Control-room log

Each line of `control_room.log` is a timestamp of the form `YYYY-MM-DDTHH:MM:SSZ`, a level word, an event name, then `key=value` tokens, all separated by whitespace.

- A line whose timestamp has that form and whose event name is `HEARTBEAT` has no effect and is not counted.
- An event line is well formed when its timestamp has that form, its event name is `CREW_LOSS`, `NEW_REQUEST` or `WITHDRAW`, its tokens carry exactly the keys listed for that event below, each once, and every key marked as an integer holds a whole number written in decimal digits with an optional leading minus sign. A `CREW_LOSS` line is well formed only when its `region` and `crew_type` are names listed under Assets, `from` is not after `to`, and `count` is at least 1.
  - `CREW_LOSS`: `region`, `crew_type`, `from` (integer), `to` (integer), `count` (integer).
  - `NEW_REQUEST`: `asset_id`, `duration_days` (integer), `earliest_start` (integer), `latest_finish` (integer), `crews` (integer).
  - `WITHDRAW`: `asset_id`.
- Every line that is neither a `HEARTBEAT` line nor a well-formed event line counts once in `ignored_lines`, whatever its timestamp.
- A well-formed event line whose timestamp is at or before `published_at` has no effect and is not counted.
- The remaining event lines take effect in line order:
  - `CREW_LOSS` removes `count` crews of `crew_type` in `region` on every day from `from` to `to`, both included. Days outside the season are unaffected. Several notices for one day add up.
  - `NEW_REQUEST` is a request record and is checked by the four tests above; its position is its line number in the log, counted from 1. An accepted record of this kind is a control-room request and has no entry in the published plan.
  - `WITHDRAW` removes the named request when that asset has an accepted request that is not yet withdrawn, and the asset joins the withdrawn list. Otherwise the line counts once in `ignored_lines`.

The active requests are the accepted records that are not withdrawn. Every later rule speaks of active requests only.
