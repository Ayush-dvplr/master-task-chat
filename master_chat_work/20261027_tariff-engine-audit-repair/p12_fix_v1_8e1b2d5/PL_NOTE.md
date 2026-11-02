# PL note: tariff-engine-audit-repair, QC v1 fix (8e1b2d5)

All 11 findings were real. Nine were fixed; two warnings are kept.

## False positives
None.

## Kept warnings
1. DS-21, ledger sizes are not hinted. The contract states the 10 second limit (api_contract.md:25-28) and the task declares 4096 MB of memory; the shipped inputs run fast, and QC itself wrote that an exact solver exists, so nothing is unreachable. The kit passes DS-21 whenever an expert can reach the answer from the files ("hard is fine; only genuinely unreachable information fails", 02_Data_Solution_QC.md:107). Writing the sizes into the contract would tell the solver which method to use.
2. TS-23, 116 checks against a 35 check guideline. It is a warn by the kit (03_Tests_QC.md:62). No two checks grade the same property, and three of the new checks come from splitting combined checks as QC asked (TS-13).

## Open questions
None.

## Lessons for the master
none
