# JUDGE_MAP (harden r2, bddb388)

Positive judge weight 39; probe band R5-R13 is 27 (69%). Oracle witnesses come from
the SELFCHECK block of `solution/solve.sh`, each printing `check <id> ok` and a witness line.

| id | requirement (file:line) | oracle shows at | test not overlapped |
|---|---|---|---|
| R1 | instruction.md:7 (extract project.zip, repair the shipped engine) | solve.py extract() then repair() over REPAIRS DFC-01..27 | tests grade documents, not how the engine was produced |
| R2 | J4; instruction.md:9 (deliver patched_engine.zip) | SELFCHECK check_error_handling (`check R2 ok`), DFC-27 reading._declared | no test runs the engine on a missing or malformed input |
| R3 | instruction.md:21 (amendments reaching no cell) | oracle transcript line from 13_amendment_classification.csv (inert rows) | tests grade doc 13, not the final message |
| R4 | instruction.md:3 (start at 00_open_this_first.txt, then replan_programme_contract.md) | oracle reads both first in solve.sh header comment order | process order only |
| R5 | instruction.md:5, :13 (pool weights settle equal charges); spec_stage_p10_objective.md:18-29 | check_tie_and_count (`check R5 ok`) | tests compare the kept set, never print the losing tie |
| R6 | instruction.md:21 (register in force, jobs set aside by reason code); spec_stage_p01_identifier_and_revision.md:3-13; act a3 never did: printed after publication beside /app/out/19_rejected_register.csv | check_drafting_copy (`check R6 ok`) | negative_drafting_register_read grades output, not the printed comparison |
| R7 | instruction.md:15 (ledger records cells owed); work_ledger_counter_contract.md | check_counters (`check R7 ok`) | tests grade doc 16 bytes, not the comparison with the withdrawn ledger |
| R8 | instruction.md:17 (graded on rounds not seen) | check_altered_copy (`check R8 ok`) | hidden rounds are graded, the agent's own altered rerun is not |
| R9 | instruction.md:19 (quiet branches); spec_stage_p13_amendments.md:13-15 | check_reversal_kind (`check R9 ok`) | tests never see the agent's added journal row |
| R10 | J4 input clause; instruction.md:9 | check_error_handling (`check R10 ok`) | no test removes an input |
| R11 | spec_stage_p11_search.md (every subset, ascending mask) | check_tie_and_count (`check R11 ok`) | tests compare subsets_examined, not an outside count |
| R12 | instruction.md:17 (implement the papers in general) | check_reordered_rows (`check R12 ok`) | negative_filename_dependent_behaviour renames files, never reorders rows |
| R13 | spec_stage_p13_amendments.md:3-8 (only lodged rows are amendments) | check_empty_journal (`check R13 ok`) | no test empties the journal |
| R14 | J3a | oracle final message cites only checks solve.sh ran after the last repair | none |
| R15 | J3b | oracle quotes figures read from /app/out | none |
| R16 | J3c | oracle states the eight self-checks and one round | none |
| R17 | readings_not_in_force.md (withdrawn publications) | oracle reports its own /app/out figures | none |
| R18 | instruction.md:7 (suite passes as shipped; papers read only) | solve.py copies before editing; the self-check edits copies under /tmp | tests check the paper directory unchanged on hidden rounds only |
