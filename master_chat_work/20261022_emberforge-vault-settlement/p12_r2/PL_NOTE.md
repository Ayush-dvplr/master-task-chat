# emberforge-vault-settlement: note for the PL (P12 r2)

Fixed (both v3 fails were real):
- Key order: record_shapes.md promises keys in a set order and nothing graded it. The weight 1 written-form check now also checks key order. A key-order slip costs one point, not the whole score.
- A2 and A4 edges: no graded season put a workshop exactly on its cap, or opened one on the first day or closed one on the last day. The cap season and the quiet-rules season now do. Getting either edge wrong now loses 3 points; the oracle still loses nothing.

False positive (not changed):
- JD-16 warn on R9 (writes under /app/data). The task runs in separate mode and /app/data is not a declared artifact, so the verifier never sees it. The kit says the judge owns scope over undeclared paths (04_Judge_QC.md:97), so R9 stays in the judge.

Kept minors: none. Questions: none.
