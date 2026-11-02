# 6cd567a PL note: dispatch-plan-reoptimization, QC v6 (c2cde12)

## False positives / kept items

- W1 X1 (warn), KEPT. structure_qc.py:71 "X1  no em/en dash in any text file; binary-skipped files warn." The five skipped files are deliberate binary input formats the solver must parse: a docx, an xlsx, a sqlite file, a pdf and `xref_manifest.db`. They cannot be text scanned, and replacing them would remove part of the parsing work. Live structure_qc.py after the fixes: exit 0, SUMMARY 17 pass, 1 warn (X1), 0 fail.
- F4 AL-27 part (c) (negative half) is NOT kept: it can arise from data the contract allows. Handbook section 7 places no sign bound on `index_bps`, and :70-71 says "Rounding is half up, away from zero". Hidden energy rows with a negative total (H2 P03 -40, H3 P22 -40, H4 P01 -45 bps) now land uplifts on exact negative halves, and M16 drops from 101 to 79.

## Deviations needing PL awareness

- DS-20 was fixed in solve.py, not the handbook, because the playbook DS-20 NEVER column forbids "Changing the contract to match the oracle". Shipped and H1-H4 outputs are byte-identical, so this has no effect on scores.
- The judge now has 11 criteria. R11 (sweep order, settled by tests) is deleted, and the old R12 is renumbered R11 because the live judge_qc J2 check requires sequential ids. R8 is narrowed to "by any means other than running its solver.py" so that one solver write into /app/data, now caught by the widened tests negative, is not penalised twice.

## UNSURE questions

None.
