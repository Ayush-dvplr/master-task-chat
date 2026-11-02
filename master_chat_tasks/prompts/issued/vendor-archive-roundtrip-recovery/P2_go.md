# vendor-archive-roundtrip-recovery P2: "go" message (master, 21 Oct 2026 13:08 IST)
Paste everything below the line into the vendor-archive build session.

=== PASTE BELOW ===

go. Before scaffolding, update DESIGN.md with these changes (they come from the two harden diagnoses run today), then continue:

1. Hidden-only is not enough. In district-heat every lever was hidden-only on the visible data, yet a solver right on each documented rule scored 1.0, because each rule had its own one-rule case. In emberforge the ONLY lever that held in a real run was a composition: two rules applying to the same record, with the rule written in a different file from where it is used, and the agent's natural code structure (an if/elif with an early return) missing it.
   - For every lever, add a line to DESIGN.md naming the natural code structure that produces the reflex (for example "one decoder object per file", "unescape the whole buffer, then split", "encoder rebuilt from the decoded dict only"), not just a misreading.
   - Every hidden separating case must combine its lever with at least one other rule whose text lives in a DIFFERENT spec file.
   - Keep each rule stated plainly; never hide one (QC IN-15, DS-21, DS-25).
2. Partial credit (CL-4). Do NOT grade the A composition only as "value AND byte-exact on the whole frame". emberforge lost 8 checks to one gap because hidden outputs were graded all-or-nothing.
   - Grade each composition frame on separate observables (decoded value, extension bytes, varint length, frame offsets, damage record), each check tied to one lever.
   - Each composition check pairs at most 2 levers. At most one all-levers check, weight 3.
3. Self-check limit. For LV-VA-2 and LV-VA-4, write a wrong encoder that is self-consistent (decode(encode(x)) == x for every record it produces) but drops or moves extensions, or canonicalises an unmodified overlong varint. Confirm it loses those levers' points. The agent will self-test this way.
4. LV-VA-5 precedence is a single ordered list in one file, which a careful agent implements directly. Weight it light (3s), and put its heavy cases where precedence meets LV-VA-6: a file with a header defect and also damaged frames, where the contract says which wins and what is still salvaged.
5. Weights (live TS-20: "a core-deliverable test carrying weight 1 ... is wrong"). Do not lower S2 by putting visible value checks at weight 1. Drop visible checks that the hidden cases grade again. Keep weight 1 only for true minor or existence checks.
6. Data volume: the record files must each be read by a graded stage. No padding rows; if A5 forces a size, the extra rows must still change a graded output when edited.
7. Judge: concrete-fact criteria only, each something the instruction asks the agent to state in its final reply (plain words, no mention of a reviewer, grader or judge), so every correct run states it (JD-7, JD-15). Examples: "The response states that the trailer CRC covers header offsets 5 to 14 only"; "The response states that dictionary state continues across the segment files of one stream". No criterion may read a value a test reads (JD-8). No effort criteria. Keep one code-quality criterion (JD-18).
8. P3 baselines later need an extra solver: S4b, right on every rule in isolation AND on each single-lever hidden case, wrong only where two rules meet. Record what it scores; if it is near 1.0 the compositions are too weak. Note it in DESIGN.md for the P3 run.
9. OPEN CONFLICT Q18: keep provenance as the generator writes it, as you said.
