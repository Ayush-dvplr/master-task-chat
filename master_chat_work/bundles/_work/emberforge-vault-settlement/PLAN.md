# PLAN harden r1
Phase 0 intake, Phase 1 diagnosis (no bundle edits), stop for "go". Phase 2 harden, Phase 3 verify once.
Scoring method for P3: (b) real tests/test_output.py under rewardkit 0.2.1 in the tests image (exe_copy tests-only copy), /app mounted.
Note: the grader regenerates every corpus from build_corpus(seed) in test_output.py; there is no _SHIPPED_DATA. Data edits = edit generator in tests + rewrite environment/data from it.

# PLAN harden r2
Phase 1 diagnosis done. Phase 2: edit grader (tests/test_output.py) first, since environment/data is written by its main(); then docs (RULEBOOK_TEXTS in grader == data/*.md byte-identical), solve.py, judge, TRUTH. Phase 3 gates once.
Design: draw conveyed by council_rulings.json (charge, return, scarcity rulings; unique over 840 draws), no settled outputs. Decoy: clerks_digest.md says window = three most recent settled forges (includes same-day); S2 says strictly before; visible season planted with one same-day boundary. LV-EF-1 by omission: A4 keeps 'judged on the charge it would carry', N3 'every other forge is tested against cap, floor, retired'. Composed seasons mx1..mx5 graded on whole documents (3 checks x w5 each); isolated = structure 5 + cl_* 6x3 + ld12 3.
