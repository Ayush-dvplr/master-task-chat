# Final reply

## What I built
`/app/out/derive_report.py` (stdlib only), run as

    python3 /app/out/derive_report.py --data /app/data --out /app/out

`--data` defaults to `/app/data`, `--out` to `/app/out`; it reads nothing outside the data folder and
writes only the nine documents into the out folder. A missing or unreadable input named in
`docs/charging_rules.md` makes it exit non-zero with `error: cannot read <file>: …` on stderr.

How it decides the plan: the day plan is a single global integer min-cost flow over all four depots,
`source -> bus (capacity = need) -> (depot, slot) -> slot (shared feeder) -> sink`, with one arc per
(bus, slot) in the bus's window capped at the bus type's `max_kwh_per_slot`. That arc is split in two
parallel arcs — the first capped at the bus's published kWh for the slot and one cent-unit cheaper — so
staying on the published plan is preferred only after cost. The three objectives of rule 15 are folded
into one integer arc cost with weights big enough to be order-preserving (weighted unmet first, then
cost, then moved energy), solved exactly by successive shortest paths with potentials; a final
lexicographic pass walks (slot, bus id) in order and pushes as much as possible into each position
around zero-reduced-cost residual cycles, which settles rule 15's last tie-break exactly.

The per-depot meter of rule 12 is identified from `settlements.csv`: candidate ways of applying a
tariff version to a slot are tested against every settled session of that depot (session kWh split
equally over its slots, version in force on `settled_date`) and only the one that bills every row to
the cent is kept. On this corpus that is "the band price at the slot's own start", for all four
depots, and it reproduces all 2243 settled rows exactly.

## Totals (from `summary.json`)
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

Energy delivered 15735 kWh of 15880 kWh of need. By depot: North 3880 kWh / 61080 c,
South 3820 kWh / 56860 c, West 4060 kWh / 70620 c, East 3975 kWh / 63125 c. By class:
commercial 11355 kWh / 178145 c (90 buses), public 4380 kWh / 73540 c (33 buses).
Plan-day prices (every depot): 31 c/kWh 12:00-16:00, 27 c 16:00-22:00, 14 c 22:00-06:00, 22 c 06:00-12:00.

All 145 unmet kWh are window-limited, not supply-limited — the three short buses are
B1015 (South, commercial, need 180, delivered 120, unmet 60, reason `window`),
B1239 (East, commercial, need 180, delivered 135, unmet 45, `window`) and
B1127 (West, commercial, need 160, delivered 120, unmet 40, `window`).
The 8 derated slots (2026-03-14T20:00-21:45, 170 kWh/slot) peak at 150 kWh, so the derating does not bind.

## Rejected records (all 5, as in `data_quality.json`)
| file | line | reason | record |
|---|---|---|---|
| published_plan.csv | 411 | published_row_outside_window | B1082 at 2026-03-14T19:15, 15 kWh — outside that bus's window |
| roster.csv | 1038 | bad_window | B5004 North, arrive 2026-03-14T22:00 later than depart 2026-03-14T19:30 |
| roster.csv | 2176 | unknown_vehicle | B9990 — no such `vehicle_id` in fleet_register.csv |
| roster.csv | 3851 | duplicate_roster_row | B1029 South — the bus was already accepted on an earlier plan-date line |
| roster.csv | 3962 | retired_vehicle | B5000 South — register status is `retired` |

## What I checked
One run on the shipped data, 0.51 s wall clock (limit 120 s), exit 0, then 27 independent checks
(`work/check.py`, 0.16 s), all passing:

* all nine documents exist with the exact key lists, 96 slot rows each where the rules ask for every
  slot, `policy_audit.json` sorted by `bus_id` with all 123 accepted buses;
* every charge recomputed: inside the bus's window, at most `max_kwh_per_slot`, strictly increasing in
  time, positive only, summing to `delivered_kwh` and never above `need_kwh`; `need_kwh`, `unmet_kwh`,
  `unmet_reason` and `changed` recomputed from the raw files and matched;
* feasibility: depot energy never exceeds cabinets-in-service x 15 kWh in any slot (both outages
  applied), feeder never exceeds 1300 kWh, and never exceeds 170 kWh in the derated window;
* cross-totals: the four regions and the two segments each sum to 15735 kWh and 251685 c, equal to
  `summary.json`, whose every field was recomputed independently;
* optimality controls the data itself defines: delivered energy equals the sum over buses of
  min(need, max_kwh_per_slot x window length), so no plan can deliver more and 145 weighted unmet kWh
  is the minimum; the cost equals the relaxed lower bound that fills each bus's need into its own
  cheapest window slots while ignoring the shared cabinet and feeder caps, so 251685 c is optimal;
  and the accepted published plan costs exactly the same 251685 c, so `moved_kwh = 0` is attainable —
  with equal totals that forces the plan to equal the published plan slot by slot, which is why
  `buses_changed` is 0 and why the rule-15 tie-break has nothing left to choose.
