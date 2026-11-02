# UNIQUENESS: candidate spaces with an exactly-one claim

## U1 meter convention (docs:27 rule 12, "the settlements allow exactly one")
- Candidate readings fitted: identity (shift 0), every slot shift 1..95, per-depot multiplier, per-band multipliers, settled price read at session start / end / max / min / previous slot (WORK/proto2/conv.py fitters; KILL_TEST.md "Redesign G-8").
- Shipped (BUNDLE/environment/data/settlements.csv, 2243 rows): shift 0 is the only shift that bills every row of each depot exactly (solve.py fit_meters asserts len 1; selfcheck `check meter_unique ok`). The multiplier and start-price readings coincide with shift 0 on shipped (degenerate by design, Shape D).
- Hidden: gen_core.conv() redraws history until, for every depot, the list of fitting shifts in range(96) equals [k_d] (assert in the generator loop). Identity and multiplier readings do not fit exactly on any hidden corpus (kill rows a, b: 0/8 kept on hidden1-4, large1).
- Verifier: the embedded generator runs the same loop for h1-h4; the reference solve (solve_proto.load) asserts exactly one fitting shift per depot.

## U2 day plan (docs:33 rule 15 terms 1-3 then the tie-break)
- The tie-break orders all plans by the list of kWh values in order of slot then bus id (lex-greater wins), a total order on distinct plans, so the optimum is unique once terms 1-3 are equal.
- Brute force: WORK/check_exact.py brute 300 tiny instances with per-depot prices: every best plan unique, solve.py make_plan and proto2 solve_flow equal it (log _runs/20261101/depot-charge-plan/build-20261101T0307/logs/ce.log "BRUTE checked 300 mismatches 0").
- Shipped: lex-min and lex-max optimal plans coincide (bigint_min EXACT 8/8 on shipped, KILL_TEST block7/bf), so the tie-break never decides on shipped; on every hidden corpus they differ (bigint_min 0/8).
