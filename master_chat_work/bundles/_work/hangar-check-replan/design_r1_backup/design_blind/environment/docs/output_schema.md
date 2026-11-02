# Output schema

All outputs are JSON files written to the output folder (default `/app/out/`). Every scheduled check,
base total and fleet total is taken from the single season plan that is optimal under the stated
order for the whole fleet, including the shared overtime limit. Every base listed in
`data_conventions.md` and both segments always get their report file and their row in
`plan_summary.json`, with zero counts and `null` for `first_start` and `last_finish` when they have
no open request this season.

Segments: `commercial` holds the classes `widebody` and `narrowbody`; `public` holds the class
`regional`.

## check_plan.json

`{"season": <season id>, "checks": [...]}` with one object per open request, sorted by `request_id`:

| field | value |
|---|---|
| `request_id`, `tail`, `base`, `check_type` | from the request row |
| `aircraft_class`, `segment` | class of the tail and its segment |
| `decision` | `scheduled` or `deferred` |
| `start_date`, `finish_date` | ISO dates; `null` when deferred |
| `compress_days`, `overtime_shifts`, `overdue_days` | whole numbers; 0 when deferred |
| `moved` | `true` or `false` as defined in `planning_policy.md` |
| `deferral_reason` | `no_slot` or `plan_trade` when deferred, `null` when scheduled |

## regions/region_<base>.json and segments/segment_<segment>.json

One file per base (`region_north.json`, `region_south.json`, `region_west.json`, `region_east.json`)
with key `base`, and one file per segment (`segment_commercial.json`, `segment_public.json`) with key
`segment`. Both carry these totals over the open requests of that base or segment:

| field | value |
|---|---|
| `checks_scheduled`, `checks_deferred` | counts |
| `compress_days`, `overtime_shifts`, `overdue_days` | sums over scheduled checks |
| `overdue_cost` | sum over scheduled checks of overdue days times `overdue_weight` |
| `deferral_cost` | sum of `deferral_penalty` over deferred requests |
| `revenue_lost` | sum over scheduled checks of days on ground times `revenue_per_day` |
| `moved` | number of moved requests |
| `first_start`, `last_finish` | earliest start date and latest finish date of scheduled checks |
| `fleet_overtime_used` | overtime shifts of the whole fleet plan |

## plan_summary.json

| field | value |
|---|---|
| `season` | season id |
| `plan_terms` | `{"first": ..., "second": ..., "third": ...}`, the three terms of the season plan |
| `overtime_pool_shifts`, `fleet_overtime_used` | the pool and the shifts the plan uses |
| `checks_scheduled`, `checks_deferred`, `moved` | fleet counts |
| `bases` | list in the order North, South, West, East of `{"base", "checks_scheduled", "checks_deferred", "overtime_shifts"}` |
| `segments` | list in the order commercial, public of `{"segment", "checks_scheduled", "checks_deferred"}` |

## data_quality.json

`{"rejected": [...], "counts": {...}}`. `rejected` lists `{"request_id", "line", "reason"}` for every
rejected row in file order. `counts` has all eight reasons of `data_conventions.md` as keys, with 0
for a reason that rejected nothing.

Each document is compared field by field with the expected values, so every number, date, flag and
list must match exactly.
