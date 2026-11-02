# BLIND_REPORT — depot-charge-plan, board fd98e12, step P13

Session renamed to `fd98e12` as the first action; the tool printed `codex: no match` and
`opencode: ['ses_e6c4c4349ffeVGyRq6WgM8Ww00']`, so only the opencode session was matched.
Started 02:13 IST, 1 Nov 2026.

## Files read, in order

1. `instruction.md`
2. `environment/docs/charging_rules.md` (the whole spec; 21 numbered rules)
3. `environment/data/grid.ini`, `bus_types.json`, `depots.json`, `disruption_notice.md`,
   `service_classes.ini`, `tariff.xml` (all small, read in full)
4. `environment/data/roster.csv`, `fleet_register.csv`, `published_plan.csv`,
   `trips.jsonl`, `contracts.json` (headers and samples read; the bulk was characterised
   with counting commands and the two analysis scripts, since they are 2000+ line tables)

No file outside the blind directory was opened, no web lookup, no subagent, no Docker/pip/git.

## Minutes to first full write

**7 minutes** — session start 02:13, `app/derive_report.py` complete at 02:20. The program
was written once, in five appends to the one file, with no logic rework afterwards.

## What the self-check covered, and its result

Result: **PASS**. One run on the shipped data (`real 0.10 s`, cap 120 s), then one
independent checker run (`real 0.07 s`). Full command log in `work/CHECKS.md`.

* All nine named reports exist in `out/` and have the stated shape: 96 slot entries in every
  slot list, in time order; `{"slot","kwh","feeder_kwh"}` in the region and segment lists;
  one audit entry per bus sorted by `bus_id`; all amounts whole integers.
* Constraint check from the written reports: every bus charges only in its window and never
  above `max_kwh_per_slot` or its need; every depot-slot cap (cabinets in service x 15 kWh,
  including the North and South outages) and every feeder-slot cap (1500, 250 in the eight
  derated slots 19:30–21:15) holds.
* Controls the files define: region energies and segment energies each sum to the 16080 kWh
  delivered; `feeder_kwh` in every slot list equals the all-depot slot total; `feeder_peak_kwh`
  equals the maximum of `feeder_kwh_by_slot`; `records_rejected` (5) equals the length of the
  `data_quality` list; `buses_planned` (123) equals the audit length; per-bus
  `need - delivered = unmet` for all 123.
* Optimality evidence: a relaxation giving each bus its own cheapest window slots with the
  shared caps removed yields 600 weighted unmet kWh and 254435 cents — exactly the plan's
  values — so rule 15 levels 1 and 2 are provably attained, and moved energy 0 is the floor.

Key figures: 123 buses, need 16260 kWh, delivered 16080, weighted unmet 600, cost 254435
cents, moved 0, feeder peak 1115 kWh, 3 buses short (all `window`), 0 changed, 5 rejects.

## Crash fixed

None. The program ran correctly on its first execution; no crash and no logic change after
the self-check.

## Lessons for the master

1. Rule 15's fourth tie-break (lexicographically greatest kWh vector) is the expensive part
   of the spec — it forces an exact optimal-face refinement, not just a min-cost flow; worth
   saying whether it is ever meant to bind.
2. The shipped data makes the published plan already optimal (moved 0, 0 buses changed), so
   the headline "redo the plan" produces no visible change and rules 13–14 and the tie-break
   go untested by the shipped instance.
3. Rule 13 does not say what to do with a published row whose `bus_id` is not a bus on the
   plan; I treated it as `published_row_outside_window` (no such row exists in this data).
4. "The disruption notice wins" on the plan date leaves `first_slot` from `grid.ini`
   ambiguous if the two ever disagree; I kept the grid as given.
5. Rule 19 ("slots as in rule 18") is ambiguous about whether `feeder_kwh` in a segment report
   is the all-depot total or the segment's own; I used the all-depot total.
