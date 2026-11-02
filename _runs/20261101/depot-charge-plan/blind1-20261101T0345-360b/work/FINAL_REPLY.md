# FINAL_REPLY (task-level answer for depot-charge-plan)

Program: `/app/out/derive_report.py` (stdlib only), run as
`python3 /app/out/derive_report.py --data /app/data --out /app/out`.
Runtime on the shipped corpus: 1.7 s. Nine documents written:
policy_audit.json, region_North.json, region_South.json, region_West.json,
region_East.json, segment_commercial.json, segment_public.json, summary.json,
data_quality.json.

## summary.json totals

| field | value |
| --- | --- |
| plan_date | 2026-03-14 |
| weighted_unmet_kwh | 145 |
| energy_cost_cents | 251685 |
| moved_kwh | 0 |
| feeder_peak_kwh | 975 |
| buses_planned | 123 |
| buses_short | 3 |
| buses_changed | 0 |
| records_rejected | 5 |

## Rejected records (file, line, reason)

| file | line | bus | reason |
| --- | --- | --- | --- |
| published_plan.csv | 411 | B1082 | published_row_outside_window (slot 2026-03-14T19:15 precedes its 19:45 arrival) |
| roster.csv | 1038 | B5004 | bad_window (arrive 22:00 is after depart 19:30) |
| roster.csv | 2176 | B9990 | unknown_vehicle (absent from fleet_register.csv) |
| roster.csv | 3851 | B1029 | duplicate_roster_row (second row for an already accepted bus) |
| roster.csv | 3962 | B5000 | retired_vehicle (status retired) |

## Supporting detail

Regions: North 31 buses / 3880 kWh / 61080 cents / 0 unmet; South 30 / 3820 /
56860 / 60; West 31 / 4060 / 70620 / 40; East 31 / 3975 / 63125 / 45.
Segments: commercial 90 buses / 11355 kWh / 178145 cents / 145 unmet;
public 33 / 4380 / 73540 / 0.
Short buses (all commercial, reason "window"): B1015 need 180 delivered 120,
B1127 need 160 delivered 120, B1239 need 180 delivered 135.
Meter inference (rule 12): all four depots bill every settlements.csv row
exactly under "band price at the slot start", so that is the per-slot price
used for cost.
