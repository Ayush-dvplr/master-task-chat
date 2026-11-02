# KEPT items, sentinel-policy-recompute, after P12 fix of QC v8 (3157183)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| K-1 TS-23 / A3 | tests/test_output.py:2036-2076 (41 registrations, 37 positive, 4 negative) | 41 checks is above the 35 cap, which the kit grades as a warn. There are no true duplicates (TS-26 review in STACKING_CHECK.md). The count rose from 40 to 41 because the QC v8 CL-1 fix restored the init/set byte-rebuild assertion as its own w1 check; folding it back into `shipped_config_carries_policy_values` would recreate the v7 TS-13 finding. Option A (Ayush 27 Oct): keep the warn with the count. | tests_qc.py A3 "cap is 35 (warn)"; 03_Tests_QC.md TS-23 severity "warn: ... cap above 35"; 04_Judge_QC.md:146 "warn: ... cap above 35" |
| K-2 X1 binary skip | environment/data (4 .parquet, 3 .xlsx, tool.zip) | These 8 files are binary containers the scripts cannot read as text. The warn has been there since QC v4, and environment/ did not change this round. | structure_qc.py X1 (warn) |
