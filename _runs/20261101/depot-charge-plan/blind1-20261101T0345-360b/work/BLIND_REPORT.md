# BLIND_REPORT (board ec4f695, depot-charge-plan, step P13, blind1)

Session renamed to `ec4f695` at 03:45:07 IST (name_session.py printed
`opencode: ['ses_e6bf858ddffeYv1XCCJA6lpi76']`). Window 03:45 - 03:58 IST.

## Files read, in order

1. `instruction.md` (25 lines) - program path, the nine required documents, stdlib-only, 120 s cap.
2. `ls -la` of BLIND_DIR and `find environment -type f` - 13 data files + Dockerfile.
3. `environment/data/docs/charging_rules.md` (48 lines, 22 rules) - rejection order, window, need, per-slot limits, meter rule 12, lexicographic objective, report fields.
4. `environment/data/grid.ini` - plan_date 2026-03-14, first slot 12:00, 96 x 15 min, feeder 1300 kWh/slot.
5. `environment/data/bus_types.json` - E12 30/20, E15 45/30, E18 60/40.
6. `environment/data/depots.json` - cabinet 15 kWh/slot; North 30, South 30, West 28, East 35 cabinets.
7. `environment/data/service_classes.ini` - public 4, commercial 1.
8. `environment/data/contracts.json` - 17 contracts (SCH-/HSP- public, COM- commercial).
9. `environment/data/tariff.xml` - 3 versions; in force on the plan date 31 / 27 / 14 / 22 cents by band.
10. `environment/data/disruption_notice.md` - 2 North cabinets out 21:15-22:30, 2 South out 02:00-03:15, feeder derate 170 kWh 20:00-22:00, extra trips B1051 35 / B1179 20 / B1292 75.
11. `environment/data/settlements.csv`, `roster.csv`, `fleet_register.csv`, `published_plan.csv`, `trips.jsonl` - 2243 / 4957 / 4000 / 5240 / 5189 rows; on the plan date 127 roster rows, 410 published rows, 359 next-day trips.
12. (step 5 only) `blind1-20261101T0345-360b.judge.md` - the 16-criterion rubric.

Nothing outside BLIND_DIR was opened apart from the rubric at step 5 and the
session-naming tool at the start.

## Minutes to first full write

The program was written in three appends and parsed clean as 881 lines at
about **03:54 IST, 9 minutes** after the 03:45:07 start; its first successful
run was at 03:55.

## Program

`app/derive_report.py`, copied verbatim to `out/derive_report.py` (the graded
path). Stdlib only, no hard-coded run paths: `--data` defaults to `/app/data`
and `--out` to `/app/out`.

Design: loaders for every declared input (ini, json, xml, markdown notice, csv,
jsonl) that return line numbers so rejections can cite them; `infer_meters()`
derives each depot's per-slot price rule from settlements.csv by testing
candidates with exact Fractions; the plan itself is a min-cost flow
(successive shortest paths, Dijkstra on reduced costs) whose arc costs encode
the lexicographic objective with big-M factors - weighted unmet first, then
energy cost, then moved energy - followed by `lex_maximise()`, which pushes
flow around zero-reduced-cost residual cycles in (slot, bus_id) order to
realise tie-break (4), the lexicographically greatest kWh vector.

## Self-check: what it covered, and its result - PASS

Two timed runs under the 600 s `perl -e 'alarm 600'` cap, both on the shipped
corpus: `app/derive_report.py` in 1.38 s, then, after the copy into `out/`,
the final `out/derive_report.py --data environment/data --out out` in 1.74 s,
exit 0, all nine documents written.

A verification script written separately from the program recomputed, and
found **0 errors** in: every charge inside its bus window; kWh <=
max_kwh_per_slot; delivered <= need; unmet = need - delivered; charges in time
order; per-depot per-slot energy <= cabinets-in-service x 15 with both cabinet
outages applied; all-depot per-slot energy <= 170 kWh inside 20:00-22:00 and
<= 1300 elsewhere; feeder peak 975; every region file's slot series against the
recomputed depot and all-depot series; region and segment sums against
summary.json; weighted unmet 145; policy_audit bus_ids sorted. A second script
compared the plan against published_plan.csv: the 409 accepted published cells
and the 409 planned cells are identical (15735 kWh each), which is the control
the data itself defines for moved_kwh 0 and buses_changed 0. The meter rule was
established by fitting candidates to all 2243 settlements rows: the slot-start
band price bills every row of all four depots (558/555/561/569), while every
whole-session candidate misses ~100 rows per depot.

Not covered: any run on a data folder built or altered by me (small-feeder
witness, lowered feeder, altered need, relocated copy, missing input) - the
prompt restricted the self-check to the shipped data.

## Crash fixed

None. The program ran correctly on its first execution and was not changed
after the self-check.

## Results handed to the judge

summary.json: plan_date 2026-03-14, weighted_unmet_kwh 145, energy_cost_cents
251685, moved_kwh 0, feeder_peak_kwh 975, buses_planned 123, buses_short 3,
buses_changed 0, records_rejected 5. The five rejected records and the region
and segment breakdowns are in work/FINAL_REPLY.md.

## Judge estimate

Lower bound **20 / 35**, upper bound **20 / 35**, 5 process criteria not
performed (R1, R2, R6, R7, R8). No negative criterion fires. Detail in
work/JUDGE_ESTIMATE.md.

## Lessons for the master

- The rubric spends 15 of 35 points on runs against data folders the agent
  builds or edits; a blind prompt that says "self-check on shipped data only"
  forfeits all of them, so that clause should permit scratch copies outside
  /app/data.
- Rule 12 (meter inference) is the one place a wrong guess silently shifts
  every cost figure, and it is cheap to settle by fitting candidates to the
  settlement rows - worth stating as a required check.
- The shipped corpus makes the published plan already optimal, so moved_kwh 0
  and buses_changed 0 exercise none of tie-break (3) or (4).
- A min-cost-flow formulation with big-M arc costs plus a residual-cycle pass
  handles all four objective levels in under 2 s; no search was needed.
- Timing was comfortable: 9 minutes to the written program, 13 to all
  deliverables.
