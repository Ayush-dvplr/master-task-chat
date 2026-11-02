# PL note: flood-repair-portfolio (QC v1 fix round)

All six v1 findings were real. Five are fixed (DS-22, JD-7, AL-27, JD-5, TS-15). Oracle 1.0 x3, owner 1.0, nop 0.0 after the fixes.

False positives: none.

Kept:
- TS-11 (warn, time limit on fresh books). The 20 second bound is stated to the agent in contract.md:15 ("within 20 seconds of wall time") and the tests use the same figure (tests/test_output.py:37 `BOOK_SECONDS = 20`). Kept under Ayush's exception of 31 Oct 11:45 for this task: losses by time-out may be the whole lever, as in the outage task.
- Oracle run count: three oracle runs instead of the kit's five (Final_checklist.md:390). Acknowledged by Ayush; all three read 1.000 in QC v1 and again in this fix gate.

Unsure questions: none.
