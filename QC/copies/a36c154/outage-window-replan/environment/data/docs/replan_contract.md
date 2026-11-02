# Replan contract

Every published figure is computed from the one replanned season that the objective order selects.

## Weights

A request's commercial weight is the number of `customers.csv` rows of class `commercial` for its asset times the commercial class weight in `risk_policy.toml`; its public weight is the same for class `public`. Its weight is the sum of the two.

## Load factors

`load_forecast.tsv` has rows for every region and every season day. The daily peak of a region on a day is the largest `load_mw` among the `load_forecast.tsv` rows for that region and day. The load factor of that region and day is the `factor` of the band in `risk_policy.toml` with the largest `min_mw` that is not above the daily peak.

## Crew capacity

The capacity of a region and crew type on a day is the number of `crew_roster.jsonl` rows for that region, crew type and day whose `status` is `on_duty`, less the crews removed on that day by `CREW_LOSS` events that take effect (`docs/intake.md`), and never below 0.

## Feasible season

A season gives every active request either one start day or the status deferred. A request scheduled to start on day `s` is out on days `s` to `s + duration_days - 1`. A season is feasible when every scheduled request meets all of these:

- it starts no earlier than its `earliest_start` and its last day out is no later than its `latest_finish`;
- its start day is not a blackout day of its region in `region_calendar.json`; a blackout day forbids a start only, and an outage that has already started stays out through it;
- on each of its days out, the `crews` of all scheduled requests of its region and crew type that are out that day add up to no more than that day's capacity;
- it is never out on a common day with a request that `network_constraints.json` lists with it under `incompatible`;
- for each `precedence` entry that names it as `after`, the request named as `before` is scheduled and the request named as `after` starts after the last day out of the request named as `before`.

Both assets of every `network_constraints.json` entry belong to one region and one crew type. An entry of `network_constraints.json` that names an asset with no active request has no effect.

## Risk-days

A scheduled request contributes its weight times the sum of the load factors of its region over its days out. A deferred request contributes its weight times its `duration_days` times `defer_factor` from `risk_policy.toml`. Commercial and public risk-days are computed the same way with the commercial and the public weight.

## Objective order

1. Among all feasible replanned seasons, the selected one has the smallest total risk-days, where a scheduled outage contributes its weight times the sum of the load-band factors of its days out and a deferred request contributes its weight times its duration times the defer factor.
2. Among seasons equal on level 1, the selected one moves the fewest outages; an outage is moved when it appeared in the published plan and its replanned start differs from its published start, a published outage that becomes deferred is moved, a request that was deferred in the published plan and is now scheduled is moved, a request that was deferred in the published plan and stays deferred is not moved, and a request added by the control-room log is never moved.
3. Among seasons equal on levels 1 and 2, the selected one has the smaller start-day list, read in ascending `asset_id` order, at the first asset where two seasons differ; a deferred request counts as later than every season day.

## Deferral reasons

A deferred request carries the first of these reasons that applies:

1. `no_feasible_start`: no day from its `earliest_start` to its `latest_finish - duration_days + 1` is a start day that is not a blackout day and leaves every day out with capacity at least its `crews`, counting this request alone.
2. `predecessor_deferred`: a request named as `before` it in a `precedence` entry is deferred.
3. `displaced`: otherwise.
