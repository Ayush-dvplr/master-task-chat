# Blind report — depot-charge-plan (d9d6ab5, P13)

Session rename: `name_session.py d9d6ab5` reported
`opencode: ['ses_e6c307723ffeIUn4B4qjNLdTZt']` and `codex: no match`. Taken as
done.

## Files read, in order

1. `instruction.md`
2. `environment/docs/charging_rules.md` (the whole spec, 21 numbered rules)
3. `environment/data/grid.ini`, `bus_types.json`, `depots.json`,
   `service_classes.ini`, `tariff.xml`, `disruption_notice.md` (full)
4. `environment/data/fleet_register.csv`, `roster.csv`, `published_plan.csv`,
   `settlements.csv`, `trips.jsonl`, `contracts.json` (headers plus scripted
   aggregation; too large to read whole)

## Minutes to first full write

Start 02:43 (first command), the program was complete and ran at 02:53 —
**10 minutes**.

## Self-check

Covered (details and commands in `work/CHECKS.md`):

- the nine named reports exist, parse, and have the stated shape (96 slots per
  slot list, 123 bus entries, the field names of rules 17–21);
- the controls the files define: region energies sum to the summary total,
  region and segment costs both equal `energy_cost_cents`, every
  `feeder_kwh` equals the matching `feeder_kwh_by_slot` entry;
- every limit of rule section 3 on the emitted plan — per-bus slot cap, need
  cap, window, per-depot cabinets in service with the two outages applied, and
  the feeder limit including the eight derated slots — zero violations;
- the meter rule of rule 12: band-at-slot-start bills all 2254 settlement rows
  of all four depots exactly, and the alternatives do not, so the choice is
  unique as the rule promises;
- optimality of the three objective levels: the 180 kWh unmet is forced (the
  three short buses are at their per-slot cap in both slots of a two-slot
  window with no spare depot or feeder room anywhere), a re-solve without the
  moved-energy term gives the same 254 435 cents so the cost is the true
  minimum at that unmet level, and `moved_kwh` 0 is the absolute floor — which
  also pins the plan uniquely, so the rule-15 tie-break could not change it.

Result: **PASS**. Runtime 0.30 s (`/usr/bin/time -p`), far inside 120 s. No
python process of mine was left running.

## Crash fixed

None. The first run of the finished program produced all nine reports.

## Lessons for the master

- Rule 12's "each depot's meter has its own way of applying a tariff" never
  says what the set of ways is; I had to guess a candidate family (band at slot
  start / mid / end / max / min over the slot) and let the settlements choose.
  On this data all four depots are plain band-at-slot-start, so the whole
  device is invisible — and on fresh data a way outside my family would break
  every cost figure.
- Rule 3 lets the notice override the plan date but says nothing about
  `first_slot`, which also carries a date; I shifted it by the same number of
  days.
- The disruption never binds here: the published plan is already optimal for
  the new needs, so `moved_kwh` and `buses_changed` are both 0 and rule 15's
  tie-break is untested by the shipped data.
- Rule 13 does not say what happens to a published row whose bus is not on the
  plan at all; I rejected it as `published_row_outside_window` (none occur).
