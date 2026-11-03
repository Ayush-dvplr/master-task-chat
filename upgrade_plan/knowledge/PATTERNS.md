DESIGN PATTERNS FOR HARD, FAIR TASKS (W1-025, 3 Nov 2026)

Source: DESIGN cards and the DESIGN share of MIXED cards in upgrade_plan/tmp/S2-CARDS plus W1-008/CARD.md (7e0d8feb). DEFECT findings and family D7 are left out. Points are lost positive test weight as written in each card. Several cards have low confidence on the exact diverging line; those are cited only for test structure.

1. DESIGN FAMILIES

D1. A DOCUMENTED BRANCH ONLY THE HIDDEN DATA FIRES (kind b)
1. What: a rule written plainly in the docs that the shipped data never exercises and every held out input does.
2. Why a careful model loses: it debugs against the shipped run, which is green, so the branch is either coded and never tested or fitted to the one shape it imagined. 8eae0f87: the solver handled one reset on one node; held out extracts carry two or three, backward steps and weakly pinned nodes. 4da82574: the branch was coded, but the rule sentence is wrapped across a line break and the phrase search never fires.
3. Determinacy: 8eae0f87 metering_standard.md:27 states the reset rule and :51 bounds the transfer time, which pins each run of offsets. 4da82574 data_lineage.md:44-45 names the prefix; the instruction warns that this epoch "does not reach every documented branch".
4. Tests: seeded in test generator, many held out inputs that each carry the branch in varied number, direction and position, whole output compare per input.
5. Cost: 8eae0f87 100 of 107; 4da82574 50 of 74. 7e0d8feb fired its branch on one seed only and cost 5 of 85: one seed is not enough.
6. Recipe: document a state change observable only indirectly (through constraints or bounds), ship a sample where it never happens, and put several varied occurrences in most held out inputs.

D2. CARRIER OR ENCODING VARIATION INSIDE A NAMED STANDARD (kind a)
1. What: the contract names a standard or a type rule in one sentence; the sample uses its plainest subset; held out inputs use legal but rarer forms.
2. Why lost: parsers are fitted to the sample and decode the rare form silently wrong with exit 0. 43986de8 joined every text node and kept moved and alternate text; e08c051f rejected floats and booleans but coerced quoted digits.
3. Determinacy: f348165e ct_svc.md:9 "A document is read as a consumer that understands every namespace ECMA-376 defines and no other"; 43986de8 std_codes.md:7; e08c051f schema.md:34 "amount_minor must be a JSON integer and carries its own sign".
4. Tests: every held out input carries at least one variant (43986de8 TRUTH table lists which extract carries which), and the decoded value feeds every per entity report.
5. Cost: f348165e 330 of 352; 43986de8 553 of 644; e08c051f 55 of 79.
6. Recipe: pick a public container or type system, write one sentence that binds the reader to the full standard, ship only the plain subset, and plant several legal variants (some obvious, some that look harmless) across held out inputs.

D3. A DOCUMENTED RULE MISREAD OR OVER APPLIED, FEEDING AN EXACT GATE (kind d)
1. What: one rule among many is read slightly wrong; the error is small in rows but sits upstream of an exact gate.
2. Why lost: models add an intuitive condition, reorder a precedence, or apply a rule wider than written. Subtypes seen: base record ranked inside a tier it only backs up (df8f123b); invented filter on an action label (4a5f9738); older spec versus a newer normative note (b6237098); a settled convention applied to figures it does not move (d4e8c327); a field documented as canonical sent through normalisation again (f5fe93be); an invented fixed width for a running value (4ef4340d).
3. Determinacy: df8f123b provenance_precedence.md:32-34; 4a5f9738 precedence_policy.md:3-4; b6237098 field notes :3-7 "normative and replace the corresponding older-build rules"; d4e8c327 instruction "apply each rule no more widely than it is written".
4. Tests: an exact entity set gate before per field checks (df8f123b), counterfactual negatives that detect each skipped mechanism (4a5f9738), each build line inside every aggregate (b6237098).
5. Cost: df8f123b 67 of 76; 4a5f9738 51 of 67; b6237098 30 of 40; d4e8c327 33 of 36; 7c2e77a1 57 of 64 (rule not located).
6. Recipe: give the rule one deciding sentence, plant a large population of records that tempt the wrong reading (partial rows, low rank amendments, a rule whose result changes nothing), and add an explicit scope sentence so over application is a documented error.

D4. A STATED RUNTIME ON A LARGE HIDDEN INPUT (kind c)
1. What: shipped data small enough that a naive exact method passes; hidden input much larger under a stated limit.
2. Why lost: the careful program is correct and too slow. fd7a2544 used per parcel grid subtraction; the reference works in an invariant frame.
3. Determinacy: fd7a2544 instruction.md:35 states the hidden size and the 60 second limit; f5fe93be states a relative budget, "four times ... plus two seconds".
4. Tests: the large case is attached to many fixtures, so one timeout zeroes all of them.
5. Cost: fd7a2544 64 of 86; f5fe93be only 3 (one timed check).
6. Recipe: choose a computation whose obvious exact method is quadratic or worse and whose fast method needs a structural insight, not tuning; put the large size into most graded runs.

D5. ONE DETAIL BURIED IN A VERY LONG DOCUMENT (kind e)
1. What: overrides placed in unrelated procedural sections, phrased differently from each other.
2. Why lost: the model builds a pattern list from the first finds. 43249294 matched three absolute substitution forms and missed "is increased by 0.6000 percentage points" (tariff_code.md:5745).
3. Cost: 62 of 71, because the missed override touches every account.
4. Recipe: vary the phrasing of each override (absolute, as if, relative), make at least one touch every record, and keep every override in the shipped text.

D6. MANY INTERACTING SEEDED FAULTS (kind e)
1. What: a repair task with dozens of independent defects of different kinds, some invisible on the shipped corpus.
2. Why lost: near complete repair still fails exact checks. cd6a3a55 has 64 seeded defects; 9cc598a9 about 37 rule points with decoy documents.
3. Cost: cd6a3a55 216 of 262; 9cc598a9 25 of 27.
4. Recipe: seed rule breaks, numeric drifts and input convention traps, tie each to one governing section, grade per family on a fresh corpus, and grade downstream layers on the agent's own upstream behind a closeness gate (cd6a3a55 test_output.py:4847).

D8 (NOT IN SUMMARY). CARRIED STATE THAT NEVER HEALS
1. What: a running total, carried lot, capacity fixpoint or position addressed operation, so one early edge record shifts every later figure.
2. Cards: 275f885b (TRUTH: "deferrals never heal"), d4e8c327 (carried lots), a7e17524 (admission gate chain with a capacity fixpoint), 072aced5 design share (rollback positions recomputed after each operation; a gate value that only the full replay produces).
3. Cost: 275f885b 71 of 78 from a handful of claims.
4. Recipe: add a carried quantity to any per entity pipeline and publish no self check count (275f885b instruction: "there is no count to check yourself against").

D9 (NOT IN SUMMARY). ONE CLAUSE HARDENING CONTRACTS
1. What: a standard's edge rule, a minimum length or a read scope stated once and never exercised by the shipped data (6defadfe design share: SemVer build metadata, 9 digit prefix, path confinement).
2. Cost: 30 of 40 lost (design share).
3. Recipe: pay each property once over several generated cases, probe only through a documented interface, and state the failure mode (raise a named error or report).

2. TEST STRUCTURE PATTERNS
1. Seeded generator inside tests/test_output.py with an embedded reference: rebuilds the shipped corpus and mints held out ones (8eae0f87 5 mutations plus 15 fresh draws). Fair when every doc file is identical across seeds and only data changes.
2. Held out corpora along named axes: each corpus pushes one axis the instruction lists to an edge (6285fcad, 9d1784a5). Rescaled copies of the visible case do not bite (7e0d8feb lesson 1).
3. Leave some traps for held out data only. 7e0d8feb planted every trap on the visible day and Opus lost 5 of 85.
4. Full core gate: every leaf check needs every core report exact on shipped and all held out corpora (6285fcad, 9d1784a5, ceadc676, b42c61b9). Opus scored about 8 percent on all four, but all four cards have low confidence and cannot name the failing rule. This is all or nothing and gives no diagnosis. Prefer per corpus groups.
5. Whole document compare per input: fair amplification when the lever is a shared lookup (43986de8, five checks at 5 per extract).
6. Mask globally coupled columns so one slip does not fail every family (daaca581).
7. Exact entity set gate then per field checks (df8f123b, e08c051f): one membership error voids the report; keep it, but give membership its own check too.
8. Closeness gate for downstream layers graded on the agent's own upstream (cd6a3a55).
9. Negatives: hard coding, path and filename dependence, nondeterminism, reading /app/data at run time, plus flipped reference variants for each mechanism (9d1784a5 seven, b42c61b9 nine). Counterfactual negatives tell you which mechanism was skipped.
10. Invariant break inputs with near twins (f348165e). If the twin carries the format lever, the error stop check inherits it (43986de8 lost 6 there).
11. Timing relative to a reference run (f5fe93be) is robust to grader speed.
12. A gate value present in no shipped file defeats copying derived layers (072aced5); conjunction over many channels (f2d019d0) gave 3 percent to a visibly correct solution, so keep partial credit per channel.

3. INSTRUCTION WORDING PATTERNS
1. Bind to the full standard in one contract sentence, without listing features (f348165e, 43986de8).
2. Warn generically that quiet branches exist (4da82574) without naming them.
3. List the axes that change in held out runs (6285fcad "other seeds, clocks, periods, profiles ...") but not the edge values.
4. State the exact bar once (e08c051f "one cent or one unit out of place costs the whole file").
5. State scope symmetry against over application (d4e8c327).
6. State that recency or labels do not decide authority (9125255a "a value is never right just because it is newer, more complete or labelled final"), then give the real precedence in the docs.
7. State runtime as one sentence; a stated size did not save fd7a2544.
8. Avoid: leaving a branch boundary unwritten (7e0d8feb, where only a test docstring settles the walk start) and grading internal function names that no document names (6defadfe).

4. RUBRIC PATTERNS
1. Self tests on mutated inputs, one item per named axis (6285fcad R1 R4 R5 R17; 9d1784a5 R3 R12 to R14).
2. Build adversarial carrier inputs and run them (f348165e R1 to R9; 43986de8 R1 R2).
3. Execute each handbook worked example and compare (b42c61b9 R6 R9 R10).
4. Inspect the exact source rows before coding the rule (ceadc676 R9 to R16).
5. Run after the last edit (9d1784a5 R23).
6. Independent second computation (f348165e; fd7a2544 R2 union area check).
7. Closing what if figures that need a rerun and appear in no artifact (71a3ecf5, 4a5f9738), each isolating one rule (7c2e77a1).
8. A worked instance must be asked for in the instruction; 7e0d8feb lost 62 of 103 rubric points on "show one instance" items the instruction never requested.
9. Note: closing figures inherit test drift (275f885b, d4e8c327), so one lever is charged twice.

5. TASK SIZE OBSERVATIONS
1. Size does not make hardness. Spearman with Opus tests percent over 108 tasks (S2-FEATURES/LAYER_B.txt): env data KB +0.05, instruction words +0.10, formats +0.23.
2. Small DESIGN tasks scored lowest: 8eae0f87 109 KB, 16 files, 526 words, 6.54; f348165e 163 KB, 6.25; 43986de8 63 KB, 14.13. Large ones too: 9cc598a9 81 MB, 7.41.
3. Typical DESIGN task: about 690 instruction words, 55 files, 33 test checks, 76 positive test weight (medians over cited ids in FEATURES.csv).
4. Test files are large because the generator and reference live there (b42c61b9 3.4 MB).

6. BUILDER CHECKLIST BEFORE QC
1. Each lever has one deciding doc line; quote it in DESIGN.md.
2. The shipped data never fires the primary lever; most held out inputs fire it, with varied count and shape.
3. A careful program written from the docs alone loses it (test this).
4. No graded value depends on an unwritten rule or a situation called unsettled.
5. Every format variant is legal under the standard the contract names.
6. Scope and precedence sentences exist for every rule that tempts over application.
7. Amplification is per corpus or per family, not one gate over everything.
8. Negatives include flipped reference variants per mechanism.
9. Each rubric process item is asked for in the instruction.
10. Runtime sentence present; reference well under the limit.
