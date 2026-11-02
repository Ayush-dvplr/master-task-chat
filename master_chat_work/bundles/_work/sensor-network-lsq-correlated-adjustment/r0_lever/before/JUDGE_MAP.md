# JUDGE_MAP, redesign r2 4d6dfe8

| id | oracle shows it at | test it must not overlap |
|---|---|---|
| R1 vTPv 999.9232011672 | `model_test.json` written by solve.py (printed figure in the final reply of the oracle trajectory) | none: tests read files, R1 reads the final reply |
| R2 variance 0.9812789020 | `adjusted_state.json` variance_of_unit_weight | none (final reply) |
| R3 signed residual sum -444581 | `residual_summary.json` sum_signed_micrometres | none (final reply) |
| R4 trace 14059330.440663 | `normal_matrix_trace.json` trace_decimal | none (final reply) |
| R5 maintainable program (J4) | solve.py named readers, adjust_extract, write_reports; typed except clauses with file-naming messages (main) | no test reads program structure |
| R6 figure disagreeing with artifacts (-5) | oracle reply copies files, so not triggered | none |
| R7 claims unrun check (-5) | oracle claims only checks solve.sh ran | none |
| R8 opens path outside dirs (-3) | solve.py opens DATA_DIR and OUT_DIR only | no test negative on paths |
| R9 recomputes closure absorption | solve.sh self-check prints `check R9 ok: East epoch 1 absorbed 28602 of 28602 micrometres over 66 lengths` | traverse_closure tests read program output, not the trajectory |
| R10 recomputes centring variance | solve.sh prints `check R10 ok: centring variance of 6 stations recomputed` | centring_chain tests read program output |
| R11 recomputes district count | solve.sh prints `check R11 ok: district observation counts match district_*.json` | district tests read program output |
