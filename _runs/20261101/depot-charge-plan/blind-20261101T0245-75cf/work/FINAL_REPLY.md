# Overnight depot charging plan — handover

## What I built

`derive_report.py` (standard library only, `--data` / `--out`, defaults
`/app/environment/data` and `/app/out`). It rebuilds the plan day from scratch:

1. **Plan day** from `grid.ini` `[plan]`, with the plan date taken from the
   disruption notice when the two disagree; 96 slots of 15 minutes from
   2026-03-14T12:00. Every "from X to Y" span is read as the slots starting in
   `[X, Y)`.
2. **Buses on the plan**: roster rows of the plan date, rejected in the stated
   order (`unknown_vehicle`, `retired_vehicle`, `duplicate_roster_row`,
   `bad_window`). Need = next-day trips + the notice's extra trips + type
   reserve − arrival SoC, floored at 0. Class from `contracts.json`, blank or
   unknown contract = `commercial`.
3. **Prices**: the tariff version in force on the plan date, and per depot the
   one meter reading of a band table under which every settlement row of that
   depot bills out to exactly its cents. On this data all four depots settle
   under "the band containing the slot's start"; a one-slot shift misbills
   100+ rows per depot, so the choice is unique.
4. **The plan** is the exact optimum of the stated three-level objective, not a
   heuristic. It is solved as one min-cost flow over all four depots at once —
   source → bus (capacity = need, cost = −weight), bus → depot-slot (capacity =
   `max_kwh_per_slot`, split into a published-kWh arc that earns the
   moved-energy credit and a plain arc), depot-slot → slot (capacity = cabinets
   in service × 15 kWh, cost = the depot's slot price), slot → feeder limit.
   The three levels are nested in the arc costs so that weighted unmet outranks
   energy cost, which outranks moved energy. The final tie-break (the
   lexicographically greatest kWh list over slots then bus ids) is then applied
   on the face of optimal solutions by raising one position at a time along
   zero-reduced-cost cycles and freezing it.

## Figures for this plan day

| | |
|---|---|
| buses on the plan | 123 (34 public, 89 commercial) |
| energy delivered | 16 080 kWh of 16 260 kWh of need |
| weighted unmet | 600 kWh-weighted (180 kWh raw, 3 buses) |
| energy cost | 254 435 cents |
| moved energy | 0 kWh — nothing had to be shifted off the published plan |
| feeder peak | 1 115 kWh in a slot (limit 1 500, derated 250 from 19:30) |
| records rejected | 5 (4 roster rows, 1 published row outside its window) |
| North / South / West / East | 3 660 / 4 180 / 3 980 / 4 260 kWh |

The three short buses (B1017, B1126, B1237) are window-limited: each has a
two-slot window and is charged to `max_kwh_per_slot` in both slots, so the
180 kWh cannot be delivered at all and they are reported `unmet_reason:
"window"`. The derating window and both cabinet outages are never binding at
the optimum, which is why `moved_kwh` is 0.

## What I checked

- All nine reports are written and parse; 96 slot entries everywhere, 123 bus
  entries in `policy_audit.json`.
- Cross-totals agree: the four region energies sum to the summary total, region
  and segment costs both sum to `energy_cost_cents`, and every region/segment
  `feeder_kwh` equals the matching `feeder_kwh_by_slot` entry.
- The plan obeys every limit of section 3: no bus over its per-slot cap or its
  need, no depot over its cabinets in service (outages applied), no slot over
  the feeder limit (the eight derated slots carry at most 225 of 250).
- Optimality: re-solving without the moved-energy term returns the same
  16 080 kWh and the same 254 435 cents, so the reported cost is the true
  minimum at the optimal unmet level, and `moved_kwh` 0 is the absolute floor.
- Runtime 0.30 s for the full run, well inside the 120 s budget.
