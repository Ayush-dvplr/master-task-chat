# Output documents

Every output document is one JSON object. Key order and whitespace are free. Lists of asset ids are in ascending `asset_id` order unless a different order is given. Day numbers, counts and risk-days are integers. Regions are listed under Assets in `docs/intake.md`.

## policy_audit.json

`requests`: one object per active request, in ascending `asset_id` order, with:

- `asset_id`, `region`, `crew_type`;
- `origin`: `published` for a request accepted from `requests.json`, `control_room` for one accepted from the log;
- `status`: `scheduled` or `deferred`;
- `start`, `end`: its first and last day out, both `null` when deferred;
- `published_start`: its start in the published plan, `null` when it has none or the published plan defers it;
- `moved`: `true` or `false` as defined in `docs/replan_contract.md`;
- `risk_days`: its risk-days;
- `reason`: its deferral reason, `null` when scheduled.

## region_North.json, region_South.json, region_West.json, region_East.json

- `region`: the region name;
- `schedule`: one object per scheduled request of the region with `asset_id`, `crew_type`, `start`, `end`, ordered by `start` and then by `asset_id`;
- `crew_days`: an object with keys `line`, `substation` and `protection`, each the sum of `crews` times `duration_days` over the scheduled requests of that crew type in the region;
- `risk_days`: the risk-days of all active requests of the region, deferred ones included;
- `deferred`: the asset ids of the region's deferred requests;
- `moved`: the number of moved requests of the region.

## segment_commercial.json, segment_public.json

- `segment`: `commercial` or `public`;
- `risk_days`: the segment's risk-days over all active requests;
- `by_region`: an object with one key per region holding the segment's risk-days in that region;
- `deferred_risk_days`: the segment's risk-days over deferred requests only.

## summary.json

- `requests`, `scheduled`, `deferred`, `moved`: counts of active requests;
- `risk_days`: total risk-days;
- `crew_days`: the sum of `crews` times `duration_days` over all scheduled requests;
- `objective`: the list `[risk_days, moved]`.

## data_quality.json

- `rejected`: one object per rejected record with `source` (`requests.json` or `control_room.log`), `position` (the index in the `requests` list counted from 0, or the log line number counted from 1), `asset_id` and `reason`, ordered by `source` in ascending string order (so `control_room.log` comes before `requests.json`) and then by `position`;
- `counts`: an object with the four rejection reasons as keys, each the number of rejected records with that reason (0 included);
- `withdrawn`: the asset ids of withdrawn requests;
- `ignored_lines`: the number of log lines counted as ignored in `docs/intake.md`.
