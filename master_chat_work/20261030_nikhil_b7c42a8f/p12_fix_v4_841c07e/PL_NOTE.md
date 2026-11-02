# PL note b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 (P12 fix v4, 841c07e)

False positives: none. All four QC v4 findings were real and are fixed.

Kept minors: none new. The six acknowledged carry-overs (KEPT 1-6) stay as they were (see KEPT.md).

UNSURE questions: none.

For reference, what changed:
- The test that checked for extra files in /app/out could never fire, because in separate mode the verifier only receives the ten declared files. We deleted it. The rule "add nothing to the output directory beyond the nine documents and the program" (instruction.md:7) is now graded by a judge negative, R35 (weight -1).
- R25 graded two things at once. It now grades only the recap's settlement strings. The log names moved to a new criterion, R34 (weight 1). The judge weight is now 0.5/66.
- The settlement values in methodology_audit.json are now checked exactly by a test (methodology_audit_remaining_sections_exact) instead of by the judge.
Oracle 1.0 x3, owner-only 1.0, nop 0.0. Every trap keeps 100% of its loss.
