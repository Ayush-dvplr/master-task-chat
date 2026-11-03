TASK: 8defd7be-eb46-5779-a556-aec18521635e, Reverse Engineering (probe accounting engine), Opus tests 2.41, rubric 15.71, final 9.06.

1. VERDICT
DESIGN, 100 percent of lost test weight, confidence medium (identifiability of every constant from the shipped rollups is the author's claim in TRUTH.md item 3; not re-verified within budget).

2. LOSSES
1. 25 single-stage probe checks, weight 1 each (gain, count rule, 6 plan, 3 layout, 2 phase, 2 mode, negative rounding, debt, tie breaks, credit, trailing record, baseline drift, doubled relief, lock, shared index): WRONG output (probes.jsonl not byte-exact).
2. 11 full-ledger unseen runs, weight 5 each (55): WRONG output.
Passed only the two shape checks (2 of 82). Opus program used gain 1270 (truth 1440), debt reach//10 (truth reach//40), held at 150 (truth above 39): almost every fitted constant is off, so every exact-match check fails.

3. DIFFICULTY KIND
(e) other: joint recovery of about fifty undocumented constants and non-affine forms (quantise, saturate, ceiling, floor on negatives) from two aggregated, confounded, debt-blind rollups; a near affine fit reproduces most rows but fails exact match. Minor (d): rounds column stored one low.

4. EVIDENCE
1. environment/data/broker.md:147-162 lists every missing constant and says the run and two rollups are the only evidence.
2. broker.md:85-92 documents the count structure (Opus got this part right) and truncation toward zero in stage 2.
3. Opus artifacts/app/out/broker.py:19 GAIN = 1270, :70 DEBT_DIVISOR = 10, :78 HELD_DEBT = 150, versus TRUTH.md item 1.

5. TEST DESIGN
Seeded in-test generator (SHAPE, FORM, REPEAT seeds plus 11 corpus seeds) re-implements the engine (resolve, derive) and builds targeted probe inputs, one per constant, plus 11 unseen full corpora. Comparison is whole-file string equality of all three reports. Amplification: one wrong constant zeroes every ledger check. Negatives: hard-coded shipped partition ids (-5), third-party import (-3), nondeterminism (-3).

6. INSTRUCTION
Quoted: "A run whose three files are not all byte-exact counts as wrong for that run." "it will be driven over runs you have never seen, and the per-lookup ledger it writes on those runs is read as closely as the two rollups are." "Use only the Python standard library." "You have 5400 seconds". Honesty: report twenty whole-number figures. Not said: that probes isolate single stages, how many unseen runs, that the shipped data pins every constant.

7. RUBRIC
Lost process items (weight 3 each): held-back block replay, rival readings on a built input, pair narrowing of a keyed adjustment, independent recompute of a figure, byte-for-byte comparison (Opus compared parsed JSON, not cmp or diff). Lost all twenty figure values (weights 5, 3, 1) because the constants were wrong. Kept: program placed early, determinism rerun, code quality, program run.

8. REUSABLE IDEA
Hide a pipeline of undocumented constants behind aggregate-only outputs, document the stage order and shape fully, include a few non-affine forms that a near linear fit misses, and grade with isolated single-stage probes plus whole-output exact match on generated corpora. Process rubric items name concrete validation acts (hold-out, discriminating input, byte compare).
