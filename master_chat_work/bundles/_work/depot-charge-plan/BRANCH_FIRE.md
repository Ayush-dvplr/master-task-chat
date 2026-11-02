# BRANCH_FIRE (prototype, Docker measured; KILL_TEST blocks 3-7)

Shipped = gen_proto shipped seeds 1-3 (120 buses). Hidden = gen_proto hidden seeds 1-6 (70-120 buses) and large seeds 1-3 (350-450 buses).

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| R1 shared feeder | feeder limit binds in a slot (load == limit, demand wants more) | 0 (seeds 1-3) | hidden 1-6: 14/15/13/12/18/14 slots; large 1-3: 15/20/11 slots |
| R3 depot cabinet supply | depot-slot load == cabinet limit | 0 (seeds 1-3) | hidden 1-6: 11/12/1/3/8/6 depot-slots; large 1-3: 12/6/7 |
| R2 term 1 weighted unmet | some bus short at departure | 0 | hidden 1: 35, 2: 820, 4: 15, 5: 10, large 1: 1075, 2: 5750 (hidden 3, 6, large 3: 0) |
| R2 term 3 moved energy | optimum must move published energy | 0 (moved 0) | all 9 hidden/large seeds (moved 3170-33545) |
| R2 tie-break decides | lex-min plan != lex-max plan at equal terms 1-3 | 0 (bigint_min EXACT on shipped 1-3, block7) | hidden 4 (bigint_min 0/8, block6); hidden 1-6 and large via flow_plain WRONG with equal objective vector |

Generator obligations carried to tests/ (G8, G12): every hidden corpus must fire R1, R3 and term 3; term 1 must fire on at least 2 of 4 corpora; the tie-break must decide on every corpus (asserted by comparing lex-min and lex-max on terms 1-3 ties in the embedded generator self-check, or by planting a flat price band across the derate block). Rare fixtures (unknown contract, window-short bus, duplicate roster row) come from their own RNG stream.

## Re-check on rendered files (Phase 0b, 02:20 IST, Docker python:3.12-slim, log _runs/20261101/depot-charge-plan/p0b-20261101T0210/logs/bf2.log ALL_DONE)
Files rendered by proto/render.py, parsed by proto/solve_proto.py, reference = proto/core.py solve_flow with tie pass.

| corpus | buses | ref s | obj [weighted unmet, cost, moved] | feeder-binding slots | cabinet-binding slots | short (window) | agree/8: bigint_min, flow_plain, greedy_id, ref_nofeed, ref_nocab |
|---|---|---|---|---|---|---|---|
| shipped:1 (= design_blind sample) | 123 | 0.38 | [600, 254435, 0] | 0 | 0 | 3 (3) | 8, 8, 8, 8, 8 |
| hidden:1 | 83 | 0.37 | [730, 168190, 7200] | 18 | 12 | 9 (2) | 0, 0, 0, 0, 0 |
| hidden:2 | 108 | 0.42 | [2965, 223970, 5025] | 20 | 13 | 24 (3) | 0, 0, 0, 0, 0 |
| hidden:3 | 95 | 0.47 | [170, 210500, 8605] | 13 | 1 | 2 (2) | 0, 0, 0, 0, 2 |
| large:1 | 374 | 5.34 | [1900, 842455, 32755] | 15 | 13 | 24 (7) | 0, 0, 0, 0, 0 |

Hard branches (feeder R1, cabinets R3, tie-break deciding = bigint_min differs): shipped 0, every hidden corpus > 0. `unmet_reason "window"` is a plain rule and fires on shipped (3 buses) and hidden (2-7); `"supply"` fires only on hidden. All 5 rejection reasons fire once on every corpus.

## Redesign G-8: meter convention (rule 12), rendered files, proto2 (log conv-20261101T0240/logs/render1.log)
| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| 12 meter convention | non-identity convention at a depot | 0 (identity at all 4 depots) | 4 of 4 depots on hidden1, hidden2, hidden3, hidden4, large1 |
| 12 tariff versions | settled date under an older version | 2255 rows, all (history only; plan date uses the current version) | all rows on every seed |
| 11 feeder (R1) | binds | 0 | hidden1 20, hidden2 15, hidden3 13 slots |
| 10 cabinets (R3) | binds | 0 | hidden1 6, hidden2 12, hidden3 5 depot-slots |
| 15 term 1 | weighted unmet > 0 | window-short only (3 buses, reason window) | supply-short on hidden1 (8 short), hidden2 (24), hidden3 (2) |
| 15 tie-break | decides | 0 (bigint_min agrees 8/8) | hidden1-3 (bigint_min 0/8) |
Shipped settlements: identity fits every row at every depot; the generator asserts it is the only one of the 96 shifts that fits. Hidden: unique shift per depot asserted.
