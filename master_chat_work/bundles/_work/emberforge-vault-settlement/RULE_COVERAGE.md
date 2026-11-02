# RULE_COVERAGE: emberforge-vault-settlement (P12 v3 r2, 24 Oct 2026)

Rows for the rules with a measured single-rule mutant (LEVER_RULES G11). Each mutant changes that rule alone in solve.py or is the lever / wrong variant in WORK/wrong/; "tests failed" is the count of failing positive checks on the fixed tests (local scorer, OUT p12_v3_r2/after/*.json). Partial table: the four AL-27 rules QC v8 named, the three levers and the three stated-rule wrong variants. Other rules of the contract have no mutant row yet (see RECHECK_FIX.md Lessons).

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| STOCK_FLOOR detail names the first short reagent in ascending order | environment/data/finding_codes.md:42-44 | wrong/al27_stock_floor_last.py | 1 |
| A2 opened on or before the first day / closed on or after the last day (edges) | environment/data/rulebook_admission.md:18-19 | wrong/al27_a2_edges.py | 1 |
| Q1 a requisition is considered only for an eligible workshop | environment/data/rulebook_requisitions.md:8 | wrong/al27_q1_all.py | 1 |
| V2 units available to entries filed on that day and later | environment/data/rulebook_scarcity.md:7 | wrong/al27_v2_strict.py | 1 |
| H1/H5 charge per unit, then multiplied by units (L7) | environment/data/rulebook_charge.md:12,37 | wrong/L7_rebased.py | 8 |
| S5 credited salvage releases charge from the cap ledger (L3) | environment/data/rulebook_salvage.md:41 | wrong/L3_rebased.py | 9 |
| S2 window over live forges only (L6) | environment/data/rulebook_salvage.md:12 | wrong/L6_rebased.py | 8 |
| I3 register after retire reinstates | environment/data/rulebook_identity.md:53-54 | wrong/no_reinstate.py | 7 |
| H7 apprentice relief | environment/data/rulebook_charge.md:49 | wrong/no_apprentice_relief.py | 4 |
| S2/I3 forge handle read on the forge's own day | environment/data/rulebook_salvage.md:12 | wrong/salvage_day_window.py | 9 |
| missing input named, non-zero exit (instruction) | instruction.md:7 | wrong/mi_generic.py, wrong/mi_traceback.py | 1 |
