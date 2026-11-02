# TRIP: depot-charge-plan attempt 1 (claude-opus-5, run_1), board c5b188a

Source: OUT/gate_run_a1 (copy of Output_RFP/depot-charge-plan/trajectories/claude-opus-5/run_1). 78 steps.
Graded: final 72.37 = tests 100.0 (197/197) + judge 44.74 (17/38). Correction to master note 1: the -3 unrun-claim
negative R12 DID fire (final message claims 950 randomized brute-force checks passed; all ran before the last edit at
step 74), so judge = 20 positive - 3 = 17 of 38.

## 1. What it read (step numbers)
| step | read |
|---|---|
| 3 | `find /app` (tree) |
| 4 | docs/charging_rules.md (whole) |
| 5 | grid.ini, depots.json, bus_types.json, service_classes.ini, contracts.json, tariff.xml, disruption_notice.md (whole) |
| 6 | wc + head of fleet_register.csv, roster.csv, trips.jsonl, published_plan.csv, settlements.csv |
| 7-8 | awk counts: roster/published rows per plan date, blank contract ids |
| 9 | python: roster rejection analysis (unknown, retired, duplicate, bad window) |
| 10 | python: published slot_start on grid / in window |
| 11 | roster x fleet join (types, home depots) |
| 12 | trips.jsonl service dates and keys |
| 13 | tariff + settlements: tries all 96 shifts per depot with Fraction, exactly one fits (East 28, others 0) |
| 14-16 | needs per bus, settlement dates, fleet counts |
instruction.md was in the prompt. No file under /tests or /logs/verifier was opened.

## 2. Documented rules it implemented and how it checked them
Program: artifacts/app/out/derive_report.py (923 lines; written step 17/19, edited 29-32, 40, 50-56, 67-69, last edit 74).
| rule (charging_rules.md line) | implemented | how a1 checked it |
|---|---|---|
| 1-2 grid, from/to spans (L7-8) | yes, all from grid.ini | v2 copy slot_minutes 30 (step 57) ran without error |
| 3-4 roster date, rejection order (L12-13) | yes, L421-435 | step 9 analysis on shipped only |
| 5 window, roster depot (L14) | yes (roster depot, arrive<=t<depart) | not checked: no folder with roster depot != home depot, no off-grid arrive |
| 6-8 type, need, class (L15-17) | yes; extras only day after plan date | validate.py step 48 with hardcoded weights/extras (shipped only) |
| 9-10 slot kWh, cabinets (L21-22) | yes, outages summed | v3 copy (step 57) outages; validate.py hardcoded caps 450/450/420/525 |
| 11 feeder (L23) | **min(base, derate) at L519-523; rule says "replaced by the derated limit"** | v3 copy derates 90 and 400, both below base 1300; never a derate above base |
| 12 tariff, meter shift (L27) | yes, plan-date version, k by exact Fraction fit | step 13 (all 96 k, exactly one) |
| 13-14 published, moved (L28-29) | yes | steps 10, 62-63 (B1035) |
| 15-16 lexicographic optimum (L33-34) | min-cost flow + lexicographic pass | steps 43-47, 64-66 /tmp/test_opt.py: random small instances vs brute force via direct calls to solve_plan (no data folder, no reports) |
| 17-21 report shapes (L38-44) | yes | certify.py step 58 imports the program's own parser (dr.build_plan, dr.parse_disruptions) |
| 22 missing file (L48) | yes | v4 copy without tariff.xml, exit 1 + message (step 57-61) |

Shipped-fitted literals in the program: none found. Every limit, weight, slot, depot name and price is read from the data
folder; the only fixed names are the segment classes commercial/public (documented). The checking scripts (not graded)
are full of shipped literals: /tmp/validate.py (step 48) hardcodes bands, East k=28, caps 450/450/420/525, feeder 1300,
derate 90, extras, weights {public 4, commercial 1}, plan end 2026-03-15T12:00.

## 3. Where checking stopped
- After step 66 it only re-ran the program and the two shipped-only scripts (steps 70-77). Last edit step 74; final
  runs 75-76; cleanup 77; final message 78.
- Never built a small data folder and compared to a hand plan (R1), never checked a lowered feeder copy's result against
  the limit (R2), never recomputed summary or region limits with code independent of the program and of shipped literals
  (R3, R4), never changed a need input and checked need_kwh moved (R6), never ran a relocated copy (R7).
- Never exercised: a derate above feeder_kwh_per_slot, roster depot != home_depot, a tariff version ending on the plan
  date, two outages on one depot in one slot, an arrive time between slot starts.

## 4. Fuzz: a1 program vs reference solve.py (Docker python:3.12-slim, 4g/2cpu)
Harness WORK/h3_a1/fuzz.py: renders a folder with the test generator (gen_core.py), runs reference and a1, compares the 9
documents whole. Logs `_runs/20261101/depot-charge-plan/harden3-20261101T1746/`.
| branch | seeds | MATCH | DIFF | fail | first DIFF field |
|---|---|---|---|---|---|
| shipped | 1-300 | 300 | 0 | 0 | none |
| hidden (h1-h3 kind) | 1-300 | 300 | 0 | 0 | none |
| hidden_reorder (altered-copy transform) | 1-300 | 300 | 0 | 0 | none |
| large (h4 kind) | 1-300 | 300 | 0 | 0 | none |
| uplift (prototype, not in bundle) | 1-300 | 0 | 300 | 0 | policy_audit.json changed/charges; all 8 plan docs differ every seed, data_quality same |

Timing: shipped ref max 2.42 s; hidden ref 1.1-1.7 s, a1 0.6-0.9 s; large ref max 18 s (3 containers sharing), a1 max 5.4 s.

## 5. Documented behaviour where a1 differs, and documented behaviour the generator never plants
| behaviour (doc line) | planted by generator? | a1 vs reference |
|---|---|---|
| derated limit above feeder_kwh_per_slot replaces it (rule 11, L23 "replaced by the derated limit") | no (hidden derates are always below base) | **a1 WRONG** (min) |
| roster depot differs from fleet home_depot (rule 5, L14 "depot on its roster row") | no (roster depot = home) | same (by reading code) |
| tariff version ends on plan date, slots after midnight (rule 12, L27 "version in force on the plan date") | no (current version runs pd..pd+60) | same (by reading code) |
| two outage lines at one depot in one slot (rule 10, L22 "less any cabinets") | no (one outage per depot) | same (both sum, by reading code) |
| arrive between slot starts (rule 5, L14 "start at or after arrive") | no (all times on the grid) | same (by reading code) |
Not determinate from the docs (not planted): overlapping derate lines (ref last wins, a1 min), duplicate fleet ids,
off-grid first_slot, slot_minutes other than 15 with k 0..95.
Result: one documented WRONG case exists; the generator never plants it. All other unplanted cases a1 handles as the
reference does.
