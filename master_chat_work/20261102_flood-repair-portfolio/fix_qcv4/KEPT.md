# KEPT: flood-repair-portfolio, fix-qcv4 420bf9a

| Finding | Evidence and current behavior | Authority and reason retained |
|---|---|---|
| TS-26 | QC v4.md:43; tests/test_output.py:1581 and :1590 still compare optimal selected lists and whole summary documents respectively. The three hidden optimal/summary pairs retain weights 5+5. Baseline AST and registration comparison proves these checks unchanged. | Ayush 2 Nov 23:4x: "2. Fix only items 1, 2 and 5" excludes this finding. QC v3.md:187 passed TS-26. No checks, weights or normalization changed for it. |
| AL-27 | QC v4.md:46; fixtures still lack simultaneous segment unknown-plus-invalid and exclusion unknown-plus-equal records; tests/test_output.py:1603 still exercises permits/exclusions as the missing-file pair. Fixtures, generator and this helper remain byte/AST-identical to the baseline. | Same Ayush ruling excludes this finding. QC v3.md:245 passed AL-27. No precedence or missing-file coverage changes were authorized. |
| TS-11 (carry-over) | tests/test_output.py:37 sets BOOK_SECONDS=20; :1462 uses that bound. environment/data/contract.md:15 states the 20-second wall-time limit. | Prior p12_fix_v1_7cc7c61/KEPT.md:5; Ayush 31 Oct 11:45: "flood-only time-out exception (losses by time-out may be the whole lever, like outage)". Live Input_Bundle_QC/03_Tests_QC.md:41 is the elapsed-time-bound rule. |
| Oracle x3 acknowledgement (carry-over) | This request explicitly requires three tests-only oracle lanes, rather than five. | Prior KEPT.md:6 records Ayush acknowledgement of three instead of five; Input_Bundle_QC/Final_checklist.md:390 otherwise requests five. Current prompt:40 independently authorizes x3. |

The two QC v4 findings above are scope-based KEPT decisions, not claims that their reported defects were repaired. No REBUT rows are asserted.

## Lessons for the master
Scope overrides should travel with the recheck request. | no change: explicit current authorization already records both KEPT findings.
