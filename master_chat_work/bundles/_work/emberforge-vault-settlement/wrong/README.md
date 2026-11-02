# Wrong solvers (round 0)

Built by `make_solvers.py` from `solution/solve.py` (each edit is an exact replacement that must hit once). Scored with `../score_p3.py`, P3 method (b): the real `tests/test_output.py` under rewardkit 0.2.1 in the exe_copy tests-only image, /app mounted; oracle 1.0 and nop 0.0 confirmed first.

| id | edit (one line) |
|---|---|
| L1 | `stable()` returns one forward pass: indices read off a sweep at zero, season charged once at them |
| L2 | `recover()` returns the draw RS-C/half-even/GFS/opening-plus-acquired without searching |
| L3 | `fund()` grants greedily by units requested (limits respected) instead of the Q7/Q8 optimum |
| L4 | `Roster.canonical` applies renames and merges whatever their effective day |
| L5 | a salvage is governed by the edition in force on its own filing day |
| L6 | the one-salvage-per-forge (S6) check is removed |
| L7 | the run's own forge reading: closed workshop gives CAP only; floor tested before the cap and short-circuits it (no CAP, no closure) |
| L7s | static refusals keep only the first condition found (used in S2 only) |
| L8 | ledger settled in file order |
| L9 | records written without the trailing newline |

S2 = L1+L2+L3+L4+L5+L6+L7+L7s+L8+L9. S4 = L7. S3_k = lever k alone. S3_L5h / S3_L6h = L5 or L6 plus L2, so the failed draw search does not zero the run.
