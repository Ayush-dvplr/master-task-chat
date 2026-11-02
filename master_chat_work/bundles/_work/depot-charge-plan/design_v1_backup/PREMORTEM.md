# PREMORTEM depot-charge-plan (board 154f570), written before any other design file

Planned task in one line: from a fleet register, a duty roster, next-shift trips, depot chargers, a
tariff, one shared grid feeder, a published charging plan and a disruption notice, write a program
`out/derive_report.py` that produces the single optimal day charging plan for four depots under a
stated lexicographic order (weighted unmet energy, energy cost, energy moved off the published plan,
then a stated tie-break), and ten JSON documents derived from it.

## How claude-opus-5 solves it in its first 10 minutes

1. `ls -R /app`, reads instruction.md, then `docs/charging_rules.md` top to bottom (the register),
   then `head` of every data file: fleet_register.csv, roster.csv, trips.jsonl, bus_types.json,
   depots.json, grid.ini, tariff.xml, service_classes.ini, contracts.json, published_plan.csv,
   disruption_notice.md. Order: instruction -> rules -> data heads -> notice.
2. Builds the inputs correctly: needs from trips + reserve - arrival charge, windows from HH:MM,
   rates from types, depot capacity from chargers minus outages, feeder limit with derates, classes
   via contracts. These chains are plainly stated; Opus gets them right (they are not levers).
3. The program it writes once. Two likely first writes:
   (A, most likely for a "plan" task) a per-bus greedy: sort buses (by id, or by departure, or by
   class weight), give each bus its cheapest available slots (ties: published slot first, then
   earliest), respecting remaining depot and feeder capacity. Checks shipped data: every bus fully
   charged, no cap exceeded, cost equals the sum of per-bus minima. Declares optimal.
   (B, a careful agent that notices "single plan optimal for all four depots together") writes a
   min-cost flow (successive shortest paths, stdlib) with composite integer costs, unmet arcs at
   class weight, a parallel arc for the published amount. For the stated tie-break it either
   (B1) relies on arc order in Dijkstra, (B2) adds a small per-slot epsilon cost (earlier cheaper),
   or (B3) runs one greedy post-pass that raises x(slot,bus) in (slot, bus id) order while capacity
   remains, without keeping the earlier objective terms fixed. (B4, rare) fixes each entry in order
   at its largest value that keeps terms 1-3 optimal, re-solving each time.
4. Self-tests it runs: shipped data only (H9). On shipped data the feeder never binds and no depot
   cabinet binds (BRANCH_FIRE shipped 0), so every bus gets its own cost-optimal charge. Program A
   equals the per-bus optimum; B1-B3 agree with A on shipped because each bus is independent there
   and the per-bus tie-break (cheapest, then published, then earliest) is what all of them produce.
   Its tiny examples (2 buses, one slot) fit in its head and do not bind both resources at once.
   Invariants it asserts (caps respected, energy balance) hold for every program above.

## Where each program goes wrong (per sharp rule)

R1 shared feeder limit per slot (one limit for all four depots).
- A goes wrong in the first slot where the feeder binds on a hidden corpus: the bus served first
  takes the cheap slot, a later bus with a shorter window is pushed to a dearer slot or left short.
  Optimal cost is lower than A's, or A leaves weighted unmet energy the optimum avoids.
- Per-depot exact then split feeder (pro rata to cabinet, or by class priority): wrong whenever the
  depots' needs for a binding slot are not proportional to the split.
- Split-into-independent-parts exact: the feeder couples every bus in a slot and windows overlap,
  so the instance has one part; it reduces to plain exact (B), which then loses on R2.
- Why self-tests miss it: shipped feeder slack is large in every slot; no shipped slot fires the
  branch; Opus never builds a binding input (H9).

R2 lexicographic order with term 3 and the stated tie-break.
- B1/B2/B3 return a plan with the optimal terms 1-3 but a different per-bus split in binding slots
  (many equal-cost optima: flat tariff bands, identical bus types). B2 minimises sum of slot*kWh,
  which differs from "greatest at the first differing place" as soon as moving one kWh earlier
  forces two later; B3 raises early entries but breaks term 2 or term 3 or stops at first fit (H8).
- Why self-tests miss it: on shipped data every bus is independent, so per-bus earliest-first is
  the stated tie-break exactly; there is no shipped place where two buses compete for one slot.

R3 depot cabinet capacity (working chargers x charger output, minus outage slots).
- A and per-depot programs that compute the cabinet but apply it after the feeder share (or not
  at all) go wrong when cabinet and feeder bind in the same slot at different depots.
- Why self-tests miss it: shipped cabinets have slack in every slot including outage slots.

Non-sharp stated rules (rejections, needs, windows, reasons, schemas): stated plainly with shipped
cases; Opus gets them right. They carry shipped-tier weight only.

## Judge criteria, would the trajectory show the act?

- P-b one-instance optimality witness (a hand-sized binding instance where greedy and the program
  disagree, run before the final answer): Opus program A never builds one; B rarely. Expect FAIL.
- P-c recompute objective terms and feeder peak outside the program from the delivered files:
  Opus often re-reads its own JSON with the same code; recompute from raw inputs is rare. ~30%.
- P-d altered-copy rerun (copy data, change one value, rerun, show a document moved): rare. ~20%.
- P-e relocated rerun (copy /app/data elsewhere, run with that path): Opus runs from /app only. ~20%.
- P-g uniqueness witness (show a second optimal plan loses on the tie-break): rare. ~10%.
- P-h missing / malformed input run: rare. ~20%.
- P-a edge-input run (a bus with window too short): rare. ~20%.
- P-f broken tool first: no shipped tool to break here; template not used.

Redesign check: program A is exact on shipped but WRONG on every hidden corpus (feeder binds);
program B without an exact tie pass is exact on shipped and WRONG on hidden corpora with ties.
Only B4 (or the reference method) is exact on a fresh hidden seed; it is the rare branch.
