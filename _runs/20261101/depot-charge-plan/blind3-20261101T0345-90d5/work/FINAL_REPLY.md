# Final reply - overnight depot charging plan

## What I built

`derive_report.py` (Python 3 standard library only, no network) shipped at `/app/out/derive_report.py`
and run as `python3 /app/out/derive_report.py --data /app/data --out /app/out`
(`--data` defaults to `/app/data`, `--out` to `/app/out`). It reads only the data folder it is given,
writes only into the output folder, and leaves the data folder untouched. A missing or unreadable
input named in the rules makes it exit non-zero with that file named on stderr.

How it derives the plan:

1. **Day grid** - `grid.ini [plan]` gives plan date 2026-03-14, 96 slots of 15 minutes from
   2026-03-14T12:00, so the day runs to 2026-03-15T11:45; every "from X to Y" range covers the slots
   starting at or after X and before Y.
2. **Buses** - roster rows for the plan date only, rejected by the first applying reason
   (unknown_vehicle, retired_vehicle, duplicate_roster_row, bad_window); need = next-day trip kWh
   + disruption extra trips + type reserve - arrival SoC, floored at 0; class from the contract,
   `commercial` when the contract is blank or unlisted.
3. **Limits** - integer kWh per slot inside the window, at most the type's `max_kwh_per_slot`,
   bus total at most its need; per depot and slot at most (cabinets minus the cabinets the notice puts
   out of service) x 15 kWh; per slot all four depots together at most 1300 kWh, derated to 170 kWh
   for 2026-03-14T20:00-22:00.
4. **Price** - each depot's meter is inferred from `settlements.csv`: of a family of ways to read the
   tariff, the one that bills every settled row of that depot exactly its `cents` under the version in
   force on its settled date. On this corpus all four depots settle exactly on the band price at the
   slot start (every one of the 2243 rows matches to the cent), so slots are priced at
   31c (12:00-16:00), 27c (16:00-22:00), 14c (22:00-06:00), 22c (06:00-12:00).
5. **Optimisation** - the whole fleet, all four depots and the shared feeder are solved jointly as one
   integer minimum-cost flow of `10^22 * weighted unmet + 10^11 * energy cost + moved energy`, so the
   three criteria are strictly lexicographic. Optimality is certified by cancelling negative residual
   cycles; the remaining ties are broken to the lexicographically **greatest** kWh vector in slot order
   then bus_id order by pushing each position to its maximum inside the zero-reduced-cost face.

Documents written: `policy_audit.json`, `region_North.json`, `region_South.json`, `region_West.json`,
`region_East.json`, `segment_commercial.json`, `segment_public.json`, `summary.json`,
`data_quality.json`.

## Totals from summary.json

| field | value |
|---|---|
| plan_date | 2026-03-14 |
| weighted_unmet_kwh | 145 |
| energy_cost_cents | 251685 |
| moved_kwh | 0 |
| feeder_peak_kwh | 975 |
| buses_planned | 123 |
| buses_short | 3 |
| buses_changed | 0 |
| records_rejected | 5 |

Supporting figures: total need 15880 kWh, delivered 15735 kWh. Cost by depot - North 61080,
South 56860, West 70620, East 63125 cents. Cost by class - commercial 178145, public 73540 cents.
The 145 kWh of weighted unmet is exactly the per-bus window bound
`sum(weight x max(0, need - max_kwh_per_slot x window slots))`, so no plan can do better on the first
criterion; the three short buses are window-limited, not supply-limited. Moved energy is 0, the global
minimum: the derived plan matches the accepted published plan slot by slot, so no bus is marked changed.
Feeder peak 975 kWh stays under the 1300 kWh limit, and the derated 20:00-22:00 slots stay at or under
170 kWh.

## Rejected records (all 5, file / line / reason)

| file | line | reason |
|---|---|---|
| published_plan.csv | 411 | published_row_outside_window |
| roster.csv | 1038 | bad_window |
| roster.csv | 2176 | unknown_vehicle |
| roster.csv | 3851 | duplicate_roster_row |
| roster.csv | 3962 | retired_vehicle |

Line numbers count the header as line 1. Four roster rows for the plan date were rejected, one for each
reason in the rules, and one published-plan row fell outside its bus's window.

## What I checked

One run on the shipped data, 0.47 s wall clock against the 120 s budget. All nine documents exist;
every slot list is the full 96 slots in time order; per-bus arithmetic (charges sum to delivered,
need - delivered = unmet, every charge within 1..max_kwh_per_slot, charges in time order) has zero
violations; no slot breaks a depot cabinet cap or the feeder cap, derating and outages included;
region and segment roll-ups and all four cost figures reconcile to the summary to the cent; the
weighted unmet equals its theoretical lower bound; and no single kWh can move to a cheaper slot inside
its bus's window without breaking a cap. Pointing the program at a missing data folder exits 2 with the
path named on stderr.
