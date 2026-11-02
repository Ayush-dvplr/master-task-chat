# QC_DEFENCE assay-plate-triage (4f33c30, fix r1)

Built 15:14 IST 26 Oct from TRUTH.md, tests/test_output.py, the bundle and the Opus run_1 trajectory (no DESIGN.md or LEVERS.md existed; WORK/LEVERS.md was written this round). Losses are of the 90 positive test points, measured by WORK/scripts/trap.py on the fixed tests (same as on the QC copy's tests).

## L01-L12 the twelve mode bits (one entry, twelve levers)
- What: each bit of the 12-bit mode word switches on one alteration of the chain (engine.md:32-38). The agent must find what each does and which bit carries it.
- Why: punishes "the mode word is a label" (ignoring it, L13) and "one bit is enough" (Opus run_1 wired one bit). Each single-bit wrong variant loses 71 or 76 of 90.
- QC check it could trip: IN-8, IN-16, DS-21, AL-F0e, AL-1, CL-10, TS-19 if the bit identity cannot be settled from shipped bytes (it could not before this round: v1 G01-1).
- Why not a defect now: LEVER_RULES_v2 0b "a record that only the right reading reproduces counts". After the fix `environment/data/bits/0x001_manifest.json` .. `0x800_manifest.json` carry the unprefixed run's digests with one bit set; every rotation of the bit map fails 194-230 shipped digests, every one of the 66 swaps fails at least 8 (WORK/scripts/probe.py). No alteration is named anywhere agent-visible; no single-bit output ships (Never 11).
- Safe fix if QC insists: none needed beyond the evidence; never name an alteration or ship single-bit outputs (playbook AL-1 NEVER column "solved list").

## L13 trap_blind (mode word ignored)
- Loses 87 of 90 (only the two mode-zero runs and delivery pass). Graded by every check at a nonzero mode.
- Could trip: CL-4 (one reading loses nearly everything). Not a defect: instruction.md:15 "It reads the mode word out of the manifest in its input directory and honours it"; FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately."
- Safe fix if QC insists: none; the requirement is stated.

## L14 alias_count (matrix rotation keyed on a fixed operator count)
- The rotation depends on the run's operator count; a reading that fixes the shipped count (5) passes the shipped digests but loses 71 of 90 on runs with other counts. Separated by the `trial_` run (6 operators) and the grown-operator corpus.
- Could trip: TS-26 (grown corpus duplicates the full runs, v1 G03-2). Fixed this round: the grown corpus now holds 11 operators, more than any other graded run (6-8).
- Safe fix if QC insists: keep the grown corpus with its distinct property; never drop it (LOSS_TABLE).

## L15 bias_count (tail trim keyed on a fixed plate count)
- The trim length depends on the plate count; a fixed reading loses 50 of 90. Separated by `trial_` (40 plates) vs unprefixed (37).
- Could trip: DS-21 / W "arbitrary formula" (v1 G02-4). Not a defect: DS-21 "hard is fine; only genuinely unreachable information fails"; the per-bit manifest 0x200 and `trial_manifest.json` settle it. Never add a sentence saying what the bit keys on (IN-17, LEVER_RULES W1).

## L16 bit identity (which bit carries which alteration)
- Before: undecidable (all digest runs at 0xfff). After: settled by the bits/ manifests. Test loss unchanged (rotation 42, swaps 7). Effect: easier by design (master direction F1); compensated in that no single-bit output ships, the alterations stay unnamed, and the grown corpus was strengthened (M2).

## D1 whole-file exact grading (CL-4)
- Each report is compared byte for byte; one plain fact wrong (quarantine strikes, status order, top_well tie, hold/quarantine order) scores 1/90.
- Not a defect: instruction.md:15 now says "Each output file is graded whole on fresh runs, and only an exact match counts."; FC:491 quoted above; LEVER_RULES_v2 G1. One-fact-wrong scores: status ladder 1/90, disposition order 1/90, top_well tie 1/90, quarantine count 1/90, top_plate tie 72/90, hold limit 78/90 (v1 G05-2 probe).
- Safe fix if QC insists: none that keeps difficulty; never split the corpus checks (master direction F4).

## D2 worked runs at mode zero only
- The example runs pin the plain chain and nothing about any bit (Never 11: no answer for a graded document). INFERRED from TRUTH.md:153-155.

## D3 33 checks (TS-23 count)
- Above 35 is not reached (33); no count cap applies anyway (playbook TS-23).

## D4 negatives
- negative_hardcoded_sample_answers -5, negative_third_party_dependency -3, negative_nondeterministic_output -3; each body states in an inline comment that True marks the forbidden behaviour (TS-15, fixed this round).

## D5 judge
- R2-R11 figure criteria weights 1/3/5 by how many alterations move the figure on the shipped run (reason per weight in TRUTH.md); R13 -5 input edit, R14 -3 reads the grader, R16 -3 claims an unrun pass (J3), R15 code quality (J4, conduct).
