# KEPT: schema-migration-plan-repair (P12 v13 fix, board 6ebf33a)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| TS-23 / A3 (warn) | tests/test_output.py (141 checks; world_47..106_core_gated_graph registrations, count unchanged in v13) | 141 checks kept with the count; no count cap (Ayush 24 Oct 12:50, option A 27 Oct); no true duplicate to merge (TS-26 candidates run different cases); v13 changed only the `_run` child-time budget | Input_Bundle_QC/03_Tests_QC.md:62 "TS-23 Counts and balance: at least 10 checks (fail), at most 35 (warn)" |
| Step 10 oracle x3 | QC run (v9.md:53 round decision) | carried over unchanged from the previous KEPT.md | previous KEPT.md row |
