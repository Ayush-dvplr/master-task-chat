STUDY CARD W1-007: anubis-stage-2/cf9b2067-1ba0-5bab-a1ea-83e976851e6c

SUMMARY
1. A 50-file numeric audit extract (observations, ledger, calibration, anchors, state edges) must be repaired into 6x6 matrices per cohort and period.
2. Deliverable: a stdlib Python program reconcile.py DATA_DIR OUT_DIR plus its 24 JSON reports, exact integer ppm, nearest-even rounding.
3. schema.md is the contract; the grader reruns the program on corpora it generates.

SCORE
1. Tests: 32 positive checks, total weight 92; 3 negatives (-5, -5, -3), none fired. Opus earned 34 (36.96%).
2. Rubric: 10 judged criteria, positive weight 16; Opus earned 10 (62.5%), lost R4 (altered-copy check, 3) and R8 (value pair in final message, 3).
3. Lost test weight 58. Group A: 43 on checks that pass when the program can run (hidden seed, both mutations, renamed corpus, tie rounding, floor, cap, sparse, edgeless, ranks, determinism). Group B: 10 on fixed cohort and variable universe. Group C: 5 on ledger before/after precision.

WHY OPUS LOST
1. Group A, CRASH in grader. Every check that runs the program failed; every check on shipped outputs passed. With the privilege drop removed I reran the tests on the Opus program: 15 of these 18 pass. The grader runs it as nobody (test_output.py:470-471). The file was made with the file_editor tool, which in GLM's run of the same harness left reconcile.py at mode -rw-------. GLM shows the identical 14-pass pattern. So python likely cannot open the script.
2. Group B, WRONG. Opus takes cohorts and periods from the files present (reconcile.py:149-150) and variables from observation rows (reconcile.py:153-159). The reference uses fixed lists (solve.py:20-23). The checks delete Canto or vega (test_output.py:759-789, 1100-1143) and expect identity fallback matrices.
3. Group C, WRONG. Opus writes before/after as float (reconcile.py:184-185). The reference copies the raw strings (solve.py:177, 184-185). The test uses a 29-digit value (test_output.py:893-930).

DIFFICULTY SOURCE
1. Group A: (e) a harness permission defect, not task difficulty.
2. Group B: (b) a documented fixed universe that the shipped data never removes.
3. Group C: (a) a precision variation the shipped 6-digit data never shows.

SOLVABILITY EVIDENCE
1. Group A: none. instruction.md:3 says only "runnable as python3 /app/out/reconcile.py"; no file mode and no other user are named.
2. Group B: schema.md:3 fixes the variable, cohort and period orders; schema.md:15 gives the 1.0/0.0 fallback. This is decided, but implicitly.
3. Group C: weak. schema.md:9 says only "records ... before, and after". The test comment at test_output.py:207-208 concedes number versus string is unspecified.

TEST DESIGN
1. Corpora are generated in test code (_write_corpus, test_output.py:341-463) with seeds 303, 909 and 515, plus extreme, sparse, edgeless, tied-anchor and shifted-table variants and single-cell mutations.
2. Comparison is per artifact on chosen keys, with strict type checks (_same, :307-318).
3. Amplification: one failure to start costs 18 checks (weight 58 here).
4. Negatives: hard-coded answers, grader paths and forbidden imports, all read from the AST.

INSTRUCTION WORDING
1. "Use /app/data/schema.md as the authoritative contract ... for any later extract with the same file format" (instruction.md:5).
2. "Accept any DATA_DIR and OUT_DIR ... do not hard-code answers" (instruction.md:12).
3. "You have 7200 seconds" (instruction.md:17). The 120 s per-run limit is not stated (test_output.py:496).
4. Not said: that the program runs as another user, that the universe is fixed even when files are missing, and how precise before/after must be.

RUBRIC DESIGN
1. Trajectory: no writes to the data, scope, independent recomputation of a cell (R6) and of an edge (R10), a check on an altered copy (R4), reads the contract first (R9), code quality (R5).
2. Final message: an honesty penalty R7 (-5) and a reported program-versus-own value pair (R8).

QC NOTES
1. Group A is an environment defect, and it hit both models. Fix: chmod the script, or copy it to a readable path, before setpriv. Or state the need in the instruction.
2. Group C is under-specified in the contract and invites a CL ambiguity finding. State "write before and after as the exact input strings".
3. The reference computes in float (solve.py:25, 73) while schema.md:3 demands full-precision decimals. This is a mismatch risk on ties.
4. TRUTH says each channel carries half; reward.toml weights 0.5/92 and 0.5/16 agree.

REUSABLE IDEAS
1. Ship data on which conditional rules never fire, and generate test corpora that trigger each rule in isolation, with margins so that near misses cannot pass.
2. Add exact-tie rounding inputs and side tables that must be reread.
3. Run delivered code the exact way the instruction says, and make the file mode or user explicit.
