W1-008 STUDY CARD: anubis-stage-2/7e0d8feb (playout conform, 14 stages)

1. SUMMARY
1. Recompute one broadcast day of a four-market playout channel from about 60 files.
2. Write 25 byte-exact artifacts in /app/out using exact rational arithmetic and carry scopes.
3. Hand back a stdlib program, conform.py, that rebuilds any other day of the same channel.

2. SCORE
1. Tests: 21 positive checks (85 weight), 8 negative checks (-3 or -5). Opus scored 80/85 = 94.12. The only loss was program_lead_drop_exact (5). No negatives fired.
2. Rubric: 34 judge criteria, 103 positive weight. Opus scored 34 = 33.01. It lost 65 positive weight and took 4 in negatives.
3. Rubric losses, grouped. "Show one concrete instance" criteria: R6, R7, R8, R9, R10, R13, R14, R16, R19, R23 (5 each, 50) and R18, R20, R24, R26 (3 each, 12). Order of evidence: R4 (3). Negatives: R2 /tmp writes (-1), R31 check claimed but never run (-3).

3. WHY OPUS LOST
1. Tests: I minted the lead drop day locally and ran Opus's conform.py on it. Four artifacts differ: slot_placement, conform_trace, playout_schedule, day_report (plus the manifest). sl_01 is dropped, so sl_03 is the first fixed junction and nothing fixed comes before it. It overruns by 558 frames. The reference trims sl_02 (CR_TRIM_FLEX 558). Opus's conform.py line 615 sets low = index when there is no previous fixed junction, so its walk is empty and it records CR_TRIM_SHORTFALL 558.
2. Rubric: the code is right, since all 20 other test checks are byte exact. But the transcript gives counts ("ten clusters", "twelve DF attempts", "three wraps") and never one worked instance, which is what the judge asks for.

4. WHY THE TESTS DID NOT BITE
1. The shipped data is generate(SAMPLE_SEED) from tests/test_output.py. Every doc file is identical across seeds, so the test days only change values and sizes.
2. The generator plants every trap in every instance ("make every kind of correction happen on every instance", test line 1108). Opus could debug every trap on the visible day.
3. About 78 KB of docs state each rule plainly. Nothing is held back.
4. The dense H29 day and the sparse day only rescale data that is already visible. Only the lead drop seed fires a branch the shipped day never reaches.

5. DIFFICULTY SOURCE
1. Test loss: (b) a documented branch that only test data fires (overrun with no previous fixed junction), made worse by (d), since Opus did not even trim the slot immediately before the junction.
2. Rubric loss: (e) evidence and narration demands that the instruction never states.

6. SOLVABILITY EVIDENCE
1. spec_stage_v8_drift_correction.md lines 11-12: "trimming flexible parts, starting with the slot immediately before the junction". Opus did not trim that slot.
2. spec_stage_v7 line 24: the dropped slot "occupies no time and the slots after it move up".
3. Weak point: nothing in the docs says where the walk stops when no previous fixed junction exists. The reference uses the day start (test line 4848, lo = 0).

7. TEST DESIGN
1. The generator is seeded and inline, with 8 seeds. The reference pipeline (run_pipeline) recomputes the expected bytes. The program runs as nobody in a temp directory, with --data and --out.
2. Comparison is byte exact per artifact family: core, conform, avail, money. That amplifies one rule across 4 families on 3 unseen days.
3. Negatives catch hard coding, ignored input, nondeterminism, path dependence, third-party imports, dirtying or out-of-directory writes, and reading /app/data at run time.

8. INSTRUCTION WORDING
1. Line 48: "run against transmission days of this channel other than this one".
2. Line 53: "Every published quantity is exact".
3. Line 76: "Work inside /app". R2 penalises the /tmp writes under this line.
4. Not said: show worked instances, show a sample cluster, show a single order's predicate walk. The rubric grades 15 of these.

9. RUBRIC DESIGN
1. Most of the weight goes to process evidence. "The agent shows one X where trap Y fires and gives the value." Each item matches one TRUTH.md trap (R02 to R40).
2. A correct, quiet implementation loses about 63 percent. The tests already prove these decisions, so the rubric double-counts them as narration.

10. QC NOTES
1. CL: the instruction does not ask for the showing behaviour that 65 of 103 rubric points need. That is an alignment gap.
2. CL: the overrun walk with no previous fixed junction is not specified. Only the test docstring settles it.
3. The shipped sqlite files differ in bytes from a local regeneration. I did not check whether their contents match.

11. LESSON
1. Make test days carry structurally new cases. Branches the visible day never fires (empty predecessor, first item removed, boundary wrap) bite, and rescaled data does not.
2. Do not seed every trap in the visible instance. Leave some for held-out days only, while keeping each one documented.
3. Spell out edge-case boundaries in the spec, or the test measures a guess.
4. If the rubric rewards shown evidence, say so in the instruction.
