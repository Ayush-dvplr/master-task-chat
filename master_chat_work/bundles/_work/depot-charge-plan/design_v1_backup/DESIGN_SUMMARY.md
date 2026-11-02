# DESIGN_SUMMARY depot-charge-plan (154f570), Shape D
Core: 4 depots, 96 slots of 15 min, buses with windows, need (trips + reserve - arrival charge), per-type kWh per slot,
depot cabinet supply limit per slot, ONE shared feeder limit per slot, tariff bands. Plan = lexicographic optimum
(1) class-weighted unmet kWh, (2) energy cost, (3) moved energy vs published plan, (4) tie-break: kWh list in (slot, bus id)
order greatest at first difference. Reference: min-cost flow + exact tie pass on the zero-reduced-cost face (brute force 300/300 unique).
Sharp rules: R1 feeder, R2 order + tie-break, R3 cabinets; all in docs/charging_rules.md. 12 input files, 6 formats.
Shipped: 120 buses, limits never bind, published plan = unique optimum (moved 0); lex-min == lex-max (BRANCH_FIRE shipped 0 for every hard branch).
Hidden (verifier generator, 4 corpora): 3 regular (70-120 buses), 1 large (350-450); feeder binds 11-20 slots, cabinets 1-12 depot-slots, tie decides.
Kill table (Docker python:3.12-slim 4g/2cpu, KILL_TEST.md, blocks 1-8 ALL_DONE):
| solver | shipped | hidden 1-6 + large 1-3 |
|---|---|---|
| per-bus greedy (id / EDF / class), greedy+swap | EXACT 8/8 | WRONG 0/8 every seed |
| per-depot exact + pro-rata / priority trim | EXACT | WRONG 0-1/8 |
| split into independent parts + exact per part | EXACT | WRONG 0/8 (feeder joins all buses into one part) |
| plain exact flow (first optimum / per-slot epsilon) | EXACT | WRONG 0/8 (same objective vector, other plan) |
| flow + post-pass | WRONG | WRONG |
| exact, tie-break read lex-min | EXACT | WRONG 0/8 |
| natural per-position re-solve (careful reader) | TIMEOUT 300 s (250 buses) | TIMEOUT 600 s |
| careful exact big-int fold of the whole order | EXACT 6-8 s | EXACT hidden 2-8 s; large 157-186 s (TIMEOUT at 120 s limit) |
| all-but-one: no feeder / no cabinets / no term 3 | EXACT / EXACT / WRONG | WRONG 0/8, 0-3/8, 0/8 |
Reference: shipped 0.4 s, hidden 0.3-0.9 s, large 5.7-7.6 s (<= 1/4 of 120 s).

Tests (85 positive): existence 1, shipped 4 x w3, hidden 12 x w5 (audit, regions, segment+summary per corpus), quality_hidden w3,
2 mutation w3. Hidden share 81%, held-out w5 71% (>= 50%), lever share 71%.
Judge: 9 probes w3 (P-a, P-b, P-c x2, P-d, P-e, P-h x2, P-g), J3a/b/c, J4, J6, J10; estimate lower 10 / mid 17 / upper 30.

DESIGN READY criteria: (a) predicted final = (first-write 20 + judge 17)/2 = 18.5 <= 35 PASS. (b) lever share 71%, w5 held-out 71% PASS.
(c) blind programs: unmeasured until Phase 0b; worst case careful exact = 82 (loses only large corpus). RISK.
(d) verifier worst about 6 runs x 120 s + compare = about 800 s of 2700 s (30%) PASS. (e) every generic solver and all-but-one
variant loses >= 15% of lever points by WRONG; shipped fast; reference <= 1/4 limit PASS.

G-10: (a) careful-reader rows present (per-position re-solve TIMEOUT; big-int fold EXACT on regular hidden). (b) coupling: one
feeder share decision moves charges across depots, every hidden corpus differs in audit, all regions and summary (0/8 families).
(c) plain exact vs reference: plain flow is as fast as reference (no time lever there); big-int fold 24x reference only at
large scale; the 120 s limit is a plain per-run sentence, loss confined to the large corpus (15/85 = 18%). (d) per-field
compare with first differing path, per-row ownership, no whole-report hash.

Main risk (hangar NO CORE lesson): a careful blind that writes the reference method or a fast big-int fold is EXACT on the
regular hidden corpora; then tests about 82 and the task fails G-7. Only the Phase 0b blind measures it; G-8 redesign if so.
DESIGN BLIND folder: /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/depot-charge-plan/design_blind/ (instruction.md + environment/docs/charging_rules.md + environment/data/ 11 files; prototype outputs per corpus under _runs/20261101/depot-charge-plan/p0b-20261101T0210/scratch_b/<corpus>/ref; BRANCH_FIRE re-check in BRANCH_FIRE.md).

## Design blind fd98e12
| corpus | families kept | lever points kept / lost | loss kind | first differing field |
|---|---|---|---|---|
| shipped:1 | 9/9 | 100% / 0% | none (EXACT, 0.36 s) | none |
| hidden:1 | 9/9 | 100% / 0% | none (EXACT, 0.34 s) | none |
| hidden:2 | 9/9 | 100% / 0% | none (EXACT, 0.34 s) | none |
| hidden:3 | 9/9 | 100% / 0% | none (EXACT, 0.32 s) | none |
| large:1 | 9/9 | 100% / 0% | none (EXACT, 1.49 s) | none |
Blind wrote min-cost flow + lexicographic refinement over the optimal face (the reference method) in 7 min; faster than the reference on large. NO CORE (G-8): one redesign after the master's go. Details: DESIGN_BLIND.md, KILL_TEST.md.
