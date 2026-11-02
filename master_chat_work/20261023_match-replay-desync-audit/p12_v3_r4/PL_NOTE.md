# PL_NOTE: match-replay-desync-audit, P12 v3 round 4 (board c958296)

## False positives
None. All six QC v4 findings were checked against the shipped code and rated REAL.

## Kept items
- W2 TS-23 / A3 (warn, v4.md:178): the tests register 46 checks and the warn threshold is 35 (03_Tests_QC.md:62, tests_qc.py:48 A3). KEPT on Ayush's instruction of 24 Oct 12:50: there is no cap on tests, and a check is never merged or dropped to meet a count. tests_qc.py exits 0 with `WARN [A3] 46 checks; cap is 35 (warn)`. WORK/QC_DEFENCE.md W-03 count updated from 42 to 46.

## UNSURE
None.

## For the PL
- F1 TRUTH sentence departs from the master wording because two tests compare scenario_visible in a different way (RECHECK_FIX.md, Deviations).
- QC v5 is the last round: P11 QC v5 needs Ayush's override.
