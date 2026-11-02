# KEPT: district-heat-flex-procurement (P12 fix ql1, session 8556721)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| QL1-F9 (TS-23 warn, 66 checks) | tests/test_output.py registrations (`_graded(...)` list at the end of the file, 66 entries) | KEEP warn with the count: every check grades its own property on its own extract; merging would remove separating cases (option A, 27 Oct). Unchanged bytes since PREV_QC_COPY 3f737e9; carried from KEPT.md of p12_fix_v6_9a85fdc. | 03_Tests_QC.md:62 TS-23 ("at most 35 (warn)"); QC_RULINGS.md:137 option A |
| QL1-F11 (SUGGEST: Popen without `env=`) | tests/test_output.py `run_agent` (Popen call, before-fix TO:1643-1645) | No kit rule is broken: all four TS-28 defences are present (fresh copy, timeout, kill on timeout, output read from files). Suggestion only; no edit by master ruling. | 03_Tests_QC.md:73 TS-28 |
