# JUDGE_MAP (fix-v1 451146f, QC v1 findings; harden r2 bddb388 copy in fix1/JUDGE_MAP.before.md)

16 criteria (12 positive weighing 36, 4 negative weighing -14). Probe band R4-R12 is
9 probes x 3 = 27 of 36 positive points (75%; was 27/39 = 69%). Oracle witnesses come
from the SELFCHECK block of `solution/solve.sh`, each printing `check <id> ok` and a
witness line. Old to new ids: R1 R1, R2 R2 (missing/malformed clause dropped, IN-8/JD-5),
R3 deleted (JD-8, AL-2 variant a), R4 R3, R5-R9 R4-R8, R10 replaced by the crosswalk
probe R9 (JD-15), R11-R13 R10-R12, R14-R17 R13-R16, R18 deleted (IN-15/JD-16).

| id | judge.toml | requirement (file:line) | oracle shows at | test not overlapped |
|---|---|---|---|---|
| R1 | :11-22 | instruction.md:7 (extract project.zip, repair it there) | solve.py extract() then repair() over REPAIRS DFC-01..27 | tests grade documents, not how the engine was produced |
| R2 | :24-35 | J4 (first half only); instruction.md:9 (deliver patched_engine.zip) | solve.sh:119-128 check_error_handling (`check R2 ok`, every handler raises), DFC-27 reading._declared | no test inspects exception handlers |
| R3 | :37-48 | instruction.md:3 (start at 00_open_this_first.txt, then replan_programme_contract.md) | oracle reads both first in solve.sh header comment order | process order only |
| R4 | :50-61 | instruction.md:5 (pool weights); spec_stage_p10_objective.md:18-29 | solve.sh:202-217 check_tie_and_count (`check R4 ok`) | tests compare the kept set, never print the losing tie |
| R5 | :63-74 | spec_stage_p01_identifier_and_revision.md:3-13 (register in force, drafting copy); act a3 never did: printed after publication beside /app/out/19_rejected_register.csv | solve.sh:225-236 check_drafting_copy (`check R5 ok`) | negative_drafting_register_read grades output, not the printed comparison |
| R6 | :76-87 | instruction.md:15 (ledger records cells owed); work_ledger_counter_contract.md | solve.sh:239-248 check_counters (`check R6 ok`) | tests grade doc 16 bytes, not the comparison with the withdrawn ledger |
| R7 | :89-100 | instruction.md:17 (graded on rounds not seen) | solve.sh:251-271 check_altered_copy (`check R7 ok`) | hidden rounds are graded, the agent's own altered rerun is not |
| R8 | :102-113 | instruction.md:19 (quiet branches); spec_stage_p13_amendments.md:13-15 | solve.sh:274-300 check_reversal_kind (`check R8 ok`) | tests never see the agent's added journal row |
| R9 | :115-126 | spec_stage_p01_identifier_and_revision.md:19-21 (every job identifier through identifier_crosswalk.tsv, both ends of a precedence row, inactive rows map nothing); worked_examples.md:73-82; a3 never ran an altered copy (h2_a3/a3_steps.txt) | solve.sh:131-159 check_crosswalk_copy (`check R9 ok`: EDG-4100 requiring JOB-1001 written as OLD-1001, differ none) | the held-out crosswalk checks grade the engine's documents on verifier rounds; no test grades the agent printing its own legacy-id rerun |
| R10 | :128-139 | spec_stage_p11_search.md (every subset, ascending mask) | solve.sh:202-219 check_tie_and_count (`check R10 ok`) | tests compare subsets_examined, not an outside count |
| R11 | :141-152 | instruction.md:17 (implement the papers in general) | solve.sh:304-315 check_reordered_rows (`check R11 ok`) | negative_filename_dependent_behaviour renames files, never reorders rows |
| R12 | :154-165 | spec_stage_p13_amendments.md:3-8 (only lodged rows are amendments) | solve.sh:319-329 check_empty_journal (`check R12 ok`) | no test empties the journal |
| R13 | :167-178 | J3a | oracle final message cites only checks solve.sh ran after the last repair | none |
| R14 | :180-191 | J3b | oracle quotes figures read from /app/out | none |
| R15 | :193-204 | J3c | oracle states its nine self-check functions over one round | none |
| R16 | :206-217 | readings_not_in_force.md (withdrawn publications) | oracle reports its own /app/out figures | none |

Removed: old R3 (instruction.md:21 promise; doc 13 already paid by shipped_amendment_classification_exact / shipped_invalidation_sets_exact, JD-8; the instruction sentence was deleted, AL-2 variant a). Old R10 (missing declared input; no doc states an error-message expectation, JD-15). Old R18 (edited working papers; instruction.md:9 binds the engine's run and `_drive` digests the paper directory either side of every run, test_output.py:5186-5187, so a judge copy double-paid; IN-15/JD-16).

## 481e976 fix-ql1 (oracle-1 agent/oracle.txt, fix3 lanes)
| criterion | where the oracle shows it |
|---|---|
| R3 | solve.sh:10-14 prints `== /app/data/00_open_this_first.txt` (oracle.txt line 1) then `== /app/data/replan_programme_contract.md` (line 14), before solve.py extracts project.zip |
| R4 | solve.sh:226 `PCT-FNW charge 419816 mills: set {JOB-1502, JOB-1503, JOB-1504} weighted 732.316666666667; set {JOB-1500, JOB-1501, JOB-1503, JOB-1504} weighted 932.066666666667; the pool weights keep {JOB-1502, JOB-1503, JOB-1504}` |
| R6 | solve.sh:256-273 prints 21 stage rows `stage/seq: mine | withdrawn` with DIFFERS marks, then `15 stages differ: amendment/1; ...; build/0` (every differing stage) |
| R10 | solve.sh:233 `PCT-FNW 4 subsets of its 9 selectable jobs pass the group and capacity tests at the winning charge 419816 mills (127 pass at any charge)` |
| R15, R16 | negatives; wording only (stand-down where R13 / R14 fire); oracle trajectory makes neither claim |
