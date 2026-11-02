# cohort-retention-reconciliation (0b8ac36): P12 r1 note

I rechecked all 9 QC findings against the live kit (3fb1650b, the same kit the report used). Every one is real, so all 9 are fixed.

- False positives: none.
- Kept minors: none. All three minors were cheap to fix, so I fixed them: the task.toml description, the R7 preference, and the stale mutation numbers in TRUTH.md.
- Open questions: none.

Fix summary:
- The oracle is now its own implementation. It tags every raw row with its full set of reasons, then filters in policy order, and uses its own builder for each report. Its output on the shipped data is unchanged, and it shares 2% of its lines with the verifier (16% before).
- The serialization and rerun checks now need the full document set and the reference cohorts. A run that writes nothing, or writes the same files every time, no longer earns them.
- R4 now says 14 reason entries, which matches the oracle. R7 is now a code-quality criterion.
- TRUTH.md is corrected: the R4 count, the build narration is removed, and the unmeasured mutation numbers are removed.

Gates: xref 0 findings; the 4 QC scripts PASS; oracle 1.0 x3, owner-only 1.0, nop 0.0 (tests only).
