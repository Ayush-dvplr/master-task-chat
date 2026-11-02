# Handover — overnight depot charging plan

## What I built

`derive_report.py` (Python 3 standard library only), shipped at `app/derive_report.py`
and `out/derive_report.py`. Interface exactly as specified:

    python3 derive_report.py --data <data folder> --out <output folder>

with `/app/environment/data/` and `/app/out/` as the defaults. It reads only the data
folder, writes only into the output folder, and left `environment/` untouched.

It reads `grid.ini`, `disruption_notice.md`, `tariff.xml`, `depots.json`,
`fleet_register.csv`, `bus_types.json`, `contracts.json`, `service_classes.ini`,
`trips.jsonl`, `roster.csv` and `published_plan.csv`, and writes the nine reports
`policy_audit.json`, `data_quality.json`, `summary.json`, `region_{North,South,West,East}.json`,
`segment_commercial.json` and `segment_public.json`.

The plan day comes from the disruption notice heading (it wins over `grid.ini`), the slot
grid from `grid.ini`. Roster rows of the plan day are screened in the stated order
(`unknown_vehicle`, `retired_vehicle`, `duplicate_roster_row`, `bad_window`), where a row
only counts as a duplicate against an earlier *accepted* row. Spans "from X to Y" always
cover the slots starting at or after X and before Y — tariff bands, cabinet outages and the
feeder derating alike.

## How the plan is computed

The day plan is the exact optimum of rule 15, not a heuristic. It is a single minimum-cost
flow over all four depots at once:

    source -> bus (capacity = need)  ->  depot-slot  ->  slot  ->  sink

* `source -> bus` carries cost `-M1 x class weight`, so maximising weighted delivered
  energy is the same as minimising weighted unmet energy (level 1).
* `slot -> sink` carries cost `M2 x cents_per_kwh` and capacity the feeder limit of that
  slot, derated where the notice says so (level 2, plus rule 11).
* each `bus -> depot-slot` pair is split into two parallel arcs — the first
  `min(published kWh, max_kwh_per_slot)` units at cost `-M3`, the rest at cost 0 — which
  is exactly the convex cost `max(0, published - planned)` of moved energy (level 3).
* `depot-slot -> slot` capacity is cabinets in service x `cabinet_kwh_per_slot` (rule 10).

The multipliers are derived from the data (`M1 >> M2 x max cost >> M3 x max moved`), so the
single cost strictly encodes the three objectives in their stated order of importance. A
primal-dual solver (Dijkstra on reduced costs plus a blocking flow) gives an integer
optimum. A final pass then walks every (slot, bus id) pair in rule-15 order, pushes that
pair's kWh as high as the optimal face still allows (augmenting cycles of zero reduced cost
in the residual graph) and freezes it — that is the lexicographically greatest optimum the
tie-break asks for.

## What I checked, and the figures

One run on the shipped data took **0.10 s** (cap is 120 s). An independent checker
(`work/verify.py`) rebuilt every control from the written reports:

* every bus charges only inside its window, never above `max_kwh_per_slot`, never above its
  need; every depot-slot cap and every feeder-slot cap holds — including the 8 derated slots
  19:30–21:15 at 250 kWh and the North/South cabinet outages (525→495, 360→330).
* the report totals agree with each other: region energies and segment energies both sum to
  the 16080 kWh delivered, `feeder_kwh` in every slot list equals the all-depot total, and
  `records_rejected` equals the length of the `data_quality` list.
* **optimality evidence**: a relaxation that lets each bus fill its own cheapest window
  slots with the shared caps switched off gives 600 weighted unmet kWh and 254435 cents —
  exactly what the plan achieves. Since a relaxation can only be better, the plan is optimal
  on level 1 and level 2, and moved energy of 0 is the floor on level 3.

Plan day 2026-03-14, 96 slots of 15 min from 12:00.

| figure | value |
|---|---|
| buses on the plan | 123 (of 127 roster rows for the day) |
| total need / delivered | 16260 / 16080 kWh |
| weighted unmet kWh | 600 (180 kWh over 3 buses) |
| energy cost | 254435 cents |
| moved kWh | 0 |
| feeder peak | 1115 kWh (limit 1500, derated 250) |
| buses short / changed | 3 / 0 |
| records rejected | 5 |

Depots: North 30 buses / 3660 kWh / 55400 c / 0 unmet; South 31 / 4180 / 68920 / 40;
West 31 / 3980 / 65600 / 80; East 31 / 4260 / 64515 / 60.
Segments: commercial 89 buses / 11540 kWh / 170920 c / 40 unmet; public 34 / 4540 / 83515 / 140.

The 5 rejected records are `published_plan.csv` line 423 (`published_row_outside_window`)
and `roster.csv` lines 757 `unknown_vehicle`, 981 `bad_window`, 1266 `duplicate_roster_row`,
1497 `retired_vehicle`.

Worth flagging for operations: all three short buses (B1126, B1237, B1017) are short for the
`window` reason — each is on site for only two slots, so no amount of grid capacity would
help; they need a longer dwell, not more cabinets. The disruptions turned out not to bind on
this day: the derated window is in the 27-cent band that the plan avoids anyway, and the peak
draw of 1115 kWh stays well under every cabinet and feeder limit, so the re-planned day
happens to coincide with the published plan (moved 0, 0 buses changed).
