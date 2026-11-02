# PL note: metered-usage-rating-pipeline, fix v3 (d21576c)

False positives: none. The one finding (G05-1, list order of missing files) was real. A program that checks the files in a slightly different order (QC's example) still got full marks, because no test removed two neighbouring files of the list at once.

Fix: one new hidden check. For each of the ten neighbouring pairs in the contract's list of 11 input files, it removes both files and wants the program to fail and name only the earlier file. Weight 3; test points now 422. The three older multi-missing checks are unchanged. Checkers that walk the list backwards, by name, or in QC's order all fail the new check; the reference program passes.

Carried items kept: the 113-check count warning (no cap, Ayush decision), and the Latin-1 encoding rebuttal for collector_south.txt. Earlier decisions on the handler criterion and malformed-input forms are unchanged; see KEPT.md.

Unsure: none.

Checked in Docker once: oracle 1.0 three times, owner-only 1.0, nop 0.0. The bundle is copied to Tasks_INPUT and matches it exactly (tree 76d42cbcdfac).

## Lessons for the master

- Ask for every adjacent pair the first time an ordered-list rule is flagged | no change: lesson recorded in RECHECK_FIX.md against the playbook AL-27 row
