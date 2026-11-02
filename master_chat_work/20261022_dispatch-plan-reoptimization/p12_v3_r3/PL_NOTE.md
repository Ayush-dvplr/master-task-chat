# 2c2361c PL note: dispatch-plan-reoptimization, QC v7 (31e7ead)

## False positives

None. All four v7 findings were rechecked as real.

## Kept items

- W1 X1 (warn), KEPT for tasker approval. structure_qc.py:71 "X1  no em/en dash in any text file; binary-skipped files warn." The five skipped files are deliberate binary inputs the solver must parse: environment/data/amendment_memo.docx (Word 2007+), capital_program.xlsx (Excel 2007+), ledger_authority.sqlite (SQLite 3), penalty_schedule.pdf (PDF 1.4, 5 pages) and xref_manifest.db (SQLite 3), checked with `file`. They cannot be text scanned, QC checked them by hand in Gate 02 (v7.md:43-44), and replacing them would remove part of the parsing work. Live structure_qc.py after the fixes: exit 0, SUMMARY 17 pass, 1 warn (X1), 0 fail. Unchanged from round 2.

## Decisions needing PL awareness

- Temp writes stay a violation. instruction.md:3 says "The program must read only from the input directory and write only inside the output directory." and the handbook grants no scratch area, so `negative_writes_outside_output_dir` (-3) still fires once when a solver writes to the temp directory. Only the second penalty for reading the same file back was removed. Note that `tempfile.gettempdir()` alone probes a write in TMPDIR, so calling it counts as the write.
- The instruction now says "It runs as a single process: no subprocess, fork or multiprocessing pool." This states what the network/process negative already graded; no checker change.

## UNSURE questions

None.
