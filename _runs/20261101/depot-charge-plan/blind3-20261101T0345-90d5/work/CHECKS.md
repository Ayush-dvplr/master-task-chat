# CHECKS.md - self-check log (step 3)

All paths relative to `/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind3-20261101T0345-90d5`.
Data folder = `environment/data` (stands for `/app/data`), output folder = `out` (stands for `/app/out`).

| # | command | input path | what it showed |
|---|---------|------------|----------------|
| 1 | `python3 -c "import ast;ast.parse(open('app/derive_report.py').read())"` | app/derive_report.py | SYNTAX_OK after each of the four write/append chunks; no crash fix needed |
| 2 | `cp app/derive_report.py out/derive_report.py` | app/derive_report.py | program shipped at both required paths |
| 3 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py --data environment/data --out out` | environment/data | exit 0, real **0.47 s** (cap 120 s). stdout: plan_date 2026-03-14, weighted_unmet_kwh 145, energy_cost_cents 251685, moved_kwh 0, feeder_peak_kwh 975, buses_planned 123, buses_short 3, buses_changed 0, records_rejected 5, and the 5 rejected rows |
| 4 | `/usr/bin/time -p python3 work/verify.py` | out/*.json + environment/data | real 0.06 s. `missing files: []` - all 9 named documents exist (policy_audit, region_North/South/West/East, segment_commercial/public, summary, data_quality) |
| 5 | same run as #4 | out/region_*.json, out/segment_*.json, out/summary.json | every `slots` list is 96 entries and matches the exact slot-label sequence 2026-03-14T12:00 .. 2026-03-15T11:45 in time order; `feeder_kwh_by_slot` likewise 96 and in order |
| 6 | same run as #4 | out/policy_audit.json | 123 buses, sorted by bus_id; `per-bus violations 0` = for every bus sum(charges)==delivered_kwh, need-delivered==unmet, unmet>=0, each charge 1..max_kwh_per_slot of its type, charges in time order |
| 7 | same run as #4 | out/policy_audit.json | need total 15880 kWh, delivered 15735 kWh (difference 145 kWh unmet, all on 3 buses) |
| 8 | same run as #4 | out/summary.json | recomputed weighted_unmet 145 == summary 145; recomputed cost 251685 == summary 251685; feeder peak 975 == summary; recomputed feeder-by-slot vector identical to summary |
| 9 | same run as #4 | out/policy_audit.json + depots.json + disruption_notice.md | `capacity violations [] count 0` - every slot respects the depot cap (cabinets minus the North 21:15-22:30 and South 02:00-03:15 outages, x15 kWh) and the feeder cap (1300, derated to 170 for 2026-03-14T20:00-22:00) |
| 10 | same run as #4 | out/region_*.json | for all four depots buses/energy_kwh/unmet_kwh equal the policy_audit roll-up, `slots.kwh` equals the depot's own slot energy and `slots.feeder_kwh` equals the all-depot slot energy. Costs: North 61080, South 56860, West 70620, East 63125 |
| 11 | same run as #4 | out/segment_*.json | commercial and public buses/energy/unmet match the roll-up by class; slot vectors match. Costs 178145 + 73540 = 251685 = summary and = region sum |
| 12 | same run as #4 | out/summary.json, out/data_quality.json | buses_planned, buses_short, buses_changed and records_rejected all agree with policy_audit and with the rejected list (5 rows) |
| 13 | same run as #4 | environment/data/roster.csv + bus_types.json | tier-1 control: the per-bus window bound sum(weight * max(0, need - max_kwh_per_slot * window slots)) = **145**, exactly the weighted_unmet achieved, so no plan can do better on criterion 1 |
| 14 | same run as #4 | environment/data/published_plan.csv | 410 plan-date published rows, 15750 kWh; minus the one rejected out-of-window row (15 kWh) = 15735 kWh = the delivered plan total; the derived plan equals the accepted published plan slot by slot, hence moved_kwh 0 (the global minimum) and buses_changed 0 |
| 15 | `/usr/bin/time -p python3 work/localopt.py` | out/policy_audit.json + environment/data | real 0.04 s. `single-unit cheaper moves available: 0` - no 1 kWh can move to a cheaper slot inside its bus's window without breaking the per-slot, depot or feeder cap, i.e. the plan is locally cost-optimal |
| 16 | `perl -e 'alarm 60; exec @ARGV' python3 out/derive_report.py --data work/no_such_data --out out` | missing folder | `error: data folder work/no_such_data is missing` on stderr, exit 2 (non-zero) - the missing-input path names the offending path and fails loudly |
| 17 | `ls -1 out/` | out/ | exactly the 9 report documents plus derive_report.py; nothing else written, environment/data untouched |
| 18 | `ps -axo pid,rss,command \| grep python` | - | no python process of mine left running |

Optimality argument recorded by the program itself: the plan is the minimum-cost integer flow of the scalarised objective
`10^22 * weighted_unmet + 10^11 * cost_cents + moved`, certified by negative-cycle cancelling on the residual graph
(no negative residual cycle remains), then raised to the lexicographically greatest kWh vector in slot-then-bus_id order
by pushing each position to the maximum inside the zero-reduced-cost face.
