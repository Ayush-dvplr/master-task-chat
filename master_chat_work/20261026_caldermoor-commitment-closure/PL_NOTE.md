# PL note: caldermoor-commitment-closure (delivered as is, Ayush 26 Oct 22:35)

Runs (claude-opus-5, harness): attempt 6 tests 98.45 / rubric 0.0 / final 49.23; attempt 7 tests 94.33 / rubric 8.57 / final 51.45. Both below 100 tests and below 70 final.
QC v1 (QC/reports/caldermoor-commitment-closure/v1.md, kit 5574d77e): MINOR, 0 fails, oracle 1.0 x5, nop 0, owner 1.0, QL rows 19/19 pass.

Kept minors (approved by tasker, not fixed):
- TS-13: test_documented_boundaries_exact (tests/test_output.py:4742-4837) grades five related boundary properties under one weight-3 check; its day-boundary part overlaps test_day_boundary_exact.
- JD-15: judge R11 (tests/judge.toml:144) asks the final message to list every identity id; the instruction does not ask for it. Missed in both runs, so it lowers no pass the agent could earn from the instruction.

Kept warns:
- A3 / TS-23: 57 checks against the 35 cap (tasker approval, same as match-replay).
- TS-29: a hanging submission can exceed the 3600 s verifier timeout because failed probe runs are not cached; correct or crashing submissions are unaffected.
