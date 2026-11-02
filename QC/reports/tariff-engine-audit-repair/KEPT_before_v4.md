# KEPT: tariff-engine-audit-repair, after QC v1 (fix board 8e1b2d5)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| F08 DS-21 (ledger scale not hinted) | environment/ci/api_contract.md:25-28 ("within 10 seconds; output that comes later counts as no output"); task.toml memory 4096 MB | Every graded figure follows from api_contract.md and the shipped data, and an exact solver exists (QC's own DS-21 line says "nothing is unreachable"). The run-time limit is stated and the container memory is declared; the shipped inputs run fast. Stating balance or voucher-list sizes would name the method. | Input_Bundle_QC/02_Data_Solution_QC.md:70 "If yes, this check passes, however brutal the task is. Difficulty is the point"; :107 "(hard is fine; only genuinely unreachable information fails)" |
| F09 TS-23 / A3 (check count over 35) | tests/test_output.py (116 checks after the F10 splits; 112 at QC) | No true duplicate was named; merging would put two properties in one check (TS-13). The count is a warn, not a fail. | Input_Bundle_QC/03_Tests_QC.md:62 "at least 10 checks (fail), at most 35 (warn)" |

## Lessons for the master
none
