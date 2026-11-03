TASK: daaca581-de32-5fc7-bd44-dd51c8f26be3, multi-source settlement pipeline (electric meter settlement, 100 files in 19 formats from six head-end systems, 9 deliverables), Opus tests 17.12, rubric 83.33, final 50.23.

1. VERDICT: DESIGN, 100 percent of lost test weight (121 of 146), confidence low. No defect found; the divergence was not located because the expected output exists only by running the seeded generator in the test, which the brief forbids.

2. LOSSES:
1. Trap family checks t01 to t03, t05 to t09, t11 to t16, 14 checks at 5, weight 70. Cause: WRONG output (focus rows differ on the visible tier, the hidden tier or both).
2. Decoy ownership checks dc03 to dc05, dc09, dc10, dc12 to dc15 at 5 and dc08, dc11 at 3, weight 51. Cause: WRONG output.
3. Passed: t04 locale numerics, t10 encoding, feeder balance shape, dc01, dc02, dc06, dc07 (25). The program ran on the hidden directory (some hidden checks passed), so no crash or timeout.

3. DIFFICULTY KIND: (e) many interacting source and precedence rules where each check owns a set of rows that every earlier stage feeds; most likely a shared upstream stage (identifier canonicalisation or boundary resolution, t01 and the read resolution rows) is off, since 23 of 31 families fail together. Not confirmed.

4. EVIDENCE:
1. solution/TRUTH.md items 1 to 31 list the rules and the checks they decide; boundary snap within 900 seconds and closest to schedule were implemented by the agent (transform.py:1769, 1791), as was half even rounding (transform.py:57).
2. tests/test_output.py:6651-6697 (_tier_ok, _hard): a check passes only when its focus lines are present on both the visible and a hidden tier.

5. TEST DESIGN: seeded generator (SAMPLE_SEED, test_output.py:6201) rebuilds the visible directory and a fresh hidden one; each check compares a subset of masked CSV lines (UFE columns 8 to 10 removed, test_output.py:6235-6241) or named JSON entries, plus an ownership check on the remaining rows of decoy-fed files. Masking UFE columns keeps one error from failing every check. Negatives: hardcoding, file name dependence, I/O outside the argument directories, nondeterminism.

6. INSTRUCTION: "compared byte for byte ... both for this directory and for the output of your program on a freshly generated directory"; "a single misread record anywhere changes the totals ... rows and figures only count when they are exact"; 1500 seconds per run; 14400 seconds; "Work out from the material itself which files feed which figure". Not said: which decoys carry needed crosswalks.

7. RUBRIC: lost only R5 (no run on a second, altered data directory); all reading and conflict rules credited.

8. REUSABLE IDEA: grade each trap family on its own focus rows across a visible and a generated hidden tier, mask the globally coupled columns so one slip does not fail every family, and keep needed crosswalks inside files that otherwise look like decoys.
