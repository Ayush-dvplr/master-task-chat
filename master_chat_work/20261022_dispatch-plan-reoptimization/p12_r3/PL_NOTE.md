# PL note, dispatch-plan-reoptimization P12 r3

- X1: Keep the scanner warning. It skipped five binary sources, but QC extracted their readable contents and found no prohibited dash. The source files are needed by the task.
- EXEC-5: Keep the process warning for now. Ayush authorized three oracle runs per fix round; the live kit's five-run requirement remains for final sign-off.
- Post-fix A3: The read-scope observer makes 36 tests. The kit warns above 35; its hard cap is 70. Keep the distinct read-scope check.

No fail was classified as a false positive. No unanswered PL question.

## Lessons for the master

Require generator and bundle tests to compare byte for byte before a P12 rebuild; r2 lost r1's credential and JSON-type fixes through generator drift.
