# vendor-archive-roundtrip-recovery (671afdb): P12 r1 note

All 8 QC v2 findings were rechecked against the live kit (3fb1650b) and all were real. All 8 are fixed. No false positives, no kept minors, no open questions.

- Judge R5/R6 (IN-8, JD-15, AL-1, AL-4, JD-5, JD-7, JD-18): the two structure criteria are gone. In their place: one code-quality criterion (QC's wording, weight 3). The reference solution meets it.
- AL-2: the "one line saying how you got it" promise is now graded by a new weight 1 criterion. We kept the instruction as it was, because deleting the clause would leave 7 criteria, below the minimum of 8.
- AL-27: a new hidden fixture sets both reserved bytes and must be rejected at offset 14. A decoder that checks 15 first now loses those 3 points.
- DS-27: TRUTH.md no longer describes tooling or seeds. It now says only "The reference solution scores 1.0 on the test channel and an agent that does nothing scores 0.0."
- TS-15 (warn): each of the five negatives now has an inline inversion comment.

Results: all four QC scripts show 0 fail. Oracle x3 = 1.0, owner-only = 1.0, nop = 0.0.
