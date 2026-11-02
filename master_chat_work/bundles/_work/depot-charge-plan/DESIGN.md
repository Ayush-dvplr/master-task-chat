# DESIGN depot-charge-plan (board 154f570)

Shape D (degenerate shipped instance). Primary source P-3 / S2 exact optimum on hidden instances that do not split (one shared feeder per slot). Plus S3 unique optimum under a stated lexicographic order with an exact tie-break; N2 held-out w5 tier; P-5 probe-band judge.

## 1. Spine stages
1. Load and validate inputs (fleet register, roster for the plan date, trips, types, contracts, classes, depots, grid, tariff, published plan, disruption notice). Rejected records go to data_quality.json with a stated reason string.
2. Derive per bus: depot, type rate (kWh per slot), class weight, window slots [arrive, depart), energy need = trips of the next service day (plus notice extra trips) + type reserve - arrival state of charge, floor 0.
3. Derive per slot: tariff price (cents/kWh), feeder limit (grid.ini, derated by the notice), per depot cabinet supply limit (cabinets in service x cabinet kWh per slot; notice outages).
4. Choose the one day plan that is optimal under the stated order for all four depots together (COUPLING sentence): (1) least class-weighted unmet energy, (2) least energy cost, (3) least moved energy against the published plan, (4) tie-break: the plan whose list of kWh values, read in order of slot then bus id, is greatest at the first place they differ.
5. Report: policy_audit (per bus), region_<depot> (per depot, per slot), segment_<class>, summary (objective terms, feeder load per slot, peak, counts), data_quality.

## 2. Input files (environment/data/)
| file | format | rows (shipped) | feeds |
|---|---|---|---|
| docs/charging_rules.md | md | ~140 lines | rule register (all rules, objective order, tie-break, output schema, reason strings) |
| fleet_register.csv | csv | ~2400 | vehicle id, type, home depot, status (active/retired) |
| roster.csv | csv | ~2100 (7 service dates) | bus, plan date, depot, arrive HH:MM, depart HH:MM, soc_arrival_kwh, contract_id |
| trips.jsonl | jsonl | ~2400 | bus, service date, trip id, kWh |
| published_plan.csv | csv | ~2200 | bus, slot HH:MM, kWh (plan date rows plus other dates) |
| bus_types.json | json | 3 types | max kWh per slot, reserve kWh |
| contracts.json | json | ~20 | contract id -> class |
| service_classes.ini | ini | 2 classes | weight per class |
| depots.json | json | 4 | cabinets, cabinet kWh per slot |
| grid.ini | ini | 1 section | plan date, feeder kWh per slot |
| tariff.xml | xml | 4-6 bands | price bands by slot range, integer cents/kWh |
| disruption_notice.md | md | short | cabinet outages (depot, slots), feeder derates (slots, limit), extra trips (bus, kWh) |
Six formats: csv, jsonl, json, ini, xml, md. Hidden corpora re-render the same files; only values change (W12).

Chains (length >= 4):
- C1 roster.contract_id -> contracts.json class -> service_classes.ini weight -> objective term 1 -> which bus is short -> audit rows, segment files, summary.
- C2 roster.bus -> fleet_register type -> bus_types rate/reserve -> need and window capacity -> unmet_reason -> audit.
- C3 trips.jsonl (service date = next day) + notice extra trips -> need -> flow -> feeder load per slot -> every region file slots and summary.
- C4 grid.ini feeder -> notice derate -> slot limit -> plan -> moved energy (term 3) -> changed flags -> summary counts.
- C5 depots.json cabinets -> notice outage -> depot slot limit -> plan -> region files.

## 3. Sharp rules (Shape D, at most 3)
R1 Shared feeder limit per slot (grid.ini + notice derates). Governing file: docs/charging_rules.md section "Supply limits". Reflex: per-bus greedy / per-depot plan that ignores the others, then trims (pro rata / priority) or splits into independent parts. Hidden: feeder binds in 6-20 slots per corpus. Shipped: feeder never binds (count 0), so every per-bus program is exact there. Interaction: the feeder couples all depots; trimming changes cost and term 3 and moves charges into other slots.
R2 Lexicographic objective with exact tie-break. Governing file: docs/charging_rules.md section "Choosing the plan". Reflex: (H8) first optimum found by the solver (arc order), or per-slot epsilon, or a post-pass that moves energy. Hidden: flat tariff bands create many equal-cost optima once limits bind; term 3 and the tie-break select one. Shipped: the published plan is itself optimal and term 3 = 0 forces it, so every solver returns the same plan (tie-break never decides; count 0).
R3 Depot cabinet supply limit per slot (depots.json + notice outages). Governing file: docs/charging_rules.md "Supply limits". Reflex: treat as per-bus cap only or ignore. Hidden: binds in 2-8 depot-slots per corpus; shipped 0.

Plain stated rules (about 20, all in docs/charging_rules.md or the file that defines the data): need formula, floor 0; next service date trips only; extra trips from notice; class from contract, unknown contract -> commercial default; weights; type rate; window [arrive, depart); slot 0 = 12:00; rejections (unknown vehicle, retired vehicle, depart not after arrive, duplicate roster row (first kept), depot differs from register, published row outside window or unknown bus); unmet_reason window|capacity; changed flag; moved energy definition; sorting and number formats of every output.

## 4. Why visible data cannot confirm R1-R3 (W5, W6)
Shipped feeder and cabinet limits exceed the total demand in every slot; the published plan is each bus's cheapest fill at full rate with strict price order inside each window (no partial chunk, no equal-price choice left). So "charge each bus as published" is the unique optimum, unmet 0, moved 0, and every candidate reading of R1-R3 reconciles on shipped (W7). Measured (KILL_TEST block7): lex-min and lex-max big-int solvers, plain flow, greedy, per-depot and split programs all EXACT 8/8 on shipped seeds 1-3 (bindF 0, bindC 0), so the tie-break never decides on shipped. No worked example where readings differ; at most one toy example of the tie-break on invented values (W6 v3), decided at Phase 2 (default: none).

## 5. Rejection paths
data_quality.json lists each rejected record with file, record key and a stated reason string from charging_rules.md. Rejected buses are not planned. A missing or malformed declared input stops the program with a message naming the file and a non-zero exit.

## 6. Test plan (G1-G13)
Invocation stated in instruction.md: `python3 /app/out/derive_report.py --data <data dir> --out <output dir>`; the verifier runs it as a foreign uid from a foreign cwd on 4 hidden corpora generated by an embedded seeded generator (seed only in tests/): corpora 1-3 regular (70-120 planned buses, feeder binds 6-20 slots, cabinets 1-12 depot-slots), corpus 4 large (350-450 buses). Stated per-run limit 120 s (reference large 7-8 s, <= 1/4); verifier worst case about 6 runs x 120 s = 720 s plus compare, well under 90% of the verifier timeout. Rare branches (window-short bus, unknown contract, duplicate roster row) use their own RNG stream (G8).
| check | weight | corpus | owns |
|---|---|---|---|
| existence of 10 outputs | 1 | shipped | presence |
| audit_shipped | 3 | shipped | policy_audit rows |
| regions_shipped | 3 | shipped | 4 region files |
| segments_summary_shipped | 3 | shipped | segment files + summary |
| quality_shipped | 3 | shipped | data_quality |
| audit_hidden_k (k=1..4) | 5 each | hidden k | policy_audit rows |
| regions_hidden_k | 5 each | hidden k | region files |
| segsum_hidden_k | 5 each | hidden k | segment files + summary |
| quality_hidden | 3 | hidden 1-4 | data_quality |
| mut_shuffled | 3 | shuffled rows of hidden 1 | whole audit (counted only where plain hidden 1 audit exact) |
| mut_relocated | 3 | hidden 2 copied to a new path, foreign cwd | whole summary (counted only where plain hidden 2 exact) |
Total 85. Hidden share (60 + 3 + 6) / 85 = 81%. Held-out w5 tier 60/85 = 71% (>= 50% N2). Lever share: every hidden w5 check grades R1-R3 (plans differ there) = 60/85 = 71%.
Per-row ownership (G1a): policy_audit rows owned by audit_*; region per-slot rows by regions_*; summary and segment by segsum_*; data_quality by quality_*. Messages give the first differing path (G7). A check that compared nothing fails.
Amplification: one wrong feeder share moves charges between buses and slots, so audit rows, region slot rows and the summary feeder vector all differ (COUPLING quantity = feeder load per slot, carried into every region file, both segment files and the summary).

## 7. Judge plan (J1-J10)
Probe band 9 criteria w3 process trajectory (55-70% of positive judge weight): P-a edge input (all buses short window), P-b one-instance optimality witness (a small hand instance where greedy is wrong), P-c recompute feeder load per slot from policy_audit outside the program, P-c recompute objective cost from audit, P-d altered-copy rerun (raise one bus need), P-e relocated rerun, P-h missing input run, P-h malformed input run, P-g uniqueness witness (two plans equal on terms 1-3 compared by the tie-break). J3a -3, J3b -5, J3c -3; J4 one code-quality criterion w3; J6 enumeration of short buses w3; J10 work-directory -1, order w3 (if a stated process order exists). Predicted Opus judge: lower 10, mid 17, upper 30.

## 8. Expected loss per lever
- R1 feeder: per-bus greedy / per-depot / split programs lose all 12 hidden w5 checks (0/8 families kept in Docker prototype on all 6 hidden seeds).
- R2 tie-break: plain min-cost flow (arc order or epsilon) reaches the same objective vector but a different plan: loses audit/regions/segsum on every hidden corpus (Docker 0/8 kept on 6/6 seeds).
- R3 cabinets: reference without cabinets (ref_nocab) keeps 0, 0, 3, 1, 0 of 8 families on hidden 1-4 and large 1 (block8): loses about 55 of 60 w5 points.
- All-but-one rows (block8): ref_nofeed 0/8, ref_nocab 0-3/8, ref_noterm3 0/8 on every hidden corpus -> each sharp rule alone >= 25% (about 60/85 = 71% each); predicted all-but-one tests about 25-30, final about (28 + 17)/2 = 22.5 < 70.
- Careful exact reader (flow_bigint or the reference method): EXACT on regular hidden corpora, TIMEOUT only on the large corpus if it uses the big-integer fold (186 s vs 120 s limit). Worst case tests about (85 - 15)/85 = 82. This is the hangar NO CORE risk; only the design blind measures it.
Predicted first-write tests: shipped 13 + existence 1 + quality_hidden 3 + mutation 0 (not counted, plain hidden not exact) = 17/85 = 20. Judge mid 17. Predicted final = (20 + 17)/2 = 18.5.

Per rule, where a careful solver loses (for the probe loss.py comparison):
| rule | hidden input | checks lost |
|---|---|---|
| R1 feeder | every hidden corpus (feeder binds 11-20 slots) | audit_hidden_1..4, regions_hidden_1..4, segsum_hidden_1..4 |
| R2 order / tie-break | every hidden corpus (flat bands, equal terms 1-3) | same 12 checks; mutation checks not counted |
| R3 cabinets | hidden 1, 2, 4 (11-12 depot-slots) and large | audit/regions/segsum on those corpora |
Per probe: P-b, P-g expected FAIL for Opus; P-c, P-d, P-e, P-h about 20-30%; P-a about 20%.

## 9. Kill test
See KILL_TEST.md (Docker, python:3.12-slim, --memory 4g --cpus 2, perl alarm).

## 10. Redesign G-8 (after design blind fd98e12 NO CORE)
- New input file `settlements.csv` (csv, 2255 rows: settled_date, depot, bus_id, start, end, kwh, cents) and `tariff.xml` now holds three dated versions (two older ones cover the settled days, the current one covers the plan date). Chain C6: tariff.xml version by settled_date -> settlements.csv rows per depot -> depot convention -> depot slot price -> plan (feeder-coupled) -> every report.
- Rule 12 (docs/charging_rules.md:27) states: price of a slot for a depot = the price its meter applies under the version in force on the plan date; the meter convention is the one under which every settlement row of the depot bills exactly, and the settlements allow exactly one.
- Reflex reading (PREMORTEM H9): identity fits every shipped row, so the tariff is used as stated; a careful reader may verify history on shipped only, see it reconcile, and stop. Hidden: every depot has a non-identity convention, so every cost, the plan (prices change which slots are cheapest, through the shared feeder) and every report family differ.
- Expected loss: all hidden families (w5 tier 71% + quality hidden) for any program that does not search shifts; kill rows in KILL_TEST.md section 'Redesign G-8'.
- Honest risk: a program that searches every cyclic shift is exact. UNIQUENESS: generator asserts exactly one of 96 shifts fits all rows per depot (shipped: identity).
