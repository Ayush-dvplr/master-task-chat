# Probe diagnosis (Run 1, claude-opus-5, tests 75/160)

Program: jobs/.../Run 1/artifacts/app/out/optimize.py (copy WORK/probe/optimize.py). Tools: probe/diag.py, rowcheck.py, opt_first.py, opt_truth.py.
Lost: 17 tests x 5 = 85 points.

| tests | pts | first cause | under it | class |
|---|---|---|---|---|
| trap sealed, chained, stepped, echoed, aliased, warded | 30 | exit -9: calibrate() (optimize.py:795-830) keeps every surviving branch; in one-flag trap corpora unused controls do not separate, branches grow 12 -> 168 -> 2688 -> 32256, run passes LAUNCH_SECONDS=120 | pass with first branch only (diag_first.txt) | runtime (agent search) |
| trap drifted, flipped, spun | 15 | same exit -9 | first branch: `calibration failed at CTRL-J (cadence_modulus)`; true quantities: PASS | runtime + settlement (CTRL-J reads surviving units / tick totals) |
| trap woven, padded, shadowed | 15 | same exit -9 | true quantities still fail: `$.units[15].unit is 'pegasus', wanted 'quasit'` (woven), `$.units[3].unit is 'dryad', wanted 'ettin'` (padded), `$.units[14]... 'pegasus', wanted 'quasit'` (shadowed); agent seats a unit whose only entries were cancelled (amount_total 0/1) | settlement |
| general empty_charter, dead_window, reversal_tiebreak, mutation_window_split | 20 | `calibration failed at CTRL-J (cadence_modulus)` | rowcheck: CTRL-A..CTRL-I ok with true values, CTRL-J differs | settlement |
| general donor_table_rotation | 5 | same CTRL-J | true quantities: `$.units[2].unit is 'cockatrice', wanted 'dryad'` | settlement |

Split: decode 0, settlement 55 (11 tests), both 0, runtime-only 30 (6 tests; agent kept every calibration branch, contract calibration.md:6-8 "At least one value ... reproduces the figure" allows several, so not a task defect).
No probe point was lost to a decode slip: every wire-control row (CTRL-A..CTRL-I) matched with the true values in all 8 rooms checked.
Bearing on F4: the probe lost 0 points to the allowance cascade in trap_* tests, so moving trap_* to under-allowance corpora does not change the probe's loss there (its trap losses are runtime + seat set).
