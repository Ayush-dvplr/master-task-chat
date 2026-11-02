# KEPT items for schema-migration-plan-repair (carry-over for P11 v3 recheck, P12 c9ea299, 28 Oct)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| TS-23 / A3 | tests/test_output.py (81 registered checks after harden f0331ad; 71 at QC v8) | Above the 35 cap is a warn, not a fail; checks read different worlds/observables, no true duplicates; merging distinct properties creates TS-13. Option A (Ayush 27 Oct). | tests_qc A3 "cap is 35 (warn)"; QC v8 recorded it as the only warn |
| Step 10 oracle x3 (v9.md:53) | QC report v9.md:53 (no bundle file) | Round decision, not a bundle defect: oracle is run x3 per Ayush; QC v9 itself says "(Round decision, not a bundle defect.)". P12 c9ea299 oracle x3 = 1.000. | v9.md:53; Ayush oracle x3 direction |
