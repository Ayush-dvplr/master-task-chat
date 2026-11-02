# Overnight depot charging: planning rules

These rules define the day plan for the electric bus fleet and every field of the planning reports. Every file named here is in the data folder. Where the disruption notice and another file disagree about the plan date, the disruption notice wins.

## 1. Plan day and slots

1. `grid.ini` section `[plan]` gives `plan_date`, `first_slot`, `slot_minutes` and `slots`. The plan day is cut into `slots` consecutive slots of `slot_minutes` minutes, the first starting at `first_slot`. A slot is named by its start time in the form `YYYY-MM-DDTHH:MM`.
2. A time span written "from X to Y" covers every slot that starts at or after X and before Y. This holds for tariff bands, cabinet outages and feeder derating.

## 2. Buses on the plan

3. Only `roster.csv` rows whose `plan_date` equals the plan date are read; rows for other dates are ignored and are not rejected.
4. A roster row of the plan date is rejected when the first of these that applies holds, checked in this order: `unknown_vehicle` (the `bus_id` is not a `vehicle_id` in `fleet_register.csv`), `retired_vehicle` (its register `status` is not `active`), `duplicate_roster_row` (the same `bus_id` was accepted on an earlier line of the plan date), `bad_window` (`arrive` is not earlier than `depart`, `arrive` is before the first slot, or `depart` is after the end of the last slot). Every other row of the plan date is accepted, and each accepted row is one bus on the plan.
5. A bus may charge only in the slots that start at or after its `arrive` and before its `depart`; these slots are its window. A bus's depot is the `depot` on its roster row.
6. A bus's type is its `type` in `fleet_register.csv`. `bus_types.json` gives, per type, `max_kwh_per_slot` (the most energy the bus can take in one slot) and `reserve_kwh`.
7. A bus's need is the sum of `kwh` of its trips in `trips.jsonl` whose `service_date` is the day after the plan date, plus the kWh of every extra trip the disruption notice lists for that bus on that date, plus the `reserve_kwh` of its type, minus its `soc_arrival_kwh`. A need below zero is zero.
8. A bus's class is the `class` of its `contract_id` in `contracts.json`. A blank `contract_id`, or one not listed there, means class `commercial`. `service_classes.ini` gives the `weight` of each class.

## 3. Limits every plan obeys

9. A bus receives a whole number of kWh in each slot of its window, from 0 to its `max_kwh_per_slot`, and nothing outside its window. The energy delivered to a bus over the day is at most its need.
10. In every slot the energy delivered to the buses of one depot is at most the cabinets in service at that depot times `cabinet_kwh_per_slot` from `depots.json`. A depot's cabinets in service are its `cabinets` in `depots.json`, less any cabinets the disruption notice lists as out of service at that depot for that slot.
11. In every slot the energy delivered to all buses at all four depots together is at most the feeder limit for that slot: `feeder_kwh_per_slot` in `grid.ini` section `[feeder]`, replaced by the derated limit for any slot the disruption notice lists under feeder derating.

## 4. Prices and the published plan

12. The price of a slot is the `cents_per_kwh` of the `tariff.xml` band that covers it. The energy cost of a plan is the sum over all charges of price times kWh, in whole cents.
13. `published_plan.csv` holds the plan published before the disruptions. Only rows whose `plan_date` equals the plan date are read. A row whose `slot_start` is not in its bus's window is rejected as `published_row_outside_window`. A bus's published kWh in a slot is the sum of its accepted rows for that slot.
14. The moved energy of a plan is the sum, over every bus and slot, of the published kWh minus the planned kWh wherever the published kWh is the larger.

## 5. The day plan

15. Unmet energy of a bus is its need minus the energy delivered to it. Of all plans that obey every limit in section 3, the day plan is the one with, in this order of importance: (1) the least sum over buses of class weight times unmet kWh; then (2) the least energy cost; then (3) the least moved energy. If several plans are still equal, the day plan is the one whose kWh values, listed in order of slot and then of bus id with 0 where a bus does not charge, is greater at the first place where the lists differ.
16. Every bus charge, depot total and fleet total is taken from the single day plan that is optimal under the stated order for all four depots together, including the shared feeder limit.

## 6. Reports

All reports are JSON documents in the output folder. Amounts are whole numbers (kWh, cents). Lists of slots hold every slot of the plan day in time order.

17. `policy_audit.json`: `plan_date`, and `buses`, one entry per bus on the plan sorted by `bus_id`, each with `bus_id`, `depot`, `class`, `need_kwh`, `delivered_kwh`, `unmet_kwh`, `unmet_reason`, `changed` and `charges`. `unmet_reason` is `null` when unmet is 0, `"window"` when the need is more than `max_kwh_per_slot` times the number of slots in the window, and `"supply"` otherwise. `changed` is `true` when the bus's planned kWh differ from its published kWh in at least one slot. `charges` lists every slot where the bus charges more than 0 kWh, in time order, as `{"slot", "kwh"}`.
18. `region_<depot>.json`, one per depot (`North`, `South`, `West`, `East`): `depot`, `buses` (number of buses on the plan at the depot), `energy_kwh`, `cost_cents`, `unmet_kwh` (depot totals), and `slots`, one entry per slot `{"slot", "kwh", "feeder_kwh"}` where `kwh` is the depot's energy in the slot and `feeder_kwh` is the energy of all four depots together in the slot.
19. `segment_commercial.json` and `segment_public.json`: `class`, `buses`, `energy_kwh`, `cost_cents`, `unmet_kwh` and `slots` as in rule 18, over the buses of that class.
20. `summary.json`: `plan_date`, `weighted_unmet_kwh`, `energy_cost_cents`, `moved_kwh`, `feeder_peak_kwh` (the largest all-depot energy in any slot), `feeder_kwh_by_slot` (one `{"slot", "kwh"}` per slot, all depots together), `buses_planned`, `buses_short` (buses with unmet above 0), `buses_changed` and `records_rejected`.
21. `data_quality.json`: `plan_date`, and `rejected`, one `{"file", "line", "reason"}` per rejected row, sorted by file name and then line. `line` is the row's line number in its file, the header being line 1.
