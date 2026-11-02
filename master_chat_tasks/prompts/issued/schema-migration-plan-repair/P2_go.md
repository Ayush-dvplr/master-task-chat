# schema-migration-plan-repair P2: "go" message (master, 21 Oct 2026 13:22 IST)
Paste everything below the line into the schema-migration build session.

=== PASTE BELOW ===

go. Before scaffolding, update DESIGN.md with these changes (they come from the two harden diagnoses run today and from your own risk list), then continue:

1. `environment/data/repo.zip`: accepted (VB §1.12 wins over the idea's name).
2. Fault list (your risk b): do NOT ship the 13-line F1..F13 list in the instruction or the contract. In district-heat, rules that were each stated plainly and graded alone leaked completely (careful solver 1.0).
   - The contract states the CORRECT behaviour of every module and stage (every graded rule stays written: QC IN-15, DS-21, DS-25).
   - It does not say which parts of the shipped code break it, or where. Finding the divergence is the repair work (lever C). A defect list is a recipe (IN-14).
   - Keep F1..F13 in TRUTH.md and DESIGN.md only.
3. Partial credit (CL-4). "LV-MR-1 is needed by checks worth 79" means one wrong lever costs about half the score. emberforge lost 8 checks to one gap this way.
   - Give the executor, replay, classify and report checks a supplied correct plan or supplied correct intermediate (through the documented entry points), so they do not need LV-MR-1.
   - No single lever may be needed by more than 25% of the positive total.
   - Each composition check pairs at most 2 levers. Replace "primary lever plus at least two others" with "primary lever plus one other, and the other rule's text lives in a different file". The most effective mechanism seen today was emberforge's L7: a hidden-only composition with the rule in a different file from its use.
   - Report the S3.k loss for every lever in P3.
4. Weights. LV-MR-4 and LV-MR-5 were meant to be light (well-known idioms, likely to leak), but they now hold 32 of 156 (20%). Together with the 15 visible points, a careful agent would already sit near 0.30.
   - Cap LV-MR-4 plus LV-MR-5 at about 10% of the positive total, unless a case is a cross-file composition.
   - Move the weight to LV-MR-1 x D, LV-MR-6 (shared FieldView) x LV-MR-7, and C compositions.
   - Do not lower S2 with weight-1 value checks (live TS-20: "a core-deliverable test carrying weight 1 ... is wrong").
5. D time limit. Set it from the oracle, not a fixed 10 s: run the oracle plan call 3 times on the largest case (2 CPUs) and set N = max(10, 10 x the slowest run), rounded up to whole seconds. Show by arithmetic that enumeration needs at least 100 x N. No check may depend on a time close to N (TS-11). LV-MR-2 at weight 8 is fine: a (cost, path) heap solves it, as you said.
6. Judge:
   - R1 to R5 (visible-run counts): DROP. summary.json holds the same counts and the tests read it, so the same fact is paid twice (JD-8, TS-26).
   - R6 to R10 (root causes): keep, but only if the instruction asks the agent, in plain words, to state in its final reply the module and function where the shipped code diverged from each contract behaviour it fixed. Otherwise a correct rewrite would not state them (JD-7, JD-15). No mention of a reviewer, grader or judge.
   - R11 and R12 (conduct: runs from a foreign folder, times the planner): DROP. They reward effort.
   - Add concrete stated-fact criteria that no test reads, so a run that misread a rule fails them. For example: "The response states that a migration edge's prerequisites are checked on the record as it is after the previous step, not as received"; "The response states that a plan is chosen per record state, so two records with the same source and target schema can take different paths".
   - Keep R13 (code quality, JD-18) and the negatives (negatives total at or below positives total).
7. P3 baselines later need an extra solver: S4b, right on every rule in isolation and on each single-lever hidden case, wrong only where two rules meet. If S4b is near 1.0 the compositions are too weak. Note it in DESIGN.md.
8. OPEN CONFLICT Q18: keep provenance as the generator writes it.
