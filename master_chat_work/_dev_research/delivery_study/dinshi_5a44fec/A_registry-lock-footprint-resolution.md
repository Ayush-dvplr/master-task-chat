# A registry-lock-footprint-resolution

**Verdict: ARTEFACT** (recorded tests 2.88 is not a measurement; genuine test points lost = 0)

Recorded: overall 48.81 / tests 2.88 / rubric 94.74 (run_1/verifier/score.json).

## Evidence
- run_1 report.json: 4 of 35 positive tests passed (the four w1 shipped-output checks); all 11 `trap_*` (w5) and 16 `held_out_*` (w5) failed = 27 tests, 135 of 139 weight. exception_info null, ctrf messages empty, no negative fired.
- Every failed test runs the delivered program as user nobody (setpriv) via `_run`. QC report `Dinshi_Jain/Kunwar_Singh_registry-lock-footprint-resolution_QC_Report.md`:
  - :9 pre-fix owner-only run 0.0288 (same figure as recorded tests).
  - :32 F1 "grading executed the agent's program as an unprivileged user without first making it readable, so every check that ran the program returned False on a correct submission."
  - :51 "re-graded against the fixed verifier and read **139 of 139 (1.0000)** ... the H6 bug alone suppressed its entire program tier. The recorded combined reward of 48.81 is therefore **not** a valid measurement".
- Fix present now: tests/test_output.py:1921-1940 `_grant_read` (docstring: "delivered program arrives at mode 0600 ... without this grant every check that executes the program returns False on a submission that is completely correct"); `_run` 1943-1980 returns None on missing/timeout/nonzero.
- Agent artefact `artifacts/app/out/optimize.py` (806 lines) implements all 11 decode flags and a generic product search for the six withheld constants that raises unless exactly one assignment fits (optimize.py:360-398), consistent with QC's 139/139.

## Per failed check
All 27: crash/path class (permission: program unreadable to the dropped uid), not wrong value. One shared gate (`_run` returning None) zeroed 27 tests; the gate is a grader defect, not an agent rule, so not PARTLY.

## Consequence for the study
No lever table (Step 2 card limited to test architecture and leak patterns, which are still instructive: generator inside tests, per-flag trap corpora, constants differing at every position in held-out corpora). Re-graded tests 100 means the task's levers did not beat Opus at all.
